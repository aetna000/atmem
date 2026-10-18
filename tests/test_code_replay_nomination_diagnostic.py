import ast
from pathlib import Path

import pytest

from benchmarks.code_replay.nomination_diagnostic import call_delta, locator_delta


def test_call_change_guard_refuses_unrelated_source_or_namespace_changes():
    candidate = Path('atmem/knowledge/code/packing.py').read_text()
    node = next(n for n in ast.parse(candidate).body if isinstance(n, ast.FunctionDef) and n.name == '_query_call_names')
    helper = ast.get_source_segment(candidate, node)
    old = '    bare = set(re.findall(r"(?<![\\w.])\\b([A-Za-z_]\\w*)\\s*\\(", task))'
    previous = candidate.replace(helper+'\n\n', '', 1).replace('    bare = _query_call_names(task)', old, 1)
    assert call_delta(previous, candidate) == helper
    with pytest.raises(ValueError): call_delta(previous, candidate.replace('graph_input(generation)', 'graph_input(other)'))
    with pytest.raises(ValueError): call_delta(previous, candidate.replace('qualified, bare = references', 'qualified, bare = other'))


def test_source_location_guard_refuses_authority_changes():
    current = Path('atmem/knowledge/code/packing.py').read_text()
    # Exercise the earlier source-location contract, not the separately guarded
    # literal/named-target extension. The original guard must remain strict.
    candidate = current.replace(
        '        if row["location_span"] is not None and (row["explicit"] or row["path"] not in explicit_paths):',
        '        if row["location_span"] is not None:', 1)
    node = next(n for n in ast.parse(candidate).body if isinstance(n, ast.FunctionDef) and n.name == '_query_source_locations')
    helper = ast.get_source_segment(candidate, node)
    previous = candidate.replace(helper+'\n\n', '', 1)
    previous = previous.replace('    locations = _query_source_locations(task, sources)\n', '', 1)
    previous = previous.replace('                           "class": isinstance(node, ast.ClassDef), "node": node,\n'
        '                           "location_span": end - start if node is not None and any(\n'
        '                               start <= first <= last <= end for first, last in locations.get(path, ())) else None})',
        '                           "class": isinstance(node, ast.ClassDef), "node": node})', 1)
    previous = previous.replace('        if row["location_span"] is not None:\n'
        '            return 20000 + 1000 / (1 + row["location_span"])\n', '', 1)
    assert locator_delta(previous, candidate) == helper
    with pytest.raises(ValueError): locator_delta(previous, current)
    with pytest.raises(ValueError): locator_delta(previous, candidate.replace('graph_input(generation)', 'graph_input(other)'))
    with pytest.raises(ValueError): locator_delta(previous, candidate.replace('sha256(raw).hexdigest() != hashes[name]', 'False'))
