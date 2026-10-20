from copy import deepcopy

import pytest

from benchmarks.code_replay.windows_uncertainty import paired_uncertainty


def rows():
    result = []
    for slot, identity in enumerate(('one__repo-1', 'two__repo-2')):
        for arm, tokens in (('native', 100), ('tools', 80)):
            result.append({'arm': arm, 'slot': slot, 'repeat': 1, 'instance_id': identity,
                'usage': {'input_tokens': tokens}, 'quality': {'grade_available': True, 'task_pass': True}})
    return result


def test_cluster_sampling_is_fixed_and_preserves_complete_equal_pairs():
    original = rows()
    result = paired_uncertainty(original, candidate_arm='tools', required_pairs=2, resamples=100)
    assert result == paired_uncertainty(list(reversed(original)), candidate_arm='tools', required_pairs=2, resamples=100)
    assert result['point']['input_reduction_percent'] == 20
    assert result['point']['candidate_task_passes'] == 2
    assert result['clustered']['issue']['input_reduction_percent_interval_95'] == [20, 20]
    assert result['clustered']['repository']['degenerate_task_pass_interval']


def test_missing_usage_unknown_grade_or_dropped_cell_cannot_be_bootstrapped():
    original = rows()
    with pytest.raises(ValueError, match='complete paired'):
        paired_uncertainty(original[:-1], candidate_arm='tools', required_pairs=2, resamples=100)
    unknown = deepcopy(original); unknown[0]['usage'] = None
    with pytest.raises(ValueError, match='complete usage'):
        paired_uncertainty(unknown, candidate_arm='tools', required_pairs=2, resamples=100)
    unknown = deepcopy(original); unknown[0]['quality']['grade_available'] = False
    with pytest.raises(ValueError, match='private grade'):
        paired_uncertainty(unknown, candidate_arm='tools', required_pairs=2, resamples=100)
    with pytest.raises(ValueError, match='distinct'):
        paired_uncertainty(original, candidate_arm='native', required_pairs=2, resamples=100)
