from copy import deepcopy
import pytest
from tools.summarize_swebench_confirmation import combine, ARMS


def example():
    selected = [{'instance_id': str(i), 'arm_order': list(ARMS)} for i in range(5)]
    first = {'cohort': 'confirmation', 'repetition': 1, 'selected': selected, 'arms': list(ARMS), 'model': 'fixed'}
    second = {**first, 'repetition': 2, 'selected': [{**row, 'arm_order': list(reversed(row['arm_order']))} for row in selected]}
    result = {'status': 'completed', 'rows': [{'instance_id': str(i), 'arm': arm,
        'usage': {'complete': True, 'total_input_tokens': 10, 'output_tokens': 2},
        'grade_valid': True, 'resolution': 'RESOLVED_FULL', 'patch_policy': True,
        'task_pass': True, 'setup_s': 2, 'solver_s': 3, 'graph_calls': 0} for i in range(5) for arm in ARMS]}
    return [first, second], [result, deepcopy(result)]


def test_both_repeats_are_reported_as_five_clusters_not_ten_independent_tasks():
    manifests, results = example()
    report = combine(manifests, results)
    assert report['scheduled_task_clusters'] == 5 and report['repetitions'] == 2
    assert report['comparisons']['three_way']['arms']['no_memory']['paired_attempts'] == 10
    assert report['comparisons']['three_way']['arms']['no_memory']['input_tokens'] == 100


def test_unavailable_provider_does_not_change_native_pair_denominator_or_become_zero_usage():
    manifests, results = example()
    for result in results:
        row = next(r for r in result['rows'] if r['instance_id'] == '0' and r['arm'] == 'cognee_structure')
        row.update(status='product_preparation_failed', task_pass=False, grade_valid=False, usage=None, solver_s=None)
    report = combine(manifests, results)
    assert report['comparisons']['three_way']['task_clusters'] == 4
    assert report['comparisons']['native_vs_atmem']['task_clusters'] == 5
    assert report['availability']['cognee_structure']['preparation_failures'] == 2
    assert report['comparisons']['three_way']['arms']['cognee_structure']['input_tokens'] == 80


def test_changed_models_missing_cells_or_wrong_second_orders_are_not_complete():
    manifests, results = example()
    bad = deepcopy(manifests); bad[1]['model'] = 'replacement'
    with pytest.raises(ValueError, match='identity differs'):
        combine(bad, results)
    bad = deepcopy(manifests); bad[1]['selected'][0]['arm_order'] = list(ARMS)
    with pytest.raises(ValueError, match='orders differ'):
        combine(bad, results)
    bad_results = deepcopy(results); bad_results[1]['rows'].pop()
    with pytest.raises(ValueError, match='missing terminal cell'):
        combine(manifests, bad_results)
