"""Adapt Enola writer identities, retaining unresolved and conflicting evidence.

Unlike the upstream name-only loader, IDs include the source file. No arbitrary
name resolution is permitted. This is a projection proposal, not admission.
"""
from collections import defaultdict
from hashlib import sha256
from pathlib import PurePosixPath

from atmem.knowledge._vendor.enola_contract import normalize_relation, relation_target_id
from atmem.knowledge.contracts import SourceAnchor, SourceSnapshot, StructuralObject, StructuralRelation


def map_facts(snapshot: SourceSnapshot, facts: list[dict], *, source_bytes=None):
    files = dict(snapshot.files)
    # These are properties of the snapshot, not of each fact. Recomputing a
    # several-thousand-file digest (and splitting the same file) per symbol
    # makes larger repositories needlessly quadratic.
    snapshot_id = snapshot.snapshot_id
    line_counts = {}
    if source_bytes is not None:
        for file, data in source_bytes.items():
            if file not in files or sha256(data).hexdigest() != files[file]:
                raise ValueError("source bytes do not match snapshot")
            line_counts[file] = max(1, len(data.splitlines()))
    grouped = defaultdict(list)
    for fact in facts:
        grouped[fact["id"]].append(fact)
    objects, relations, properties, conflicts, locations = [], [], {}, [], {}
    for writer_id, rows in sorted(grouped.items()):
        row = rows[0]
        anchors = set()
        for fact in rows:
            file = fact.get("file")
            if file:
                # Upstream modules and explicitly derived module-edge rollups
                # can name package directories. Neither supplies a file span.
                # Do not generalize this allowance to arbitrary dependencies.
                props = fact.get("props", {})
                module_rollup = (fact["kind"] == "dependency"
                    and isinstance(props, dict)
                    and props.get("coupling_kind") == props.get("derived") == "symbol-rollup"
                    and fact["name"].startswith("module-edge: " + file + " -> "))
                ansible_role = (fact["kind"] == "symbol" and isinstance(props, dict)
                    and props.get("language") == "ansible" and props.get("ansible_kind") == "role"
                    and props.get("symbol_kind") == "type")
                directory = ((fact["kind"] == "module" or module_rollup or ansible_role)
                    and (file == "." or any(p.startswith(file + "/") for p in files)))
                account = fact["kind"] == "extraction" and file == fact["repo"]
                # Enola's Ruby/PHP rollups use <source-dir>/_coupling.rb/.php,
                # not a file it read. Bind both directories to admitted source;
                # do not turn this virtual location into a source span/hash.
                endpoints = fact["name"].split(" -> ")
                virtual_rollup = (fact["kind"] == "dependency" and isinstance(props, dict)
                    and props.get("synthetic_coupling") is True and props.get("source") == "internal"
                    and ((props.get("language") == "ruby" and props.get("coupling_kind") == "require"
                          and PurePosixPath(file).name == "_coupling.rb")
                         or (props.get("language") == "php" and PurePosixPath(file).name == "_coupling.php"))
                    and len(endpoints) == 2
                    and str(PurePosixPath(file).parent) == endpoints[0]
                    and all(part == "." or any(p.startswith(part + "/") for p in files) for part in endpoints))
                if file not in files and not directory and not account and not virtual_rollup:
                    raise ValueError("fact source is outside the authorized snapshot")
                if file in files:
                    if source_bytes is not None and file not in line_counts:
                        raise ValueError("source bytes do not match snapshot")
                    start = fact.get("line")
                    if start is not None:
                        anchor = SourceAnchor(file, files[file], start, fact.get("end_line", start))
                        if source_bytes is not None and anchor.end_line > line_counts[file]:
                            raise ValueError("measured source span exceeds actual file")
                        anchors.add(anchor)
                    locations.setdefault("fact-" + writer_id, []).append({"path": file, "content_sha256": files[file],
                                                                          "line": start, "end_line": fact.get("end_line", start)})
                else:
                    locations.setdefault("fact-" + writer_id, []).append({"path": file, "content_sha256": None,
                        "line": None, "end_line": None, "kind": "extractor_virtual" if virtual_rollup else "directory" if directory else "extraction_account"})
            if fact.get("props", {}) != row.get("props", {}):
                conflicts.append({"object_id": "fact-" + writer_id, "reason": "conflicting_properties"})
            for rel in fact.get("relations", []):
                kind, name = normalize_relation(rel)
                target = relation_target_id(rel)
                resolved = target in grouped
                relations.append(StructuralRelation("fact-" + writer_id, "fact-" + target if resolved else None,
                                                    kind, name, "resolver" if resolved else "unresolved"))
        obj = StructuralObject("fact-" + writer_id, snapshot.scope, snapshot_id, row["kind"], row["name"],
                               tuple(sorted(anchors, key=lambda a: (a.path, a.start_line, a.end_line))),
                               "declared" if row["kind"] in {"intent", "extraction"} else
                               "heuristic" if row["kind"] == "insight" else "syntax")
        objects.append(obj)
        properties[obj.object_id] = [r.get("props", {}) for r in rows]
    return {"objects": objects, "relations": sorted(set(relations), key=lambda r: (r.source_id, r.kind, r.target_name, r.target_id or "")),
            "property_variants": properties, "conflicts": conflicts, "source_locations": locations}
