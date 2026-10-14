import json
import sqlite3

import pytest

from research.laya_memory_evidence.workdb import initialize, integrity_report


def _seed(connection):
    connection.execute(
        "INSERT INTO source_dataset VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("wildchat", "repo", "rev", "license", "organic human conversation",
         "methodology", "sha256:source", "2026-10-13T00:00:00Z"),
    )
    connection.execute(
        "INSERT INTO conversation VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("c1", "wildchat", "source-c1", "u1", "s1", "scope:u1", "english",
         "Latn", "sha256:conversation"),
    )
    connection.execute(
        "INSERT INTO turn VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("t1", "c1", 0, "user", "I prefer concise answers.", "row:1",
         "sha256:turn", None),
    )
    connection.execute(
        "INSERT INTO candidate VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("m1", "c1", "t1", "scope:u1", json.dumps({"candidate_turn_id": "t1"}),
         "sha256:input", "english", "[]", "eligible", None, "group:c1",
         "2026-10-13T00:00:00Z"),
    )
    connection.commit()


def test_schema_initializes_and_reopens(tmp_path):
    path = tmp_path / "work.sqlite3"
    connection = initialize(path)
    _seed(connection)
    assert integrity_report(connection)["integrity"] == "ok"
    connection.close()
    reopened = initialize(path)
    assert integrity_report(reopened)["counts"]["candidate"] == 1


def test_source_and_annotations_are_append_only(tmp_path):
    connection = initialize(tmp_path / "work.sqlite3")
    _seed(connection)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute("UPDATE turn SET content = 'changed' WHERE turn_id = 't1'")


def test_unknown_schema_version_fails_closed(tmp_path):
    path = tmp_path / "work.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 99")
    connection.close()
    with pytest.raises(RuntimeError, match="unsupported"):
        initialize(path)


def test_v1_database_migrates_to_v2(tmp_path):
    path = tmp_path / "work.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 1")
    connection.close()
    migrated = initialize(path)
    assert migrated.execute("PRAGMA user_version").fetchone()[0] == 2
    assert migrated.execute(
        "SELECT mode FROM labeling_policy_event ORDER BY event_id DESC LIMIT 1"
    ).fetchone()[0] == "dual_codex_claude"


def test_final_label_requires_both_frozen_judges(tmp_path):
    connection = initialize(tmp_path / "work.sqlite3")
    _seed(connection)
    decision = json.dumps({"disposition": "STORE", "meaning": {"relation_to_prior": "new"}})
    for judge in ("codex", "claude"):
        run = f"{judge}-first"
        connection.execute(
            "INSERT INTO judge_run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run, judge, "cli", "model", "rubric", "schema", "first_pass", 1,
             "frozen", "start", "end", f"sha256:{judge}"),
        )
        connection.execute(
            "INSERT INTO judgment(candidate_id, run_id, judge, pass_kind, pass_number, "
            "prior_judgment_id, disposition, memory_class, decision_json, decision_digest, "
            "change_reason, query_receipt_ids_json, output_digest, confidence, validation_state, created_at) "
            "VALUES (?, ?, ?, 'first_pass', 1, NULL, 'STORE', 'preference', ?, ?, NULL, '[]', ?, 0.9, 'valid', 'now')",
            ("m1", run, judge, decision, "sha256:decision", f"sha256:{judge}-output"),
        )
    status = connection.execute("SELECT final_status FROM final_label WHERE candidate_id='m1'").fetchone()[0]
    assert status == "pending_freeze"
    views = json.dumps(["duplicate_clusters", "scope_chronology", "stratified", "contradiction_outliers"])
    for judge in ("codex", "claude"):
        connection.execute(
            "INSERT INTO judge_freeze VALUES (?, 'now', 1, ?, ?)",
            (judge, views, f"sha256:{judge}-history"),
        )
    status = connection.execute("SELECT final_status FROM final_label WHERE candidate_id='m1'").fetchone()[0]
    assert status == "agreed"


def test_disclosed_codex_only_mode_can_finalize_after_freeze(tmp_path):
    connection = initialize(tmp_path / "work.sqlite3")
    _seed(connection)
    connection.execute(
        "INSERT INTO labeling_policy_event(mode, reason, created_at) VALUES(?, ?, ?)",
        ("codex_only_credit_exhausted", "Claude CLI allowance exhausted", "now"),
    )
    connection.execute(
        "INSERT INTO judge_run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("codex-first", "codex", "cli", "model", "rubric", "schema",
         "first_pass", 1, "frozen", "start", "end", "sha256:run"),
    )
    decision = json.dumps({"disposition": "STORE", "meaning": {"relation_to_prior": "new"}})
    connection.execute(
        "INSERT INTO judgment(candidate_id, run_id, judge, pass_kind, pass_number, "
        "prior_judgment_id, disposition, memory_class, decision_json, decision_digest, "
        "change_reason, query_receipt_ids_json, output_digest, confidence, validation_state, created_at) "
        "VALUES ('m1', 'codex-first', 'codex', 'first_pass', 1, NULL, 'STORE', "
        "'preference', ?, 'sha256:decision', NULL, '[]', 'sha256:output', 0.9, 'valid', 'now')",
        (decision,),
    )
    views = json.dumps(["duplicate_clusters", "scope_chronology", "stratified", "contradiction_outliers"])
    connection.execute(
        "INSERT INTO judge_freeze VALUES ('codex', 'now', 1, ?, 'sha256:history')",
        (views,),
    )
    status = connection.execute("SELECT final_status FROM final_label WHERE candidate_id='m1'").fetchone()[0]
    assert status == "single_judge_reviewed"
