"""Controller-owned OpenRouter transport with budget enforcement and exact records.

The agent receives only a per-run local credential, never the paid provider key.
No extraction, retrieval, memory classification or rubric logic lives here.
"""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
import urllib.error
import urllib.request
import uuid

from .recording import BudgetLedger

ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'


def save_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def reservation(body, *, input_per_million, output_per_million):
    if body.get('n', 1) != 1 or any(k in body for k in ('best_of', 'plugins', 'models')):
        raise ValueError('Unbounded or extra-cost generation options are not permitted')
    if any(tool.get('type') != 'function' for tool in body.get('tools', [])):
        raise ValueError('Only local client function tools are permitted; no hosted-tool fees')
    values = [body[k] for k in ('max_tokens', 'max_completion_tokens') if k in body]
    if len(values) != 1 or type(values[0]) is not int or not 1 <= values[0] <= 16000:
        raise ValueError('Set exactly one output-token bound between 1 and 16000')
    # Conservatively reserve one token per UTF-8 byte plus envelope allowance.
    # This is a pre-request cost bound, not reported usage or a performance metric.
    input_bound = len(json.dumps(body, ensure_ascii=False).encode()) + 4096
    return (input_bound * input_per_million + values[0] * output_per_million) / 1_000_000


def decode_usage(raw, streaming):
    if not streaming:
        value = json.loads(raw)
        return value, value.get('usage')
    events = []
    for line in raw.decode().splitlines():
        if line.startswith('data: ') and line != 'data: [DONE]':
            events.append(json.loads(line[6:]))
    if not any(line.strip() == 'data: [DONE]' for line in raw.decode().splitlines()):
        raise ValueError('Incomplete streaming response')
    usage = next((e['usage'] for e in reversed(events) if e.get('usage')), None)
    return events, usage


class Gateway(ThreadingHTTPServer):
    # server_close must join paid requests, even if an agent abandons its local
    # connection. Otherwise a CLI exit can destroy a still-billable receipt.
    daemon_threads = False

    def __init__(self, *, key, output, ledger_path, campaign_identity, cap_usd,
                 phase, model, input_per_million, output_per_million, endpoint=ENDPOINT,
                 output_token_cap=4096, required_tool_catalog=None):
        if endpoint != ENDPOINT and not endpoint.startswith('http://127.0.0.1:'):
            raise ValueError('Only OpenRouter or an explicit local offline fixture is supported')
        self.endpoint = endpoint
        if type(output_token_cap) is not int or not 1 <= output_token_cap <= 16000:
            raise ValueError('Invalid declared output-token cap')
        self.output_token_cap = output_token_cap
        self.required_tool_catalog = required_tool_catalog
        self.key, self.output = key, Path(output)
        self.ledger_path, self.campaign_identity = ledger_path, campaign_identity
        self.cap_usd, self.phase, self.model = cap_usd, phase, model
        self.input_price, self.output_price = input_per_million, output_per_million
        self.local_token = secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1', 0), Handler)

    def start(self):
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.shutdown()
        self.server_close()
        self.thread.join(10)

    @property
    def base_url(self):
        return f'http://127.0.0.1:{self.server_port}/v1'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Never log headers, keys or content through the HTTP server.

    def error_response(self, code, message):
        raw = json.dumps({'error': {'message': message, 'type': 'atmem_transport_guard'}}).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        server = self.server
        if self.path != '/v1/chat/completions':
            return self.error_response(404, 'Only the declared chat-completions transport is available')
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + server.local_token):
            return self.error_response(401, 'Invalid local transport credential')
        book = None
        body = None
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 1 <= length <= 16 * 1024 * 1024:
                raise ValueError('Request size outside bounds')
            body = json.loads(self.rfile.read(length))
            if body.get('model') != server.model:
                raise ValueError('Model differs from frozen campaign configuration')
            if server.required_tool_catalog and body.get('tools') and server.required_tool_catalog not in json.dumps(body['tools']):
                raise ValueError('Required simulated app tools were not discovered; refusing a paid request')
            # Some Hermes CLI routes omit their configured cap. Enforce the
            # declared transport cap explicitly; retain this adjustment, never
            # pretend the original CLI supplied it.
            adjustments = {}
            if not any(k in body for k in ('max_tokens', 'max_completion_tokens')):
                body['max_completion_tokens'] = server.output_token_cap
                adjustments['max_completion_tokens'] = {'original': None, 'effective': server.output_token_cap}
            elif any(body.get(k, 0) > server.output_token_cap for k in ('max_tokens', 'max_completion_tokens')):
                raise ValueError('Requested output limit exceeds the declared campaign cap')
            expected_routing = {'only': ['azure'], 'allow_fallbacks': False,
                                'require_parameters': True,
                                'max_price': {'prompt': server.input_price, 'completion': server.output_price}}
            # Routing is declared in the campaign; semantic prompts and messages are untouched.
            if 'provider' in body and body['provider'] != expected_routing:
                raise ValueError('Caller attempted to override the declared Azure-only routing')
            body['provider'] = expected_routing
            bound = reservation(body, input_per_million=server.input_price,
                                output_per_million=server.output_price)
            call_id = uuid.uuid4().hex
            directory = server.output / server.phase / call_id
            book = BudgetLedger(server.ledger_path, cap_usd=server.cap_usd, identity=server.campaign_identity)
            # Both the exact outgoing request and the reservation are durable before send.
            save_new(directory / 'request.json', body)
            save_new(directory / 'transport.json', {'call_id': call_id, 'phase': server.phase,
                                                    'started_ns': time.time_ns(),
                                                    'parameter_adjustments': adjustments})
            book.reserve(call_id, phase=server.phase, request=body, maximum_usd=bound)
            started = time.monotonic()
            req = urllib.request.Request(server.endpoint, data=json.dumps(body).encode(), headers={
                'Authorization': 'Bearer ' + server.key, 'Content-Type': 'application/json',
                'X-Title': 'AtMem DolphinBench disclosed Azure-only OpenRouter transport'})
            try:
                with urllib.request.urlopen(req, timeout=300) as response:
                    raw = response.read(64 * 1024 * 1024 + 1)
                    if len(raw) > 64 * 1024 * 1024:
                        raise ValueError('Response size outside bounds; cost remains reserved')
                    content_type = response.headers.get('Content-Type', 'application/json')
            except urllib.error.HTTPError as exc:
                save_new(directory / 'error.json', {'http_status': exc.code, 'cost_status': 'reserved_uncertain',
                                                    'elapsed_seconds': time.monotonic() - started})
                return self.error_response(exc.code, 'Upstream request failed; reservation retained for reconciliation')
            decoded, usage = decode_usage(raw, bool(body.get('stream')))
            save_new(directory / 'response.json', {'response': decoded,
                                                   'elapsed_seconds': time.monotonic() - started})
            records = decoded if isinstance(decoded, list) else [decoded]
            if any(r.get('provider') and r['provider'].lower() != 'azure' for r in records):
                raise ValueError('Unexpected upstream provider; quarantine response and stop')
            if not any(r.get('provider', '').lower() == 'azure' for r in records):
                raise ValueError('Missing upstream provider attestation')
            if not usage or 'cost' not in usage:
                raise ValueError('Missing API cost/usage; reservation retained')
            if any(r.get('model') and r['model'] not in {server.model, server.model + '-20260709'} for r in records):
                raise ValueError('Unexpected response model; quarantine response and stop')
            book.complete(call_id, actual_usd=usage['cost'], usage=usage, response=decoded)
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except PermissionError:
            self.error_response(402, 'Campaign budget guard stopped this request before forwarding')
        except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
            # Keep a bounded diagnostic for failed configuration gates. These are
            # outgoing request bodies, never authentication headers.
            if body is not None and server.key not in json.dumps(body):
                save_new(server.output / 'rejected' / (uuid.uuid4().hex + '.json'),
                         {'request': body, 'error_type': type(exc).__name__,
                          'reason': str(exc)[:500]})
            self.error_response(400, 'Transport qualification failed; inspect retained evidence before retrying')
        finally:
            if book is not None:
                book.close()
