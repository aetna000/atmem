"""Join native hook identities to exact gateway requests, including auxiliary costs.

The upstream append-only validator remains authoritative. Auxiliary calls are
retained separately, never misrepresented as conversation turns.
"""
import copy
import json
from pathlib import Path

from .recording import fingerprint


def normalize_identical_argument_keys(answer):
    """Collapse only identical repeated JSON keys, retaining exact wire strings.

    Native JSON decoding already coalesces these. Conflicting values must never
    be selected by this recorder. This does not repair missing/invalid arguments.
    """
    result, changes = copy.deepcopy(answer), []
    for position, call in enumerate(result.get('tool_calls', [])):
        function = call.get('function', {})
        raw = function.get('arguments')
        if not isinstance(raw, str):
            continue
        duplicates = []

        def identical_pairs(pairs):
            values = {}
            for key, value in pairs:
                if key in values:
                    if fingerprint(values[key]) != fingerprint(value):
                        raise ValueError('Conflicting duplicate model argument keys cannot be normalized')
                    duplicates.append(key)
                values[key] = value
            return values

        parsed = json.loads(raw, object_pairs_hook=identical_pairs)
        if duplicates:
            function['arguments'] = json.dumps(parsed, ensure_ascii=False, allow_nan=False)
            changes.append({'tool_call_position': position, 'original_arguments': raw,
                'identical_duplicate_keys': duplicates, 'normalized_arguments': function['arguments']})
    return result, changes


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


def export_interaction(calls_root, witness_path, *, app_calls=None, default_source_paths=(), terminal_failure=None):
    from harness.submission import SETTINGS_FIELDS, clean_message
    from harness.submission_capture import build_rollout, chat_messages

    witnesses = [json.loads(line) for line in Path(witness_path).read_text().splitlines()]
    pending, completed, failed = {}, set(), set()
    for event in witnesses:
        key = event.get('api_request_id')
        if event['event'].startswith('pre_'):
            if (key in failed and key not in completed and pending.get(key) == event):
                continue  # Native retry reuses its request identity, identical input.
            if not key or key in pending:
                raise ValueError('Missing or duplicate native request identity')
            pending[key] = event
        elif event['event'] in {'post_api_request', 'post_auxiliary_call'}:
            if key not in pending or event.get('error_type'):
                raise ValueError('Incomplete native request lifecycle')
            completed.add(key)
        elif event['event'] == 'api_request_error':
            if key not in pending or key in completed:
                raise ValueError('Unmatched native API failure')
            failed.add(key)
    if failed - completed and terminal_failure is None:
        raise ValueError('Native API attempt failed; retain evidence for reconciliation')
    if set(pending) != completed | failed:
        raise ValueError('Native API completion witness missing')
    unmatched = [e for key, e in pending.items() if key in completed]
    directories = sorted(Path(calls_root).rglob('transport.json'),
        key=lambda p: json.loads(p.read_text())['started_ns'])
    events, auxiliary, failed_attempts, argument_keys = [], [], [], []
    for transport in directories:
        directory = transport.parent
        request = json.loads((directory / 'request.json').read_text())
        digest = fingerprint(request['messages'])
        if not (directory / 'response.json').exists():
            if (not (directory / 'error.json').exists()
                    or not any(pending[k].get('messages_sha256') == digest for k in failed)):
                raise ValueError('Unreconciled missing gateway response')
            failed_attempts.append({'call_directory': str(directory),
                'messages_sha256': digest, 'usage': None,
                'response_delivered': False,
                'request_messages': chat_messages(request['messages'])})
            continue
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
        answer, keys = normalize_identical_argument_keys(answer)
        if keys:
            argument_keys.append({'call_directory': str(directory), 'changes': keys})
        message = clean_message(answer)
        message['duration_ms'] = recorded['elapsed_seconds'] * 1000
        message['usage'] = usage
        events.append({'settings': settings, 'messages': chat_messages(request['messages']),
                       'assistant': message})
    if unmatched:
        raise ValueError('Native request has no exact gateway receipt')
    result = build_rollout(events)
    result['identical_argument_key_normalization'] = argument_keys
    result['failed_transport_attempts'] = [{k: v for k, v in a.items() if k != 'request_messages'}
        for a in failed_attempts]
    if terminal_failure is not None:
        # The CLI's actual terminal error is runtime output, NOT model text.
        # Preserve tool results from the exact next request; no model/tool replay.
        from harness.submission_capture import _plain
        if not failed_attempts or not terminal_failure.get('error') or terminal_failure.get('exit_code') != 1:
            raise ValueError('Native terminal failure proof missing')
        tail = failed_attempts[0]['request_messages']
        if (len(tail) < len(result['messages']) or
                [_plain(m) for m in tail[:len(result['messages'])]] != [_plain(m) for m in result['messages']] or
                any(m['role'] != 'tool' for m in tail[len(result['messages']):]) or
                any(a['request_messages'] != tail for a in failed_attempts)):
            raise ValueError('Failed attempts changed conversation state')
        result['messages'].extend(copy.deepcopy(tail[len(result['messages']):]))
        result['messages'].append({'role': 'assistant', 'content': terminal_failure['text'],
            'usage': {'input_tokens': 0, 'output_tokens': 0}})
        result['native_terminal_failure'] = {'native_result': terminal_failure,
            'terminal_message_origin': 'verbatim native CLI error, not a model completion',
            'terminal_message_tokens': 'zero model tokens for runtime-generated error only',
            'failed_provider_usage': 'unknown, excluded from reported token lower bounds',
            'failed_attempts': [{k: v for k, v in a.items() if k != 'request_messages'} for a in failed_attempts],
            'model_or_tool_replay': False}
    result['messages'], result['dispatch_envelope_normalization'] = normalize_dispatch_envelopes(result['messages'])
    if app_calls is not None:
        from .tool_defaults import normalize_effective_arguments
        result['messages'], result['application_default_normalization'] = normalize_effective_arguments(
            result['messages'], app_calls, default_source_paths)
    result['auxiliary_calls'] = auxiliary
    return result
