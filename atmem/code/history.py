"""Explicit prompt-owner integration, not a native CLI interception hook."""
from copy import deepcopy

from atmem.code.contracts import _id


def mask_observations(history, *, retain, keep_last=10):
    """Return a copy, retaining exact eligible old output before substituting it.

    The prompt owner supplies an authorized durable `retain(message)` callback
    returning a retrievable evidence ID. This helper cannot claim that arbitrary
    hosts support prompt mutation or that an output has been independently verified.
    """
    if not isinstance(history, list) or any(not isinstance(row, dict) for row in history):
        raise ValueError('history must contain message objects')
    if type(keep_last) is not int or not 1 <= keep_last <= 1000 or not callable(retain):
        raise ValueError('positive retention window and explicit evidence retainer required')
    result = deepcopy(history)
    pending, observations = set(), []
    for index, row in enumerate(result):
        if row.get('role') == 'assistant':
            for call in row.get('tool_calls', []):
                if isinstance(call, dict) and isinstance(call.get('id'), str):
                    pending.add(call['id'])
        if row.get('role') == 'tool' and row.get('tool_call_id') in pending:
            pending.remove(row['tool_call_id'])
            observations.append(index)
    masked = []
    for index in observations[:-keep_last]:
        row = result[index]
        if (row.get('retain_in_context') or row.get('unresolved_error') or row.get('is_error')
                or not isinstance(row.get('content'), str)):
            continue
        reference = retain(deepcopy(row))
        _id('retained observation', reference)
        row['content'] = '[Earlier tool output retained as ' + reference + '; fetch it if needed.]'
        masked.append({'message_index': index, 'reference': reference})
    return {'format': 'atmem-observation-mask-v1', 'messages': result, 'masked': masked,
            'native_host_qualification': False}
