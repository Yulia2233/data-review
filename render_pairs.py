#!/usr/bin/env python3
"""Render target/rebuild isometrics with SimpleCADAPI's shared camera/scale.

Use cad-code/.runtime/python/bin/python -I render_pairs.py --scope all --workers 3.
Each STEP pair is processed in a bounded subprocess; no notebook code is run.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('DATA_REVIEW_ROOT', HERE)).expanduser().resolve()
DATA_DIR = Path(os.environ.get('DATA_REVIEW_DATA_DIR', HERE)).expanduser().resolve()
BATCH = ROOT / "stepir_geom_gen/cadcode_synth_v63"
PACK = ROOT / "datasets/data-traj2/stepir-v6.3"
VIEW = (35.264389682754654, -45.0, "isometric")
CAMERA = {"elevation": VIEW[0], "azimuth": VIEW[1], "bounds": "union(target,rebuild)",
          "fit": "shared", "projection": "parallel", "cell_pixels": [780, 780]}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path else None


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, path)


def inventory(scope):
    manifest = Path(os.environ.get('DATA_REVIEW_CATALOG', DATA_DIR / 'active-catalog.json'))
    if not manifest.is_file():
        manifest = DATA_DIR / 'catalog.json'
    if manifest.exists():
        rows = []
        for row in json.loads(manifest.read_text())['rows']:
            if scope == 'packed' and not row['in_packed']:
                continue
            if scope == 'new' and not row['new_accepted']:
                continue
            rows.append({'case': row['case'], 'target': str(ROOT / row['target']),
                         'rebuild': str(ROOT / row['rebuild']) if row['rebuild'] else None,
                         'packed': row['in_packed']})
        return sorted(rows, key=lambda row: (not row['packed'], row['case']))
    packed = [json.loads(line) for line in (PACK / "index.jsonl").read_text().splitlines() if line]
    chosen = {row["case"] for row in packed}
    if scope == "new":
        chosen = {row["case"] for row in packed if row.get("source_batch") == "cadcode_synth_v63"}
    if scope == "all":
        chosen |= {p.parent.name for p in (BATCH / "out").glob("*/verdict.json")}
    rows = []
    for case in chosen:
        if (BATCH / "out" / case / "verdict.json").exists():
            target = BATCH / "jobs" / case / "target.step"
            directory = BATCH / "out" / case
            rebuild = next((p for p in (directory / "model.step", directory / "verify_model_long/candidate.step",
                                        directory / "verify_model/candidate.step") if p.is_file() and p.stat().st_size), None)
        else:
            target = PACK / case / "target.step"
            rebuild = PACK / case / "rebuild.step"
        rows.append({"case": case, "target": str(target), "rebuild": str(rebuild) if rebuild else None,
                     "packed": case in {row["case"] for row in packed}})
    return sorted(rows, key=lambda row: (not row["packed"], row["case"]))


def render_one(row):
    from PIL import Image
    from simplecadapi.inspect import brep
    import importlib.metadata

    target = Path(row["target"])
    rebuild = Path(row["rebuild"]) if row["rebuild"] else None
    directory = DATA_DIR / "images" / row["case"]
    directory.mkdir(parents=True, exist_ok=True)
    provenance = {"case": row["case"], "target_sha256": sha(target), "rebuild_sha256": sha(rebuild),
                  "camera": CAMERA, "sdk": importlib.metadata.version("simplecadapi"), "version": 1}
    meta = directory / "render.json"
    expected = [directory / "target.png"] + ([directory / "rebuild.png"] if rebuild else [])
    if meta.is_file() and all(p.is_file() for p in expected):
        previous = json.loads(meta.read_text())
        if all(previous.get(k) == v for k, v in provenance.items() if k != "camera") and previous.get("status") in ("ok", "missing_rebuild"):
            return "cached"
    atomic_json(meta, {**provenance, "status": "rendering", "started": time.time()})
    if rebuild:
        pair = directory / "pair.png"
        try:
            brep.render_step_comparison_rpath(target_step_path=target, current_step_path=rebuild, output_path=pair,
                                             views=(VIEW,), image_size=(12.0, 6.0), dpi=130,
                                             linear_deflection=0.08, angular_deflection=0.15, show_brep_edges=True)
        except ValueError as error:
            if "STEP BREP is invalid" not in str(error) and "Expected one STEP root" not in str(error):
                raise
            # XCAF display can show invalid/multi-root originals which the strict
            # comparison loader rejects. Record the different fit explicitly.
            provenance["camera"] = {**CAMERA, "fit": "independent", "bounds": "each model"}
            provenance["fallback_reason"] = str(error)
            for side, source in (("target", target), ("rebuild", rebuild)):
                tmp = directory / (side + ".tmp.png")
                brep.render_step_views_rpath(step_path=source, output_path=tmp, views=(VIEW,), image_size=(6.0, 6.0),
                                            dpi=130, title="", linear_deflection=0.08, angular_deflection=0.15,
                                            show_brep_edges=True)
                os.replace(tmp, directory / (side + ".png"))
        else:
            with Image.open(pair) as image:
                width, height = image.size
                assert width % 2 == 0
                for side, bounds in (("target", (0, 0, width//2, height)), ("rebuild", (width//2, 0, width, height))):
                    tmp = directory / (side + ".tmp.png")
                    image.crop(bounds).save(tmp)
                    os.replace(tmp, directory / (side + ".png"))
        status = "ok"
    else:
        provenance["camera"] = {**CAMERA, "fit": "target_only", "bounds": "target"}
        tmp = directory / "target.tmp.png"
        brep.render_step_views_rpath(step_path=target, output_path=tmp, views=(VIEW,), image_size=(6.0, 6.0), dpi=130,
                                    title="", linear_deflection=0.08, angular_deflection=0.15, show_brep_edges=True)
        os.replace(tmp, directory / "target.png")
        status = "missing_rebuild"
    assert sha(target) == provenance["target_sha256"] and sha(rebuild) == provenance["rebuild_sha256"]
    atomic_json(meta, {**provenance, "status": status, "finished": time.time()})
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("new", "packed", "all"), default="all")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case", action="append")
    parser.add_argument("--one", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.one:
        print(render_one(json.loads(args.one)), flush=True)
        return
    rows = inventory(args.scope)
    if args.case:
        rows = [row for row in rows if row["case"] in args.case]
    if args.limit:
        rows = rows[:args.limit]
    print(f"Rendering {len(rows)} pairs; workers={args.workers}", flush=True)
    status = {"total": len(rows), "done": 0, "ok": 0, "cached": 0, "missing_rebuild": 0, "errors": {}}

    def launch(row):
        env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "CUDA_VISIBLE_DEVICES": "",
               "SIMPLECAD_VTK_RENDER_LOCK": str(DATA_DIR / "images/.render.lock")}
        try:
            result = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--one", json.dumps(row)],
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=args.timeout, env=env)
            if result.returncode:
                raise RuntimeError((result.stderr or result.stdout)[-1800:])
            return row, result.stdout.strip().splitlines()[-1]
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            atomic_json(DATA_DIR / "images" / row["case"] / "render.json",
                        {"case": row["case"], "status": "error", "error": error[-1800:], "camera": CAMERA})
            return row, error

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(launch, row) for row in rows]
        for future in as_completed(futures):
            row, result = future.result()
            status["done"] += 1
            if result in ("ok", "cached", "missing_rebuild"):
                status[result] += 1
            else:
                status["errors"][row["case"]] = result
            atomic_json(DATA_DIR / "render-status.json", status)
            print(f"{status['done']}/{len(rows)} {row['case']} {result[:100]}", flush=True)


if __name__ == "__main__":
    main()
