"""No-cost replay qualification for the disclosed Sol routing alias."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import threading

import pytest


def test_sol_alias_records_fixed_settings_and_replays_without_network():
    upstream = Path('/Volumes/AtMemDolphin/upstream')
    if not upstream.is_dir():
        pytest.skip('Pinned local DolphinBench checkout is not installed')
    sys.path.append(str(upstream))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from benchmarks.dolphinbench.judge import openrouter_judge
    from graders import llm_judge
    from graders.judge_recording import record_judge, replay_judge
    requests = []
    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            raw = json.dumps({'model': 'openai/gpt-5.6-sol', 'choices': [
                {'finish_reason': 'stop', 'message': {'role': 'assistant',
                 'content': '{"passed":true,"reasoning":"offline fixture only"}'}}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'cost': 0}}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        gateway = SimpleNamespace(base_url=f'http://127.0.0.1:{server.server_port}/v1', local_token='offline-only')
        with record_judge() as recorded, openrouter_judge(gateway):
            assert llm_judge._call_judge('fixture system', 'fixture user', {})['passed']
        assert requests[0]['model'] == 'openai/gpt-5.6-sol'
        assert recorded.settings == {'model': 'gpt-5.6-sol', 'reasoning_effort': 'medium',
            'max_completion_tokens': 8000, 'response_format': {'type': 'json_object'}}
        with replay_judge(recorded.messages, recorded.settings):
            assert llm_judge._call_judge('fixture system', 'fixture user', {})['passed']
        assert len(requests) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
