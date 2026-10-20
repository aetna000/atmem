import ast
import inspect

import pytest

from benchmarks.code_replay import compatibility_qualification as original
from benchmarks.code_replay.corrective_qualification import qualification_source, RUN, BUILD, ROOT
from benchmarks.code_replay.corrective_qualification import require_transport_only_failure
from benchmarks.code_replay.corrective_qualification import configuration_source
from benchmarks.code_replay.corrective_qualification import reuse_completed_extraction
from benchmarks.code_replay.corrective_qualification import continuation_source, require_mcp_import_failure
from benchmarks.code_replay.corrective_qualification import owned_state_continuation_source


def test_corrective_control_preserves_all_real_cases_and_boundary_checks():
    import inspect
    source = qualification_source(inspect.getsource(original))
    namespace = {'__name__': 'qualification_test'}
    exec(compile(source, '<qualification>', 'exec'), namespace)
    assert namespace['RUN'] == RUN
    assert namespace['IDENTITIES'] == original.IDENTITIES
    assert BUILD in source and ROOT in source
    program = namespace['PROGRAM']
    ast.parse(program, feature_version=(3, 10))
    assert "foreign=replace(lane.scope,agent_id=" in program
    assert "lane.knowledge.authorize(foreign)" in program
    assert "'foreign_scope_denied':True" in program
    for check in ("max_context_bytes=4096", "'bundle_exact_generation':True",
                  "user=1000,group=1000,extra_groups=[]", "'freshness_withholding':True"):
        assert check in program
    marker = " from dataclasses import replace\n"
    start = program.index(marker)
    end = program.index(' generation=lane.knowledge.current(str(workspace))', start)
    recovered = program[:start]+program[end:]
    recovered = recovered.replace("'foreign_scope_denied':True,", '')
    assert recovered == original.PROGRAM


def test_changed_source_cannot_silently_adapt():
    with pytest.raises(ValueError):
        qualification_source('unknown control')


def test_transport_resume_rejects_any_started_or_ambiguous_worker():
    rows = [{'exit_code': 255, 'streams': {'stdout': {'bytes': 0}}}]*5
    errors = [b'Host key verification failed.\r\n']*5
    require_transport_only_failure(rows, errors, [False]*5)
    with pytest.raises(ValueError):
        require_transport_only_failure(rows, errors, [True]*5)
    with pytest.raises(ValueError):
        require_transport_only_failure(rows, [b'other']*5, [False]*5)


def test_actual_mcp_helpers_run_in_a_fresh_namespace(tmp_path):
    from types import SimpleNamespace
    from benchmarks.code_replay.windows_execute import runner_helpers
    import sys
    namespace = {}
    exec(configuration_source(runner_helpers()[1]), namespace)
    database = tmp_path/'memory.db'
    database.touch()
    result = namespace['configuration'](sys.executable, [], database=database, root=tmp_path,
        scope=SimpleNamespace(subject_id='subject', project_id='project', profile_id='shared', agent_id='codex'),
        focused=True)
    assert result['enabled_tools'][0] == 'code_context'
    assert namespace['arguments'](result)


def test_extraction_continuation_cannot_replace_or_reextract_source():
    program = reuse_completed_extraction(original.PROGRAM)
    assert 'HouseholdApplication.initialize' not in program
    assert "git('init'" not in program
    assert "target.write_bytes" not in program
    assert "retained source differs" in program
    assert "retained extraction is not current" in program
    for check in ("bundle_exact_generation", "freshness_withholding", "user=1000,group=1000"):
        assert check in program
    with pytest.raises(ValueError):
        reuse_completed_extraction('unknown')


def test_complete_continuation_keeps_prior_failures_and_records_helpers():
    import inspect
    source = continuation_source(inspect.getsource(original))
    namespace = {'__name__': 'continuation_test'}
    exec(compile(source, '<continuation-test>', 'exec'), namespace)
    assert namespace['RUN'].endswith('-mcp-import-continuation')
    assert 'HouseholdApplication.initialize' not in namespace['PROGRAM']
    assert 'prior_failure_guard()' in source
    # Two protected captures plus the original worker payload.
    assert source.count("'configuration_source':job['configuration_source']") == 3


def test_post_extraction_resume_rejects_unrelated_failure():
    rows = [{'exit_code': 1, 'streams': {'stdout': {'bytes': 0}}}]*5
    error = b"line 4, in configuration\nNameError: name 'Path' is not defined. Did you mean: 'path'?\n"
    require_mcp_import_failure(rows, [error]*5)
    with pytest.raises(ValueError):
        require_mcp_import_failure(rows, [b'other']*5)


def test_ownership_exception_is_only_process_local_for_verified_benchmark_root():
    source = owned_state_continuation_source(inspect.getsource(original))
    namespace = {'__name__': 'ownership_control_test'}
    exec(compile(source, '<ownership-control>', 'exec'), namespace)
    program = namespace['PROGRAM']
    assert "workspace.stat().st_uid!=1000" in program
    assert "GIT_CONFIG_VALUE_0=str(workspace)" in program
    assert "GIT_CONFIG_KEY_0='safe.directory'" in program
    assert 'git config --global' not in program
    assert 'HouseholdApplication.initialize' not in program
    assert namespace['RUN'].endswith('-owned-state-continuation')
