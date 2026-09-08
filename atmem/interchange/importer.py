"""Transactional, resumable and idempotent neutral archive admission."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
import json
import uuid
from typing import Any, Iterable

from atmem.core.canonical import canonical_json, sha256_hex
from .models import ArchiveRecord, ImportReceipt, ScopeMap
from .plan import ImportPlan, plan_import


class InterchangeImporter:
    def __init__(self, memory: Any) -> None: self.memory = memory

    def dry_run(self, records: Iterable[ArchiveRecord]) -> ImportPlan: return plan_import(self.memory, records)

    def commit(self, records: Iterable[ArchiveRecord], *, approved_source_ids: set[str] | None = None, batch_size: int = 100, interrupt_after_batches: int | None = None) -> ImportReceipt:
        values = tuple(sorted(records, key=lambda item: item.source_id))
        if not values: raise ValueError("archive contains no records")
        scope = values[0].scope
        if any(item.scope != scope for item in values): raise ValueError("one import run requires one explicit scope map")
        plan = self.dry_run(values)
        decisions = {item["source_id"]: item for item in plan.decisions}
        if any(item["requires_review"] and item["source_id"] not in (approved_source_ids or set()) for item in plan.decisions): raise ValueError("review-required decisions must be explicitly approved")
        archive_sha = sha256_hex(canonical_json([item.to_dict() for item in values])); options_sha = sha256_hex(canonical_json({"scope": scope.to_dict(), "approved": sorted(approved_source_ids or ())}))
        store = self.memory.store; now = datetime.now(timezone.utc).isoformat()
        row = store._conn.execute("SELECT * FROM interchange_runs WHERE subject_id=? AND archive_sha256=? AND options_sha256=?", (scope.subject_id, archive_sha, options_sha)).fetchone()
        if row is None:
            run_id = f"imp_{uuid.uuid4().hex}"
            with store.transaction(): store._conn.execute("INSERT INTO interchange_runs VALUES(?,?,?,?,?,?,?,?,?,?)", (run_id, scope.subject_id, archive_sha, options_sha, "running", 0, json.dumps(plan.counts), "[]", now, now))
            checkpoint, affected = 0, []
        else:
            run_id, checkpoint = str(row["run_id"]), int(row["checkpoint"]); affected = json.loads(row["affected_ids_json"])
            if str(row["state"]) == "complete": return self._receipt(row, scope)
        batches = 0
        for start in range(checkpoint, len(values), max(1, batch_size)):
            batch = values[start : start + max(1, batch_size)]
            with store.transaction():
                for item in batch:
                    decision = decisions[item.source_id]
                    if decision["outcome"] not in {"add", "update", "conflict"}: continue
                    result = self.memory.remember(scope.subject_id, item.content, force=True, source_type="user_message", actor="interchange", raw={"interchange_source": item.source, "source_id": item.source_id, "source_sha256": item.sha256, "scope_map": scope.to_dict(), "metadata": item.metadata or {}})
                    ids = [str(row["id"]) for row in result.get("records") or []]; affected.extend(ids)
                    store._conn.execute("INSERT OR IGNORE INTO interchange_items VALUES(?,?,?,?,?,?)", (run_id, item.source_id, item.sha256, decision["outcome"], json.dumps(ids), now))
                checkpoint = min(len(values), start + len(batch))
                store._conn.execute("UPDATE interchange_runs SET checkpoint=?,affected_ids_json=?,updated_at=? WHERE run_id=?", (checkpoint, json.dumps(affected), datetime.now(timezone.utc).isoformat(), run_id))
            batches += 1
            if interrupt_after_batches is not None and batches >= interrupt_after_batches: raise InterruptedError(run_id)
        with store.transaction(): store._conn.execute("UPDATE interchange_runs SET state='complete',updated_at=? WHERE run_id=?", (datetime.now(timezone.utc).isoformat(), run_id))
        final = store._conn.execute("SELECT * FROM interchange_runs WHERE run_id=?", (run_id,)).fetchone()
        return self._receipt(final, scope)

    def rollback(self, run_id: str, scope: ScopeMap) -> ImportReceipt:
        store = self.memory.store; row = store._conn.execute("SELECT * FROM interchange_runs WHERE run_id=? AND subject_id=?", (run_id, scope.subject_id)).fetchone()
        if row is None: raise KeyError(run_id)
        affected = json.loads(row["affected_ids_json"])
        for record_id in affected:
            record = store.get_record(scope.subject_id, record_id)
            if record is not None:
                self.memory.forget_record(scope.subject_id, record_id, actor="interchange-rollback")
        with store.transaction(): store._conn.execute("UPDATE interchange_runs SET state='rolled_back',updated_at=? WHERE run_id=?", (datetime.now(timezone.utc).isoformat(), run_id))
        updated = store._conn.execute("SELECT * FROM interchange_runs WHERE run_id=?", (run_id,)).fetchone()
        receipt = self._receipt(updated, scope); return replace(receipt, rollback=True)

    @staticmethod
    def _receipt(row: Any, scope: ScopeMap) -> ImportReceipt:
        affected = tuple(json.loads(row["affected_ids_json"])); return ImportReceipt(str(row["run_id"]), str(row["archive_sha256"]), str(row["options_sha256"]), scope, {str(k): int(v) for k, v in json.loads(row["counts_json"]).items()}, affected, int(row["checkpoint"]), {"valid": str(row["state"]) in {"complete", "rolled_back"}, "state": str(row["state"]), "affected_count": len(affected)})
