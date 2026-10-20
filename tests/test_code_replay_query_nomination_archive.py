import inspect

import pytest

from benchmarks.code_replay import confirmation_v3_archive, query_nomination_archive
from benchmarks.code_replay.query_nomination_screen import PREFIX
from tests.test_code_replay_confirmation_v3_report import fixture


def event(kind, payload):
    return {'envelope': {'event_type': kind, 'payload': payload}}


def test_cd2_archive_requires_full_fresh_controls_and_installed_replays():
    namespace = {'__name__': 'cd2_archive_test'}
    source = query_nomination_archive.archive_source(inspect.getsource(confirmation_v3_archive))
    exec(compile(source, '<cd2-archive>', 'exec'), namespace)
    rows, blocks = fixture(); rows, blocks = rows[:38], blocks[:19]
    rows = [{**r, 'task_run': f"case-{r['slot']}-{r['arm']}", 'qualified': True, 'model_calls': 0} for r in rows]
    lock = {'staging_manifest': {'blocks': blocks, 'source_descriptors': {}, 'prior_manifest_run': 'original'},
            'staged_blocks': [], 'grade_plans': {}}
    records = {'original': [event('external.confirmation_manifest_frozen', {'blocks': [{'slot': i} for i in range(38)]})]}
    for suffix, kind in [('mcp-readiness', 'external.v3_mcp_case_summary'), ('sandbox', 'external.v3_sandbox_case_summary')]:
        records[PREFIX+suffix+'-v1-20261018'] = [event(kind, r) for r in rows]
    qualification = 'external-windows-query-nomination-qualification-v1-20261018'
    records[qualification] = [event('external.compatibility_case_result', {
        'identity': identity, 'task_run': qualification+'-'+identity,
        'qualified': True, 'model_calls': 0, 'foreign_scope_denied': True})
        for identity in namespace['QUALIFICATION_IDENTITIES']]
    records[qualification].append(event('external.compatibility_qualification_completed', {'qualified': True}))
    replay = 'external-windows-query-nomination-installed-replay-v1-20261018'
    records[replay] = [event('external.query_nomination_installed_replay_case', {'identity': str(i), 'matches': True}) for i in range(19)]
    records[replay].append(event('external.query_nomination_installed_replay_completed', {
        'qualified': True, 'identities': 19, 'model_calls': 0}))
    runs = namespace['required_runs'](lock, rows, rows, rows, records.__getitem__)
    assert replay in runs
    assert PREFIX+'execution-v1-20261018' in runs
    assert 'external-windows-product-build-query-nomination-v1-20261018' in runs
    assert 'original-block-37' in runs
    assert not any('owned-state-continuation' in run for run in runs)
    records[replay].pop(0)
    with pytest.raises(ValueError):
        namespace['required_runs'](lock, rows, rows, rows, records.__getitem__)
