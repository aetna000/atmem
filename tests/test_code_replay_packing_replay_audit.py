from benchmarks.code_replay.packing_replay_audit import lexical_inspector
from tests.test_knowledge_packing import example


def test_diagnostic_reuses_source_scoring_without_emitting_a_model_pack():
    inspector,source=lexical_inspector()
    result=inspector(example(),'entry',budget=1024)
    assert result['query_terms']==['entry']
    assert result['top_lexical'][0]['name'].endswith('entry')
    assert result['top_lexical'][0]['score']>0
    assert 'graph_input(generation)' in source
