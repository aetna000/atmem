import inspect

import pytest

from benchmarks.code_replay import confirmation_v3_capture, confirmation_v3_lock, confirmation_v3_prepare, confirmation_v3_execute
from benchmarks.code_replay.corrective_execution import source_capture, case_lock, preparation_source, model_source
from benchmarks.code_replay.corrective_execution import supporting_sources, load_support, SUPPORT_NAMES
from benchmarks.code_replay.corrective_execution import grading_source, report_source
from benchmarks.code_replay.corrective_execution import recovery_source, finish_source


def namespace(source):
    scope = {'__name__': 'corrective_execution_test'}
    exec(compile(source, '<corrective-execution>', 'exec'), scope)
    return scope


def test_lock_requires_all_fresh_distinct_paired_cells():
    lock = namespace(case_lock(inspect.getsource(confirmation_v3_lock)))
    blocks = [{'slot': i, 'instance_id': str(i), 'repeat': 1, 'order': ['native', 'tools']} for i in range(19)]
    rows = [{'slot': i, 'instance_id': str(i), 'repeat': 1, 'arm': arm, 'qualified': True, 'model_calls': 0}
            for i in range(19) for arm in ('native', 'tools')]
    assert len(lock['require_cases'](rows, blocks)) == 38
    with pytest.raises(ValueError):
        lock['require_cases'](rows[:-1], blocks)
    rows[-1]['qualified'] = False
    with pytest.raises(ValueError):
        lock['require_cases'](rows, blocks)


def test_preparation_and_models_keep_budget_grade_and_no_retry_gates():
    prepare = preparation_source(inspect.getsource(confirmation_v3_prepare))
    model = model_source(inspect.getsource(confirmation_v3_execute))
    namespace(prepare); namespace(model)
    assert "'model_attempts':38" in prepare
    assert "'max_seconds':600,'max_tool_calls':100" in prepare
    assert "'max_context_bytes':4096" in prepare
    assert "'no_model_retries':True" in model
    assert "'model':'gpt-6-luna','effort':'low'" in model
    assert 'termination=quiesce(group)' in model
    assert "private_grading':'after all models'" in model


def test_capture_changes_only_authorized_fresh_root():
    original = inspect.getsource(confirmation_v3_capture)
    adapted = source_capture(original)
    assert "capture_stopped_workspace" in adapted and "writers_stopped" in adapted
    assert "if populated(Path(process_scope))" in adapted


def test_unknown_execution_sources_cannot_be_adapted():
    for adapt in (source_capture, case_lock, preparation_source, model_source):
        with pytest.raises(ValueError):
            adapt('unknown')


def test_operator_imports_resolve_new_scopes_without_changing_product(monkeypatch):
    import sys
    import benchmarks.code_replay as package
    sources = supporting_sources()
    with monkeypatch.context() as changes:
        for name in SUPPORT_NAMES:
            changes.setitem(sys.modules, name, sys.modules[name])
            attribute = name.rsplit('.', 1)[1]
            changes.setattr(package, attribute, getattr(package, attribute))
        load_support(sources)
        from benchmarks.code_replay.confirmation_v3_process_scope import ROOT, CHILD_BOOTSTRAP
        assert 'corrective-development' in str(ROOT)
        assert str(ROOT) in CHILD_BOOTSTRAP
        assert sys.modules[SUPPORT_NAMES[1]].captured_case.__module__ == SUPPORT_NAMES[1]
    with pytest.raises(ValueError):
        load_support({})


def test_development_metrics_cannot_claim_confirmation_or_goal_completion():
    from benchmarks.code_replay import confirmation_v3_report, confirmation_v3_grade
    from tests.test_code_replay_confirmation_v3_report import fixture
    report = namespace(report_source(inspect.getsource(confirmation_v3_report)))
    grade = namespace(grading_source(inspect.getsource(confirmation_v3_grade)))
    rows, blocks = fixture()
    rows, blocks = rows[:38], blocks[:19]
    value = report['comparison'](rows, blocks)
    assert value['acceptance']['input_reduction_percent'] == '25'
    assert value['arms']['tools']['full_task_passes'] == 19
    assert value['scope'].startswith('reused-issue CD1 development')
    assert value['goal_complete'] is False and value['archive_verified'] is False
    assert len(grade['complete_cases']({'staging_manifest': {'blocks': blocks}}, rows,
        [{'attempts_completed': 38}])) == 38
    with pytest.raises(ValueError):
        report['comparison'](rows[:-1], blocks)
    with pytest.raises(ValueError):
        grade['complete_cases']({'staging_manifest': {'blocks': blocks}}, rows, [])
    rows[1]['usage'] = None
    assert report['comparison'](rows, blocks)['arms']['tools']['token_totals']['input_tokens'] is None


def test_postprocessing_waits_for_all_new_models_and_never_restarts_them():
    from benchmarks.code_replay import confirmation_v3_retain, confirmation_v3_finish
    retain = recovery_source(inspect.getsource(confirmation_v3_retain))
    finish = namespace(finish_source(inspect.getsource(confirmation_v3_finish)))
    namespace(retain)
    event = {'envelope': {'event_type': 'external.v3_models_completed', 'payload': {'attempts_completed': 38}}}
    assert finish['readiness']([event])
    assert not finish['readiness']([])
    stopped = {'envelope': {'event_type': 'external.v3_models_stopped', 'payload': {}}}
    with pytest.raises(ValueError):
        finish['readiness']([stopped])
    assert "'models_repeated': 0" in retain
    assert "from benchmarks.code_replay.windows_retain import PROGRAM, decode_recovery" in retain
