"""Restricted, receipted read-only queries for independent CLI judges."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable


MAX_LIMIT = 500


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _authorizer(action: int, _arg1: str | None, _arg2: str | None, _db: str, _trigger: str | None) -> int:
    allowed = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_PRAGMA,
    }
    return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY


class JudgeQuery:
    """A deliberately small query vocabulary over an immutable snapshot."""

    def __init__(self, database: Path, judge: str, *, include_own_history: bool = False) -> None:
        if judge not in {"codex", "claude"}:
            raise ValueError("judge must be codex or claude")
        self.judge = judge
        self.include_own_history = include_own_history
        # mode=ro still observes a live WAL; immutable=1 would silently ignore it.
        uri = f"file:{database.resolve()}?mode=ro"
        self.connection = sqlite3.connect(uri, uri=True)
        self.connection.row_factory = sqlite3.Row
        self.connection.set_authorizer(_authorizer)
        self.connection.execute("PRAGMA query_only = ON")

    def close(self) -> None:
        self.connection.close()

    def _result(self, kind: str, parameters: dict[str, Any], rows: Iterable[sqlite3.Row]) -> dict[str, Any]:
        values = [dict(row) for row in rows]
        ids = [row.get("candidate_id") for row in values if row.get("candidate_id")]
        core = {"judge": self.judge, "query_kind": kind, "parameters": parameters, "result_ids": ids}
        return {**core, "rows": values, "query_digest": _digest(core)}

    @staticmethod
    def _limit(value: int) -> int:
        if value < 1 or value > MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
        return value

    def row(self, candidate_id: str) -> dict[str, Any]:
        parameters = {"candidate_id": candidate_id}
        rows = self.connection.execute(
            """
            SELECT c.candidate_id, c.scope_key, c.language, c.risk_tags_json,
                   c.authorized_input_json, c.input_digest, c.source_split_key,
                   co.source_id, co.source_conversation_id, dm.cluster_id
            FROM candidate c
            JOIN conversation co ON co.conversation_id = c.conversation_id
            LEFT JOIN duplicate_member dm ON dm.candidate_id = c.candidate_id
            WHERE c.candidate_id = ? AND c.eligibility = 'eligible'
            """,
            (candidate_id,),
        )
        return self._result("row", parameters, rows)

    def scope(self, scope_key: str, *, limit: int = 200) -> dict[str, Any]:
        limit = self._limit(limit)
        parameters = {"scope_key": scope_key, "limit": limit}
        rows = self.connection.execute(
            """
            SELECT c.candidate_id, c.scope_key, c.language, t.turn_order,
                   t.turn_id AS candidate_turn_id, t.content AS candidate_text
            FROM candidate c JOIN turn t ON t.turn_id = c.candidate_turn_id
            WHERE c.scope_key = ? AND c.eligibility = 'eligible'
            ORDER BY t.turn_order, c.candidate_id LIMIT ?
            """,
            (scope_key, limit),
        )
        return self._result("scope", parameters, rows)

    def chronology(self, candidate_id: str, *, limit: int = 200) -> dict[str, Any]:
        limit = self._limit(limit)
        parameters = {"candidate_id": candidate_id, "limit": limit}
        rows = self.connection.execute(
            """
            SELECT c.candidate_id, t.turn_id, t.turn_order, t.role, t.content, t.observed_at
            FROM candidate c
            JOIN turn candidate_turn ON candidate_turn.turn_id = c.candidate_turn_id
            JOIN turn t ON t.conversation_id = c.conversation_id
                       AND t.turn_order <= candidate_turn.turn_order
            WHERE c.candidate_id = ?
            ORDER BY t.turn_order LIMIT ?
            """,
            (candidate_id, limit),
        )
        return self._result("chronology", parameters, rows)

    def cluster(self, candidate_id: str, *, limit: int = 200) -> dict[str, Any]:
        limit = self._limit(limit)
        parameters = {"candidate_id": candidate_id, "limit": limit}
        rows = self.connection.execute(
            """
            SELECT member.candidate_id, candidate.scope_key, candidate.language,
                   turn.content AS candidate_text, cluster.canonical_candidate_id,
                   member.cluster_id
            FROM duplicate_member seed
            JOIN duplicate_member member ON member.cluster_id = seed.cluster_id
            JOIN duplicate_cluster cluster ON cluster.cluster_id = member.cluster_id
            JOIN candidate ON candidate.candidate_id = member.candidate_id
            JOIN turn ON turn.turn_id = candidate.candidate_turn_id
            WHERE seed.candidate_id = ?
            ORDER BY member.candidate_id LIMIT ?
            """,
            (candidate_id, limit),
        )
        return self._result("cluster", parameters, rows)

    def list_rows(
        self,
        *,
        language: str | None = None,
        source_id: str | None = None,
        risk_tag: str | None = None,
        cluster_size_min: int = 1,
        order: str = "candidate_id",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        limit = self._limit(limit)
        orders = {
            "candidate_id": "c.candidate_id",
            "language": "c.language, c.candidate_id",
            "cluster_size": "cluster_size DESC, c.candidate_id",
            "scope": "c.scope_key, c.candidate_id",
        }
        if order not in orders:
            raise ValueError(f"unsupported order: {order}")
        if cluster_size_min < 1 or offset < 0:
            raise ValueError("cluster_size_min must be positive and offset nonnegative")
        filters = ["c.eligibility = 'eligible'"]
        values: list[Any] = []
        if language:
            filters.append("c.language = ?")
            values.append(language)
        if source_id:
            filters.append("co.source_id = ?")
            values.append(source_id)
        if risk_tag:
            filters.append("EXISTS (SELECT 1 FROM json_each(c.risk_tags_json) WHERE value = ?)")
            values.append(risk_tag)
        filters.append("COALESCE(cs.cluster_size, 1) >= ?")
        values.extend((cluster_size_min, limit, offset))
        parameters = {
            "language": language, "source_id": source_id, "risk_tag": risk_tag,
            "cluster_size_min": cluster_size_min,
            "order": order, "limit": limit, "offset": offset,
        }
        rows = self.connection.execute(
            f"""
            SELECT c.candidate_id, c.scope_key, c.language, co.source_id,
                   dm.cluster_id, COALESCE(cs.cluster_size, 1) AS cluster_size,
                   t.content AS candidate_text
            FROM candidate c
            JOIN conversation co ON co.conversation_id = c.conversation_id
            JOIN turn t ON t.turn_id = c.candidate_turn_id
            LEFT JOIN duplicate_member dm ON dm.candidate_id = c.candidate_id
            LEFT JOIN (
                SELECT cluster_id, COUNT(*) AS cluster_size
                FROM duplicate_member GROUP BY cluster_id
            ) cs ON cs.cluster_id = dm.cluster_id
            WHERE {' AND '.join(filters)}
            ORDER BY {orders[order]} LIMIT ? OFFSET ?
            """,
            values,
        )
        return self._result("list", parameters, rows)

    def lexical(self, text: str, *, language: str | None = None, limit: int = 100) -> dict[str, Any]:
        limit = self._limit(limit)
        if not text.strip():
            raise ValueError("search text cannot be empty")
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where = ["t.content LIKE ? ESCAPE '\\'"]
        values: list[Any] = [f"%{escaped}%"]
        if language:
            where.append("c.language = ?")
            values.append(language)
        values.append(limit)
        parameters = {"text": text, "language": language, "limit": limit}
        rows = self.connection.execute(
            f"""
            SELECT c.candidate_id, c.scope_key, c.language, t.content AS candidate_text
            FROM candidate c JOIN turn t ON t.turn_id = c.candidate_turn_id
            WHERE {' AND '.join(where)} ORDER BY c.candidate_id LIMIT ?
            """,
            values,
        )
        return self._result("lexical", parameters, rows)

    def semantic(self, candidate_id: str, *, limit: int = 100) -> dict[str, Any]:
        limit = self._limit(limit)
        parameters = {"candidate_id": candidate_id, "limit": limit}
        rows = self.connection.execute(
            """
            SELECT CASE WHEN de.left_candidate_id = ? THEN de.right_candidate_id
                        ELSE de.left_candidate_id END AS candidate_id,
                   de.edge_kind, de.score, de.same_scope, de.method_revision,
                   t.content AS candidate_text
            FROM duplicate_edge de
            JOIN candidate c ON c.candidate_id = CASE
                WHEN de.left_candidate_id = ? THEN de.right_candidate_id ELSE de.left_candidate_id END
            JOIN turn t ON t.turn_id = c.candidate_turn_id
            WHERE de.left_candidate_id = ? OR de.right_candidate_id = ?
            ORDER BY de.score DESC, candidate_id LIMIT ?
            """,
            (candidate_id, candidate_id, candidate_id, candidate_id, limit),
        )
        return self._result("semantic", parameters, rows)

    def own_history(self, candidate_id: str, *, limit: int = 20) -> dict[str, Any]:
        if not self.include_own_history:
            raise PermissionError("own judgment history is unavailable during an independent first pass")
        limit = self._limit(limit)
        parameters = {"candidate_id": candidate_id, "limit": limit}
        rows = self.connection.execute(
            """
            SELECT j.candidate_id, j.judgment_id, j.pass_kind, j.pass_number,
                   j.decision_json, j.decision_digest, j.change_reason, j.confidence,
                   j.created_at
            FROM judgment j
            WHERE j.candidate_id = ? AND j.judge = ?
            ORDER BY j.judgment_id DESC LIMIT ?
            """,
            (candidate_id, self.judge, limit),
        )
        return self._result("own_history", parameters, rows)

    def aggregate(self, dimension: str) -> dict[str, Any]:
        dimensions = {
            "language": ("c.language", "candidate c"),
            "source": ("co.source_id", "candidate c JOIN conversation co ON co.conversation_id=c.conversation_id"),
            "cluster_size": (
                "cluster_size",
                "(SELECT cluster_id, COUNT(*) AS cluster_size FROM duplicate_member GROUP BY cluster_id) c",
            ),
            "risk_tag": (
                "j.value",
                "candidate c, json_each(c.risk_tags_json) j",
            ),
        }
        if dimension not in dimensions:
            raise ValueError(f"unsupported aggregate dimension: {dimension}")
        field, source = dimensions[dimension]
        rows = self.connection.execute(
            f"SELECT {field} AS value, COUNT(*) AS count FROM {source} GROUP BY {field} ORDER BY count DESC, value"
        )
        return self._result("aggregate", {"dimension": dimension}, rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--judge", choices=("codex", "claude"), required=True)
    parser.add_argument("--own-history", action="store_true")
    subparsers = parser.add_subparsers(dest="query", required=True)
    row = subparsers.add_parser("row")
    row.add_argument("candidate_id")
    cluster = subparsers.add_parser("cluster")
    cluster.add_argument("candidate_id")
    cluster.add_argument("--limit", type=int, default=200)
    chronology = subparsers.add_parser("chronology")
    chronology.add_argument("candidate_id")
    chronology.add_argument("--limit", type=int, default=200)
    scope = subparsers.add_parser("scope")
    scope.add_argument("scope_key")
    scope.add_argument("--limit", type=int, default=200)
    listing = subparsers.add_parser("list")
    listing.add_argument("--language")
    listing.add_argument("--source-id")
    listing.add_argument("--risk-tag")
    listing.add_argument("--cluster-size-min", type=int, default=1)
    listing.add_argument("--order", default="candidate_id")
    listing.add_argument("--limit", type=int, default=100)
    listing.add_argument("--offset", type=int, default=0)
    lexical = subparsers.add_parser("lexical")
    lexical.add_argument("text")
    lexical.add_argument("--language")
    lexical.add_argument("--limit", type=int, default=100)
    semantic = subparsers.add_parser("semantic")
    semantic.add_argument("candidate_id")
    semantic.add_argument("--limit", type=int, default=100)
    history = subparsers.add_parser("own_history")
    history.add_argument("candidate_id")
    history.add_argument("--limit", type=int, default=20)
    aggregate = subparsers.add_parser("aggregate")
    aggregate.add_argument("dimension", choices=("language", "source", "cluster_size", "risk_tag"))
    args = parser.parse_args()
    interface = JudgeQuery(args.database, args.judge, include_own_history=args.own_history)
    try:
        kwargs = vars(args).copy()
        for key in ("database", "judge", "own_history", "query"):
            kwargs.pop(key, None)
        result = getattr(interface, args.query if args.query != "list" else "list_rows")(**kwargs)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        interface.close()


if __name__ == "__main__":
    main()
