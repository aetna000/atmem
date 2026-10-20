import ast

from benchmarks.code_replay.public_selector_runtime import worker_source
from benchmarks.code_replay.literal_anchor_screen import CASE_ROOT


def test_runtime_control_preserves_candidate_and_adds_original_unchanged_nested_test():
    source = worker_source()
    ast.parse(source, feature_version=(3, 10))
    assert CASE_ROOT in source
    assert 'qualification-public-selector-baseline' in source
    assert "'patch':'','paths':['xarray/tests/test_options.py']" in source
    assert 'unchanged_public_qualified' in source
    assert "baseline_answer.get('test_exit_code')==0" in source
    assert "result['selector_denials_qualified']" in source
    assert "answer.get('test_exit_code')==0 and '3 passed'" in source
    assert 'original_preset_unchanged' in source
    assert 'original_server_unchanged' in source
    assert "result['qualified']=bool(result['unchanged_public_qualified']" in source
