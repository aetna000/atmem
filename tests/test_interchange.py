from __future__ import annotations

import json

import pytest

from atmem import Memory
from atmem.interchange import ArchiveRecord, InterchangeImporter, ScopeMap, export_archive, read_archive, read_mem0


def _scope(subject="alice") -> ScopeMap:
    return ScopeMap(subject, "workspace", "main")


def test_mem0_mapping_dry_run_interrupt_resume_replay_and_rollback(tmp_path) -> None:
    memory = Memory(tmp_path / "memory.db")
    records, mapping = read_mem0([{"id": "one", "memory": "My city is Sydney.", "unknown": "reported"}, {"id": "two", "memory": "My timezone is UTC."}], scope=_scope())
    assert mapping["unsupported_fields"] == {"unknown": 1}
    importer = InterchangeImporter(memory)
    assert importer.dry_run(records).counts["add"] == 2
    with pytest.raises(InterruptedError):
        importer.commit(records, batch_size=1, interrupt_after_batches=1)
    receipt = importer.commit(records, batch_size=1)
    assert receipt.verification["valid"] and receipt.checkpoint == 2
    assert importer.commit(records).run_id == receipt.run_id
    rolled = importer.rollback(receipt.run_id, _scope())
    assert rolled.rollback and memory.list("alice") == []
    memory.close()


def test_neutral_export_is_scope_bound_and_digest_verified(tmp_path) -> None:
    memory = Memory(":memory:")
    memory.remember("alice", "My city is Sydney.")
    memory.remember("bob", "My city is Melbourne.")
    receipt = export_archive(memory, _scope(), tmp_path / "archive.jsonl")
    lines = [json.loads(line) for line in (tmp_path / "archive.jsonl").read_text().splitlines()]
    assert receipt["manifest"]["record_count"] == 1
    assert lines[1]["value"]["scope"]["subject_id"] == "alice"
    assert "Melbourne" not in str(lines)
    memory.close()


def test_missing_scope_and_review_conflict_fail_closed() -> None:
    with pytest.raises(ValueError, match="explicit complete scope"):
        _scope("")
    memory = Memory(":memory:")
    record = ArchiveRecord("one", "Sensitive", _scope(), metadata={"sensitive": True})
    importer = InterchangeImporter(memory)
    assert importer.dry_run([record]).requires_review
    with pytest.raises(ValueError, match="explicitly approved"):
        importer.commit([record])
    memory.close()


def test_neutral_round_trip_and_tamper_rejection(tmp_path) -> None:
    memory=Memory(":memory:"); memory.remember("alice","Synthetic archive value.",force=True); target=tmp_path/"archive.jsonl"; export_archive(memory,_scope(),target)
    manifest,records=read_archive(target); assert manifest.record_count==len(records)==1
    target.write_text(target.read_text().replace("Synthetic", "Tampered", 1))
    with pytest.raises(ValueError,match="digest"): read_archive(target)
    memory.close()
