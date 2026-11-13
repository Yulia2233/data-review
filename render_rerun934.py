#!/usr/bin/env python3
"""Render target/rebuild isometric images for the rerun934 catalog scope."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('DATA_REVIEW_ROOT', HERE)).expanduser().resolve()
DATA_DIR = Path(os.environ.get('DATA_REVIEW_DATA_DIR', HERE)).expanduser().resolve()
RENDER = HERE / "render_pairs.py"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="rerun934")
    args = parser.parse_args()
    rows = json.loads(Path(os.environ.get("DATA_REVIEW_CATALOG", DATA_DIR / "active-catalog.json")).read_text())["rows"]
    selected = []
    for row in rows:
        if row.get("batch") != args.batch:
            continue
        item = dict(row)
        item["target"] = str(ROOT / row["target"])
        item["rebuild"] = str(ROOT / row["rebuild"]) if row.get("rebuild") else None
        selected.append(item)
    selected.sort(key=lambda row: row["case"])
    status = {"total": len(selected), "done": 0, "ok": 0, "cached": 0, "missing_rebuild": 0, "errors": {}}
    status_path = DATA_DIR / f"render-{args.batch}-status.json"

    def launch(row: dict) -> tuple[str, str]:
        env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "CUDA_VISIBLE_DEVICES": "", "SIMPLECAD_VTK_RENDER_LOCK": str(DATA_DIR / "images/.render.lock")}
        result = subprocess.run([sys.executable, "-I", str(RENDER), "--one", json.dumps({"case": row["case"], "target": row["target"], "rebuild": row["rebuild"], "packed": row.get("in_packed", False)})], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600, env=env)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout)[-1800:])
        return row["case"], result.stdout.strip().splitlines()[-1]

    print(f"Rendering {args.batch} {len(selected)} cases", flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(launch, row): row["case"] for row in selected}
        for future in as_completed(futures):
            case = futures[future]
            try:
                case, result = future.result()
                if result in ("ok", "cached", "missing_rebuild"):
                    status[result] += 1
                else:
                    status["errors"][case] = result
            except Exception as error:
                status["errors"][case] = f"{type(error).__name__}: {error}"[-1800:]
            status["done"] += 1
            status_path.write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n")
            print(f"{status['done']}/{status['total']} {case} {status['errors'].get(case, result if 'result' in locals() else 'error')}", flush=True)


if __name__ == "__main__":
    main()
