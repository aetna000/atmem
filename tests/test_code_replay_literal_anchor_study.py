import ast
import inspect

import pytest

from benchmarks.code_replay.literal_anchor_study import controller_source, controller_namespace


def test_controller_adapts_only_local_profile_imports_and_protocol():
    preparation = controller_source('prepare')
    execution = controller_source('execute')
    for source in (preparation, execution):
        ast.parse(source, feature_version=(3, 10))
        assert 'import literal_anchor_screen as screen' in source
    assert 'screen.controls.QUALIFY' in preparation
    assert 'screen.controls.REPLAY' in preparation
    assert 'literal-anchor-development-screen-v1.md' in preparation
    assert "'phase failed; preserve evidence and inspect: '" in preparation
    assert "'attempts_completed'] != 38" in execution
    assert "'grading_only_after_all_38_models': True" in execution
    assert "'no_model_retries': True" in execution
    with pytest.raises(ValueError):
        controller_source('restart')


@pytest.mark.parametrize('mode', ['prepare', 'execute'])
def test_retained_remote_function_source_can_be_captured_before_ssh(mode):
    source = controller_source(mode)
    namespace = controller_namespace(source)
    assert inspect.getsource(namespace['remote']).startswith('def remote():')
    assert inspect.getsource(namespace['remote']) in source
    assert namespace['RUN'].startswith('external-windows-literal-anchor-development-')
