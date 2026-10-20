import ast
from benchmarks.code_replay.confirmation_bridge_readiness import PROGRAM
from benchmarks.code_replay.confirmation_v3_readiness import worker_program


def test_v3_reuses_original_mcp_control_with_only_exact_root_change():
    source=worker_program();ast.parse(source,feature_version=(3,10))
    assert source.replace('confirmation-stage-v3/block-','confirmation-stage-v1/block-')==PROGRAM
    assert 'user=1000,group=1000,extra_groups=[]' in source
    assert 'run_cli' not in source and "'model_calls':0" in source
