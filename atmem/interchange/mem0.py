"""Bounded Mem0 export reader with explicit field-loss reporting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .models import ArchiveRecord, ScopeMap


def read_mem0(source: str | Path | Iterable[dict[str, Any]], *, scope: ScopeMap) -> tuple[list[ArchiveRecord], dict[str, Any]]:
    if isinstance(source, (str, Path)):
        value = json.loads(Path(source).read_text(encoding="utf-8"))
        rows = value.get("memories", value) if isinstance(value, dict) else value
    else:
        rows = list(source)
    if not isinstance(rows, list):
        raise ValueError("Mem0 input must be a list or an object containing memories")
    records: list[ArchiveRecord] = []
    losses: dict[str, int] = {}
    supported = {"id", "memory", "text", "metadata", "created_at", "updated_at", "user_id", "agent_id", "run_id"}
    for index, row in enumerate(rows):
        if not isinstance(row, dict): raise ValueError(f"Mem0 row {index} must be an object")
        source_id = str(row.get("id") or "").strip()
        content = str(row.get("memory") or row.get("text") or "").strip()
        if not source_id or not content: raise ValueError(f"Mem0 row {index} needs id and memory")
        unknown = sorted(set(row) - supported)
        for field in unknown: losses[field] = losses.get(field, 0) + 1
        metadata = dict(row.get("metadata") or {})
        metadata["mem0_created_at"] = row.get("created_at")
        metadata["mem0_updated_at"] = row.get("updated_at")
        records.append(ArchiveRecord(source_id, content, scope, source="mem0", metadata=metadata, evidence=({"kind": "import_source", "source_id": source_id},)))
    return records, {"format": "atmem-mem0-mapping-v1", "input_records": len(rows), "mapped_records": len(records), "unsupported_fields": losses, "scope_map": scope.to_dict()}
