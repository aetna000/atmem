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


def test_transient_http_504_retries_without_rerunning_actions(monkeypatch):
    import io
    import urllib.error
    upstream=Path('/Users/javadtaghia/gitlab/benchmark-sources/dolphinbench')
    if not upstream.is_dir(): pytest.skip('Pinned benchmark source unavailable')
    sys.path.insert(0,str(upstream))
    from benchmarks.dolphinbench import judge
    from graders import llm_judge
    calls=[]
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, *args):
            return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{"passed":true}'}}]}).encode()
    def request(req, timeout):
        calls.append(req.full_url)
        if len(calls)<=4: raise urllib.error.HTTPError(req.full_url,504,'timeout',{},io.BytesIO())
        return Reply()
    monkeypatch.setattr(judge.urllib.request,'urlopen',request)
    monkeypatch.setattr(judge.time,'sleep',lambda _:None)
    with judge.openrouter_judge(SimpleNamespace(base_url='http://127.0.0.1:1/v1',local_token='offline')):
        assert llm_judge._call_judge('fixture system','fixture user',{})['passed'] is True
    assert len(calls)==5


def test_gateway_embedded_timeout_then_judge_success(tmp_path, monkeypatch):
    upstream = Path('/Users/javadtaghia/gitlab/benchmark-sources/dolphinbench')
    if not upstream.is_dir(): pytest.skip('Pinned benchmark source unavailable')
    sys.path.insert(0, str(upstream))
    from benchmarks.dolphinbench import gateway, judge
    from graders import llm_judge
    requests = []
    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            payload = ({'error': {'code': 504, 'message': 'idle timeout'}} if len(requests) == 1 else
                {'provider': 'Azure', 'model': 'openai/gpt-5.6-sol', 'choices': [
                    {'finish_reason': 'stop', 'message': {'content': '{"passed":true}'}}],
                 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'cost': 0}})
            raw = json.dumps(payload).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(raw)))
            self.end_headers(); self.wfile.write(raw)
    fixture = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    thread = threading.Thread(target=fixture.serve_forever, daemon=True); thread.start()
    server = gateway.Gateway(key='fixture-only', output=tmp_path/'calls', ledger_path=tmp_path/'ledger.db',
        campaign_identity={'test': True}, cap_usd=1, phase='judge', model='openai/gpt-5.6-sol',
        input_per_million=5, output_per_million=30, output_token_cap=8000,
        endpoint=f'http://127.0.0.1:{fixture.server_port}/v1/chat/completions', provider_name='Azure').start()
    monkeypatch.setattr(judge.time, 'sleep', lambda _: None)
    try:
        with judge.openrouter_judge(server):
            assert llm_judge._call_judge('fixture system', 'fixture user', {})['passed'] is True
        assert len(requests) == 2 and requests[0] == requests[1]
        book = gateway.BudgetLedger(tmp_path/'ledger.db', cap_usd=1, identity={'test': True})
        try:
            assert sorted(row[0] for row in book.connection.execute('SELECT state FROM calls')) == ['completed', 'reserved']
        finally: book.close()
    finally:
        server.stop(); fixture.shutdown(); fixture.server_close(); thread.join(5)
