from __future__ import annotations

from pathlib import Path

from research.laya_memory_evidence.build_duplicate_graph import build_duplicate_graph
from research.laya_memory_evidence.judge_worker import build_first_pass_queue, run_worker
from research.laya_memory_evidence.workdb import initialize
from tests.research.test_laya_memory_duplicate_graph import _seed


def _label(candidate: dict) -> dict:
    turn_id = candidate["authorized_input"]["candidate_turn_id"]
    return {
        "disposition": "DO_NOT_STORE", "memory_class": "non_memory",
        "evidence_turn_ids": [turn_id], "supersedes_turn_ids": [],
        "duplicate_of_turn_ids": [], "normalized_memory": None, "meaning": None,
        "confidence": 0.9, "rationale": "No durable future value.",
    }


def test_queue_keeps_clusters_together_and_worker_is_restart_safe(tmp_path: Path) -> None:
    database = tmp_path / "work.sqlite3"
    _seed(database)
    build_duplicate_graph(database, include_semantic=False)
    queued = build_first_pass_queue(database, "codex", target_tokens=1_000, max_rows=2)
    assert queued == {
        "packets": 2, "judge_candidates": 3,
        "public_canonical_candidates": 2, "languages": {"en": 2},
    }

    def fake(batch, **_kwargs):
        return ({row["candidate_id"]: _label(row) for row in batch}, {"output_sha256": "sha256:test"})

    first = run_worker(database, "codex", "test-model", max_packets=1, labeler=fake)
    second = run_worker(database, "codex", "test-model", labeler=fake)
    assert first["labeled_rows"] == 2
    assert second["labeled_rows"] == 1
    db = initialize(database)
    assert db.execute("SELECT COUNT(*) FROM judgment").fetchone()[0] == 3
    assert db.execute("SELECT COUNT(*) FROM query_receipt").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM work_queue WHERE state='complete'").fetchone()[0] == 2
    db.close()
