#!/usr/bin/env python3
"""Add the completed rerun934 trajectories to the review catalog."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('DATA_REVIEW_ROOT', HERE)).expanduser().resolve()
DATA_DIR = Path(os.environ.get('DATA_REVIEW_DATA_DIR', HERE)).expanduser().resolve()
SOURCE = ROOT / "stepir_geom_gen" / "cadcode_synth_rerun934_v63"
ACTIVE = DATA_DIR / "active-catalog.json"
ARCHIVE = DATA_DIR / "active-catalog-before-rerun934.json"
OUTPUT = DATA_DIR / "catalog-rerun934.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def choose_rebuild(output: Path, case: str) -> Path | None:
    packed = ROOT / "datasets" / "data-traj4" / "stepir-v6.3" / case / "rebuild.step"
    candidates = [
        output / "model.step",
        output / "verify_model_long" / "candidate.step",
        output / "verify_model" / "candidate.step",
        packed,
    ]
    return next((path for path in candidates if path.is_file() and path.stat().st_size), None)


def main() -> None:
    old = json.loads(ACTIVE.read_text())
    if not ARCHIVE.exists():
        shutil.copy2(ACTIVE, ARCHIVE)
    old_rows = {row["case"]: row for row in old["rows"]}
    jobs = json.loads((SOURCE / "jobs.json").read_text())
    if len(jobs) != 934:
        raise RuntimeError(f"expected 934 rerun jobs, found {len(jobs)}")

    added = {}
    for job in jobs:
        case = job["case"]
        identity = f"rerun934--{case}"
        output = SOURCE / "out" / case
        verdict_path = output / "verdict.json"
        trajectory = SOURCE / "trajectories" / f"{case}.json"
        target = SOURCE / "jobs" / case / "target.step"
        model = output / "model.py"
        report = output / "report.json"
        verdict = json.loads(verdict_path.read_text())
        model_result = verdict.get("model") or {}
        rebuild = choose_rebuild(output, case)
        design_intent = ""
        if report.is_file():
            try:
                design_intent = str(json.loads(report.read_text()).get("design_intent", ""))
            except (ValueError, TypeError):
                design_intent = ""
        clean_ok = bool(model_result.get("ok")) and not model_result.get("cheated") and not verdict.get("forbidden_calls")
        added[identity] = {
            "case": identity,
            "part_name": case,
            "batch": "rerun934",
            "batch_label": "934 重跑 · v6.3",
            "ir_version": "v6.3",
            "in_batch": True,
            "in_packed": (ROOT / "datasets" / "data-traj4" / "stepir-v6.3" / case).is_dir(),
            "new_accepted": clean_ok,
            "riou": model_result.get("riou"),
            "ok": clean_ok,
            "minutes": round((verdict.get("secs") or 0) / 60, 1),
            "session": verdict.get("session"),
            "target": relative(target),
            "rebuild": relative(rebuild),
            "trajectory": relative(trajectory),
            "model": relative(model) if model.is_file() else None,
            "report": relative(report) if report.is_file() else None,
            "target_image": relative(DATA_DIR / "images" / identity / "target.png"),
            "design_intent": design_intent,
            "agent_delivered": bool(verdict.get("model_step")),
            "target_sha256": sha(target),
            "trajectory_sha256": sha(trajectory),
            "relief": bool(job.get("relief")),
            "vision_calls": verdict.get("vision_calls", 0),
        }

    rows = dict(old_rows)
    rows.update(added)
    payload = {
        "schema_version": "stepir-review-catalog-v4-rerun934",
        "snapshot_time": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "batches": dict(Counter(row.get("batch", "unknown") for row in rows.values())),
        "previous_active_catalog": "active-catalog-before-rerun934.json",
        "previous_active_total": len(old_rows),
        "added_batch": "rerun934",
        "added_count": len(added),
        "rows": [rows[key] for key in sorted(rows)],
    }
    temp = OUTPUT.with_name(OUTPUT.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    os.replace(temp, OUTPUT)
    temp = ACTIVE.with_name(ACTIVE.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    os.replace(temp, ACTIVE)
    print(json.dumps({"previous": len(old_rows), "added": len(added), "total": len(rows), "batches": payload["batches"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
