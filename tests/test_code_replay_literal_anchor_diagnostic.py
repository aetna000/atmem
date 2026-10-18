import ast
from pathlib import Path

import pytest

from benchmarks.code_replay.literal_anchor_diagnostic import allowed_delta


def previous_source(candidate):
    tree = ast.parse(candidate)
    helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_query_literal_targets')
    packer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'pack_generation')
    lines = candidate.splitlines(keepends=True)
    removed = set(range(helper.lineno - 1, helper.end_lineno + 2))
    for node in packer.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {'literal_targets', 'explicit_paths'} for t in node.targets):
            removed.update(range(node.lineno - 1, node.end_lineno))
    lexical = next(n for n in packer.body if isinstance(n, ast.FunctionDef) and n.name == 'lexical')
    for node in lexical.body:
        if ((isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'literal_priority' for t in node.targets))
                or (isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == 'literal_priority')):
            removed.update(range(node.lineno - 1, node.end_lineno))
    result = ''.join(line for i, line in enumerate(lines) if i not in removed)
    result = result.replace('        if row["location_span"] is not None and (row["explicit"] or row["path"] not in explicit_paths):',
                            '        if row["location_span"] is not None:', 1)
    return result


def test_exact_literal_delta_preserves_all_other_source_and_authority_bytes():
    candidate = Path('atmem/knowledge/code/packing.py').read_text()
    previous = previous_source(candidate)
    assert allowed_delta(previous, candidate).startswith('def _query_literal_targets(')
    for old, new in [('graph_input(generation)', 'graph_input(other)'),
                     ('sha256(raw).hexdigest() != hashes[name]', 'False')]:
        with pytest.raises(ValueError):
            allowed_delta(previous, candidate.replace(old, new))
