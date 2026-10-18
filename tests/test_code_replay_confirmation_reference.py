from copy import deepcopy

from benchmarks.code_replay.windows_confirmation_reference import strict_reference_qualified
from benchmarks.code_replay.windows_confirmation_reference import verified_material_cache
from benchmarks.code_replay.external_catalog import digest
import pytest


def pair():
    common = {'reason': None, 'exit_code': 0, 'worker': {
        'worker_failure': None, 'base_source_verified': True, 'embedded_test_patch_verified': True,
        'grading': {'expected_f2p': 2, 'expected_p2p': 3, 'results_found': True,
            'p2p_skipped': 0, 'p2p_failure': 0, 'p2p_success': 3}}}
    a, b = deepcopy(common), deepcopy(common)
    a['worker']['grading'].update(observed_f2p_failures=2, f2p_failure=2, f2p_success=0)
    b['worker']['grading'].update(f2p_success=2, f2p_failure=0, resolution='RESOLVED_FULL')
    return a, b


def test_parent_requires_every_declared_target_observed_failing_not_missing():
    a, b = pair()
    assert strict_reference_qualified(a, b)
    a['worker']['grading']['observed_f2p_failures'] = 1
    assert not strict_reference_qualified(a, b)


def test_regressions_source_binding_and_missing_controller_fail_closed():
    for field, value in [('p2p_skipped', 1), ('p2p_failure', 1), ('p2p_success', 2)]:
        a, b = pair(); b['worker']['grading'][field] = value
        assert not strict_reference_qualified(a, b)
    a, b = pair(); b['worker']['base_source_verified'] = False
    assert not strict_reference_qualified(a, b)
    assert not strict_reference_qualified({}, {})


def test_material_cache_is_complete_bound_and_never_silently_refetched():
    def event(kind, payload):
        return {'envelope': {'event_type': kind, 'payload': payload}}
    row = {'instance_id': 'fixture-1', 'verified': True, 'material': {'full': 'bytes'}}
    row['material_sha256'] = digest(row['material'])
    complete = event('external.eligibility_materials_completed', {'worker_sha256': 'a' * 64, 'material_records': 1})
    result = event('external.eligibility_material_result', row)
    assert verified_material_cache([], 'a' * 64) is None
    with pytest.raises(ValueError, match='live'):
        verified_material_cache([result], 'a' * 64)
    assert verified_material_cache([result, complete], 'a' * 64)['fixture-1'] == row
    with pytest.raises(ValueError, match='registration'):
        verified_material_cache([result, complete], 'b' * 64)
    with pytest.raises(ValueError, match='duplicate'):
        verified_material_cache([result, result, complete], 'a' * 64)
    bad = deepcopy(result); bad['envelope']['payload']['material']['full'] = 'changed'
    with pytest.raises(ValueError, match='digest'):
        verified_material_cache([bad, complete], 'a' * 64)
