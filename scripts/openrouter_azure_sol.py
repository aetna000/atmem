#!/usr/bin/env python3
"""Check Azure-hosted Sol via OpenRouter; never impersonate a direct Azure deployment."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

BASE = 'https://openrouter.ai/api/v1'
MODEL = 'openai/gpt-5.6-sol'


def load_key(path=None):
    values = {}
    if path:
        for line in Path(path).read_text().splitlines():
            match = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$', line)
            if match:
                value = match[2]
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                values[match[1]] = value
    for name in ('OPEN_ROUTER', 'OPENROUTER_API_KEY', 'OPEN_ROUTER_API_KEY'):
        if value := os.environ.get(name) or values.get(name):
            return value
    raise ValueError('Missing OPEN_ROUTER or OPENROUTER_API_KEY')


def api(path, key, body=None):
    req = urllib.request.Request(BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                 'X-Title': 'AtMem Azure Sol route qualification'})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Do not emit arbitrary upstream bodies or request headers containing secrets.
        raise RuntimeError(f'OpenRouter HTTP {exc.code}; no automatic retry or provider fallback') from None


def smoke_request():
    return {
        'model': MODEL,
        'messages': [{'role': 'user', 'content': 'Return a JSON object with exactly one property: "status": "AZURE_SOL_OK".'}],
        'reasoning_effort': 'medium',
        'max_completion_tokens': 8000,
        'response_format': {'type': 'json_object'},
        'provider': {'only': ['azure'], 'allow_fallbacks': False,
                     'require_parameters': True,
                     'max_price': {'prompt': 5, 'completion': 30}},
    }


def validate_response(response):
    if response.get('provider', '').lower() != 'azure':
        raise ValueError('Response did not identify Azure; route is not qualified')
    if response.get('model') not in {MODEL, MODEL + '-20260709', 'gpt-5.6-sol', 'gpt-5.6-sol-2026-07-09'}:
        raise ValueError('Unexpected model; route is not qualified')
    choice = response['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Response did not finish normally')
    if json.loads(choice['message']['content']) != {'status': 'AZURE_SOL_OK'}:
        raise ValueError('Unexpected smoke response')
    usage = response['usage']
    for name in ('prompt_tokens', 'completion_tokens'):
        if type(usage.get(name)) is not int or usage[name] < 0:
            raise ValueError('Missing or invalid API-reported usage')
    cost = usage.get('cost')
    if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
        raise ValueError('Missing or invalid API-reported cost')
    return usage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'smoke'))
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--confirm-paid-call', action='store_true')
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    if args.command == 'smoke':
        if not args.confirm_paid_call or not args.evidence:
            parser.error('smoke requires --confirm-paid-call and --evidence (new file)')
        if args.evidence.exists():
            parser.error('Evidence already exists; refusing to repeat a potentially paid call')
    key = load_key(args.env_file)
    api('/key', key)  # Authenticate without exposing key labels, hashes or billing details.
    endpoints = api('/models/openai/gpt-5.6-sol/endpoints', key)['data']['endpoints']
    azure = [e for e in endpoints if e.get('provider_name', '').lower() == 'azure']
    if not azure:
        raise ValueError('No Azure Sol endpoint advertised; refusing any alternative provider')
    if args.command == 'check':
        print(json.dumps({'authenticated': True, 'model': MODEL,
                          'azure_endpoints_advertised': len(azure), 'inference_calls': 0}))
        return
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    # Reserve before calling: even transport uncertainty must not trigger silent paid retries.
    fd = os.open(args.evidence, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    request = smoke_request()
    with os.fdopen(fd, 'w') as stream:
        stream.write(json.dumps({'status': 'inflight', 'request': request}) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    started = time.monotonic()
    response = api('/chat/completions', key, request)
    receipt = {'format': 'atmem-openrouter-azure-sol-smoke-v1',
               'transport': 'openrouter', 'official_dolphinbench_acceptance': 'unconfirmed',
               'request': request, 'response': response,
               'elapsed_seconds': time.monotonic() - started}
    try:
        usage = validate_response(response)
        receipt['status'] = 'passed'
    except (ValueError, KeyError, IndexError, TypeError):
        receipt['status'] = 'failed_validation'
        raise
    finally:
        encoded = json.dumps(receipt, indent=2) + '\n'
        if key in encoded:
            raise ValueError('Secret detected in evidence; refusing to save response')
        with args.evidence.open('w') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    print(json.dumps({'status': 'passed', 'transport': 'openrouter',
                      'provider': response['provider'], 'model': response['model'],
                      'usage': usage, 'elapsed_seconds': receipt['elapsed_seconds'],
                      'evidence': str(args.evidence)}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, KeyError, OSError) as exc:
        raise SystemExit(f'{type(exc).__name__}: {exc}') from None
