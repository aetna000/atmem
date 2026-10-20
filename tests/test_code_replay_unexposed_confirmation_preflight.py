import pytest

from benchmarks.code_replay import unexposed_confirmation_preflight as preflight


def tree():
    return {'sha': preflight.catalog.TASK_TREE, 'truncated': False,
            'tree': [{'path': repo.replace('/', '__')+'-'+str(i), 'type': 'tree', 'sha': format(i+1, '040x')}
                     for repo in preflight.EXCLUDED+preflight.REPOSITORIES for i in range(10)]}


def test_all_remaining_groups_are_frozen_without_outcome_selection():
    value = preflight.selection(tree())
    reversed_tree = tree(); reversed_tree['tree'].reverse()
    assert value == preflight.selection(reversed_tree)
    assert len(value['selected']) == 40
    assert value['per_repo'] == 8
    assert value['final_model_tasks_per_repository'] == 4
    assert set(r['repo'] for r in value['selected']).isdisjoint(preflight.EXCLUDED)
    assert value['content_paths_permitted'] == ['Dockerfile', 'task.yaml']
    assert value['solver_calls'] == 0
    for repo in preflight.REPOSITORIES:
        assert [r['instance_id'] for r in value['selected'] if r['repo'] == repo] == value['ordered_candidate_pools'][repo][:8]


def test_missing_catalog_groups_cannot_be_silently_replaced():
    changed = tree(); changed['tree'] = [r for r in changed['tree'] if not r['path'].startswith('sympy__sympy-')]
    with pytest.raises(ValueError):
        preflight.selection(changed)


def test_metadata_refuses_other_content_without_fetching_gold():
    item = {'instance_id': 'repo__repo-1', 'task_tree': '0'*40}
    calls = []
    def fetch(path):
        calls.append(path)
        return {'sha': item['task_tree'], 'truncated': False, 'tree': [{'path': 'gold.patch'}]}
    with pytest.raises(ValueError):
        preflight.metadata(item, fetch=fetch)
    assert calls == ['git/trees/'+'0'*40]
