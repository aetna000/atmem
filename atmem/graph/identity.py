"""Conservative alias resolution and previewed identity repair."""

from __future__ import annotations

from dataclasses import dataclass
import json
import uuid
from typing import Any

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.store.sqlite import utc_now
from . import _normalize
from .models import IdentityMutationReceipt


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    query: str
    status: str
    entity_id: str | None
    candidate_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


class IdentityService:
    def __init__(self, store: Any) -> None: self.store = store

    def resolve(self, subject_id: str, alias: str) -> IdentityResolution:
        normalized = _normalize(alias)
        rows = self.store._conn.execute(
            """SELECT DISTINCT e.id FROM entities e LEFT JOIN entity_aliases a ON a.entity_id=e.id
               WHERE e.subject_id=? AND e.status='active' AND (e.normalized=? OR (a.normalized=? AND a.status='active')) ORDER BY e.id""",
            (subject_id, normalized, normalized),
        ).fetchall()
        ids = tuple(str(row["id"]) for row in rows)
        if len(ids) == 1: return IdentityResolution(alias, "resolved", ids[0], ids, ("exact_authorized_alias",))
        if len(ids) > 1: return IdentityResolution(alias, "review_required", None, ids, ("ambiguous_alias",))
        return IdentityResolution(alias, "withheld", None, (), ("alias_not_found",))

    def preview(self, subject_id: str, action: str, entity_ids: list[str], *, new_name: str | None = None, alias_id: str | None = None) -> dict[str, Any]:
        if action not in {"merge", "split", "rename", "delete", "supersede"}: raise ValueError("unsupported identity mutation")
        unique = tuple(dict.fromkeys(str(item) for item in entity_ids))
        if not unique: raise ValueError("at least one entity is required")
        placeholders = ",".join("?" for _ in unique)
        entities = [dict(row) for row in self.store._conn.execute(f"SELECT * FROM entities WHERE subject_id=? AND id IN ({placeholders}) ORDER BY id", (subject_id, *unique)).fetchall()]
        if len(entities) != len(unique): raise ValueError("an entity is missing or outside scope")
        if action in {"merge", "supersede"} and len(unique) < 2: raise ValueError("merge/supersede requires a target and source")
        if action in {"rename", "split"} and not str(new_name or "").strip(): raise ValueError("new_name is required")
        aliases = [dict(row) for row in self.store._conn.execute(f"SELECT * FROM entity_aliases WHERE subject_id=? AND entity_id IN ({placeholders}) ORDER BY id", (subject_id, *unique)).fetchall()]
        edges = [dict(row) for row in self.store._conn.execute(f"SELECT * FROM edges WHERE subject_id=? AND (src_entity IN ({placeholders}) OR dst_entity IN ({placeholders})) ORDER BY id", (subject_id, *unique, *unique)).fetchall()]
        body = {"subject_id": subject_id, "action": action, "entity_ids": list(unique), "new_name": new_name, "alias_id": alias_id, "before": {"entities": entities, "aliases": aliases, "edges": edges}}
        return {"format": "atmem-graph-identity-preview-v1", **body, "preview_sha256": sha256_hex(canonical_json(body)), "requires_confirmation": True}

    def commit(self, preview: dict[str, Any], *, confirm_sha256: str, actor: str, reason: str) -> IdentityMutationReceipt:
        if confirm_sha256 != preview.get("preview_sha256"): raise ValueError("identity preview confirmation does not match")
        if not actor.strip() or not reason.strip(): raise ValueError("actor and reason are required")
        subject_id, action = str(preview["subject_id"]), str(preview["action"]); ids = [str(item) for item in preview["entity_ids"]]
        mutation_id = f"gmut_{uuid.uuid4().hex}"; now = utc_now(); created: list[str] = []
        with self.store.transaction():
            if action == "rename":
                name = str(preview["new_name"]).strip(); self.store._conn.execute("UPDATE entities SET canonical=?,normalized=?,updated_at=? WHERE subject_id=? AND id=?", (name, _normalize(name), now, subject_id, ids[0]))
            elif action == "delete":
                self.store._conn.execute("UPDATE entities SET status='tombstoned',updated_at=? WHERE subject_id=? AND id=?", (now, subject_id, ids[0])); self.store._conn.execute("UPDATE entity_aliases SET status='tombstoned' WHERE subject_id=? AND entity_id=?", (subject_id, ids[0])); self.store._conn.execute("UPDATE edges SET status='tombstoned',updated_at=? WHERE subject_id=? AND (src_entity=? OR dst_entity=?)", (now, subject_id, ids[0], ids[0]))
            elif action in {"merge", "supersede"}:
                target = ids[0]
                for source in ids[1:]: self.store._conn.execute("UPDATE entities SET status='merged',merged_into=?,updated_at=? WHERE subject_id=? AND id=?", (target, now, subject_id, source)); self.store._conn.execute("UPDATE entity_aliases SET status='superseded' WHERE subject_id=? AND entity_id=?", (subject_id, source))
            elif action == "split":
                alias_id = str(preview.get("alias_id") or ""); alias = self.store._conn.execute("SELECT * FROM entity_aliases WHERE subject_id=? AND entity_id=? AND id=?", (subject_id, ids[0], alias_id)).fetchone()
                if alias is None: raise ValueError("split requires an alias belonging to the entity")
                name = str(preview["new_name"]).strip(); new_id = f"ent_{uuid.uuid4().hex}"; created.append(new_id)
                self.store._conn.execute("INSERT INTO entities(id,subject_id,canonical,normalized,kind,status,source_record,created_at) VALUES(?,?,?,?,?,'active',?,?)", (new_id, subject_id, name, _normalize(name), "other", alias["source_record"], now)); self.store._conn.execute("UPDATE entity_aliases SET entity_id=? WHERE id=?", (new_id, alias_id))
            after = {"created_entity_ids": created}
            self.store._conn.execute("INSERT INTO graph_identity_mutations VALUES(?,?,?,?,?,?,?,?,?,?,NULL)", (mutation_id, subject_id, action, confirm_sha256, json.dumps(preview["before"], sort_keys=True), json.dumps(after, sort_keys=True), actor, reason, "committed", now))
            self.store._conn.execute("UPDATE graph_generations SET status='repair_required' WHERE subject_id=? AND status='active'", (subject_id,))
        return IdentityMutationReceipt(mutation_id, subject_id, action, confirm_sha256, tuple(ids + created), tuple({"from": item, "to": ids[0]} for item in ids[1:]), None, "repair_required")

    def rollback(self, mutation_id: str, *, actor: str) -> IdentityMutationReceipt:
        row = self.store._conn.execute("SELECT * FROM graph_identity_mutations WHERE mutation_id=?", (mutation_id,)).fetchone()
        if row is None: raise KeyError(mutation_id)
        if row["status"] != "committed": raise ValueError("identity mutation is not rollbackable")
        before, after = json.loads(row["before_json"]), json.loads(row["after_json"])
        with self.store.transaction():
            for entity_id in after.get("created_entity_ids", []): self.store._conn.execute("DELETE FROM entities WHERE id=?", (entity_id,))
            for entity in before["entities"]:
                self.store._conn.execute("UPDATE entities SET canonical=?,normalized=?,kind=?,status=?,merged_into=?,source_record=?,updated_at=? WHERE id=?", (entity["canonical"], entity["normalized"], entity["kind"], entity["status"], entity["merged_into"], entity["source_record"], entity["updated_at"], entity["id"]))
            for alias in before["aliases"]: self.store._conn.execute("UPDATE entity_aliases SET entity_id=?,status=? WHERE id=?", (alias["entity_id"], alias["status"], alias["id"]))
            for edge in before["edges"]: self.store._conn.execute("UPDATE edges SET status=?,src_entity=?,dst_entity=?,updated_at=? WHERE id=?", (edge["status"], edge["src_entity"], edge["dst_entity"], edge["updated_at"], edge["id"]))
            self.store._conn.execute("UPDATE graph_identity_mutations SET status='rolled_back',rolled_back_at=? WHERE mutation_id=?", (utc_now(), mutation_id))
        ids = tuple(str(item["id"]) for item in before["entities"])
        return IdentityMutationReceipt(mutation_id, str(row["subject_id"]), str(row["action"]), str(row["preview_sha256"]), ids, (), None, "rolled_back")
