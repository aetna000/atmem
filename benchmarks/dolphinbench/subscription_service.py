"""Controller-only subscription bridge using Hermes's own Codex converter.

No agent loop or memory behavior is implemented here. OAuth credentials remain
inside this controller process; provider wire bodies and usage are archived
without authorization headers. No paid provider fallback is available.
"""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid
from urllib.parse import urlparse


def main():
    # Bootstrap can re-exec: do it before creating files or opening listeners.
    sys.path.insert(0, '/Users/javadtaghia/.hermes/hermes-agent')
    import hermes_bootstrap  # noqa: F401
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--listener-file', type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    root.relative_to(Path('/Volumes/AtMemDolphin'))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from benchmarks.dolphinbench.gateway import save_new
    from agent.auxiliary_client import _build_codex_client
    client, model = _build_codex_client('gpt-5.6-luna')
    if client is None or model != 'gpt-5.6-luna' or urlparse(str(client.base_url)).hostname != 'chatgpt.com':
        raise RuntimeError('The existing Hermes ChatGPT OAuth route is unavailable; no API fallback')
    client._real_client.max_retries = 0
    local = threading.local()

    def request_hook(request):
        if urlparse(str(request.url)).hostname != 'chatgpt.com':
            raise RuntimeError('Subscription credential cannot be sent to another host')
        save_new(local.attempt / 'provider-request.json', {'url': str(request.url),
            'body': json.loads(request.content), 'authorization_headers_saved': False})

    def response_hook(response):
        # The native Hermes converter consumes the same cached SSE bytes.
        raw = response.read()
        events = []
        for line in raw.decode(errors='strict').splitlines():
            if line.startswith('data: ') and line[6:] != '[DONE]':
                events.append(json.loads(line[6:]))
        local.events = events
        save_new(local.attempt / 'provider-response.json', {'http_status': response.status_code,
            'content_type': response.headers.get('content-type'),
            'sse_utf8': raw.decode(), 'authorization_headers_saved': False})

    client._real_client._client.event_hooks = {'request': [request_hook], 'response': [response_hook]}
    token = os.environ['ATMEM_SUBSCRIPTION_PROXY_TOKEN']
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path != '/health':
                self.send_error(404)
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ready":true,"provider":"OpenAI-Subscription"}')

        def do_POST(self):
            if self.path != '/v1/chat/completions' or not hmac.compare_digest(
                    self.headers.get('Authorization', ''), 'Bearer ' + token):
                self.send_error(403)
                return
            size = int(self.headers.get('Content-Length', '0'))
            if not 1 <= size <= 16 * 1024 * 1024:
                self.send_error(413)
                return
            body = json.loads(self.rfile.read(size))
            if body.get('model') != 'openai/gpt-5.6-luna':
                self.send_error(400)
                return
            with lock:
                directory = root / 'calls' / uuid.uuid4().hex
                save_new(directory / 'request.json', body)
                # Each attempt preserves its provider response. Only transient
                # transport/rate errors retry, never a completed model answer.
                for attempt in range(120):
                    local.attempt = directory / f'attempt-{attempt:02d}'
                    local.events = []
                    try:
                        kwargs = {k: v for k, v in body.items() if k not in {
                            'model', 'stream', 'stream_options', 'provider', 'n'}}
                        extra = dict(kwargs.pop('extra_body', {}) or {})
                        effort = kwargs.pop('reasoning_effort', 'medium') or 'medium'
                        if effort != 'medium':
                            raise ValueError('Subscription agent reasoning differs from the frozen medium configuration')
                        extra['reasoning'] = {'effort': effort}
                        result = client.chat.completions.create(model=model, **kwargs,
                            extra_body=extra, timeout=180)
                        completed = [event for event in local.events if event.get('type') == 'response.completed']
                        if not completed or completed[-1].get('response', {}).get('status') != 'completed':
                            raise RuntimeError('Missing completed provider response; do not manufacture a finalization')
                        actual_model = completed[-1]['response'].get('model', '')
                        if actual_model != model and not actual_model.startswith(model + '-20'):
                            raise RuntimeError('Actual provider model differs from the requested Luna family')
                        break
                    except Exception as exc:
                        status = getattr(exc, 'status_code', None)
                        save_new(local.attempt / 'error.json', {'error_type': type(exc).__name__,
                            'http_status': status, 'usage': None, 'paid_api_fallback': False})
                        if status not in {429, 500, 502, 503, 504} or attempt == 119:
                            self.send_error(502, 'Subscription request failed; evidence retained')
                            return
                        # Respect rate limiting; no looping completed generations.
                        delay = min(300, 15 * (2 ** min(attempt, 5)))
                        response = getattr(exc, 'response', None)
                        if response is not None:
                            try:
                                delay = max(delay, min(3600, float(response.headers.get('Retry-After', 0))))
                            except (TypeError, ValueError):
                                pass
                        print(json.dumps({'subscription_retry': attempt + 1,
                            'http_status': status, 'wait_seconds': delay}), flush=True)
                        time.sleep(delay)
                usage = result.usage
                usage = usage.model_dump() if hasattr(usage, 'model_dump') else dict(vars(usage))
                provider_usage = completed[-1]['response'].get('usage')
                if not isinstance(provider_usage, dict):
                    self.send_error(502, 'Actual provider usage missing')
                    return
                if usage.get('prompt_tokens') != provider_usage.get('input_tokens') or usage.get('completion_tokens') != provider_usage.get('output_tokens'):
                    self.send_error(502, 'Hermes and provider usage disagree')
                    return
                # Hermes's compatibility shim retains totals but drops detail
                # buckets. Restore only buckets reported in the actual wire
                # response, not estimated cache/reasoning values.
                if isinstance(provider_usage.get('input_tokens_details'), dict):
                    usage['prompt_tokens_details'] = provider_usage['input_tokens_details']
                if isinstance(provider_usage.get('output_tokens_details'), dict):
                    usage['completion_tokens_details'] = provider_usage['output_tokens_details']
                if any(type(usage.get(k)) is not int for k in ('prompt_tokens', 'completion_tokens')):
                    self.send_error(502, 'Provider token usage missing')
                    return
                usage['cost'] = 0.0
                usage['cost_basis'] = 'incremental_api_charge_zero_subscription_usage_not_free_or_unlimited'
                choice = result.choices[0]
                message = {'role': 'assistant', 'content': choice.message.content}
                if choice.message.tool_calls:
                    message['tool_calls'] = [{'id': call.id, 'type': 'function',
                        'function': {'name': call.function.name, 'arguments': call.function.arguments}}
                        for call in choice.message.tool_calls]
                payload = {'id': directory.name, 'model': body['model'], 'provider': 'OpenAI-Subscription',
                    'object': 'chat.completion', 'choices': [{'index': 0, 'message': message,
                        'finish_reason': choice.finish_reason}], 'usage': usage}
                save_new(directory / 'normalized-response.json', payload)
                save_new(directory / 'transport.json', {'provider': 'Hermes openai-codex OAuth',
                    'output_cap': 'Codex backend does not support explicit max_output_tokens; native behavior retained',
                    'wire_model': model, 'requested_output_cap': body.get('max_completion_tokens'),
                    'paid_api_fallback': False})
                if body.get('stream'):
                    payload['object'] = 'chat.completion.chunk'
                    payload['choices'][0]['delta'] = payload['choices'][0].pop('message')
                    for i, call in enumerate(payload['choices'][0]['delta'].get('tool_calls', [])):
                        call['index'] = i
                    raw = ('data: ' + json.dumps(payload) + '\n\ndata: [DONE]\n\n').encode()
                    content_type = 'text/event-stream'
                else:
                    raw, content_type = json.dumps(payload).encode(), 'application/json'
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = False
    listener = args.listener_file.resolve() if args.listener_file else root / 'listener.json'
    listener.relative_to(root)
    save_new(listener, {'endpoint': f'http://127.0.0.1:{server.server_port}/v1/chat/completions',
        'pid': os.getpid(), 'provider': 'OpenAI-Subscription', 'model': model})
    try:
        server.serve_forever()
    finally:
        server.server_close()
        client.close()


if __name__ == '__main__':
    main()
