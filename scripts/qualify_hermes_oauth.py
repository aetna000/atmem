"""One bounded subscription diagnostic through Hermes's explicit Codex provider.

No benchmark data, paid API fallback, copied credentials or token output.
This is a provider diagnostic, not native-agent or submission qualification.
"""
import argparse
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlparse


def main():
    # Bootstrap may exec into managed dependencies. Do this before any writes,
    # so that a re-exec cannot collide with an already-created diagnostic root.
    sys.path.insert(0, '/Users/javadtaghia/.hermes/hermes-agent')
    import hermes_bootstrap  # noqa: F401: use the installed Hermes dependencies
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--confirm-subscription-call', action='store_true')
    args = parser.parse_args()
    if not args.confirm_subscription_call:
        parser.error('Explicit subscription-use confirmation is required')
    root = args.output.resolve()
    root.relative_to(Path('/Volumes/AtMemDolphin'))
    root.mkdir(mode=0o700)
    from agent.auxiliary_client import _build_codex_client
    from hermes_cli.auth import get_codex_auth_status
    status = get_codex_auth_status()
    if not status.get('logged_in'):
        raise RuntimeError('Existing Hermes OAuth login is unavailable; no paid fallback')
    client, model = _build_codex_client('gpt-5.6-luna')
    if client is None or model != 'gpt-5.6-luna':
        raise RuntimeError('Hermes cannot resolve the requested subscription model')
    url = urlparse(str(client.base_url))
    if url.scheme != 'https' or url.hostname != 'chatgpt.com' or not url.path.startswith('/backend-api/codex'):
        client.close()
        raise RuntimeError('Refusing a non-ChatGPT subscription endpoint')
    # Exactly one attempt. Do not retry or switch provider on quota/auth errors.
    client._real_client.max_retries = 0
    started = time.monotonic()
    try:
        response = client.chat.completions.create(model=model,
            messages=[{'role': 'user', 'content': 'Reply with exactly OAUTH_OK. Do not use tools.'}],
            reasoning_effort='medium', max_tokens=64, timeout=60)
        usage = response.usage
        if hasattr(usage, 'model_dump'):
            usage = usage.model_dump()
        elif hasattr(usage, '__dict__'):
            usage = vars(usage)
        result = {'diagnostic_only': True, 'native_agent_qualified': False,
            'submission_recording_qualified': False, 'provider': 'openai-codex',
            'endpoint': str(client.base_url), 'requested_model': model,
            'response_model': response.model,
            'response': response.choices[0].message.content,
            'usage': usage, 'elapsed_seconds': time.monotonic() - started,
            'billing_route': 'existing ChatGPT OAuth subscription',
            'paid_api_fallback': False, 'credential_material_saved': False}
        with (root / 'result.json').open('x') as output:
            json.dump(result, output, indent=2)
        print(json.dumps(result))
    except Exception as exc:
        # Exception bodies can include request details; retain only their type/status.
        result = {'diagnostic_only': True, 'success': False,
            'error_type': type(exc).__name__, 'http_status': getattr(exc, 'status_code', None),
            'paid_api_fallback': False, 'credential_material_saved': False}
        with (root / 'error.json').open('x') as output:
            json.dump(result, output)
        print(json.dumps(result))
        raise SystemExit(1) from None
    finally:
        client.close()


if __name__ == '__main__':
    main()
