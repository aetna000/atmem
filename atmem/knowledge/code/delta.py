"""Exact, source-bound projection changes; not runtime impact or intent."""
from datetime import datetime, timezone

from atmem.core.canonical import canonical_json


def generation_delta(prior, current):
    def objects(value):
        return {obj["object_id"]: canonical_json({
            "object": {k: v for k, v in obj.items() if k != "snapshot_id"},
            "properties": value["property_variants"].get(obj["object_id"], []),
            "locations": value.get("source_locations", {}).get(obj["object_id"], []),
        }) for obj in value.get("objects", [])}
    def edges(value):
        return {canonical_json(row) for row in value.get("relations", []) if row["target_id"] is not None}
    prior = prior or {}
    before, after = objects(prior), objects(current)
    added, removed = after.keys() - before.keys(), before.keys() - after.keys()
    updated = {key for key in after.keys() & before.keys() if before[key] != after[key]}
    old_edges, new_edges = edges(prior), edges(current)
    names = {row["object_id"]: row["name"] for value in (prior, current) for row in value.get("objects", [])}
    old_files = dict(prior.get("snapshot", {}).get("files", []))
    new_files = dict(current["snapshot"]["files"])
    return {"format": "atmem-code-generation-delta-v1", "basis": "exact source-bound objects/properties/locations and resolved edges; not runtime behavior",
        "previous_snapshot_id": prior.get("snapshot_id"), "snapshot_id": current["snapshot_id"],
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "nodes_added": len(added), "nodes_updated": len(updated), "nodes_removed": len(removed),
        "nodes_unchanged": len(after.keys() & before.keys()) - len(updated),
        "edges_added": len(new_edges - old_edges), "edges_removed": len(old_edges - new_edges),
        "samples_added": sorted(names[key] for key in added)[:20],
        "samples_updated": sorted(names[key] for key in updated)[:20],
        "samples_removed": sorted(names[key] for key in removed)[:20],
        "files_added": len(new_files.keys() - old_files.keys()), "files_removed": len(old_files.keys() - new_files.keys()),
        "files_changed": sum(old_files[key] != new_files[key] for key in old_files.keys() & new_files.keys())}
