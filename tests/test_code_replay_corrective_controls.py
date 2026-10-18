import inspect
from pathlib import Path

import pytest

from benchmarks.code_replay import confirmation_v3_readiness, confirmation_v3_process_scope, confirmation_v3_sandbox
from benchmarks.code_replay.corrective_controls import readiness_source, process_source, sandbox_source, CASE_ROOT, CGROUP


def namespace(source):
    result = {'__name__': 'control_test'}
    exec(compile(source, '<control-test>', 'exec'), result)
    return result


def test_readiness_only_changes_new_cohort_identity_count_and_root():
    source = readiness_source(inspect.getsource(confirmation_v3_readiness))
    control = namespace(source)
    old = confirmation_v3_readiness.worker_program()
    assert control['worker_program']() == old.replace('/home/jt/atmem-benchmark-runtime-20261018/confirmation-stage-v3/block-', CASE_ROOT)
    assert "'cases':38" in source and "'all_38_cases_qualified'" in source


def test_new_cgroup_cannot_reuse_old_confirmation_groups():
    control = namespace(process_source(inspect.getsource(confirmation_v3_process_scope)))
    assert control['ROOT'] == Path(CGROUP)
    assert control['group_path']('block-18-tools').parent == Path(CGROUP)
    with pytest.raises(ValueError):
        control['group_path']('block-19-tools')
    assert CGROUP in control['CHILD_BOOTSTRAP']


def test_fresh_sandbox_keeps_identical_corrected_probe_and_policy():
    source = sandbox_source(inspect.getsource(confirmation_v3_sandbox))
    control = namespace(source)
    assert control['hidden_view_program']() == confirmation_v3_sandbox.hidden_view_program()
    assert control['PREVIOUS'].endswith('sandbox-v2-20261018')
    assert "'all_38_cases_qualified':len(results)==38" in source
    assert 'not hidden_canary_failure' not in source


def test_unrecognized_controls_are_rejected():
    for adapt in (readiness_source, process_source, sandbox_source):
        with pytest.raises(ValueError):
            adapt('unknown')
