#!/usr/bin/env python3
"""Append the 1772 retained datav1 trajectories to the review catalog only."""
import hashlib
import json
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('DATA_REVIEW_ROOT', HERE)).expanduser().resolve()
DATA_DIR = Path(os.environ.get('DATA_REVIEW_DATA_DIR', HERE)).expanduser().resolve()
DATAV1 = ROOT / 'datasets/datav1-viewer-source/trajectories'
SOURCE = ROOT / 'datasets/v8-data-review_20261102/trajectories'
CONVERTED = ROOT / 'datasets/v8-qwen-full-thinking_20261103'
OLD_MANIFEST = ROOT / 'sites/datav1-labeler/manifest.json'
OLD_CACHE = ROOT / 'sites/datav1-labeler/cache'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')
    os.replace(temp, path)


def main():
    manifest = json.loads(OLD_MANIFEST.read_text())
    prior_catalog = DATA_DIR / 'catalog.json'
    prior_rows = {row['case']: row for row in json.loads(prior_catalog.read_text())['rows']}
    archival_catalog = DATA_DIR / 'catalog-1572.json'
    if not archival_catalog.exists():
        shutil.copy2(prior_catalog, archival_catalog)
    rows = {}
    entries = {entry['id']: entry for entry in json.loads((CONVERTED / 'index.json').read_text())['cases']
               if entry['dataset'] == 'trajectories'}
    sample_paths = {}
    for path in DATAV1.glob('*/sample.json'):
        sample = json.loads(path.read_text())
        sample_paths[sample['id']] = path
    source_rows = [row for row in manifest['cases'] if row['collection'] == 'trajectories']
    if len(source_rows) != 1772:
        raise RuntimeError(f'Expected the approved datav1 trajectory set of 1772, found {len(source_rows)}')
    expected = {'abc:00000027', 'abc:00000940'}
    ids = {row['id'] for row in source_rows}
    if expected & ids:
        raise RuntimeError('The two removed image trajectories are present in the datav1 manifest')
    for source in source_rows:
        trajectory_id = source['id']
        entry, sample_path = entries.get(trajectory_id), sample_paths.get(trajectory_id)
        if not entry or not sample_path:
            raise RuntimeError('Missing converted datav1 sample: ' + trajectory_id)
        sample = json.loads(sample_path.read_text())
        if sample['id'] != trajectory_id or sample['schema_version'] != 'datav1-qwen-assistant-actions-v1':
            raise RuntimeError('Unexpected Qwen trajectory schema: ' + trajectory_id)
        case_dir = SOURCE / sample['source']['path'].split('/trajectories/', 1)[1].rsplit('/', 1)[0]
        target = case_dir / 'raw/target.step'
        if not target.is_file() or sha(target) != source['sha256']:
            raise RuntimeError('Original target hash mismatch: ' + trajectory_id)
        cache_image = OLD_CACHE / (source['sha256'] + '.png')
        if not cache_image.is_file():
            raise RuntimeError('Missing existing target render: ' + trajectory_id)
        if trajectory_id in ('abc:00000027', 'abc:00000940'):
            raise RuntimeError('Removed image trajectory cannot be added')
        report_path = case_dir / 'raw/report.json'
        report = json.loads(report_path.read_text()) if report_path.is_file() else {}
        verdict_path = case_dir / 'raw/verdict.json'
        verdict = json.loads(verdict_path.read_text()) if verdict_path.is_file() else {}
        metric = verdict.get('rebuild') or verdict.get('final') or {}
        key = 'datav1--' + trajectory_id
        if key in rows:
            raise RuntimeError('Catalog identity already exists: ' + key)
        rel = lambda path: str(path.relative_to(ROOT))
        rows[key] = {
            'case': key, 'part_name': trajectory_id, 'batch': 'datav1',
            'batch_label': 'datav1 · 含思考', 'ir_version': 'historical',
            'trajectory_format': 'qwen', 'in_batch': True, 'in_packed': False,
            'new_accepted': False, 'riou': metric.get('riou'),
            'ok': bool(metric.get('robust_ok')), 'minutes': None, 'session': trajectory_id,
            'target': rel(target), 'target_image': rel(cache_image), 'rebuild': None,
            'trajectory': rel(sample_path),
            'model': rel(case_dir / 'raw/final.py') if (case_dir / 'raw/final.py').is_file()
                     else rel(case_dir / 'raw/rebuild.py'),
            'report': rel(report_path) if report_path.is_file() else None,
            'design_intent': str(report.get('design_intent') or report.get('summary') or ''),
            'agent_delivered': False, 'target_sha256': source['sha256'],
            'trajectory_sha256': sha(sample_path), 'source_render_sha256': sha(cache_image),
            'reasoning_origin': 'historical and Codex post-hoc visible-evidence annotations; see each message source label',
            'training_quality': 'pending review; dataset training_ready is false',
        }
    active = {'schema_version': 'stepir-review-catalog-v3-datav1', 'total': len(rows),
              'display_scope': 'The current site displays only the 1772 selected datav1 trajectories.',
              'previous_snapshot_total': 1572, 'previous_snapshot_catalog': 'catalog-1572.json',
              'previous_snapshot_marks_preserved': True, 'added_batch': 'datav1', 'added_count': 1772,
              'source_datav1_manifest_sha256': sha(OLD_MANIFEST), 'rows': list(rows.values())}
    if len(rows) != 1772:
        raise RuntimeError(f'Expected active datav1 catalog size 1772, found {len(rows)}')
    marks_path = DATA_DIR / 'annotations/marks.json'
    original = json.loads(marks_path.read_text())
    if len(original) != 1572:
        raise RuntimeError(f'Existing 1572-session marks changed: {len(original)}')
    atomic(DATA_DIR / 'active-catalog.json', active)
    marks_after = json.loads(marks_path.read_text())
    if marks_after != original:
        raise RuntimeError('Existing annotations changed while adding the datav1 catalog')
    print(json.dumps({'active_display_total': len(rows), 'preserved_existing': len(original),
                      'datav1_added': 1772, 'all_targets_and_renders_hashed': True}))


if __name__ == '__main__':
    main()
