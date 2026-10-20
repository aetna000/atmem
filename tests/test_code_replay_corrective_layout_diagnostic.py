from pathlib import Path

import pytest

from benchmarks.code_replay.corrective_layout_diagnostic import allowed_delta, lexical_inspector


def test_only_declared_helper_and_query_weights_can_change():
    candidate = Path('atmem/knowledge/code/packing.py').read_text()
    import ast
    node = next(n for n in ast.parse(candidate).body if isinstance(n, ast.FunctionDef) and n.name == '_query_term_weights')
    helper = ast.get_source_segment(candidate, node)
    old = '    weights = {t: 1 + math.log(1 + len(candidates) / (1 + frequency[t])) for t in terms}'
    new = '    query_weights = _query_term_weights(task)\n    weights = {t: query_weights[t] * (1 + math.log(1 + len(candidates) / (1 + frequency[t]))) for t in terms}'
    baseline = candidate.replace(helper+'\n\n', '', 1).replace(new, old, 1)
    assert allowed_delta(baseline, candidate) == helper
    with pytest.raises(ValueError): allowed_delta(baseline, candidate.replace('graph_input(generation)', 'graph_input(other)'))
    with pytest.raises(ValueError): allowed_delta(baseline, candidate+'\n# unrelated change\n')


def test_diagnostic_reuses_the_selected_source_namespace_and_lexical_boundary():
    from atmem.knowledge.code import packing
    from tests.test_knowledge_packing import example
    source = Path('atmem/knowledge/code/packing.py').read_text()
    diagnostic = lexical_inspector(source, dict(vars(packing)))
    rows = diagnostic(example(), 'entry\n### Configuration', budget=1024)
    assert rows[0]['name'].endswith('entry')
    assert rows[0]['score'] > 0
