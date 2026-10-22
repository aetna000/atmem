import ast
import pytest

from benchmarks.code_replay.windows_cohort import ARMS, manifest, model_program, stage_program


def test_manifest_retains_failed_environment_and_all_fixed_slots():
    identities = ["marshmallow-code__marshmallow-1229", "marshmallow-code__marshmallow-1810",
        "psf__requests-1327", "psf__requests-4356", "pylint-dev__astroid-934", "pylint-dev__astroid-1616"]
    rows = manifest(identities)
    assert rows == manifest(list(reversed(identities)))
    assert len(rows) == 12 and sum(len(row['order']) for row in rows) == 36
    assert all(set(row['order']) == set(ARMS) for row in rows)
    assert sum(row['eligibility'] == 'qualified' for row in rows) == 10
    assert sum(row['eligibility'] == 'unqualified_environment' for row in rows) == 2


def test_adapters_preserve_caps_auth_cleanup_and_source_isolation():
    stage, model = stage_program(), model_program()
    ast.parse(stage); ast.parse(model)
    assert "code_config=None\nif arm=='tools':" in model
    assert model.count("if arm!='native':") == 3
    assert 'max_seconds=600,max_tool_calls=100' in model
    assert "if auth.is_file():auth.unlink()" in model
    assert 'privileged broker directly executable' in model
    assert 'job["probe_source"]' in model
    assert 'generation_zlib_base64' in stage and 'zlib.compress' in stage
    assert "cases['pack']['prepared']['package']['content']!=cases['tools']['prepared']['package']['content']" in stage
    assert "operator.mkdir(mode=0o700)" in stage
    assert "if arm=='atmem'" not in stage


def test_stage_case_descriptors_keep_real_atmem_database_and_home():
    from pathlib import PurePosixPath as Path  # this AST executes in the Linux/WSL worker
    tree = ast.parse(stage_program())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == 'cases' for t in n.targets))
    for arm in ARMS:
        values = dict(cases={}, arm=arm, case=Path('/trial') / arm, workspace=Path('/trial') / arm / 'workspace',
            operator=Path('/trial') / arm / 'operator', installation_home=Path('/trial/pack/atmem-home'),
            scope={}, prepared={}, generation='compressed', initial_commit='a', initial_tree='b')
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'stage-case-descriptor', 'exec'), values)
        case = values['cases'][arm]
        assert case['atmem_home'] == (None if arm == 'native' else '/trial/pack/atmem-home')
        assert case['database'] == (None if arm == 'native' else '/trial/' + arm + '/atmem-home/memory.db')


def test_nested_probe_is_real_python_not_backslash_escaped_text():
    tree = ast.parse(model_program())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'probe' for t in n.targets))
    values = {'job': {'probe_source': 'astroid/__init__.py'}}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'probe-builder', 'exec'), values)
    compile(values['probe'], 'sandbox-probe', 'exec')
    assert '\n' in values['probe']


def test_executor_preserves_full_transport_and_reuses_usage_without_imputation():
    from benchmarks.code_replay.windows_execute import model_metadata, runner_helpers
    usage = {'type': 'turn.completed', 'usage': {'input_tokens': 12, 'cached_input_tokens': 7}}
    meta = model_metadata({'events': [usage], 'stdout_base64': 'raw', 'stderr_base64': '', 'stop_reason': None})
    assert meta['usage_receipts'] == [usage] and 'events' not in meta
    assert model_metadata({'events': [], 'stop_reason': 'tool_budget'})['usage_receipts'] == []
    runner, helpers = runner_helpers()
    ast.parse(runner); ast.parse(helpers)
    assert '--ignore-user-config' in runner and 'gpt-6-luna' in runner
    assert 'str(session.tool_temporary)' in runner


def test_private_grading_waits_for_every_frozen_cell_and_terminal_capture():
    from benchmarks.code_replay.windows_grade import require_complete_cohort
    identities = ["marshmallow-code__marshmallow-1229", "marshmallow-code__marshmallow-1810",
        "psf__requests-1327", "psf__requests-4356", "pylint-dev__astroid-934", "pylint-dev__astroid-1616"]
    frozen = {'blocks': manifest(identities)}
    rows = [{'slot': block['slot'], 'arm': arm, 'temporary_cli_auth_absent': True, 'writer_processes_observed': []}
        for block in frozen['blocks'] if block['eligibility'] == 'qualified' for arm in block['order']]
    complete = [{'attempts_completed': 30}]
    assert len(require_complete_cohort(frozen, rows, rows, complete)) == 30
    with pytest.raises(ValueError, match='finish'):
        require_complete_cohort(frozen, rows, rows, [])
    with pytest.raises(ValueError, match='per frozen cell'):
        require_complete_cohort(frozen, rows[:-1] + [rows[0]], rows, complete)
    with pytest.raises(ValueError, match='terminal'):
        require_complete_cohort(frozen, [{**r, 'temporary_cli_auth_absent': False} for r in rows], rows, complete)
