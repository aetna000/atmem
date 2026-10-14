from __future__ import annotations

import json
from pathlib import Path

from research.laya_memory_evidence.build_duplicate_graph import build_duplicate_graph
from research.laya_memory_evidence.judge_worker import build_first_pass_queue, run_worker
from research.laya_memory_evidence.review_worker import (
    build_review_queue,
    freeze_judge,
    run_review_pass,
)
from research.laya_memory_evidence.workdb import REVIEW_VIEWS, initialize
from tests.research.test_laya_memory_duplicate_graph import _seed
from tests.research.test_laya_memory_judge_worker import _label


def test_all_review_views_complete_before_freeze(tmp_path: Path) -> None:
    database = tmp_path / "work.sqlite3"
    _seed(database)
    build_duplicate_graph(database, include_semantic=False)
    build_first_pass_queue(database, "codex", target_tokens=1_000, max_rows=2)

    def first_pass(batch, **_kwargs):
        return ({row["candidate_id"]: _label(row) for row in batch}, {"output_sha256": "sha256:first"})

    run_worker(database, "codex", "test-model", labeler=first_pass)

    def unchanged(prompt, **_kwargs):
        items = json.loads(prompt.split("REVIEW ITEMS:\n", 1)[1])
        return ({"labels": [
            {"candidate_id": item["candidate_id"], "label": item["prior_label"],
             "change_reason": "unchanged after review"}
            for item in items
        ]}, {"output_sha256": "sha256:review"})

    for view in REVIEW_VIEWS:
        build_review_queue(database, "codex", view, 1, target_tokens=1_000, max_rows=2)
        result = run_review_pass(
            database, "codex", "test-model", view, 1, reviewer=unchanged,
        )
        assert result["changed"] == 0
        assert result["remaining"] == 0
    frozen = freeze_judge(database, "codex")
    assert frozen["first_pass_rows"] == 3
    db = initialize(database)
    assert db.execute("SELECT COUNT(*) FROM judge_freeze").fetchone()[0] == 1
    db.close()
