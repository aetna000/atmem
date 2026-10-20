"""Independent graph boundary tests and optional pinned-source differentials."""
import ast
from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from atmem.code.contracts import CodeScope
from atmem.knowledge.contracts import StructuralObject, StructuralRelation, SourceAnchor
from atmem.knowledge.code.queries import query_generation, graph_input
from atmem.knowledge._vendor import code_retriever as incorporated


def generation():
    scope = CodeScope("owner", "project", "shared", "codex")
    digest = "a" * 64
    objects = [StructuralObject(name, scope, digest, "symbol", name,
                                (SourceAnchor(name + ".py", digest, 1, 2),), "syntax").to_dict()
               for name in ("entry", "middle", "storage")]
    relations = [StructuralRelation(a, b, "calls", b, "resolver").to_dict()
                 for a, b in (("entry", "middle"), ("middle", "storage"))]
    return {"objects": objects, "relations": relations, "scope": scope.to_dict(), "snapshot_id": digest,
            "generation": 1, "property_variants": {}, "receipt": {}, "coverage": "unit fixture only", "excluded_counts": {}}


@pytest.mark.parametrize("operation,config", [
    ("query_facts", {}), ("explore", {"id": "entry"}), ("traverse", {"start_id": "entry"}),
    ("find_path", {"source_id": "entry", "target_id": "storage"}),
    ("impact_analysis", {"target_id": "storage"}), ("architecture", {}), ("delta", {}), ("insights", {}),
])
def test_supported_query_algorithms_have_structured_results(operation, config):
    result = query_generation(generation(), operation=operation, config=config)
    assert result["status"] == "current" and result["result"]["operation"] == operation


def test_forbidden_intermediate_is_removed_before_path_construction():
    data = generation()
    config = {"source_id": "entry", "target_id": "storage", "type_rollup": False}
    full = query_generation(data, operation="find_path", config=config)
    assert full["result"]["found"]
    restricted = query_generation(data, operation="find_path", config=config, permitted_ids={"entry", "storage"})
    assert not restricted["result"]["found"]
    assert "middle" not in str(restricted)
    assert restricted["result"]["path"] == []


def test_mixed_snapshot_or_subject_is_not_queryable():
    data = generation()
    data["objects"][0]["snapshot_id"] = "b" * 64
    with pytest.raises(PermissionError):
        query_generation(data)
    data = generation()
    data["objects"][0]["scope"]["subject_id"] = "other"
    with pytest.raises(PermissionError):
        query_generation(data)


def test_response_budget_withholds_not_silent_json_truncation():
    result = query_generation(generation(), max_bytes=256)
    assert result["status"] == "withheld" and result["reason"] == "response_budget"


def test_result_is_not_a_mutable_alias_of_stored_properties():
    data = generation()
    data["property_variants"]["entry"] = [{"nested": {"value": 1}}]
    first = query_generation(data)
    entry = next(f for f in first["result"]["facts"] if f["id"] == "entry")
    entry["properties"]["nested"]["value"] = 99
    assert data["property_variants"]["entry"][0]["nested"]["value"] == 1


def test_pinned_original_methods_differential():
    """Compare unchanged original methods, not another handwritten algorithm.

    Source checkout is optional for distributed unit suites. Qualification on the
    maintainer machine must run this test without skipping it.
    """
    checkout = Path("/tmp/atmem-code-research.yKNuul/cognee")
    if not checkout.is_dir():
        pytest.skip("pinned upstream source checkout not present")
    pin = "f154b32a9e544dac73e7ddf2010327cf9988edcd"
    raw = subprocess.check_output(["git", "-C", str(checkout), "show", f"{pin}:cognee/modules/retrieval/code_retriever.py"], text=True)
    tree = ast.parse(raw)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CodeRetriever")
    cls.bases = []
    # Constructor + algorithms compiled directly from the original blob;
    # backend imports are intentionally not initialized for this pure test.
    namespace = vars(incorporated).copy()
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), "pinned-upstream", "exec"), namespace)
    original = namespace["CodeRetriever"]
    nodes, edges = graph_input(generation())
    snapshot = incorporated._CodeGraphSnapshot(nodes, edges)
    for operation, config in [
        ("query_facts", {}), ("explore", {"id": "entry"}), ("traverse", {"start_id": "entry"}),
        ("find_path", {"source_id": "entry", "target_id": "storage"}),
        ("impact_analysis", {"target_id": "storage"}), ("architecture", {}), ("delta", {}), ("insights", {}),
    ]:
        before = original(operation=operation, **config)
        expected = getattr(before, "_" + operation)(snapshot, "")
        if before.diagram_format:
            expected["diagram"] = incorporated.render_result_diagram(expected, before.diagram_format)
        actual = query_generation(deepcopy(generation()), operation=operation, config=config)["result"]
        assert actual == expected
