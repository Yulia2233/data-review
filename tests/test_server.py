import json
import base64
import os
from pathlib import Path
import subprocess
import socket
import sys
import tempfile
import time
import urllib.request
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReviewServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="data-review-test-")
        self.state = Path(self.temp.name)
        (self.state / "annotations").mkdir()
        (self.state / "active-catalog.json").write_text(
            json.dumps({"schema_version": "test", "rows": [{
                "case": "fixture--001", "part_name": "Fixture", "batch": "test",
                "target": "missing.step", "rebuild": None, "trajectory": "trajectory.json",
                "model": None, "report": None, "in_batch": True, "in_packed": False,
                "new_accepted": False,
            }]})
        )
        self.raw = json.dumps({
            "schema_version": "cad-code-session-v2", "id": "fixture-session",
            "messages": [{"info": {"role": "assistant"}, "parts": [
                {"type": "reasoning", "text": ""},
                {"type": "tool", "tool": "exec", "callID": "call-fixture",
                 "state": {"status": "completed", "input": {"code": "text('fixture')"},
                           "output": "first line\nsecond line"}}
            ]}],
            "tool_media": [{"callID": "call-fixture", "content": [
                {"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(b'fixture-png').decode()}
            ]}]
        }, indent=2).encode()
        (self.state / "trajectory.json").write_bytes(self.raw)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            self.port = listener.getsockname()[1]
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        self.proc = subprocess.Popen([
            sys.executable, str(ROOT / "server.py"), "--port", str(self.port),
            "--root", str(self.state), "--data-dir", str(self.state),
            "--catalog", str(self.state / "active-catalog.json"),
            "--images", str(self.state / "images"),
            "--annotations", str(self.state / "annotations"),
        ], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(50):
            try:
                self.get("/api/catalog")
                break
            except Exception:
                time.sleep(.05)
        else:
            self.proc.terminate()
            _, errors = self.proc.communicate(timeout=3)
            self.fail(errors)

    def tearDown(self):
        self.proc.terminate()
        self.proc.wait(timeout=3)
        self.proc.stdout.close()
        self.proc.stderr.close()
        self.temp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=2) as response:
            return json.loads(response.read())

    def test_catalog_trajectory_and_mark_history(self):
        catalog = self.get("/api/catalog")
        self.assertEqual(len(catalog["cases"]), 1)
        self.assertFalse(catalog["cases"][0]["has_rebuild"])
        trajectory = self.get("/api/trajectory?case=fixture--001")
        self.assertEqual(trajectory["schema_version"], "cad-code-session-v2")
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/marks", method="POST",
            data=json.dumps({"case": "fixture--001", "label": "pass"}).encode(),
            headers={"Content-Type": "application/json", "X-Review-Token": catalog["token"]})
        with urllib.request.urlopen(request, timeout=2) as response:
            self.assertTrue(json.loads(response.read())["ok"])
        self.assertEqual(json.loads((self.state / "annotations/marks.json").read_text())["fixture--001"]["label"], "pass")
        self.assertEqual(len((self.state / "annotations/history.jsonl").read_text().splitlines()), 1)

    def test_invalid_mark_is_rejected(self):
        catalog = self.get("/api/catalog")
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/marks", method="POST",
            data=json.dumps({"case": "fixture--001", "label": "maybe"}).encode(),
            headers={"Content-Type": "application/json", "X-Review-Token": catalog["token"]})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=2)
        self.assertEqual(error.exception.code, 400)
        error.exception.close()

    def test_raw_export_media_and_observations_are_preserved(self):
        data = self.get('/api/trajectory?case=fixture--001')
        self.assertEqual(data['messages'][0]['parts'][0]['text'], '')
        self.assertEqual(data['messages'][0]['parts'][1]['state']['output'], 'first line\nsecond line')
        image_url = data['tool_media'][0]['content'][0]['image_url']
        with urllib.request.urlopen(f'http://127.0.0.1:{self.port}{image_url}', timeout=2) as response:
            self.assertEqual(response.read(), b'fixture-png')
        with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/api/raw-trajectory?case=fixture--001', timeout=2) as response:
            self.assertEqual(response.read(), self.raw)
        self.assertEqual((self.state / 'trajectory.json').read_bytes(), self.raw)

    def test_existing_labels_and_history_are_kept(self):
        old = {'old--case': {'label': 'fail', 'updated_at': 'historic'}}
        path = self.state / 'annotations/marks.json'
        path.write_text(json.dumps(old))
        catalog = self.get('/api/catalog')
        self.assertEqual(catalog['marks'], old)
        for label in ['pass', 'fail']:
            req = urllib.request.Request(f'http://127.0.0.1:{self.port}/api/marks', method='POST',
                data=json.dumps({'case': 'fixture--001', 'label': label}).encode(),
                headers={'X-Review-Token': catalog['token'], 'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=2) as response:
                self.assertTrue(json.loads(response.read())['ok'])
        marks = json.loads(path.read_text())
        self.assertEqual(marks['old--case'], old['old--case'])
        self.assertEqual(marks['fixture--001']['label'], 'fail')
        history = [json.loads(line) for line in (self.state / 'annotations/history.jsonl').read_text().splitlines()]
        self.assertEqual(history[-1]['previous']['label'], 'pass')
        self.assertEqual(self.get('/api/marks'), marks)
        # Simulate a process restart, using the same state and annotation paths.
        command = self.proc.args
        self.proc.terminate()
        self.proc.communicate(timeout=3)
        self.proc = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
        for _ in range(50):
            try:
                reloaded = self.get('/api/catalog')
                if reloaded['token'] != catalog['token']:
                    break
            except OSError:
                pass
            time.sleep(.05)
        else:
            self.fail('Server did not restart')
        self.assertEqual(reloaded['marks'], marks)
        self.assertEqual(len((self.state / 'annotations/history.jsonl').read_text().splitlines()), 2)

    def test_existing_origin_host_token_and_static_guards(self):
        base = f'http://127.0.0.1:{self.port}'
        token = self.get('/api/catalog')['token']
        attempts = [
            urllib.request.Request(base + '/api/catalog', headers={'Host': 'other.invalid'}),
            urllib.request.Request(base + '/server.py'),
            urllib.request.Request(base + '/api/marks', method='POST', data=b'{}'),
            urllib.request.Request(base + '/api/marks', method='POST', data=b'{}',
                                   headers={'X-Review-Token': token, 'Origin': 'http://other.invalid'}),
        ]
        for request, expected in zip(attempts, [403, 404, 403, 403]):
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(error.exception.code, expected)
            error.exception.close()

    def test_explicit_missing_catalog_is_an_error(self):
        result = subprocess.run([sys.executable, str(ROOT / 'server.py'), '--catalog',
                                 str(self.state / 'does-not-exist.json')],
                                capture_output=True, text=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--catalog must be an existing JSON file', result.stderr)


class QwenAdapterTests(unittest.TestCase):
    def test_tool_pairing_and_posthoc_thinking_label(self):
        sys.path.insert(0, str(ROOT))
        from qwen_adapter import display
        sample = {'id': 'example', 'messages': [
            {'role': 'assistant', 'content': 'report', 'reasoning_content': 'visible explanation',
             'tool_calls': [{'id': 'c1', 'function': {'name': 'exec', 'arguments': '{"cmd":"test"}'}}]},
            {'role': 'tool', 'tool_call_id': 'c1', 'content': 'exact\noutput'},
        ], 'message_meta': [{'reasoning_sources': [{'origin': 'codex_synthesized_annotation'}]}, {}]}
        data = display(sample)
        self.assertEqual(data['messages'][0]['parts'][0]['source_label'], '事后补写解释')
        self.assertEqual(data['messages'][0]['parts'][-1]['state']['output'], 'exact\noutput')
        self.assertEqual(sample['messages'][1]['content'], 'exact\noutput')


if __name__ == "__main__":
    unittest.main()
