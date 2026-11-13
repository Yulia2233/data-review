#!/usr/bin/env python3
"""Local trajectory review: immutable source artifacts, atomic independent binary marks."""
from __future__ import annotations
import argparse
import base64
import json
import mimetypes
import os
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('DATA_REVIEW_ROOT', HERE)).expanduser().resolve()
DATA_DIR = Path(os.environ.get('DATA_REVIEW_DATA_DIR', HERE)).expanduser().resolve()
IMAGES = Path(os.environ.get('DATA_REVIEW_IMAGES', DATA_DIR / 'images')).expanduser().resolve()
PACKED = ROOT / 'datasets/data-traj2/stepir-v6.3'
BATCH = ROOT / 'stepir_geom_gen/cadcode_synth_v63'
LOCK = threading.RLock()
TOKEN = secrets.token_urlsafe(32)
ANNOTATIONS = Path(os.environ.get('DATA_REVIEW_ANNOTATIONS', DATA_DIR / 'annotations')).expanduser().resolve()
PORT = 8778
CATALOG = Path(os.environ.get('DATA_REVIEW_CATALOG', DATA_DIR / 'active-catalog.json')).expanduser().resolve()


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def catalog():
    manifest = CATALOG if CATALOG.exists() else DATA_DIR / 'catalog.json'
    if manifest.exists():
        payload = read_json(manifest)
        rows = {}
        for item in payload['rows']:
            row = dict(item)
            for field in ('target', 'target_image', 'rebuild', 'trajectory', 'model', 'report'):
                row[field] = ROOT / row[field] if row.get(field) else None
            rows[row['case']] = row
        return rows
    if not (PACKED / 'index.jsonl').is_file():
        return {}
    packed_rows = [json.loads(x) for x in (PACKED / 'index.jsonl').read_text().splitlines() if x.strip()]
    rows = {}
    for p in sorted((BATCH / 'out').glob('*/verdict.json')):
        verdict = read_json(p)
        case = p.parent.name
        model = verdict.get('model') or {}
        rebuild = next((x for x in (p.parent / 'model.step', p.parent / 'verify_model_long/candidate.step',
                                   p.parent / 'verify_model/candidate.step') if x.is_file() and x.stat().st_size), None)
        rows[case] = {'case': case, 'in_batch': True, 'in_packed': False, 'new_accepted': False,
                      'riou': model.get('riou'), 'ok': bool(model.get('ok')),
                      'minutes': round((verdict.get('secs') or 0) / 60, 1),
                      'session': verdict.get('session'), 'target': BATCH / 'jobs' / case / 'target.step',
                      'rebuild': rebuild, 'trajectory': BATCH / 'trajectories' / (case + '.json'),
                      'model': p.parent / 'model.py', 'report': p.parent / 'report.json',
                      'design_intent': '', 'agent_delivered': bool(verdict.get('model_step'))}
    for item in packed_rows:
        case = item['case']
        row = rows.setdefault(case, {'case': case, 'in_batch': False})
        row.update(in_packed=True, new_accepted=item.get('source_batch') == 'cadcode_synth_v63',
                   riou=item.get('riou'), ok=True, minutes=item.get('minutes'), session=item.get('session'),
                   target=PACKED / case / 'target.step', rebuild=PACKED / case / 'rebuild.step',
                   trajectory=PACKED / case / 'trajectory.json', model=PACKED / case / 'model.py',
                   report=BATCH / 'out' / case / 'report.json', design_intent=item.get('design_intent', ''),
                   agent_delivered=item.get('rebuild_step', '').startswith('agent export'))
    return dict(sorted(rows.items()))


ROWS = {}


def public_row(row):
    return {k: v for k, v in row.items() if k not in ('target', 'target_image', 'rebuild', 'trajectory', 'model', 'report')} | {
        'has_target': bool(row.get('target') and row['target'].is_file()), 'has_rebuild': bool(row.get('rebuild') and row['rebuild'].is_file()),
        'has_trajectory': bool(row.get('trajectory') and row['trajectory'].is_file()), 'has_target_image': bool(row.get('target_image') and row['target_image'].is_file())}


def marks():
    return read_json(ANNOTATIONS / 'marks.json', {})


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as fh:
            json.dump(value, fh, ensure_ascii=False, indent=2)
            fh.write('\n')
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def trajectory(row):
    data = read_json(row['trajectory'])
    if not data:
        raise FileNotFoundError('轨迹文件缺失')
    if row.get('trajectory_format') == 'qwen':
        import importlib.util
        adapter_path = (HERE / 'qwen_adapter.py').resolve()
        spec = importlib.util.spec_from_file_location('v63_qwen_adapter', adapter_path)
        if not spec or not spec.loader:
            raise RuntimeError('Qwen trajectory adapter unavailable')
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        return adapter.display(data)
    # Keep every observation intact; move only inline bitmap bytes to image endpoints.
    for index, item in enumerate(data.get('tool_media', [])):
        for part_index, part in enumerate(item.get('content', [])):
            if part.get('type') == 'input_image' and str(part.get('image_url', '')).startswith('data:image/'):
                part['image_url'] = f"/api/tool-image?case={row['case']}&media={index}&part={part_index}"
    return data


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{PORT}', f'localhost:{PORT}')

    def reply_bytes(self, body, content_type, status=200, download=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(body)

    def reply(self, value, status=200):
        self.reply_bytes(json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8', status)

    def do_GET(self):
        if not self.valid_host():
            return self.reply({'error': 'Host refused'}, 403)
        u = urlsplit(self.path)
        q = parse_qs(u.query)
        case = q.get('case', [''])[0]
        row = ROWS.get(case)
        try:
            if u.path == '/api/catalog':
                with LOCK:
                    return self.reply({'cases': [public_row(r) for r in ROWS.values()], 'marks': marks(), 'token': TOKEN})
            if u.path == '/api/marks':
                with LOCK:
                    return self.reply(marks())
            if u.path in ('/api/trajectory', '/api/raw-trajectory', '/api/image', '/api/artifact', '/api/tool-image', '/api/render-case'):
                if not row:
                    return self.reply({'error': '未知零件'}, 404)
                if u.path == '/api/trajectory':
                    return self.reply(trajectory(row))
                if u.path == '/api/render-case':
                    if row.get('batch') == 'datav1':
                        return self.reply({'status': 'missing_rebuild', 'camera': {'fit': 'target_only'}})
                    return self.reply(read_json(IMAGES / case / 'render.json', {'status': 'pending'}))
                if u.path == '/api/raw-trajectory':
                    return self.reply_bytes(row['trajectory'].read_bytes(), 'application/json', download=case+'.json')
                if u.path == '/api/image':
                    kind = q.get('kind', [''])[0]
                    if kind not in ('target', 'rebuild'):
                        return self.reply({'error': '未知图片类型'}, 400)
                    if row.get('batch') == 'datav1' and kind == 'target':
                        image = row.get('target_image')
                        if image and image.is_file():
                            return self.reply_bytes(image.read_bytes(), 'image/png')
                    if row.get('batch') == 'datav1' and kind == 'rebuild':
                        return self.reply({'error': 'datav1 原始样本未包含重建 STEP'}, 404)
                    image = IMAGES / case / (kind + '.png')
                    if image.is_file():
                        return self.reply_bytes(image.read_bytes(), 'image/png')
                    return self.reply({'error': '未交付重建 STEP' if kind == 'rebuild' and not row['rebuild'] else '等测图准备中'}, 404)
                if u.path == '/api/tool-image':
                    data = read_json(row['trajectory'])
                    part = data['tool_media'][int(q['media'][0])]['content'][int(q['part'][0])]
                    uri = part['image_url']
                    if not uri.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,')):
                        raise ValueError('Unsupported image')
                    header, encoded = uri.split(',', 1)
                    return self.reply_bytes(base64.b64decode(encoded, validate=True), header[5:].split(';')[0])
                kind = q.get('kind', [''])[0]
                if kind not in ('target', 'rebuild', 'model'):
                    return self.reply({'error': '未知文件类型'}, 400)
                source = row[kind]
                if not source or not source.is_file():
                    return self.reply({'error': '文件未交付'}, 404)
                return self.reply_bytes(source.read_bytes(), 'text/x-python; charset=utf-8' if kind == 'model' else 'application/step', download=source.name)
            if u.path == '/api/render-status':
                return self.reply(read_json(DATA_DIR / 'render-status.json', {}))
            static = {'/': 'index.html', '/index.html': 'index.html', '/app.js': 'app.js', '/styles.css': 'styles.css'}
            if u.path not in static:
                return self.reply({'error': 'Not found'}, 404)
            p = HERE / static[u.path]
            return self.reply_bytes(p.read_bytes(), mimetypes.guess_type(p.name)[0] + ('; charset=utf-8' if p.suffix in ('.html', '.js', '.css') else ''))
        except (FileNotFoundError, KeyError, IndexError, ValueError) as exc:
            return self.reply({'error': str(exc)}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if not self.valid_host() or self.headers.get('X-Review-Token') != TOKEN:
            return self.reply({'error': '请求来源无效，请刷新页面'}, 403)
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'):
            return self.reply({'error': 'Origin refused'}, 403)
        if urlsplit(self.path).path != '/api/marks':
            return self.reply({'error': 'Not found'}, 404)
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size < 4096:
                raise ValueError('标注请求无效')
            payload = json.loads(self.rfile.read(size))
            case, label = payload.get('case'), payload.get('label')
            if case not in ROWS or label not in ('pass', 'fail'):
                raise ValueError('只支持 ✅ 和 ❌')
            mark = {'label': label, 'updated_at': datetime.now(timezone.utc).isoformat()}
            with LOCK:
                data = marks()
                previous = data.get(case)
                data[case] = mark
                atomic_json(ANNOTATIONS / 'marks.json', data)
                with (ANNOTATIONS / 'history.jsonl').open('a') as fh:
                    fh.write(json.dumps({'case': case, 'previous': previous, 'mark': mark}, ensure_ascii=False) + '\n')
                    fh.flush()
                    os.fsync(fh.fileno())
            return self.reply({'ok': True, 'case': case, 'mark': mark})
        except (ValueError, TypeError) as exc:
            return self.reply({'error': str(exc)}, 400)

    def log_message(self, fmt, *args):
        if args and str(args[0]).startswith('POST'):
            print(fmt % args, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--annotations', type=Path, help='Mark and append-only history directory')
    parser.add_argument('--root', type=Path, default=ROOT, help='Root for catalog artifact paths')
    parser.add_argument('--data-dir', type=Path, default=DATA_DIR, help='Local catalog/cache directory')
    parser.add_argument('--catalog', type=Path, help='Explicit catalog JSON; missing files are an error')
    parser.add_argument('--images', type=Path, help='Pre-rendered images directory')
    args = parser.parse_args()
    if args.catalog and not args.catalog.is_file():
        parser.error('--catalog must be an existing JSON file')
    ROOT, DATA_DIR = args.root.resolve(), args.data_dir.resolve()
    PACKED, BATCH = ROOT / 'datasets/data-traj2/stepir-v6.3', ROOT / 'stepir_geom_gen/cadcode_synth_v63'
    CATALOG = args.catalog.resolve() if args.catalog else Path(os.environ.get('DATA_REVIEW_CATALOG', DATA_DIR / 'active-catalog.json')).resolve()
    IMAGES = args.images.resolve() if args.images else Path(os.environ.get('DATA_REVIEW_IMAGES', DATA_DIR / 'images')).resolve()
    PORT = args.port
    ANNOTATIONS = args.annotations.resolve() if args.annotations else Path(os.environ.get('DATA_REVIEW_ANNOTATIONS', DATA_DIR / 'annotations')).resolve()
    ROWS = catalog()
    print(f'http://127.0.0.1:{PORT}/ — {len(ROWS)} trajectories', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
