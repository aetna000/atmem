from copy import deepcopy
import pytest
from benchmarks.code_replay.swebench_selection import score, rank


def example():
    manifest = {'cohort': 'validation', 'selected': [{'instance_id': str(i)} for i in range(5)]}
    result = {'status': 'completed', 'rows': [{'instance_id': str(i), 'arm': 'atmem_structure',
        'task_pass': True, 'usage': {'complete': True, 'total_input_tokens': 100},
        'setup_s': 2, 'solver_s': 3} for i in range(5)]}
    return manifest, result


def test_selection_cannot_use_confirmation_or_partial_validation():
    manifest, result = example()
    expected = {'operational_full_passes': 5, 'complete_input_tokens': 500,
                'measured_setup_plus_solver_seconds': 25}
    assert score(manifest, result) == expected
    assert rank(expected) < rank({**expected, 'operational_full_passes': 4, 'complete_input_tokens': 1})
    assert rank(expected) < rank({**expected, 'complete_input_tokens': 501})
    for m, r in [({**manifest, 'cohort': 'confirmation'}, result),
                 (manifest, {**result, 'status': 'running'}),
                 (manifest, {**result, 'rows': result['rows'][:-1]})]:
        with pytest.raises(ValueError):
            score(m, r)


def test_missing_usage_is_not_rewarded_as_zero_input():
    manifest, result = example()
    broken = deepcopy(result)
    broken['rows'][0]['usage'] = None
    measured = score(manifest, result)
    missing = score(manifest, broken)
    assert missing['complete_input_tokens'] is None
    assert rank(measured) < rank(missing)
