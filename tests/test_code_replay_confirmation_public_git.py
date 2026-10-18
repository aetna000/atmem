import pytest
from benchmarks.code_replay.confirmation_public_git import public_path


def test_only_public_git_objects_for_original_repositories():
    assert public_path('pallets/flask', 'trees', 'a'*40).endswith('?recursive=1')
    for args in [('private/repository', 'trees', 'a'*40), ('pallets/flask', 'issues', 'a'*40),
                 ('pallets/flask', 'commits', '../main')]:
        with pytest.raises(ValueError):
            public_path(*args)
