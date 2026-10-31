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
from urllib.parse import urlsplit
import uuid

from .recording import BudgetLedger, fingerprint

ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'


def local_bridge_endpoint(endpoint):
    """Reject user-info/fragment/query and lookalike loopback URL prefixes."""
    try:
        parsed = urlsplit(endpoint)
        return (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
                and parsed.username is None and parsed.password is None
                and parsed.port is not None and 1 <= parsed.port <= 65535
                and not parsed.query and not parsed.fragment
                and parsed.path in {'', '/', '/chat/completions', '/v1/chat/completions'})
    except (ValueError, TypeError):
        return False


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
                 output_token_cap=4096, required_tool_catalog=None, provider_name='Azure',
                 upstream_timeout=300, required_instruction_text=None, execution_profile=None, readiness_options=None):
        self.execution_profile = execution_profile
        self.readiness_options = readiness_options
        if endpoint != ENDPOINT and not local_bridge_endpoint(endpoint):
            raise ValueError('Only OpenRouter or an explicit local offline fixture is supported')
        self.endpoint = endpoint
        if type(output_token_cap) is not int or not 1 <= output_token_cap <= 16000:
            raise ValueError('Invalid declared output-token cap')
        self.output_token_cap = output_token_cap
        self.required_tool_catalog = required_tool_catalog
        if required_instruction_text is not None and (not isinstance(required_instruction_text,str)
                or not required_instruction_text.strip() or len(required_instruction_text.encode())>4096):
            raise ValueError('bounded required host instruction text needed')
        self.required_instruction_text=required_instruction_text
        if provider_name not in {'Azure', 'OpenAI-Subscription'}:
            raise ValueError('Unsupported declared transport provider')
        if provider_name == 'OpenAI-Subscription' and not local_bridge_endpoint(endpoint):
            raise ValueError('Subscription transport requires the qualified local Hermes bridge')
        if provider_name == 'OpenAI-Subscription' and model not in {'openai/gpt-5.6-luna', 'openai/gpt-5.6-sol'}:
            raise ValueError('Unsupported qualified subscription model')
        self.provider_name = provider_name
        self.upstream_timeout = upstream_timeout
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
        directory = None
        forwarding_started = False
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 1 <= length <= 16 * 1024 * 1024:
                raise ValueError('Request size outside bounds')
            body = json.loads(self.rfile.read(length))
            if server.readiness_options is not None:
                from .readiness import require_options
                require_options(server.readiness_options)
            if server.execution_profile is not None:
                from .execution_profile import validate
                validate(server.execution_profile, body)
                if body.get('reasoning_effort') != 'high' or any(k in body for k in ('temperature', 'top_p', 'seed')):
                    raise ValueError('Actual reader inference settings differ from frozen baseline')
                caps = [body[k] for k in ('max_tokens', 'max_completion_tokens') if k in body]
                if caps and caps != [4096]:
                    raise ValueError('Actual reader completion cap differs from frozen baseline')
            if server.phase == 'judge':
                if (body.get('reasoning_effort') != 'medium' or body.get('max_completion_tokens') != 8000
                        or body.get('response_format') != {'type': 'json_object'}
                        or any(k in body for k in ('temperature', 'top_p', 'seed'))):
                    raise ValueError('Actual judge inference settings differ from frozen baseline')
            if body.get('model') != server.model:
                raise ValueError('Model differs from frozen campaign configuration')
            if server.required_tool_catalog and server.required_tool_catalog not in json.dumps(body.get('tools', [])):
                raise ValueError('Required simulated app tools were not discovered; refusing a paid request')
            if server.required_instruction_text is not None and not any(
                    server.required_instruction_text.strip() in message.get('content','')
                    for message in body.get('messages',[]) if message.get('role') in {'system','developer'}
                    and isinstance(message.get('content'),str)):
                raise ValueError('Configured native host identity is missing; request not forwarded')
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
            if server.provider_name == 'Azure':
                body['provider'] = expected_routing
            elif 'provider' in body:
                raise ValueError('Subscription requests cannot override provider routing')
            bound = reservation(body, input_per_million=server.input_price,
                                output_per_million=server.output_price)
            call_id = uuid.uuid4().hex
            directory = server.output / server.phase / call_id
            book = BudgetLedger(server.ledger_path, cap_usd=server.cap_usd, identity=server.campaign_identity)
            # Both the exact outgoing request and the reservation are durable before send.
            save_new(directory / 'request.json', body)
            save_new(directory / 'transport.json', {'call_id': call_id, 'phase': server.phase,
                                                    'started_ns': time.time_ns(),
                                                    'provider': server.provider_name,
                                                    'cash_reservation_usd': 0 if server.provider_name == 'OpenAI-Subscription' else bound,
                                                    'parameter_adjustments': adjustments})
            if server.provider_name == 'OpenAI-Subscription':
                book.reserve_subscription(call_id, phase=server.phase, request=body)
            else:
                book.reserve(call_id, phase=server.phase, request=body, maximum_usd=bound)
            started = time.monotonic()
            req = urllib.request.Request(server.endpoint, data=json.dumps(body).encode(), headers={
                'Authorization': 'Bearer ' + server.key, 'Content-Type': 'application/json',
                'X-Title': 'AtMem DolphinBench disclosed Azure-only OpenRouter transport'})
            try:
                forwarding_started = True
                with urllib.request.urlopen(req, timeout=server.upstream_timeout) as response:
                    raw = response.read(64 * 1024 * 1024 + 1)
                    if len(raw) > 64 * 1024 * 1024:
                        raise ValueError('Response size outside bounds; cost remains reserved')
                    content_type = response.headers.get('Content-Type', 'application/json')
            except urllib.error.HTTPError as exc:
                save_new(directory / 'error.json', {'http_status': exc.code, 'cost_status': 'reserved_uncertain',
                                                    'elapsed_seconds': time.monotonic() - started})
                if server.provider_name == 'OpenAI-Subscription':
                    receipt = {'provider': server.provider_name, 'response_delivered': False,
                        'http_status': exc.code, 'usage': None,
                        'incremental_api_charge_usd': 0,
                        'billing_basis': 'subscription, not paid API; generation outcome unknown'}
                    save_new(directory / 'subscription-failure.json', receipt)
                    book.settle_subscription_failure(call_id, request=body, failure_receipt=receipt)
                return self.error_response(exc.code, 'Upstream request failed; reservation retained for reconciliation')
            except TimeoutError:
                save_new(directory / 'error.json', {'http_status': 504, 'cost_status': 'reserved_uncertain',
                                                    'elapsed_seconds': time.monotonic() - started})
                return self.error_response(504, 'Upstream timed out; reservation retained for reconciliation')
            except urllib.error.URLError as exc:
                if not isinstance(exc.reason, TimeoutError):
                    raise
                save_new(directory / 'error.json', {'http_status': 504, 'cost_status': 'reserved_uncertain',
                                                    'elapsed_seconds': time.monotonic() - started})
                return self.error_response(504, 'Upstream timed out; reservation retained for reconciliation')
            decoded, usage = decode_usage(raw, bool(body.get('stream')))
            save_new(directory / 'response.json', {'response': decoded,
                                                   'elapsed_seconds': time.monotonic() - started})
            records = decoded if isinstance(decoded, list) else [decoded]
            # OpenRouter can return HTTP 200 with an embedded upstream timeout.
            # Retain the response and full reservation; propagate only known
            # transient failures so the judge's bounded retry can handle them.
            if isinstance(decoded, dict) and isinstance(decoded.get('error'), dict):
                code = decoded['error'].get('code')
                if type(code) is int and code in {429, 500, 502, 503, 504} and 'choices' not in decoded:
                    return self.error_response(code, 'Upstream transient failure; reservation retained')
            if any(r.get('provider') and r['provider'].lower() != server.provider_name.lower() for r in records):
                raise ValueError('Unexpected upstream provider; quarantine response and stop')
            if not any(r.get('provider', '').lower() == server.provider_name.lower() for r in records):
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
            if directory is not None:
                row = book.connection.execute('SELECT state FROM calls WHERE call_id=?', (call_id,)).fetchone()
                save_new(directory / 'guard-denial.json', {
                    'call_id': call_id, 'request_sha256': fingerprint(body),
                    'forwarding_started': forwarding_started,
                    'ledger_state': row[0] if row else None,
                    'provider_usage': None if forwarding_started else {'prompt_tokens': 0, 'completion_tokens': 0},
                    'outcome': 'requires_reconciliation' if forwarding_started else 'proven_unsent',
                })
            message = ('Campaign budget guard stopped this request after forwarding; reconciliation required'
                       if forwarding_started else 'Campaign budget guard stopped this request before forwarding')
            self.error_response(402, message)
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
