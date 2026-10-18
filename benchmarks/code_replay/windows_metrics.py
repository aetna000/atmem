"""Conservative cohort counters; no missing-value imputation or score invention."""
import base64
from collections import Counter
from decimal import Decimal
from hashlib import sha256

from atmem.core.canonical import canonical_json


def recover_stream(by_object_id, expected):
    """Follow exact receipts, including when a pre-inference failure shares a cell."""
    chunks, offset = [], 0
    for receipt in expected['receipts']:
        event = by_object_id[receipt['object_id']]
        payload = event['envelope']['payload']
        if sha256(canonical_json(payload).encode()).hexdigest() != receipt['payload_sha256']:
            raise ValueError('chunk receipt payload identity differs')
        if payload['offset'] != offset or payload['total_bytes'] != expected['bytes'] or payload['sha256'] != expected['sha256']:
            raise ValueError('stream chunk sequence or identity differs')
        raw = base64.b64decode(payload['content_base64'], validate=True)
        chunks.append(raw); offset += len(raw)
    raw = b''.join(chunks)
    if len(raw) != expected['bytes'] or sha256(raw).hexdigest() != expected['sha256']:
        raise ValueError('full stream byte length or digest differs')
    return raw


def trace_summary(events):
    items = {}
    for event in events:
        item = event.get('item', {})
        if event.get('type') == 'item.completed' and isinstance(item.get('id'), str):
            if item['id'] in items and items[item['id']] != item:
                raise ValueError('conflicting repeated completed CLI item')
            items[item['id']] = item
    commands = [i for i in items.values() if i.get('type') == 'command_execution']
    mcp = [i for i in items.values() if i.get('type') == 'mcp_tool_call']
    return {'native_commands': len(commands),
        'native_command_output_bytes': sum(len(i['aggregated_output'].encode()) for i in commands if isinstance(i.get('aggregated_output'), str)),
        'code_mcp_calls': sum(i.get('server') == 'atmem_code' for i in mcp),
        'public_test_calls': sum(i.get('server') == 'benchmark_public_tests' for i in mcp),
        'completed_item_types': dict(Counter(i.get('type') for i in items.values())),
        'assurance': 'completed CLI items, not proof of attention, source authority or causal token attribution'}


def usage(model):
    receipts = model.get('usage_receipts', [])
    if len(receipts) != 1 or model.get('stop_reason') is not None or model.get('exit_code') != 0:
        return None
    values = receipts[0].get('usage', {})
    names = ('input_tokens', 'cached_input_tokens', 'output_tokens')
    if any(type(values.get(name)) is not int or values[name] < 0 for name in names):
        return None
    if values['cached_input_tokens'] > values['input_tokens']:
        return None
    return {**{name: values[name] for name in names},
        'uncached_input_tokens': values['input_tokens'] - values['cached_input_tokens']}


def quality(grade, *, source_policy_compliant, expected_f2p, expected_p2p):
    controller = grade.get('controller', {})
    worker = controller.get('worker', {})
    marks = worker.get('grading', {})
    available = (grade.get('transport_exit_code') == 0 and controller.get('exit_code') == 0
        and not controller.get('reason') and not worker.get('worker_failure')
        and marks.get('results_found') is True
        and marks.get('expected_f2p') == expected_f2p and marks.get('expected_p2p') == expected_p2p)
    tests_pass = bool(available and marks.get('f2p_success') == expected_f2p
        and marks.get('f2p_failure') == 0 and marks.get('p2p_success') == expected_p2p
        and marks.get('p2p_failure') == 0 and marks.get('p2p_skipped') == 0
        and marks.get('resolution') == 'RESOLVED_FULL')
    authority = bool(source_policy_compliant and worker.get('base_source_verified') is True
        and worker.get('public_base_verified') is True and worker.get('assembled_bytes_verified') is True
        and worker.get('image_only_bytes_preserved') is True and worker.get('gold_patch_written') is False
        and not worker.get('out_of_scope_changes'))
    return {'grade_available': bool(available), 'tests_pass': tests_pass,
        'source_authority_pass': authority, 'task_pass': tests_pass and authority}


def reduction(native, candidate):
    if native is None or candidate is None or native <= 0:
        return None
    return (Decimal(native) - Decimal(candidate)) * 100 / Decimal(native)


def acceptance(rows, arm, *, required_pairs=10):
    """Primary totals use the identical complete eligible task/repeat cells."""
    native = {(r['slot'], r['repeat']): r for r in rows if r['arm'] == 'native'}
    candidate = {(r['slot'], r['repeat']): r for r in rows if r['arm'] == arm}
    no_duplicates = sum(r['arm'] == 'native' for r in rows) == len(native) and sum(r['arm'] == arm for r in rows) == len(candidate)
    complete = (no_duplicates and len(native) == len(candidate) == required_pairs and native.keys() == candidate.keys()
        and all(r.get('usage') is not None for r in [*native.values(), *candidate.values()]))
    grade_complete = (no_duplicates and len(native) == len(candidate) == required_pairs and native.keys() == candidate.keys()
        and all(r.get('quality', {}).get('grade_available') is True for r in [*native.values(), *candidate.values()]))
    native_pass = sum(bool(r.get('quality', {}).get('task_pass')) for r in native.values())
    candidate_pass = sum(bool(r.get('quality', {}).get('task_pass')) for r in candidate.values())
    saving = reduction(sum(r['usage']['input_tokens'] for r in native.values()),
        sum(r['usage']['input_tokens'] for r in candidate.values())) if complete else None
    quality_met = grade_complete and candidate_pass >= native_pass
    return {'arm': arm, 'complete_paired_usage': complete, 'complete_grading': grade_complete,
        'native_task_passes': native_pass, 'candidate_task_passes': candidate_pass,
        'input_reduction_percent': str(saving) if saving is not None else None,
        'quality_met': quality_met, 'fifty_percent_met': bool(quality_met and saving is not None and saving >= 50),
        'twenty_percent_met': bool(quality_met and saving is not None and saving >= 20),
        'confirmation_required': True, 'goal_complete': False}
