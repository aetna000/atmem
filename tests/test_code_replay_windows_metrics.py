from decimal import Decimal
import base64
from hashlib import sha256
import pytest
from atmem.core.canonical import canonical_json

from benchmarks.code_replay.windows_metrics import acceptance, reduction, usage, quality, recover_stream


def test_stream_recovery_follows_receipts_not_matching_cell_labels():
    raw = b'full transport\x00bytes'
    payload = {'offset': 0, 'total_bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
        'content_base64': base64.b64encode(raw).decode()}
    expected = {'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'receipts': [
        {'object_id': 'success', 'payload_sha256': sha256(canonical_json(payload).encode()).hexdigest()}]}
    events = {'success': {'envelope': {'payload': payload}},
        'earlier_failure_same_cell': {'envelope': {'payload': {**payload, 'content_base64': 'YmFk'}}}}
    assert recover_stream(events, expected) == raw
    with pytest.raises(ValueError, match='length or digest'):
        recover_stream(events, {**expected, 'receipts': []})


def test_only_complete_normal_usage_is_known_and_cache_is_not_added_twice():
    value = {'exit_code': 0, 'stop_reason': None, 'usage_receipts': [{'usage': {
        'input_tokens': 100, 'cached_input_tokens': 80, 'output_tokens': 10}}]}
    assert usage(value)['input_tokens'] == 100
    assert usage(value)['uncached_input_tokens'] == 20
    assert usage({**value, 'stop_reason': 'tool_budget'}) is None
    assert usage({**value, 'usage_receipts': []}) is None
    assert usage({**value, 'usage_receipts': value['usage_receipts'] * 2}) is None


def test_exact_threshold_never_rounds_a_near_miss_to_acceptance():
    assert reduction(1126556, 906298) < Decimal(20)
    assert reduction(None, 1) is None


def test_missing_receipt_or_quality_regression_blocks_primary_acceptance():
    rows = [{'slot': 0, 'repeat': 1, 'arm': arm, 'usage': {'input_tokens': tokens},
        'quality': {'grade_available': True, 'task_pass': True}} for arm, tokens in [('native', 100), ('pack', 50)]]
    assert acceptance(rows, 'pack', required_pairs=1)['fifty_percent_met']
    assert not acceptance(rows, 'pack', required_pairs=1)['goal_complete']
    rows[1]['usage'] = None
    assert not acceptance(rows, 'pack', required_pairs=1)['twenty_percent_met']
    rows[1]['usage'] = {'input_tokens': 50}; rows[1]['quality']['task_pass'] = False
    assert not acceptance(rows, 'pack', required_pairs=1)['twenty_percent_met']


def test_controller_success_is_not_a_test_or_authority_pass():
    assert not quality({'transport_exit_code': 0, 'controller': {'exit_code': 0}},
        source_policy_compliant=True, expected_f2p=1, expected_p2p=31)['task_pass']
