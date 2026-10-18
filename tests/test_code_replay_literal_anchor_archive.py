import ast
import inspect

import pytest

from benchmarks.code_replay import confirmation_v3_archive
from benchmarks.code_replay import literal_anchor_archive as archive
from benchmarks.code_replay import literal_anchor_screen as screen
from benchmarks.code_replay.literal_anchor_study import controller_namespace


def test_archive_preserves_full_cohort_and_uses_exact_current_qualification():
    source = archive.archive_source(inspect.getsource(confirmation_v3_archive))
    namespace = controller_namespace(source)
    assert namespace['LOCK'] == screen.PREFIX+'execution-lock-v1-20261018'
    assert namespace['REPORT'] == screen.PREFIX+'comparison-v1-20261018'
    assert archive.QUALIFY in source and archive.REPLAY in source
    assert screen.BUILD in source
    assert '!= (38, 38, 38)' in source
    assert 'all original CD2 requests' not in source
    assert 'all actual installed query replays required' in source
    assert 'external.public_selector_runtime_completed' in source
    assert 'actual unchanged/candidate public selector control required' in source


@pytest.mark.parametrize('mode', ['archive', 'transfer'])
def test_archive_and_transfer_profiles_keep_exact_separate_paths_and_no_models(mode):
    source = archive.controller_source(mode)
    ast.parse(source, feature_version=(3, 10))
    namespace = controller_namespace(source)
    assert namespace['OUTPUT'] == (archive.EXPORT_OUTPUT if mode == 'archive' else archive.OUTPUT)
    assert namespace['KEYS'] == (archive.EXPORT_KEYS if mode == 'archive' else archive.KEYS)
    assert namespace['PREFIX'] == screen.PREFIX
    assert 'literal_anchor_archive as query_nomination_archive' in source
    if mode == 'transfer':
        assert namespace['REMOTE_OUTPUT'] == archive.EXPORT_OUTPUT
        assert namespace['REMOTE_KEYS'] == archive.EXPORT_KEYS
        with pytest.raises(ValueError):
            namespace['copy_command']('/unrelated/', archive.OUTPUT)
