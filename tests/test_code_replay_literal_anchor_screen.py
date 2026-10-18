import ast

from benchmarks.code_replay import literal_anchor_screen as screen
from benchmarks.code_replay import public_selector_profile as selectors


def test_cd3_preserves_fixed_workload_and_installed_gates():
    sources = screen.sources()
    for source in sources.values():
        ast.parse(source, feature_version=(3, 10))
        assert 'external-windows-query-nomination-development-' not in source
    namespace = {'__name__': 'cd3_fixture'}
    exec(compile(sources['staging'], '<cd3-fixture>', 'exec'), namespace)
    blocks = [{'instance_id': str(i), 'repeat': r, 'slot': 2*i+r-1}
              for i in range(19) for r in (1, 2)]
    scheduled = namespace['development_blocks'](blocks)
    assert len(scheduled) == 19
    assert scheduled == namespace['development_blocks'](list(reversed(blocks)))
    assert namespace['SEED'] == screen.SEED
    assert namespace['FROZEN_VALIDATORS'] == selectors.validators()
    assert "role='server',validator_pair=FROZEN_VALIDATORS" in sources['staging']
    assert "role='worker',validator_pair=FROZEN_VALIDATORS" in sources['staging']
    assert screen.BUILD in sources['staging']
    assert screen.controls.QUALIFY in sources['staging']
    assert screen.controls.REPLAY in sources['staging']
    assert "'model_attempts':38" in sources['prepare']
    assert "'max_seconds':600,'max_tool_calls':100" in sources['prepare']
    assert "'model':'gpt-6-luna','effort':'low'" in sources['models']
    assert "'no_model_retries':True" in sources['models']
    assert 'not independent confirmation' in sources['report']


def test_runtime_probe_adds_real_nested_nodes_and_denials_not_model_hints():
    source = screen.sources()['readiness']
    namespace = {'__name__': 'cd3_readiness_fixture'}
    exec(compile(source, '<cd3-readiness-fixture>', 'exec'), namespace)
    worker = namespace['worker_program']()
    assert 'qualification-deny-' in worker
    assert "job['probe_paths']" in worker
    assert 'selector_denials_qualified' in worker
    assert '== -32602' in worker or '==-32602' in worker
    assert 'xarray/tests/test_atmem_public_boundary_20261018.py' in source
    assert "actual_probe+'::'+n" in source
    assert '3 passed' in worker
    assert "'max_workers':4" in source
