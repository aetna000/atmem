from copy import deepcopy
import pytest
from benchmarks.code_replay.confirmation_v3_report import comparison, private_controller


def fixture():
    blocks = []; rows = []
    for slot in range(38):
        identity = f'repo{slot % 5}__project-{slot // 2}'
        blocks.append({'slot': slot, 'instance_id': identity, 'repeat': slot % 2 + 1, 'order': ['native', 'tools']})
        for arm, tokens in [('native', 100), ('tools', 75)]:
            rows.append({'slot': slot, 'instance_id': identity, 'repeat': slot % 2 + 1, 'arm': arm,
                'usage': {'input_tokens': tokens, 'cached_input_tokens': 0, 'uncached_input_tokens': tokens, 'output_tokens': 2},
                'quality': {'grade_available': True, 'task_pass': True}, 'grading': {'f2p_success': 1},
                'trace': {'code_mcp_calls': 0, 'public_test_calls': 1}, 'elapsed_ms': 1000,
                'stop_reason': None, 'source_policy_compliant': True})
    return rows, blocks


def test_matched_total_input_and_quality_do_not_claim_archive_completion():
    rows, blocks = fixture(); result = comparison(rows, blocks)
    assert result['acceptance']['twenty_percent_met']
    assert result['acceptance']['input_reduction_percent'] == '25'
    assert result['arms']['tools']['full_task_passes'] == 38
    assert result['uncertainty']['resamples'] == 10000
    assert not result['archive_verified'] and not result['goal_complete']


def test_missing_usage_never_becomes_success_only_token_total():
    rows, blocks = fixture(); rows[1]['usage'] = None
    result = comparison(rows, blocks)
    assert result['arms']['tools']['token_totals']['input_tokens'] is None
    assert not result['acceptance']['twenty_percent_met'] and result['uncertainty'] is None


def test_partial_cohort_duplicate_or_quality_regression_cannot_pass():
    rows, blocks = fixture()
    with pytest.raises(ValueError): comparison(rows[:-1], blocks)
    duplicate = deepcopy(rows); duplicate[-1] = duplicate[0]
    with pytest.raises(ValueError): comparison(duplicate, blocks)
    rows[1]['quality']['task_pass'] = False
    assert not comparison(rows, blocks)['acceptance']['twenty_percent_met']


def test_private_grade_reconstructed_from_exact_retained_bytes():
    import base64
    from hashlib import sha256
    import json
    from atmem.core.canonical import canonical_json
    raw = json.dumps({'exit_code': 1, 'reason': 'retained failure'}).encode()
    payload = {'offset': 0, 'bytes_base64': base64.b64encode(raw).decode()}
    receipt = {'object_id': 'raw', 'payload_sha256': sha256(canonical_json(payload).encode()).hexdigest()}
    event = {'object_id': 'raw', 'envelope': {'event_type': 'external.runtime_projection_chunk', 'payload': payload}}
    row = {'transport_exit': 0, 'streams': {'stdout': {'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'receipts': [receipt]}}}
    assert private_controller([event], row)['reason'] == 'retained failure'
    event['envelope']['payload']['bytes_base64'] = base64.b64encode(b'changed').decode()
    with pytest.raises(ValueError): private_controller([event], row)
