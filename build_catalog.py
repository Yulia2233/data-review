#!/usr/bin/env python3
"""Freeze the requested 1572-session v6.3 snapshot without changing source artifacts or marks."""
import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('DATA_REVIEW_ROOT', HERE)).expanduser().resolve()
DATA_DIR = Path(os.environ.get('DATA_REVIEW_DATA_DIR', HERE)).expanduser().resolve()
SNAPSHOT = '2026-11-10T14:06:40.085179+08:00'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    annotations = DATA_DIR / 'annotations'
    saved = {}
    backup = DATA_DIR / 'annotation-backups' / datetime.now().strftime('%Y%m%d_%H%M%S')
    for name in ('marks.json', 'history.jsonl'):
        path = annotations / name
        if path.is_file():
            backup.mkdir(parents=True, exist_ok=True)
            saved[name] = sha(path)
            shutil.copy2(path, backup / name)
    packed = {}
    for dataset in ('data-traj2', 'data-traj3'):
        folder = ROOT / 'datasets' / dataset / 'stepir-v6.3'
        for line in (folder / 'index.jsonl').read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                packed[(dataset, row['case'])] = (folder / row['case'], row)
    old = ROOT / 'stepir_geom_gen/cadcode_synth_1108'
    versions = json.loads((old / 'ir_versions_done.json').read_text())
    cohorts = [
        ('old_v63', '早期 v6.3', old, 'data-traj2', sorted(c for c, v in versions.items() if v['version'] == 'v6.3')),
        ('batch_v63', 'new-data v6.3', ROOT / 'stepir_geom_gen/cadcode_synth_v63', 'data-traj2', None),
        ('data1106', 'data-1106', ROOT / 'stepir_geom_gen/cadcode_synth_data1106_v63', 'data-traj3', None),
        ('rerun934', '934 重跑 · 前 32 条', ROOT / 'stepir_geom_gen/cadcode_synth_rerun934_v63', None, None),
    ]
    rows, sessions = {}, set()
    snapshot = datetime.fromisoformat(SNAPSHOT).timestamp()
    for batch, label, folder, dataset, cases in cohorts:
        if cases is None:
            cases = sorted(p.parent.name for p in (folder / 'out').glob('*/verdict.json')
                           if batch != 'rerun934' or p.stat().st_mtime <= snapshot)
        for case in cases:
            output, inputs = folder / 'out' / case, folder / 'jobs' / case
            verdict = json.loads((output / 'verdict.json').read_text())
            model = verdict.get('model') or {}
            session = verdict.get('session')
            identity = f'{batch}--{case}' if batch in ('data1106', 'rerun934') else case
            if identity in rows or not session or session in sessions:
                raise RuntimeError('Duplicate trajectory identity: ' + identity)
            sessions.add(session)
            source = folder / 'trajectories' / (case + '.json')
            exported = json.loads(source.read_text())
            if exported['id'] != session or exported.get('schema_version') != 'cad-code-session-v2':
                raise RuntimeError('Export/session mismatch: ' + case)
            rebuild = next((p for p in (output / 'model.step', output / 'verify_model_long/candidate.step',
                                        output / 'verify_model/candidate.step') if p.is_file() and p.stat().st_size), None)
            target, notebook = inputs / 'target.step', output / 'model.py'
            pack = packed.get((dataset, case))
            intent = ''
            if pack:
                directory, item = pack
                target, rebuild = directory / 'target.step', directory / 'rebuild.step'
                notebook, source = directory / 'model.py', directory / 'trajectory.json'
                intent = item.get('design_intent', '')
                if json.loads(source.read_text())['id'] != session:
                    raise RuntimeError('Packed session differs: ' + case)
            report = output / 'report.json'
            if not intent and report.exists():
                try:
                    intent = str(json.loads(report.read_text()).get('design_intent', ''))
                except ValueError:
                    pass
            if not target.is_file():
                raise RuntimeError('Missing target: ' + case)
            if batch != 'old_v63' and (inputs / 'ir_version.txt').read_text().strip() != 'v6.3':
                raise RuntimeError('IR version mismatch: ' + case)
            rel = lambda p: str(p.relative_to(ROOT)) if p is not None else None
            clean_ok = bool(model.get('ok')) and not model.get('cheated') and not verdict.get('forbidden_calls')
            rows[identity] = {'case': identity, 'part_name': case, 'batch': batch, 'batch_label': label,
                'ir_version': 'v6.3', 'in_batch': True, 'in_packed': bool(pack), 'new_accepted': clean_ok,
                'riou': model.get('riou'), 'ok': clean_ok, 'minutes': round(verdict.get('secs', 0) / 60, 1),
                'session': session, 'target': rel(target), 'rebuild': rel(rebuild), 'trajectory': rel(source),
                'model': rel(notebook), 'report': rel(report), 'design_intent': intent,
                'agent_delivered': bool(verdict.get('model_step')), 'target_sha256': sha(target),
                'trajectory_sha256': sha(source)}
    counts = Counter(row['batch'] for row in rows.values())
    if dict(counts) != {'old_v63': 15, 'batch_v63': 1268, 'data1106': 257, 'rerun934': 32} or len(rows) != 1572:
        raise RuntimeError('Unexpected snapshot counts: ' + str(dict(counts)))
    marks = json.loads((annotations / 'marks.json').read_text()) if (annotations / 'marks.json').exists() else {}
    if any(key not in rows for key in marks):
        raise RuntimeError('Existing annotation would be orphaned by the catalog')
    payload = {'snapshot_time': SNAPSHOT, 'total': len(rows), 'batches': dict(counts),
               'annotation_backup': str(backup.relative_to(HERE)) if saved else None,
               'annotation_hashes_before': saved, 'rows': list(rows.values())}
    fd, temp = tempfile.mkstemp(prefix='.catalog-', dir=HERE)
    with os.fdopen(fd, 'w') as out:
        json.dump(payload, out, ensure_ascii=False, indent=1)
        out.write('\n')
    os.replace(temp, DATA_DIR / 'catalog.json')
    if any(sha(annotations / name) != digest for name, digest in saved.items()):
        raise RuntimeError('Annotation changed during catalog build; backup needs inspection')
    print(json.dumps({'total': len(rows), 'batches': dict(counts), 'existing_annotations_preserved': len(marks),
                      'unique_sessions': len(sessions)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
