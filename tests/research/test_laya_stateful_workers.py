import sqlite3

from research.laya_memory_evidence.baseline_worker import _packets, decisions_agree
from research.laya_memory_evidence import challenge_worker


def test_stateful_judge_packets_are_bounded_by_rows_and_prompt_size():
    rows = [object() for _ in range(5)]
    inputs = [
        {"observation": {"content": "x" * size}}
        for size in (10, 10, 90, 10, 10)
    ]
    packets = _packets(
        rows, inputs, batch_size=3, max_packet_chars=120,
    )
    assert [len(packet_rows) for packet_rows, _ in packets] == [2, 1, 2]
    assert [row for packet_rows, _ in packets for row in packet_rows] == rows


def test_independent_passes_must_agree_on_every_supervised_field():
    first = {
        "operation": "STORE_NEW", "memory_class": "preference",
        "target_memory_id": None, "context_sufficient": True,
        "durable": True, "future_utility_level": 3,
        "evidence_memory_ids": ["m2", "m1"], "reason_codes": ["first"],
    }
    verification = {**first, "evidence_memory_ids": ["m1", "m2"], "reason_codes": ["second"]}
    assert decisions_agree(first, verification)
    for key, value in (
        ("memory_class", "episode"), ("durable", False),
        ("future_utility_level", 2), ("context_sufficient", False),
    ):
        changed = {**verification, key: value}
        assert not decisions_agree(first, changed)


def test_challenge_inputs_freeze_and_reuse_one_production_retrieval(tmp_path, monkeypatch):
    path = tmp_path / "work.sqlite3"
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE challenge(
          transition_id TEXT PRIMARY KEY, group_id TEXT, split_family TEXT,
          scope_id TEXT, candidate_id TEXT, content TEXT, source_digest TEXT,
          status TEXT
        );
        INSERT INTO challenge VALUES(
          't1','g1','train','scope-1','c1','Remember blue','sha256:x','ready'
        );
        """
    )
    challenge_worker._migrate(connection)
    row = connection.execute("SELECT * FROM challenge").fetchone()
    calls = []

    def retrieve(_memory, _row):
        calls.append(_row["transition_id"])
        return ([{
            "id": "m1", "content": "Blue", "status": "active",
            "generation": 1, "memory_class": "preference",
            "retrieval_score": 0.9,
        }], {"format": "test-retrieval-receipt"})

    monkeypatch.setattr(challenge_worker, "_retrieve", retrieve)
    first = challenge_worker._inputs(connection, object(), [row])
    second = challenge_worker._inputs(connection, object(), [row])
    assert calls == ["t1"]
    assert first == second
    assert first[0]["current_memories"][0]["id"] == "m1"
    assert connection.execute(
        "SELECT COUNT(*) FROM challenge_retrieval"
    ).fetchone()[0] == 1
    connection.close()


def test_invalid_retry_archives_receipts_without_touching_accepted_rows(tmp_path):
    path = tmp_path / "work.sqlite3"
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE challenge(
          transition_id TEXT PRIMARY KEY, group_id TEXT, split_family TEXT,
          scope_id TEXT, candidate_id TEXT, content TEXT, source_digest TEXT,
          status TEXT
        );
        INSERT INTO challenge VALUES
          ('bad','g1','sealed_test','s1','c1','x','sha256:x','adjudicated'),
          ('good','g2','sealed_test','s2','c2','y','sha256:y','adjudicated');
        """
    )
    challenge_worker._migrate(connection)
    invalid = {
        "operation": "REVIEW", "reason_codes": ["judge_output_validation_failed"]
    }
    valid = {"operation": "DO_NOT_STORE", "reason_codes": ["ephemeral"]}
    for transition_id, accepted, expected in (
        ("bad", 0, invalid), ("good", 1, valid),
    ):
        connection.execute(
            "INSERT INTO challenge_judgment VALUES (?,?,?,?,?,?,?,?)",
            (transition_id, "claude", "first", "{}", "sha256:i", "{}",
             f"sha256:{transition_id}", "2026-01-01T00:00:00Z"),
        )
        connection.execute(
            "INSERT INTO challenge_adjudication VALUES (?,?,?,?,?,?,?,?)",
            (transition_id, "claude", challenge_worker.canonical_json(expected),
             "sha256:pre", f"sha256:post-{transition_id}", accepted,
             f"sha256:receipt-{transition_id}", "2026-01-01T00:00:00Z"),
        )
    connection.commit()
    connection.close()

    result = challenge_worker.archive_and_reset_invalid(
        path, partition="sealed_test", authority="claude",
    )
    assert result == {"archived": 1, "reset": 1}

    connection = sqlite3.connect(path)
    assert connection.execute(
        "SELECT status FROM challenge WHERE transition_id='bad'"
    ).fetchone()[0] == "ready"
    assert connection.execute(
        "SELECT COUNT(*) FROM challenge_failed_attempt WHERE transition_id='bad'"
    ).fetchone()[0] == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM challenge_judgment WHERE transition_id='bad'"
    ).fetchone()[0] == 0
    assert connection.execute(
        "SELECT status FROM challenge WHERE transition_id='good'"
    ).fetchone()[0] == "adjudicated"
    assert connection.execute(
        "SELECT COUNT(*) FROM challenge_judgment WHERE transition_id='good'"
    ).fetchone()[0] == 1
    connection.close()
