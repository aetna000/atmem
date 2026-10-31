"""Join native hook identities to exact gateway requests, including auxiliary costs.

The upstream append-only validator remains authoritative. Auxiliary calls are
retained separately, never misrepresented as conversation turns.
"""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3

from .recording import fingerprint


# Audited legacy controller: request/transport are saved before reserve(); a
# durable reservation always precedes network I/O and is never deleted. This
# proof cannot be applied to arbitrary controllers just because a row is absent.
LEGACY_GUARD_SOURCE_SHA256 = '2139a2eae0df366bf04b07299f92c6e99185381d3a400754633b7914feaa8355'
UNSENT_GUARD_ERROR = 'HTTP 402: Campaign budget guard stopped this request before forwarding'


def prove_unforwarded_guard(directory, request, *, pending, failed, terminal_failure,
                            ledger_path, campaign_identity, original_gateway_source):
    """Read-only proof for a retained local rejection, not a failed generation."""
    directory = Path(directory)
    if (not terminal_failure or terminal_failure.get('exit_code') != 1
            or terminal_failure.get('error') != UNSENT_GUARD_ERROR
            or UNSENT_GUARD_ERROR not in terminal_failure.get('text', '')
            or request.get('model') not in {'openai/gpt-5.6-sol', 'openai/gpt-5.6-luna'}
            or 'provider' in request):
        raise ValueError('Exact local subscription guard failure required')
    if hashlib.sha256(Path(original_gateway_source).read_bytes()).hexdigest() != LEGACY_GUARD_SOURCE_SHA256:
        raise ValueError('Original controller control flow is not qualified')
    if any((directory / name).exists() for name in ('response.json', 'error.json', 'subscription-failure.json')):
        raise ValueError('Potential forwarded request cannot use unsent proof')
    transport = json.loads((directory / 'transport.json').read_text())
    if transport.get('call_id') != directory.name or transport.get('phase') != 'tests':
        raise ValueError('Original call identity mismatch')
    matches = [key for key in failed if pending[key].get('event') == 'pre_api_request'
               and pending[key].get('messages_sha256') == fingerprint(request['messages'])]
    if len(matches) != 1:
        raise ValueError('Unique native failure witness required')
    with sqlite3.connect(Path(ledger_path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.execute('BEGIN')
        campaign = db.execute('SELECT identity FROM campaign WHERE singleton=1').fetchone()
        row = db.execute('SELECT state FROM calls WHERE call_id=?', (directory.name,)).fetchone()
        if campaign != (fingerprint(campaign_identity),) or row is not None:
            raise ValueError('Unchanged original ledger must prove no reservation or forwarding')
    return {'basis': 'qualified_legacy_local_guard_before_reservation_and_forwarding',
        'native_request_id': matches[0], 'request_sha256': fingerprint(request),
        'original_gateway_sha256': LEGACY_GUARD_SOURCE_SHA256,
        'original_ledger': str(Path(ledger_path).resolve()),
        'campaign_identity_sha256': fingerprint(campaign_identity),
        'provider_request_sent': False, 'incremental_api_charge_usd': 0,
        'model_or_tool_replay': False}


def _observed_arguments(call, raw, parsed, messages):
    """Use an actual subsequent native request, never the recorder's preference.

    Conflicting JSON is not independently exportable. A native host can already
    have decoded and executed it, however. Require its uniquely identified,
    duplicate-free assistant history and following tool-result witness. The
    complete rollout is still checked by upstream's append-only validator.
    """
    if not isinstance(messages, list) or not isinstance(call.get('id'), str):
        raise ValueError('Conflicting duplicate model argument keys cannot be normalized')
    matches = [(position, item, candidate)
               for position, item in enumerate(messages) if item.get('role') == 'assistant'
               for candidate in item.get('tool_calls', []) if candidate.get('id') == call['id']]
    if len(matches) != 1:
        raise ValueError('Conflicting arguments require one exact native history witness')
    position, message, observed = matches[0]
    function = observed.get('function', {})
    if function.get('name') != call.get('function', {}).get('name'):
        raise ValueError('Native argument witness changed function identity')
    witnessed = function.get('arguments')
    if not isinstance(witnessed, str):
        raise ValueError('Native argument witness must retain serialized arguments')

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Native argument witness still has duplicate keys')
            value[key] = item
        return value

    effective = json.loads(witnessed, object_pairs_hook=unique_pairs)
    if not isinstance(effective, dict) or fingerprint(effective) != fingerprint(parsed):
        raise ValueError('Native argument witness disagrees with observed JSON decoding')
    if not any(item.get('role') == 'tool' and item.get('tool_call_id') == call['id']
               for item in messages[position + 1:]):
        raise ValueError('Native argument witness lacks a subsequent tool result')
    return witnessed, {'basis': 'exact_next_native_request_with_tool_result',
        'call_id': call['id'], 'original_arguments': raw,
        'observed_native_arguments': witnessed,
        'witness_message_sha256': fingerprint(message),
        'next_request_messages_sha256': fingerprint(messages),
        'model_or_tool_replay': False, 'semantic_repair': False}


def normalize_identical_argument_keys(answer, *, observed_next_messages=None):
    """Collapse only identical repeated JSON keys, retaining exact wire strings.

    Native JSON decoding already coalesces these. Conflicting values require
    independently recorded effective native arguments; absent that witness they
    remain an error. This does not repair missing/invalid arguments.
    """
    result, changes = copy.deepcopy(answer), []
    for position, call in enumerate(result.get('tool_calls', [])):
        function = call.get('function', {})
        raw = function.get('arguments')
        if not isinstance(raw, str):
            continue
        duplicates, conflicts = [], []

        def identical_pairs(pairs):
            values = {}
            for key, value in pairs:
                if key in values:
                    if fingerprint(values[key]) != fingerprint(value):
                        conflicts.append(key)
                    else:
                        duplicates.append(key)
                values[key] = value
            return values

        parsed = json.loads(raw, object_pairs_hook=identical_pairs)
        if conflicts:
            witnessed, receipt = _observed_arguments(call, raw, parsed, observed_next_messages)
            function['arguments'] = witnessed
            changes.append({'tool_call_position': position,
                'conflicting_duplicate_keys': conflicts,
                'identical_duplicate_keys': duplicates, **receipt})
        elif duplicates:
            function['arguments'] = json.dumps(parsed, ensure_ascii=False, allow_nan=False)
            changes.append({'tool_call_position': position, 'original_arguments': raw,
                'identical_duplicate_keys': duplicates, 'normalized_arguments': function['arguments']})
    return result, changes


def normalize_witnessed_duplicate_inspections(answer, request_messages, next_messages):
    """Represent host-suppressed duplicate reads only when the next request proves them.

    The original model response remains in the gateway evidence. This changes
    neither executed tool results nor an application action, and never guesses
    what an absent or contradictory next request might have contained.
    """
    from harness.submission import clean_message
    from harness.submission_capture import _plain, chat_messages

    if not isinstance(next_messages, list):
        return copy.deepcopy(answer), []
    prior = chat_messages(request_messages)
    following = chat_messages(next_messages)
    position = len(prior)
    if (len(following) <= position or
            [_plain(m) for m in following[:position]] != [_plain(m) for m in prior]):
        return copy.deepcopy(answer), []
    observed = following[position]
    original = clean_message(answer)
    original_calls = original.get('tool_calls', [])
    observed_calls = observed.get('tool_calls', [])
    if observed.get('role') != 'assistant' or not original_calls or not observed_calls:
        return copy.deepcopy(answer), []
    old_ids = [call.get('id') for call in original_calls]
    kept_ids = [call.get('id') for call in observed_calls]
    if (any(not isinstance(i, str) or not i for i in old_ids + kept_ids)
            or len(set(old_ids)) != len(old_ids) or len(set(kept_ids)) != len(kept_ids)
            or not set(kept_ids) < set(old_ids)):
        return copy.deepcopy(answer), []
    kept = [call for call in original_calls if call['id'] in set(kept_ids)]
    if kept != observed_calls:
        return copy.deepcopy(answer), []
    dropped = [call for call in original_calls if call['id'] not in set(kept_ids)]
    for call in dropped:
        matches = [item for item in kept if item['name'] == call['name']
                   and fingerprint(item['arguments']) == fingerprint(call['arguments'])]
        if (call.get('name') != 'mcp__atmem_discovery__memory_inspect'
                or len(matches) != 1 or old_ids.index(matches[0]['id']) >= old_ids.index(call['id'])):
            return copy.deepcopy(answer), []
    candidate = copy.deepcopy(answer)
    candidate['tool_calls'] = [call for call in candidate['tool_calls'] if call['id'] in set(kept_ids)]
    if _plain(clean_message(candidate)) != _plain(observed):
        return copy.deepcopy(answer), []
    results = following[position + 1:]
    if (len(results) != len(kept_ids)
            or any(item.get('role') != 'tool' for item in results)
            or [item.get('tool_call_id') for item in results] != kept_ids):
        return copy.deepcopy(answer), []
    return candidate, [{'basis': 'next_native_request_with_matching_read_results',
        'original_response_sha256': fingerprint(answer),
        'next_request_messages_sha256': fingerprint(next_messages),
        'suppressed_calls': copy.deepcopy(dropped),
        'retained_call_ids': kept_ids, 'model_or_tool_replay': False}]


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


def witnessed_sdk_retry(request, later_successes, pending, completed, error):
    """Reconcile transport framing, never choose among generated responses."""
    if type(error.get('http_status')) is not int or error['http_status'] not in {429,500,502,503,504}:
        return None
    framing={'stream','stream_options'}
    def semantic(value):
        if 'stream' in value and type(value['stream']) is not bool:return None
        options=value.get('stream_options')
        if options is not None and (not isinstance(options,dict)
                or set(options)!={'include_usage'} or options['include_usage'] is not True):return None
        return fingerprint({k:v for k,v in value.items() if k not in framing})
    identity=semantic(request)
    if identity is None:return None
    message_digest=fingerprint(request['messages'])
    witnesses=[(key,event) for key,event in pending.items() if key in completed
        and event.get('event')=='pre_api_request' and event.get('messages_sha256')==message_digest]
    matches=[(path,value) for path,value in later_successes if semantic(value)==identity]
    if len(witnesses)!=1 or len(matches)!=1:return None
    path,value=matches[0]
    return {'basis':'unique_completed_native_lifecycle_and_semantically_identical_sdk_retry',
        'native_request_id':witnesses[0][0],'successful_call_directory':str(path),
        'semantic_request_sha256':identity,'messages_sha256':message_digest,
        'framing_changes':{k:{'failed':request.get(k),'successful':value.get(k)} for k in framing
                           if request.get(k)!=value.get(k)},
        'model_or_tool_replay':False,'usage_of_failed_attempt':None}


def export_interaction(calls_root, witness_path, *, app_calls=None, default_source_paths=(), terminal_failure=None,
                       unforwarded_guard=None):
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
    events, auxiliary, failed_attempts, argument_keys, duplicate_inspections = [], [], [], [], []
    requests = [json.loads((p.parent / 'request.json').read_text()) for p in directories]
    for directory_index, transport in enumerate(directories):
        directory = transport.parent
        request = requests[directory_index]
        digest = fingerprint(request['messages'])
        if not (directory / 'response.json').exists():
            error_path=directory/'error.json'
            native_failure=any(pending[k].get('messages_sha256')==digest for k in failed)
            unsent = (prove_unforwarded_guard(directory, request, pending=pending, failed=failed,
                terminal_failure=terminal_failure, **unforwarded_guard)
                if unforwarded_guard is not None and not error_path.exists() else None)
            retry=(witnessed_sdk_retry(request,
                [(p.parent,requests[i]) for i,p in enumerate(directories)
                    if i>directory_index and (p.parent/'response.json').exists()],
                pending,completed,json.loads(error_path.read_text())) if error_path.exists() else None)
            if unsent is None and (not error_path.exists() or (not native_failure and retry is None)):
                raise ValueError('Unreconciled missing gateway response')
            failed_attempts.append({'call_directory': str(directory),
                'messages_sha256': digest,
                'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'cost': 0} if unsent else None,
                'response_delivered': False,
                'request_messages': chat_messages(request['messages']),
                'failure_witness':unsent or ({'basis':'native_api_request_error'} if native_failure else retry)})
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
        # Only actual native primary-request history can witness host decoding.
        # Auxiliary calls, invented messages and replayed actions are not evidence.
        next_messages = None
        for following in requests[directory_index + 1:]:
            following_digest = fingerprint(following['messages'])
            witnesses = [e for e in pending.values()
                         if e['event'] == 'pre_api_request'
                         and e.get('messages_sha256') == following_digest]
            if len(witnesses) == 1:
                next_messages = following['messages']
                break
        answer, keys = normalize_identical_argument_keys(answer,
            observed_next_messages=next_messages)
        if keys:
            argument_keys.append({'call_directory': str(directory), 'changes': keys})
        answer, suppressed = normalize_witnessed_duplicate_inspections(
            answer, request['messages'], next_messages)
        if suppressed:
            duplicate_inspections.append({'call_directory': str(directory), 'changes': suppressed})
        message = clean_message(answer)
        message['duration_ms'] = recorded['elapsed_seconds'] * 1000
        message['usage'] = usage
        events.append({'settings': settings, 'messages': chat_messages(request['messages']),
                       'assistant': message})
    if unmatched:
        raise ValueError('Native request has no exact gateway receipt')
    result = build_rollout(events)
    result['witnessed_duplicate_inspection_suppression'] = duplicate_inspections
    result['identical_argument_key_normalization'] = [
        {'call_directory': entry['call_directory'],
         'changes': [c for c in entry['changes'] if 'conflicting_duplicate_keys' not in c]}
        for entry in argument_keys
        if any('conflicting_duplicate_keys' not in c for c in entry['changes'])]
    result['witnessed_conflicting_argument_key_normalization'] = [
        {'call_directory': entry['call_directory'],
         'changes': [c for c in entry['changes'] if 'conflicting_duplicate_keys' in c]}
        for entry in argument_keys
        if any('conflicting_duplicate_keys' in c for c in entry['changes'])]
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
        all_unsent = all(a['failure_witness'].get('provider_request_sent') is False for a in failed_attempts)
        result['messages'].append({'role': 'assistant', 'content': terminal_failure['text'],
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0} if all_unsent
                     else {'input_tokens': 0, 'output_tokens': 0}})
        result['native_terminal_failure'] = {'native_result': terminal_failure,
            'terminal_message_origin': 'verbatim native CLI error, not a model completion',
            'terminal_message_tokens': 'zero model tokens for runtime-generated error only',
            'failed_provider_usage': ('proven zero: rejected before provider forwarding' if all_unsent
                                      else 'unknown, excluded from reported token lower bounds'),
            'failed_attempts': [{k: v for k, v in a.items() if k != 'request_messages'} for a in failed_attempts],
            'model_or_tool_replay': False}
    result['messages'], result['dispatch_envelope_normalization'] = normalize_dispatch_envelopes(result['messages'])
    if app_calls is not None:
        from .tool_defaults import normalize_effective_arguments
        result['messages'], result['application_default_normalization'] = normalize_effective_arguments(
            result['messages'], app_calls, default_source_paths)
    result['auxiliary_calls'] = auxiliary
    return result
