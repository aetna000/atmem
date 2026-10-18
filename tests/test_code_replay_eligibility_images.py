from copy import deepcopy

import pytest

from benchmarks.code_replay.external_catalog import TASK_TREE, ELIGIBILITY_REPOSITORIES, ELIGIBILITY_SEED, catalog, digest
from benchmarks.code_replay.windows_eligibility_images import validate_pool


def fixture():
    tree = {'sha': TASK_TREE, 'truncated': False, 'tree': [
        {'path': repo.replace('/', '__') + '-' + str(i), 'type': 'tree', 'sha': f'{i:040x}'}
        for repo in ELIGIBILITY_REPOSITORIES for i in range(1, 10)]}
    selection = catalog(tree, seed=ELIGIBILITY_SEED, per_repo=8, repositories=ELIGIBILITY_REPOSITORIES, eligibility_pool=True)
    metadata = {'selection_sha256': digest(selection), 'reports': [
        {'instance_id': r['instance_id'], 'status': 'metadata_verified_environment_not_executed',
         'metadata': {'instance_id': r['instance_id']}} for r in selection['selected']]}
    return selection, metadata


def test_candidate_eligibility_cannot_silently_become_a_smaller_model_set():
    selection, metadata = fixture()
    validate_pool(selection, metadata)
    shorter = deepcopy(selection); shorter['selected'].pop()
    with pytest.raises(ValueError, match='forty'):
        validate_pool(shorter, metadata)
    reordered = deepcopy(selection); reordered['selected'][0], reordered['selected'][1] = reordered['selected'][1], reordered['selected'][0]
    with pytest.raises(ValueError, match='order'):
        validate_pool(reordered, {**metadata, 'selection_sha256': digest(reordered)})
