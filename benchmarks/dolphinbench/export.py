"""Join native hook identities to exact gateway requests, including auxiliary costs.

The upstream append-only validator remains authoritative. Auxiliary calls are
retained separately, never misrepresented as conversation turns.
"""
import copy
import json
from pathlib import Path

from .recording import fingerprint


def normalize_dispatch_envelopes(messages):
    """Export modern unary dispatch in the upstream-supported unary envelope.

    Only the wrapper shape changes, not call IDs, arguments, tool results,
    model text, ordering or usage. Retain reversible originals separately.
    Native Hermes rejects multi-entry batches of these local MCP tools; leave
    those rejected requests untouched rather than inventing dispatched calls.
    """
    result = copy.deepcopy(messages)
    changes = []
    for position, message in enumerate(result):
        for index, call in enumerate(message.get('tool_calls', [])):
            arguments = call.get('arguments', {})
            if call.get('name') != 'tool_call' or set(arguments) != {'calls'}:
                continue
            entries = arguments['calls']
            if not isinstance(entries, list) or len(entries) != 1:
                continue
            entry = entries[0]
            if (not isinstance(entry, dict) or set(entry) != {'name', 'arguments'}
                    or not isinstance(entry['name'], str)
                    or not isinstance(entry['arguments'], dict)):
                continue
            changes.append({'message_position': position, 'tool_call_position': index,
                            'original': copy.deepcopy(call)})
            call['arguments'] = copy.deepcopy(entry)
    return result, {'format': 'hermes-unary-envelope-export-v1',
                    'original_messages_sha256': fingerprint(messages),
                    'exported_messages_sha256': fingerprint(result), 'changes': changes}


def assistant_response(response):
    if isinstance(response, dict):
        return response['choices'][0]['message'], response['usage']
    content, calls, usage = [], {}, None
    for event in response:
        if event.get('usage'):
            usage = event['usage']
        for choice in event.get('choices', []):
            if choice.get('index', 0) != 0:
                raise ValueError('Multiple response choices are not supported')
            delta = choice.get('delta', {})
            if delta.get('content'):
                content.append(delta['content'])
            for call in delta.get('tool_calls', []):
                target = calls.setdefault(call['index'], {'id': '', 'type': 'function',
                    'function': {'name': '', 'arguments': ''}})
                if call.get('id'):
                    target['id'] = call['id']
                for key in ('name', 'arguments'):
                    target['function'][key] += call.get('function', {}).get(key, '')
    answer = {'role': 'assistant', 'content': ''.join(content) or None}
    if calls:
        answer['tool_calls'] = [calls[i] for i in sorted(calls)]
    if usage is None:
        raise ValueError('Streaming response has no API usage')
    return answer, usage


def export_interaction(calls_root, witness_path, *, app_calls=None, default_source_paths=()):
    from harness.submission import SETTINGS_FIELDS, clean_message
    from harness.submission_capture import build_rollout, chat_messages

    witnesses = [json.loads(line) for line in Path(witness_path).read_text().splitlines()]
    pending, completed = {}, set()
    for event in witnesses:
        key = event.get('api_request_id')
        if event['event'].startswith('pre_'):
            if not key or key in pending:
                raise ValueError('Missing or duplicate native request identity')
            pending[key] = event
        elif event['event'] in {'post_api_request', 'post_auxiliary_call'}:
            if key not in pending or event.get('error_type'):
                raise ValueError('Incomplete native request lifecycle')
            completed.add(key)
        elif event['event'] == 'api_request_error':
            raise ValueError('Native API attempt failed; retain evidence for reconciliation')
    if set(pending) != completed:
        raise ValueError('Native API completion witness missing')
    unmatched = list(pending.values())
    directories = sorted(Path(calls_root).rglob('transport.json'),
        key=lambda p: json.loads(p.read_text())['started_ns'])
    events, auxiliary = [], []
    for transport in directories:
        directory = transport.parent
        request = json.loads((directory / 'request.json').read_text())
        digest = fingerprint(request['messages'])
        matches = [e for e in unmatched if e.get('messages_sha256') == digest]
        if len(matches) != 1:
            raise ValueError('Outgoing request cannot be uniquely matched to native lifecycle')
        native = matches[0]
        unmatched.remove(native)
        recorded = json.loads((directory / 'response.json').read_text())
        answer, usage = assistant_response(recorded['response'])
        if native['event'] == 'pre_auxiliary_call':
            auxiliary.append({'native': native, 'call_directory': str(directory), 'usage': usage})
            continue
        settings = {k: v for k, v in request.items() if k in SETTINGS_FIELDS and v is not None}
        message = clean_message(answer)
        message['duration_ms'] = recorded['elapsed_seconds'] * 1000
        message['usage'] = usage
        events.append({'settings': settings, 'messages': chat_messages(request['messages']),
                       'assistant': message})
    if unmatched:
        raise ValueError('Native request has no exact gateway receipt')
    result = build_rollout(events)
    result['messages'], result['dispatch_envelope_normalization'] = normalize_dispatch_envelopes(result['messages'])
    if app_calls is not None:
        from .tool_defaults import normalize_effective_arguments
        result['messages'], result['application_default_normalization'] = normalize_effective_arguments(
            result['messages'], app_calls, default_source_paths)
    result['auxiliary_calls'] = auxiliary
    return result
