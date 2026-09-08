"""Streaming authorized neutral export."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any, Iterator

from atmem.core.canonical import canonical_json, sha256_hex
from .models import ArchiveManifest, ArchiveRecord, ScopeMap


def iter_archive(memory: Any, scope: ScopeMap, *, include_inactive: bool = False) -> Iterator[ArchiveRecord]:
    for row in memory.list(scope.subject_id, include_inactive=include_inactive):
        if not include_inactive and row.get("status") != "active": continue
        raw = row.get("raw") or {}
        yield ArchiveRecord(str(row["id"]), str(row["content"]), scope, status=str(row["status"]), source="atmem", metadata={"fact_key": row.get("fact_key"), "created_at": row.get("created_at")}, history=tuple(raw.get("history") or ()), evidence=({"record_id": row["id"], "content_sha256": sha256_hex(str(row["content"]))},))


def export_archive(memory: Any, scope: ScopeMap, destination: str | Path, *, include_inactive: bool = False) -> dict[str, Any]:
    records = tuple(iter_archive(memory, scope, include_inactive=include_inactive))
    digest = sha256_hex(canonical_json([record.to_dict() for record in records]))
    manifest = ArchiveManifest(f"arc_{uuid.uuid4().hex}", datetime.now(timezone.utc).isoformat(), len(records), digest, "atmem")
    path = Path(destination)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "manifest", "value": manifest.to_dict()}, sort_keys=True) + "\n")
        for record in records: handle.write(json.dumps({"type": "record", "value": record.to_dict(), "sha256": record.sha256}, sort_keys=True) + "\n")
    archive_sha256 = sha256_hex(path.read_bytes())
    return {"format": "atmem-memory-export-receipt-v1", "path": str(path), "archive_sha256": archive_sha256, "manifest": manifest.to_dict(), "scope_map": scope.to_dict()}


def read_archive(source: str | Path) -> tuple[ArchiveManifest, list[ArchiveRecord]]:
    """Read and verify the v1 neutral JSONL archive before store access."""
    lines = Path(source).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("archive is empty")
    first = json.loads(lines[0])
    raw_manifest = first.get("value", {}) if first.get("type") == "manifest" else {}
    if raw_manifest.get("format") != "atmem-memory-archive-v1" or raw_manifest.get("version") != "1":
        raise ValueError("unsupported archive format or version")
    manifest = ArchiveManifest(**raw_manifest)
    records: list[ArchiveRecord] = []
    for line in lines[1:]:
        envelope = json.loads(line)
        value = dict(envelope.get("value", {}))
        scope = ScopeMap(**value.pop("scope"))
        record = ArchiveRecord(scope=scope, history=tuple(value.pop("history", ())), evidence=tuple(value.pop("evidence", ())), **value)
        if envelope.get("sha256") != record.sha256:
            raise ValueError("archive record digest mismatch")
        records.append(record)
    if len(records) != manifest.record_count or sha256_hex(canonical_json([r.to_dict() for r in records])) != manifest.records_sha256:
        raise ValueError("archive manifest digest mismatch")
    return manifest, records
