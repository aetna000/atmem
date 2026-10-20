from copy import deepcopy
import pytest
from benchmarks.code_replay.confirmation_v3_archive import core_runs, required_runs, validate_run
from tests.test_code_replay_confirmation_v3_report import fixture


def test_archive_requires_all_cells_and_full_source_and_grader_members():
    rows, blocks = fixture()
    model = [{**r, 'task_run': f"model-{r['slot']}-{r['arm']}"} for r in rows]
    grade = [{**r, 'task_run': f"grade-{r['slot']}-{r['arm']}"} for r in rows]
    public = [{**r, 'task_run': f"public-{r['slot']}-{r['arm']}"} for r in rows]
    lock = {'staging_manifest': {'blocks': blocks, 'source_descriptors': {'one': {'export_run': 'full-source'}}},
            'staged_blocks': [{'task_run': 'full-staging'}], 'grade_plans': {'one': {'task_run': 'private-grader'}}}
    runs = core_runs(lock, model, grade, public)
    assert {'full-source', 'full-staging', 'private-grader'} <= runs
    assert all(r['task_run'] in runs for r in model + grade + public)
    with pytest.raises(ValueError): core_runs(lock, model[:-1], grade, public)
    duplicate = deepcopy(public); duplicate[-1] = duplicate[0]
    with pytest.raises(ValueError): core_runs(lock, model, grade, duplicate)


def test_archive_cannot_substitute_another_run_or_empty_event_list():
    with pytest.raises(ValueError): validate_run('expected', [])
    with pytest.raises(ValueError):
        validate_run('expected', [{'envelope': {'run_id': 'other', 'event_type': 'example'}}])
    assert validate_run('expected', [{'object_id': 'one', 'envelope': {
        'run_id': 'expected', 'event_type': 'example', 'payload': {}}}])['events'] == 1


def test_archive_recovery_requires_failed_readiness_and_previous_staging_too():
    rows, blocks = fixture()
    rows = [{**r, 'task_run': f"case-{r['slot']}-{r['arm']}"} for r in rows]
    lock = {'staging_manifest': {'blocks': blocks, 'source_descriptors': {}, 'prior_manifest_run': 'prior'},
            'staged_blocks': [], 'grade_plans': {}}
    records = {}
    for root, kind in [('external-windows-confirmation-v3-mcp-readiness-v1-20261018', 'external.v3_mcp_case_summary'),
                       ('external-windows-confirmation-v3-sandbox-v1-20261018', 'external.v3_sandbox_case_summary'),
                       ('external-windows-confirmation-v3-sandbox-v2-20261018', 'external.v3_sandbox_case_summary')]:
        records[root] = [{'envelope': {'event_type': kind, 'payload': {
            **r, 'task_run': root + '-' + r['task_run'], 'qualified': False}}} for r in rows]
    records['external-windows-source-storage-qualification-v1-20261018'] = [
        {'envelope': {'event_type': 'external.compatibility_case_result', 'payload': {'task_run': f'compatibility-{i}'}}}
        for i in range(5)]
    runs = required_runs(lock, rows, rows, rows, records.__getitem__)
    assert 'prior-block-37' in runs and 'compatibility-4' in runs
    failed = 'external-windows-confirmation-v3-sandbox-v1-20261018'
    assert failed + '-case-0-native' in runs
    records[failed].pop()
    with pytest.raises(ValueError): required_runs(lock, rows, rows, rows, records.__getitem__)
