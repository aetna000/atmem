import ast
import inspect

from benchmarks.code_replay import query_nomination_archive_waiter as waiter


def test_waiter_uses_actual_postprocessing_helpers_before_allocating_export():
    source = inspect.getsource(waiter.remote)
    ast.parse(source, feature_version=(3, 10))
    assert "of(models, 'external.v3_models_stopped')" in source
    assert "ends[0]['comparison_and_public_recovery'] is not True" in source
    assert "post['postprocess_programs'].items()" in source
    assert source.index('archive.validate_run(') < source.index('archive.main()')
    assert "'MEM_copy_and_independent_recovery': 'still required'" in source
    assert 'create_group' not in source
    assert 'run_cli(' not in source
    assert 'sleep(30)' in source
    assert waiter.OUTPUT != waiter.KEYS
    assert waiter.KEYS.startswith('/home/jt/')
