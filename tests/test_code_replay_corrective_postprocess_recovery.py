from copy import deepcopy

import pytest

from benchmarks.code_replay.corrective_postprocess_recovery import missing_summaries, projected_controller, summary


def test_only_missing_identical_parent_projections_can_be_added():
    rows = [{'slot': i, 'arm': a, 'unchanged_result': True} for i in range(19) for a in ('native', 'tools')]
    assert missing_summaries(rows, rows[:24]) == rows[24:]
    changed = deepcopy(rows[:24]); changed[0]['unchanged_result'] = False
    with pytest.raises(ValueError): missing_summaries(rows, changed)
    with pytest.raises(ValueError): missing_summaries(rows, [rows[0], rows[0]])
    with pytest.raises(ValueError): missing_summaries(rows[:-1], [])


def test_original_heavy_worker_projection_is_exact_not_a_new_grade():
    full = {'exit_code': 0, 'worker': {'grading': {'task_pass': False}, 'original_files_base64': {'a.py': 'original'}}}
    inline = {'exit_code': 0, 'worker': {'grading': {'task_pass': False}}}
    retained = {'transport_exit': 0, 'controller': inline, 'decoded_worker_stream': {},
        'worker_fields_projection': {'omitted_from_inline_only': ['original_files_base64'], 'complete_result_retained': True}}
    assert projected_controller(retained, full) == inline
    retained['controller']['worker']['grading']['task_pass'] = True
    with pytest.raises(ValueError): projected_controller(retained, full)


def test_summary_preserves_failed_test_outcome_and_original_metadata():
    case = {'slot': 1, 'instance_id': 'original', 'repeat': 1, 'arm': 'tools', 'source_policy_compliant': False}
    retained = {'instance_id': 'original', 'phase': 'solver_candidate', 'transport_exit': 0,
                'controller': {'exit_code': 1, 'reason': 'original failure'}}
    row = summary(case, retained, retained['controller'], {'expected_f2p': 2, 'expected_p2p': 3}, 'grade-original')
    assert row['controller']['reason'] == 'original failure'
    assert row['source_policy_compliant'] is False
    assert row['expected_f2p'] == 2


def test_operator_uses_retained_phase_modules_not_uninstalled_v3_files():
    import inspect
    from benchmarks.code_replay import corrective_postprocess_recovery
    source = inspect.getsource(corrective_postprocess_recovery.main)
    assert 'from benchmarks.code_replay.confirmation_v3_report import' not in source
    assert 'from benchmarks.code_replay.confirmation_v3_dispatch_audit import' not in source
    assert "programs = plan['postprocess_programs']" in source
    assert "'request_audit_source': job['request_audit_source']" in source
    assert 'writing_run=GRADING' in source
    assert source.count('grade_vault.capture(run_id=GRADING') == 2
