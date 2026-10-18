import inspect

import pytest

from benchmarks.code_replay import query_nomination_case_review as review


def test_feedback_is_a_distinct_explicit_read_only_profile():
    assert review.profile([]) == review.RUN
    assert review.profile(['feedback']) == review.FEEDBACK_RUN
    assert review.RUN != review.FEEDBACK_RUN
    with pytest.raises(ValueError):
        review.profile(['rerun'])


def test_reviewer_requires_all_pairs_and_binds_original_receipts_before_details():
    source = inspect.getsource(review.review)
    assert 'len(rows) != 38' in source and 'len(by_identity) != 19' in source
    assert "set(p) != {'native', 'tools'}" in source
    assert "receipts != model['usage_receipts']" in source
    assert 'original usage differs from comparison' in source
    assert "source_vault_opened': False" in source
    assert 'difflib.unified_diff' in source
    assert 'run_cli(' not in source and 'subprocess.run(' not in source
    assert 'public_tool_calls' in source
