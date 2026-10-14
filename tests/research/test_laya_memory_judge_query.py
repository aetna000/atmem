from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from research.laya_memory_evidence.judge_query import JudgeQuery
from tests.research.test_laya_memory_duplicate_graph import _seed
from research.laya_memory_evidence.build_duplicate_graph import build_duplicate_graph


def test_judge_queries_are_receipted_and_read_only(tmp_path: Path) -> None:
    database = tmp_path / "work.sqlite3"
    _seed(database)
    build_duplicate_graph(database, include_semantic=False)
    query = JudgeQuery(database, "codex")
    try:
        result = query.list_rows(order="cluster_size")
        assert len(result["rows"]) == 3
        assert result["query_digest"].startswith("sha256:")
        assert query.cluster("candidate-0")["result_ids"] == ["candidate-0", "candidate-1"]
        assert query.lexical("retain")["result_ids"] == ["candidate-2"]
        assert query.aggregate("language")["rows"] == [{"value": "en", "count": 3}]
        with pytest.raises(PermissionError):
            query.own_history("candidate-0")
        with pytest.raises(sqlite3.DatabaseError):
            query.connection.execute("DELETE FROM candidate")
    finally:
        query.close()


def test_interface_rejects_unbounded_or_unapproved_queries(tmp_path: Path) -> None:
    database = tmp_path / "work.sqlite3"
    _seed(database)
    query = JudgeQuery(database, "claude")
    try:
        with pytest.raises(ValueError):
            query.list_rows(limit=501)
        with pytest.raises(ValueError):
            query.aggregate("judgment")
    finally:
        query.close()
