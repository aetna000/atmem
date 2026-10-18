"""Bounded upstream query algorithms over one authorized current generation."""
from atmem.knowledge._vendor.code_retriever import CodeRetriever, _TYPE_BY_KIND
from atmem.knowledge.contracts import StructuralObject, StructuralRelation
from atmem.core.canonical import canonical_json


def graph_input(generation, *, permitted_ids=None):
    objects = [StructuralObject.from_dict(o) for o in generation["objects"]]
    if len(objects) > 10000 or len(generation["relations"]) > 50000:
        raise ValueError("structural graph execution budget exceeded")
    permitted = {o.object_id for o in objects} if permitted_ids is None else set(permitted_ids)
    nodes = []
    for obj in objects:
        if obj.object_id not in permitted:
            continue
        if obj.scope.to_dict() != generation["scope"] or obj.snapshot_id != generation["snapshot_id"]:
            raise PermissionError("mixed-scope or mixed-generation object")
        anchor = obj.anchors[0] if obj.anchors else None
        location = (generation.get("source_locations", {}).get(obj.object_id) or [{}])[0]
        properties = dict(generation["property_variants"].get(obj.object_id, [{}])[0])
        if location.get("kind"):
            properties["source_location_kind"] = location["kind"]
        nodes.append((obj.object_id, {
            "type": "CodeRepository" if obj.kind == "repository" else _TYPE_BY_KIND[obj.kind],
            "name": obj.name, "repo": "repository", "file_path": anchor.path if anchor else location.get("path", ""),
            "line": anchor.start_line if anchor else location.get("line"), "end_line": anchor.end_line if anchor else location.get("end_line"),
            "enola_id": obj.object_id.removeprefix("fact-"),
            "fact_properties": properties,
            "last_snapshot_id": generation["snapshot_id"], "extraction_receipt": generation["receipt"],
        }))
    available = {n[0] for n in nodes}
    repository = generation.get("repository")
    if repository and (permitted_ids is None or repository["id"] in permitted):
        nodes.append((repository["id"], {"type": "CodeRepository", "name": repository["name"],
            "repo": repository["name"], "last_snapshot_id": generation["snapshot_id"],
            "last_delta": repository.get("last_delta") if permitted_ids is None else None,
            "last_receipt": generation["receipt"] if permitted_ids is None else None}))
    edges = []
    for row in generation["relations"]:
        relation = StructuralRelation.from_dict(row)
        # Filtering must precede adjacency construction, including intermediates.
        if relation.source_id in available and relation.target_id in available:
            edges.append((relation.source_id, relation.target_id, relation.kind, {"assurance": relation.assurance}))
    return nodes, edges


def query_generation(generation, *, operation="query_facts", query="", config=None, permitted_ids=None, max_bytes=262144):
    if type(max_bytes) is not int or not 256 <= max_bytes <= 1_000_000:
        raise ValueError("invalid structural response budget")
    if not isinstance(query, str) or len(query.encode()) > 4000:
        raise ValueError("invalid structural query")
    config = {} if config is None else dict(config)
    nodes, edges = graph_input(generation, permitted_ids=permitted_ids)
    result = CodeRetriever(operation=operation, **config).execute(nodes, edges, query)
    envelope = {"status": "current", "snapshot_id": generation["snapshot_id"],
                "generation": generation["generation"], "result": result,
                "coverage": generation["coverage"], "excluded_counts": generation["excluded_counts"]}
    if len(canonical_json(envelope).encode()) > max_bytes:
        return {"status": "withheld", "reason": "response_budget", "snapshot_id": generation["snapshot_id"]}
    return envelope


def query_current(knowledge, root, **kwargs):
    generation = knowledge.current(root)
    if generation is None:
        return {"status": "not_current", "result": None}
    result = query_generation(generation, **kwargs)
    # Revalidate after traversal, not only when loading the graph.
    latest = knowledge.current(root)
    if latest is None or latest["snapshot_id"] != generation["snapshot_id"]:
        return {"status": "withheld", "reason": "source_changed_during_query"}
    return result
