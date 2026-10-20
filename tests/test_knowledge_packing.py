"""Boundary fixtures only, never training or task-performance evidence."""
import base64
from copy import deepcopy
from hashlib import sha256

import pytest
from atmem.knowledge.code.packing import pack_generation, _cleanup_sites, _named, _references, _compound_terms
import ast
from tests.test_knowledge_queries import generation


def example():
    value = generation()
    value["snapshot"] = {"files": []}
    value["source_bytes"] = {}
    for obj in value["objects"]:
        path = obj["anchors"][0]["path"]
        content = (f"def {obj['name']}():\n    return '東京'\n").encode()
        identity = sha256(content).hexdigest()
        obj["anchors"][0]["content_sha256"] = identity
        value["snapshot"]["files"].append([path, identity])
        value["source_bytes"][path] = base64.b64encode(content).decode()
    return value


def test_source_definitions_have_readable_references_and_byte_budget():
    value = example()
    result = pack_generation(value, "entry", budget=1024)
    assert "AtMem structure entry.py:1-2" in result
    assert "def entry():" in result and "return '東京'" in result
    for budget in (0, 50, 128, 256, 512):
        assert len(pack_generation(value, "entry", budget=budget).encode()) <= budget
    assert pack_generation(value, "unrelated weather", budget=1024) == ""


def test_packing_navigation_excludes_unused_metadata_without_changing_evidence(monkeypatch):
    import atmem.knowledge.code.packing as module
    value = example()
    before = pack_generation(value, 'entry', budget=4096)
    value['property_variants'].setdefault(value['objects'][0]['object_id'], [{}])
    for variants in value['property_variants'].values():
        variants[0]['large_navigation_irrelevant_property'] = ['retained original metadata'] * 100
    calls = []
    original = module.CodeRetriever.execute
    def checked(self, nodes, edges, query=''):
        assert all('fact_properties' not in node and 'extraction_receipt' not in node for _, node in nodes)
        compact = original(self, nodes, edges, query)
        from atmem.knowledge.code.queries import graph_input
        full_nodes, full_edges = graph_input(value)
        full = original(self, full_nodes, full_edges, query)
        assert [(x['id'], x.get('depth')) for x in compact.get('nodes', [])] == [
            (x['id'], x.get('depth')) for x in full.get('nodes', [])]
        assert [(x['source_id'], x['target_id'], x['type']) for x in compact.get('edges', [])] == [
            (x['source_id'], x['target_id'], x['type']) for x in full.get('edges', [])]
        calls.append(True)
        return compact
    monkeypatch.setattr(module.CodeRetriever, 'execute', checked)
    assert pack_generation(value, 'entry', budget=4096) == before
    assert calls
    assert any('large_navigation_irrelevant_property' in variants[0] for variants in value['property_variants'].values())


def test_unfittable_candidates_do_not_rescan_every_graph_edge(monkeypatch):
    import atmem.knowledge.code.packing as module
    value = example()
    original = list(value['objects'])
    for index in range(40):
        row = deepcopy(original[0])
        row['object_id'] = 'extra-' + str(index)
        value['objects'].append(row)
    for index, row in enumerate(value['objects']):
        row['name'] = 'package.entry_' + 'long_identifier_' * 8 + str(index)
    real = module.graph_input
    iterations = []
    class CountedEdges(list):
        def __iter__(self):
            iterations.append(True)
            return super().__iter__()
    def checked(generation):
        nodes, edges = real(generation)
        return nodes, CountedEdges(edges)
    monkeypatch.setattr(module, 'graph_input', checked)
    assert module.pack_generation(value, 'entry', budget=200) == ''
    assert len(iterations) <= 4


def test_corrupt_source_or_scope_never_becomes_context():
    value = example()
    value["source_bytes"]["entry.py"] = base64.b64encode(b"CORRUPTED_SOURCE").decode()
    with pytest.raises(ValueError, match="source evidence"):
        pack_generation(value, "entry", budget=1024)
    value = example()
    value["objects"][0]["scope"]["subject_id"] = "outsider"
    with pytest.raises(PermissionError):
        pack_generation(value, "entry", budget=1024)
    value = example()
    value["objects"][0]["anchors"][0]["content_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="anchor"):
        pack_generation(value, "entry", budget=1024)


def test_long_implementation_is_explicit_partial_source_not_silent_truncation():
    value = example()
    raw = ("def entry():\n" + "    x = 'long repeated source line'\n" * 200).encode()
    identity = sha256(raw).hexdigest()
    value["snapshot"]["files"][0][1] = identity
    value["objects"][0]["anchors"][0]["content_sha256"] = identity
    value["source_bytes"]["entry.py"] = base64.b64encode(raw).decode()
    result = pack_generation(value, "entry", budget=4096)
    assert "partial implementation" in result and "source lines omitted" in result
    assert "x = 'long repeated source line'" in result
    entry_header = next(line for line in result.splitlines() if "AtMem structure entry.py:" in line)
    assert "complete definition" not in entry_header


def test_repeated_owner_vocabulary_does_not_displace_relevant_local_symbol():
    value = example()
    value["objects"][0]["name"] = "package.FileConnection.__enter__"
    value["objects"][1]["name"] = "package.FileConnection.__exit__"
    value["objects"][2]["name"] = "package.write_file"
    result = pack_generation(value, "write file", budget=600)
    assert "package.write_file" in result
    if "package.FileConnection" in result:
        assert result.index("package.write_file") < result.index("package.FileConnection")


def test_compact_compound_identifier_matches_multiple_query_words():
    value = example()
    obj = value["objects"][0]
    raw = b"def storememory():\n    return 1\n"
    identity = sha256(raw).hexdigest()
    value["source_bytes"]["entry.py"] = base64.b64encode(raw).decode()
    value["snapshot"]["files"][0][1] = identity
    obj["name"] = "package.storememory"
    obj["anchors"][0]["content_sha256"] = identity
    result = pack_generation(value, "store memory", budget=600)
    assert "package.storememory" in result


def test_compound_matching_requires_complete_identifier_parts():
    assert _compound_terms("storememory", {"store", "memory"}) == {"store", "memory"}
    assert _compound_terms("storememory", {"storememory", "store", "memory"}) == {"store", "memory"}
    assert _compound_terms("decorated_with_property", {"proper", "rated"}) == set()
    assert _compound_terms("profilestore", {"file", "store"}) == set()
    assert _compound_terms("updateInformation", {"date", "information"}) == set()
    assert _compound_terms("store_memory", {"tore", "memo"}) == set()
    assert _compound_terms("storememory" * 30, {"store", "memory"}) == set()


def test_incidental_prose_cannot_create_property_context():
    value = example()
    raw = b"def decorated_with_property():\n    return 1\n"
    identity = sha256(raw).hexdigest()
    value["source_bytes"]["entry.py"] = base64.b64encode(raw).decode()
    value["snapshot"]["files"][0][1] = identity
    value["objects"][0]["name"] = "package.decorated_with_property"
    value["objects"][0]["anchors"][0]["content_sha256"] = identity
    assert pack_generation(value, "proper rated", budget=1024) == ""


def test_file_fact_at_class_line_is_not_an_executable_symbol():
    value = example()
    raw = b"class Container:\n    def execute(self): return 1\n"
    identity = sha256(raw).hexdigest()
    value["source_bytes"]["entry.py"] = base64.b64encode(raw).decode()
    value["snapshot"]["files"][0][1] = identity
    obj = value["objects"][0]
    obj.update(kind="file_ref", name="entry.py")
    obj["anchors"][0]["content_sha256"] = identity
    value["relations"] = []
    result = pack_generation(value, "storage entry.py", budget=1024)
    headers = [line for line in result.splitlines() if line.startswith("[AtMem structure ")]
    assert "storage.py" in headers[0]
    for header in headers:
        if "entry.py:" in header:
            assert "source anchor" in header
            assert "method inventory" not in header and "complete definition" not in header


def test_observed_module_and_renamed_symbol_aliases_nominate_source():
    refs = _references("Fix this:\n```python\nimport vendor as v\nv.process()\n```\n")
    assert _named("src/vendor/service.process", refs)
    assert not _named("src/other/service.process", refs)
    refs = _references("```python\nfrom vendor import convert as fn\nfn()\n```\n")
    assert _named("src/vendor/api.convert", refs)
    refs = _references("import vendor as v\nv.process()")
    assert _named("src/vendor/api.process", refs)


def test_doctest_import_alias_is_parsed_without_running_query_code():
    refs = _references("```pycon\n>>> import vendor as v\n>>> v.process()\nexpected output\n```\n")
    assert _named("src/vendor/api.process", refs)
    refs = _references("```python\nimport vendor as v\nraise RuntimeError('must not run')\nv.process()\n```\n")
    assert _named("src/vendor/api.process", refs)


@pytest.mark.parametrize("body", [
    "import vendor as v\nimport other as v\nv.process()",
    "import vendor as v\nv = object()\nv.process()",
    "import vendor as v\ndef f(v):\n    v.process()",
    "import vendor as v\nfrom other import *\nv.process()",
    "import vendor as v\ndef f():\n    import other as v\n    v.process()",
])
def test_ambiguous_or_rebound_alias_is_not_resolved(body):
    assert not _named("src/vendor/api.process", _references("```python\n" + body + "\n```\n"))


def test_prose_and_dynamic_imports_do_not_create_alias_bindings():
    refs = _references("The phrase 'import vendor as v' appears in prose; v.process() fails.")
    assert not _named("src/vendor/api.process", refs)
    refs = _references("v = __import__('vendor')\nv.process()")
    assert not _named("src/vendor/api.process", refs)


def test_cleanup_annotation_is_static_and_excludes_nested_functions():
    tree = ast.parse("def stream():\n    try:\n        yield value\n    finally:\n        resource.close()\n")
    assert "resource.close@5" in _cleanup_sites(tree.body[0])
    assert "not observed execution" in _cleanup_sites(tree.body[0])
    outer = ast.parse("def outer():\n    def inner():\n        try:\n            yield 1\n        finally:\n            resource.close()\n    return inner\n")
    assert _cleanup_sites(outer.body[0]) == ""


def test_explicit_symbol_beats_keyword_rich_navigation_headings():
    value = example()
    raw = b"def entry():\n    return 1\n"
    identity = sha256(raw).hexdigest()
    value["source_bytes"]["entry.py"] = base64.b64encode(raw).decode()
    value["snapshot"]["files"][0][1] = identity
    value["objects"][0]["anchors"][0]["content_sha256"] = identity
    heading = b"# User entry validation prompts arguments escape sequences\n"
    template = deepcopy(value["objects"][1])
    for i in range(6):
        obj = deepcopy(template)
        obj["object_id"] = "heading-" + str(i)
        obj["name"] = "docs/prompts#user-entry-validation-arguments-escape-sequences"
        path = f"docs-{i}.md"
        obj["anchors"][0].update(path=path, start_line=1, end_line=1, content_sha256=sha256(heading).hexdigest())
        value["objects"].append(obj)
        value["snapshot"]["files"].append([path, sha256(heading).hexdigest()])
        value["source_bytes"][path] = base64.b64encode(heading).decode()
    result = pack_generation(value, "Validate package.entry() user prompts arguments escape sequences", budget=1024)
    assert "def entry():" in result
    if "docs-" in result:
        assert result.index("entry.py") < result.index("docs-")


def test_named_symbol_matching_respects_external_namespaces_and_methods():
    refs = _references("package.run() accepts pathlib.Path(...); preserve Command.execute")
    assert _named("src/package/service.run", refs)
    assert _named("src/package/core.Command.execute", refs)
    assert not _named("src/package/types.Path", refs)
    assert not _named("src/unrelated/run.execute", refs)
    assert not _named("src/package/service.Run", refs)


def test_property_mention_does_not_claim_exact_getter_identity():
    refs = _references("Preserve timeout_seconds while changing connection retries")
    assert _named("network.Config.timeout_seconds", refs)
    assert not _named("network.Config.get_timeout_seconds", refs)
    assert _named("network.Config.get_timeout_seconds", _references("Config.get_timeout_seconds()"))


def test_upstream_call_traversal_delivers_related_implementations():
    result = pack_generation(example(), "entry", budget=4096)
    assert "def entry():" in result
    assert "def middle():" in result
    assert "def storage():" in result


def test_inline_navigation_deduplicates_only_fully_included_targets():
    result = pack_generation(example(), "entry", budget=4096)
    assert "def middle():" in result and "def storage():" in result
    assert "calls: middle (middle.py:1)" not in result
    assert "calls: storage (storage.py:1)" not in result
    value = example()
    raw = ("def storage():\n" + "    data = 'long implementation'\n" * 200).encode()
    identity = sha256(raw).hexdigest()
    value["source_bytes"]["storage.py"] = base64.b64encode(raw).decode()
    value["snapshot"]["files"][2][1] = identity
    value["objects"][2]["anchors"][0]["content_sha256"] = identity
    result = pack_generation(value, "entry", budget=1024)
    assert "def storage():" not in result
    assert "calls: storage (storage.py:1)" in result
    result = pack_generation(value, "entry", budget=4096)
    assert "partial implementation" in result
    assert "calls: storage (storage.py:1)" in result


@pytest.mark.parametrize("budget", [1024, 2048, 4096])
def test_metadata_reduction_preserves_p9_source_and_usage_golden(budget):
    value = example()
    raw = b"def test_entry():\n    assert entry()\n"
    value["source_bytes"]["tests/test_entry.py"] = base64.b64encode(raw).decode()
    value["snapshot"]["files"].append(["tests/test_entry.py", sha256(raw).hexdigest()])
    result = pack_generation(value, "entry", budget=budget)
    canonical = "\n".join(line for line in result.splitlines() if not line.startswith("calls:"))
    # Captured from P9 before note compaction: exact anchors, bodies, usage,
    # order and assurance labels, not merely matching selected names.
    assert sha256(canonical.encode()).hexdigest() == "d861120bd930d20ffa9d395709f5e25fe77283c3ce33aeb617875423c64f8f73"
    assert len(result.encode()) < 613


def test_import_completion_cannot_displace_the_direct_call_path():
    value = example()
    raw = b"def middle():\n    from helpers import imported_worker\n    return imported_worker()\n"
    identity = sha256(raw).hexdigest()
    value["source_bytes"]["middle.py"] = base64.b64encode(raw).decode()
    value["snapshot"]["files"][1][1] = identity
    value["objects"][1]["anchors"][0]["content_sha256"] = identity
    raw = b"def imported_worker():\n    return 1\n"
    identity = sha256(raw).hexdigest()
    obj = deepcopy(value["objects"][2])
    obj.update(object_id="imported", name="helpers.imported_worker")
    obj["anchors"][0].update(path="helpers.py", content_sha256=identity, start_line=1, end_line=2)
    value["objects"].append(obj)
    value["snapshot"]["files"].append(["helpers.py", identity])
    value["source_bytes"]["helpers.py"] = base64.b64encode(raw).decode()
    result = pack_generation(value, "entry", budget=4096)
    assert result.index("def middle():") < result.index("def imported_worker():")


def test_referenced_class_is_a_method_map_with_relevant_method_bodies():
    value = generation()
    raw = ("class Job:\n"
           "    def finish(self):\n        self.done = True\n"
           "    def update(self):\n        self.count += 1\n"
           "    def display(self):\n        return self.count\n"
           "def create_job():\n    return Job()\n").encode()
    identity = sha256(raw).hexdigest()
    template = value["objects"][0]
    value["objects"] = []
    for object_id, name, start, end in (("job", "package.Job", 1, 7),
        ("finish", "package.Job.finish", 2, 3), ("update", "package.Job.update", 4, 5),
        ("display", "package.Job.display", 6, 7), ("factory", "package.create_job", 8, 9)):
        obj = deepcopy(template)
        obj.update(object_id=object_id, name=name)
        obj["anchors"][0].update(path="job.py", content_sha256=identity, start_line=start, end_line=end)
        value["objects"].append(obj)
    value["snapshot"] = {"files": [["job.py", identity]]}
    value["source_bytes"] = {"job.py": base64.b64encode(raw).decode()}
    value["relations"] = []
    result = pack_generation(value, "package.create_job() must finish and update a job", budget=4096)
    assert "method inventory" in result
    # The enclosing header already identifies this file. Repeating its path
    # for every method wastes budget that should hold implementation evidence.
    assert "method finish: 2-3" in result
    assert "method finish: job.py:" not in result
    assert "def finish(self):" in result and "self.done = True" in result
    assert "def update(self):" in result and "self.count += 1" in result


def test_function_local_relative_import_nominates_exact_module_body():
    value = example()
    value["relations"] = []
    value["snapshot"]["files"] = []
    value["source_bytes"] = {}
    for obj, path, name, raw in zip(value["objects"],
            ("pkg/entry.py", "pkg/helpers.py", "other/helpers.py"),
            ("pkg.entry.entry", "pkg.helpers.worker", "other.helpers.worker"),
            (b"def entry():\n    from .helpers import worker as run\n    return run()\n",
             b"def worker():\n    return 'AUTHORIZED_HELPER'\n",
             b"def worker():\n    return 'WRONG_NAMESPACE'\n")):
        identity = sha256(raw).hexdigest()
        obj["name"] = name
        obj["anchors"][0].update(path=path, content_sha256=identity, start_line=1, end_line=len(raw.splitlines()))
        value["snapshot"]["files"].append([path, identity])
        value["source_bytes"][path] = base64.b64encode(raw).decode()
    result = pack_generation(value, "pkg.entry.entry()", budget=900)
    assert "AUTHORIZED_HELPER" in result
    if "WRONG_NAMESPACE" in result:
        assert result.index("AUTHORIZED_HELPER") < result.index("WRONG_NAMESPACE")


def test_current_test_source_without_graph_object_can_explain_usage():
    value = example()
    raw = b"def test_entry():\n    assert entry() == 'expected'\n"
    value["source_bytes"]["tests/test_entry.py"] = base64.b64encode(raw).decode()
    value["snapshot"]["files"].append(["tests/test_entry.py", sha256(raw).hexdigest()])
    result = pack_generation(value, "entry", budget=2048)
    assert "AtMem existing test tests/test_entry.py:1-2" in result
    assert "assert entry() == 'expected'" in result and "not executed" in result
    assert len(result.encode()) <= 2048
    # These excerpts do not become graph objects or authority-bearing facts.
    assert len(value["objects"]) == 3
    value["source_bytes"]["tests/test_entry.py"] = base64.b64encode(b"corrupted").decode()
    with pytest.raises(ValueError, match="source evidence"):
        pack_generation(value, "entry", budget=2048)


def test_usage_selection_is_bounded_and_does_not_run_test_source():
    value = example()
    raw = ("def test_entry():\n    raise RuntimeError('not executed')\n" +
           "    assert entry() == 'value'\n" * 200).encode()
    value["source_bytes"]["tests/test_entry.py"] = base64.b64encode(raw).decode()
    value["snapshot"]["files"].append(["tests/test_entry.py", sha256(raw).hexdigest()])
    result = pack_generation(value, "entry", budget=8192)
    assert "partial source" in result and "omitted" in result
    assert len(result.encode()) <= 8192


def test_demonstrated_api_usage_beats_generic_keyword_overlap():
    from atmem.knowledge.code.packing import _usage_examples, _definitions
    text = ("def test_update_default_value():\n    unrelated.update()\n"
            "def test_processing():\n    progressbar().update()\n")
    result = _usage_examples({"tests/test_bar.py": text.splitlines()},
        {"tests/test_bar.py": _definitions(text)}, {"update", "default", "value"},
        budget=2048, entry_name="progressbar")
    assert "test_processing" in result and "test_update_default_value" not in result


def test_most_relevant_usage_is_fitted_instead_of_replaced_by_shorter_noise():
    from atmem.knowledge.code.packing import _usage_examples, _definitions
    text = ("def test_entry_cache_expiration():\n" +
            "    setup = '東京 cache expiration configuration'\n" * 60 +
            "    assert entry() == 'fresh'\n"
            "def test_cache_expiration():\n    assert unrelated()\n")
    result = _usage_examples({"tests/test_cache.py": text.splitlines()},
        {"tests/test_cache.py": _definitions(text)}, {"entry", "cache", "expiration"},
        budget=600, entry_name="entry")
    assert "test_entry_cache_expiration" in result
    assert "def test_cache_expiration():" not in result
    assert "assert entry() == 'fresh'" in result
    assert "partial source" in result and "source lines omitted" in result
    assert len(result.encode()) <= 600


def test_example_reservation_cannot_displace_connected_implementation():
    value = example()
    raw = ("def middle():\n    total = 0\n" + "    total += 1\n" * 24 + "    return total\n").encode()
    identity = sha256(raw).hexdigest()
    value["source_bytes"]["middle.py"] = base64.b64encode(raw).decode()
    value["snapshot"]["files"][1][1] = identity
    value["objects"][1]["anchors"][0]["content_sha256"] = identity
    # Freeze the original P9 failing-boundary budget. Deriving it from the
    # output under test would shift the scenario when metadata gets shorter.
    budget = 1202
    raw = ("def test_entry():\n" + "    data = 'setup'\n" * 100 + "    assert entry()\n").encode()
    value["source_bytes"]["tests/test_entry.py"] = base64.b64encode(raw).decode()
    value["snapshot"]["files"].append(["tests/test_entry.py", sha256(raw).hexdigest()])
    result = pack_generation(value, "entry", budget=budget)
    for name in ("entry", "middle", "storage"):
        assert f"def {name}():" in result
    assert "AtMem existing test" in result
    assert len(result.encode()) <= budget


@pytest.mark.parametrize("budget", [256, 512, 1024])
def test_usage_window_budget_counts_utf8_headers_and_omission_markers(budget):
    from atmem.knowledge.code.packing import _usage_examples, _definitions
    text = "def test_entry():\n" + "    data = '東京'\n" * 200 + "    assert entry()\n"
    result = _usage_examples({"tests/test_unicode.py": text.splitlines()},
        {"tests/test_unicode.py": _definitions(text)}, {"entry"}, budget=budget, entry_name="entry")
    assert result and "not executed" in result
    assert len(result.encode()) <= budget


def test_typing_only_examples_are_not_behavioral_usage():
    from atmem.knowledge.code.packing import _usage_examples, _definitions
    typing = "def test_entry():\n    assert_type(entry(), str)\n"
    example = "def demo():\n    print(entry())\n"
    sources = {"tests/typing/test_entry.py": typing.splitlines(), "examples/demo.py": example.splitlines()}
    definitions = {"tests/typing/test_entry.py": _definitions(typing), "examples/demo.py": _definitions(example)}
    result = _usage_examples(sources, definitions, {"entry"}, budget=2048, entry_name="entry")
    assert "usage example examples/demo.py" in result and "assert_type" not in result


def test_partial_usage_keeps_multiline_call_with_result_assertion():
    import ast
    from atmem.knowledge.code.packing import _usage_window
    text = ("def test_behavior(runner):\n" + "    irrelevant = '東京 padding'\n" * 30 +
            "    result = runner.invoke(\n        command,\n        ['--value', '42'],\n    )\n"
            "    assert result.exit_code == 0\n")
    body = "\n".join(f"{n}: {line}" for n, line in enumerate(text.splitlines(), 1))
    result = _usage_window(body, {"behavior"}, maximum=240, node=ast.parse(text).body[0])
    assert "result = runner.invoke(" in result
    assert "['--value', '42']" in result and "assert result.exit_code == 0" in result
    assert len(result.encode()) <= 240
    for line in result.splitlines():
        if line[:1].isdigit():
            assert line in body.splitlines()


def test_oversized_call_assertion_group_is_not_split():
    import ast
    from atmem.knowledge.code.packing import _usage_window
    text = "def test_behavior():\n    result = invoke('" + "x" * 400 + "')\n    assert result.ok\n"
    body = "\n".join(f"{n}: {line}" for n, line in enumerate(text.splitlines(), 1))
    result = _usage_window(body, {"behavior"}, maximum=150, node=ast.parse(text).body[0])
    assert "assert result.ok" not in result and "result = invoke" not in result
    assert len(result.encode()) <= 150


def test_call_assertion_links_do_not_cross_blocks_or_nested_scope():
    import ast
    from atmem.knowledge.code.packing import _assertion_groups
    text = ("def test_scope():\n    result = outer()\n    if flag:\n"
            "        assert result.ok\n    def inner():\n        result = inner_call()\n"
            "        assert result.ok\n    assert result.ok\n")
    lines = [f"{n}: {line}" for n, line in enumerate(text.splitlines(), 1)]
    assert _assertion_groups(ast.parse(text).body[0], lines) == []


def test_plain_reassignment_invalidates_old_call_link():
    import ast
    from atmem.knowledge.code.packing import _assertion_groups
    text = "def test_scope():\n    result = invoke()\n    result = 3\n    assert result == 3\n"
    lines = [f"{n}: {line}" for n, line in enumerate(text.splitlines(), 1)]
    assert _assertion_groups(ast.parse(text).body[0], lines) == []
