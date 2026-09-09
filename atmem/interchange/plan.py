"""Deterministic, no-write interchange planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from atmem.core.policy import normalize_content
from .models import ArchiveRecord


@dataclass(frozen=True, slots=True)
class ImportPlan:
    decisions: tuple[dict[str, Any], ...]
    counts: dict[str, int]
    requires_review: bool
    format: str = "atmem-memory-import-plan-v1"
    def to_dict(self) -> dict[str, Any]: return {"format": self.format, "decisions": list(self.decisions), "counts": self.counts, "requires_review": self.requires_review}


def plan_import(memory: Any, records: Iterable[ArchiveRecord]) -> ImportPlan:
    rows = tuple(records)
    existing: dict[str, dict[str, Any]] = {}
    for scope in {row.scope.subject_id for row in rows}:
        for record in memory.list(scope, include_inactive=True): existing[normalize_content(str(record.get("content") or ""))] = record
    seen: set[str] = set(); decisions = []; counts = {name: 0 for name in ("add", "update", "conflict", "duplicate", "reject", "skip")}
    for row in sorted(rows, key=lambda item: item.source_id):
        reason = "new_source"; outcome = "add"; review = False
        if row.source_id in seen: outcome, reason = "duplicate", "duplicate_source_id"
        elif not row.content.strip(): outcome, reason = "reject", "empty_content"
        elif normalize_content(row.content) in existing: outcome, reason = "skip", "same_content_exists"
        elif (row.metadata or {}).get("sensitive") or row.status not in {"active", "quarantined"}: outcome, reason, review = "conflict", "review_required", True
        seen.add(row.source_id); counts[outcome] += 1
        decisions.append({"source_id": row.source_id, "source_sha256": row.sha256, "outcome": outcome, "reason_code": reason, "requires_review": review})
    return ImportPlan(tuple(decisions), counts, any(item["requires_review"] for item in decisions))
