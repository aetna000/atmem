import importlib
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
gateway = importlib.import_module('benchmarks.dolphinbench.gateway')


def test_rejects_unknown_or_unbounded_cost_options():
    for body in ({}, {'max_tokens': 0}, {'max_tokens': True}, {'max_tokens': 16001},
                 {'max_tokens': 10, 'n': 2}, {'max_tokens': 10, 'plugins': []},
                 {'max_tokens': 10, 'tools': [{'type': 'web_search'}]},
                 {'max_tokens': 1, 'max_completion_tokens': 1}):
        with pytest.raises(ValueError):
            gateway.reservation(body, input_per_million=5, output_per_million=30)


def test_non_ascii_input_bound_is_conservative():
    body = {'messages': [{'role': 'user', 'content': '你好'}], 'max_completion_tokens': 8000}
    assert gateway.reservation(body, input_per_million=5, output_per_million=30) > 0.24


def test_streaming_usage_and_missing_terminator():
    raw = b'data: {"provider":"Azure","usage":{"prompt_tokens":1,"completion_tokens":2,"cost":0.01}}\n\ndata: [DONE]\n\n'
    events, usage = gateway.decode_usage(raw, True)
    assert usage['cost'] == 0.01 and events[0]['provider'] == 'Azure'
    with pytest.raises(ValueError):
        gateway.decode_usage(raw.replace(b'data: [DONE]', b''), True)


def test_gateway_rejects_bad_credentials_and_model_before_network(tmp_path, monkeypatch):
    real_urlopen = urllib.request.urlopen
    def local_only(request, *args, **kwargs):
        address = request.full_url if isinstance(request, urllib.request.Request) else request
        assert address.startswith('http://127.0.0.1:'), 'Unexpected paid request in offline test'
        return real_urlopen(request, *args, **kwargs)
    monkeypatch.setattr(urllib.request, 'urlopen', local_only)
    server = gateway.Gateway(key='test-not-a-provider-key', output=tmp_path / 'calls',
        ledger_path=tmp_path / 'ledger.db', campaign_identity={'test': True}, cap_usd=250,
        phase='qualification', model='openai/gpt-5.6-sol', input_per_million=5, output_per_million=30).start()
    try:
        for token, model, code in [('wrong', server.model, 401), (server.local_token, 'wrong', 400)]:
            req = urllib.request.Request(server.base_url + '/chat/completions',
                data=json.dumps({'model': model, 'max_completion_tokens': 10}).encode(),
                headers={'Authorization': 'Bearer ' + token})
            with pytest.raises(urllib.error.HTTPError) as error:
                real_urlopen(req, timeout=5)
            assert error.value.code == code
        assert not (tmp_path / 'ledger.db').exists()
    finally:
        server.stop()


def test_gateway_retains_receipt_and_declares_missing_token_cap(tmp_path):
    received = []
    started = threading.Event()
    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            started.set()
            time.sleep(0.1)
            raw = json.dumps({'provider': 'Azure', 'model': 'openai/gpt-5.6-luna',
                'choices': [{'message': {'role': 'assistant', 'content': 'fixture'}}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'cost': 0}}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    fixture = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    thread = threading.Thread(target=fixture.serve_forever, daemon=True)
    thread.start()
    server = gateway.Gateway(key='fixture-only', output=tmp_path / 'calls',
        ledger_path=tmp_path / 'ledger.db', campaign_identity={'test': True}, cap_usd=1,
        phase='qualification', model='openai/gpt-5.6-luna', input_per_million=1, output_per_million=5,
        endpoint=f'http://127.0.0.1:{fixture.server_port}/chat/completions', output_token_cap=123).start()
    errors = []
    def request():
        try:
            req = urllib.request.Request(server.base_url + '/chat/completions',
                data=json.dumps({'model': server.model, 'messages': [{'role': 'user', 'content': 'fixture'}]}).encode(),
                headers={'Authorization': 'Bearer ' + server.local_token})
            with urllib.request.urlopen(req, timeout=5) as response:
                response.read()
        except Exception as exc:
            errors.append(exc)
    caller = threading.Thread(target=request)
    caller.start()
    try:
        assert started.wait(5)
        server.stop()
        caller.join(5)
        assert not caller.is_alive() and not errors
        assert received[0]['max_completion_tokens'] == 123
        transport = json.loads(next((tmp_path / 'calls').rglob('transport.json')).read_text())
        assert transport['parameter_adjustments']['max_completion_tokens'] == {'original': None, 'effective': 123}
        assert len(list((tmp_path / 'calls').rglob('response.json'))) == 1
    finally:
        fixture.shutdown()
        fixture.server_close()
        thread.join(5)
