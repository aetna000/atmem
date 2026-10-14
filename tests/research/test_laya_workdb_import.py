import json

from research.laya_memory_evidence.build_dataset import MANIFEST_FORMAT
from research.laya_memory_evidence.import_workdb import import_candidates
from research.laya_memory_evidence.workdb import initialize


def test_imports_authentic_candidate_idempotently(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    candidate = {
        "candidate_id": "m1",
        "input_digest": "sha256:input",
        "authorized_input": {
            "candidate_turn_id": "t0",
            "prior_user_turn_ids": [],
            "turns": [{"turn_id": "t0", "role": "user", "content": "I prefer concise answers."}],
        },
        "provenance": {
            "source": "wildchat-1m", "group_id": "g1", "record_id": "row:1",
            "language": "english",
        },
    }
    data = json.dumps(candidate) + "\n"
    (root / "candidates.jsonl").write_text(data, encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({
        "format": MANIFEST_FORMAT,
        "rows": 1,
        "unlabeled": True,
        "generated_or_translated_conversations": 0,
        "files": {"candidates.jsonl": {"sha256": "sha256:data"}},
        "source_revisions": {"wildchat-1m": {
            "repo_id": "repo", "revision": "rev", "license": "license",
        }},
    }), encoding="utf-8")
    database = tmp_path / "work.sqlite3"
    first = import_candidates(database, root)
    second = import_candidates(database, root)
    assert first["inserted"]["candidates"] == 1
    assert second["inserted"]["candidates"] == 0
    connection = initialize(database)
    assert connection.execute("SELECT content FROM turn").fetchone()[0] == "I prefer concise answers."


def test_rejects_generated_candidate_manifest(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "candidates.jsonl").write_text("", encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({
        "format": MANIFEST_FORMAT,
        "generated_or_translated_conversations": 1,
    }), encoding="utf-8")
    try:
        import_candidates(tmp_path / "work.sqlite3", root)
    except ValueError as error:
        assert "forbidden" in str(error)
    else:
        raise AssertionError("generated content was accepted")


def test_imports_multiple_candidate_windows_from_one_conversation(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    common = {"source": "wildchat-1m", "group_id": "g1", "language": "english"}
    rows = [
        {
            "candidate_id": "m1", "input_digest": "sha256:one",
            "authorized_input": {"candidate_turn_id": "t0000", "prior_user_turn_ids": [],
                                 "turns": [{"turn_id": "t0000", "role": "user", "content": "one"}]},
            "provenance": {**common, "record_id": "row:1"},
        },
        {
            "candidate_id": "m2", "input_digest": "sha256:two",
            "authorized_input": {"candidate_turn_id": "t0002", "prior_user_turn_ids": ["t0000"],
                                 "turns": [
                                     {"turn_id": "t0000", "role": "user", "content": "one"},
                                     {"turn_id": "t0001", "role": "assistant", "content": "reply"},
                                     {"turn_id": "t0002", "role": "user", "content": "two"},
                                 ]},
            "provenance": {**common, "record_id": "row:1"},
        },
    ]
    (root / "candidates.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    (root / "manifest.json").write_text(json.dumps({
        "format": MANIFEST_FORMAT, "rows": 2, "unlabeled": True,
        "generated_or_translated_conversations": 0,
        "files": {"candidates.jsonl": {"sha256": "sha256:data"}},
        "source_revisions": {"wildchat-1m": {
            "repo_id": "repo", "revision": "rev", "license": "license",
        }},
    }))
    database = tmp_path / "work.sqlite3"
    import_candidates(database, root)
    connection = initialize(database)
    assert connection.execute("SELECT COUNT(*) FROM conversation").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM turn").fetchone()[0] == 3
    assert connection.execute("SELECT COUNT(*) FROM candidate").fetchone()[0] == 2
    assert [row[0] for row in connection.execute("SELECT turn_order FROM turn ORDER BY turn_order")] == [0, 1, 2]
