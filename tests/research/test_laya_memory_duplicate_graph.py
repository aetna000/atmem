from __future__ import annotations

import json
from pathlib import Path

from research.laya_memory_evidence.build_duplicate_graph import (
    CandidateText,
    build_duplicate_graph,
    exact_edges,
    exact_fingerprint,
    normalized_text,
)
from research.laya_memory_evidence.workdb import initialize


def _seed(path: Path) -> None:
    db = initialize(path)
    with db:
        db.execute(
            "INSERT INTO source_dataset VALUES ('s', 'org/repo', 'r', 'apache-2.0', 'real', 'proof', 'd', 'now')"
        )
        for number, text in enumerate((" Remember  Café  ", "remember café", "do not retain this")):
            conversation = f"c{number}"
            turn = f"t{number}"
            candidate = f"candidate-{number}"
            db.execute(
                "INSERT INTO conversation VALUES (?, 's', ?, NULL, NULL, ?, 'en', 'Latn', ?)",
                (conversation, conversation, conversation, f"digest-{number}",),
            )
            db.execute(
                "INSERT INTO turn VALUES (?, ?, 0, 'user', ?, ?, ?, NULL)",
                (turn, conversation, text, f"source#{number}", f"turn-digest-{number}"),
            )
            db.execute(
                "INSERT INTO candidate VALUES (?, ?, ?, ?, ?, ?, 'en', '[]', 'eligible', NULL, ?, 'now')",
                (
                    candidate, conversation, turn, conversation,
                    json.dumps({
                        "candidate_turn_id": turn,
                        "turns": [{"turn_id": turn, "role": "user", "content": text}],
                    }),
                    f"input-{number}", conversation,
                ),
            )
    db.close()


def test_unicode_normalization_and_exact_edges() -> None:
    assert normalized_text("  CAFÉ\n") == "café"
    assert exact_fingerprint("CAFÉ") == exact_fingerprint("cafe\u0301")
    rows = [
        CandidateText("a", "scope-a", 0, " Same "),
        CandidateText("b", "scope-b", 0, "same"),
    ]
    assert exact_edges(rows) == [("a", "b", "exact", 1.0, 0)]


def test_exact_graph_covers_singletons_and_is_immutable(tmp_path: Path) -> None:
    database = tmp_path / "work.sqlite3"
    _seed(database)
    result = build_duplicate_graph(database, include_semantic=False)
    assert result["candidates"] == 3
    assert result["clusters"] == 2
    assert result["edges"] == {"exact": 1}
    db = initialize(database)
    assert db.execute("SELECT COUNT(*) FROM duplicate_member").fetchone()[0] == 3
    assert db.execute("SELECT COUNT(*) FROM duplicate_cluster").fetchone()[0] == 2
    db.close()
