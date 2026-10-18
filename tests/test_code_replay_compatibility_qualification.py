import ast
from benchmarks.code_replay.compatibility_qualification import PROGRAM,IDENTITIES


def test_real_source_qualification_is_unscored_and_keeps_originals():
    ast.parse(PROGRAM,feature_version=(3,10))
    assert len(IDENTITIES)==5 and len(set(IDENTITIES))==5
    assert "generation['source_bytes']" in PROGRAM and "encoded!=job['source']['files_base64'][name]" in PROGRAM
    assert "'bundle_exact_generation':True" in PROGRAM
    assert "user=1000,group=1000,extra_groups=[]" in PROGRAM
    assert "'model_calls':0" in PROGRAM and 'run_cli' not in PROGRAM
    assert 'max_context_bytes=4096' in PROGRAM
    assert 'max_facts=' not in PROGRAM and 'max_bytes=' not in PROGRAM
