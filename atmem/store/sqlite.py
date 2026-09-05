from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator
import uuid

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.core.policy import normalize_content
from atmem.core.storage import HouseholdLock, HouseholdPolicy, connect, row_factory_for


class SQLiteStore:
    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        policy: HouseholdPolicy | None = None,
    ) -> None:
        self.path = str(path)
        self.policy = policy or HouseholdPolicy.load(path)
        self._household_lock = HouseholdLock(self.policy).acquire()
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # Autocommit mode keeps transaction ownership explicit. Public write
        # methods enter ``transaction()``; an outer engine operation can wrap
        # several of them in one atomic unit without an inner method committing
        # early through sqlite3.Connection.__exit__.
        try:
            self._conn = connect(
                self.path, policy=self.policy, isolation_level=None
            )
        except Exception:
            self._household_lock.close()
            raise
        self._conn.row_factory = row_factory_for(self.policy)
        self._transaction_depth = 0
        self._fts_enabled = False
        self._graph_fts_enabled = False
        self._audit_fts_enabled = False
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        if self.path != ":memory:":
            try:
                self._conn.execute("PRAGMA journal_mode = WAL")
            except Exception as exc:
                # Concurrent first-open calls can race while one connection
                # changes the persistent journal mode. BEGIN IMMEDIATE still
                # provides correct serialization; the winning connection has
                # already made WAL persistent for subsequent opens.
                if "locked" not in str(exc).lower():
                    raise
        self._migrate()

    def close(self) -> None:
        try:
            self._conn.close()
        finally:
            self._household_lock.close()

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator["SQLiteStore"]:
        """Join or open one explicit SQLite unit of work.

        The outermost scope owns BEGIN/COMMIT/ROLLBACK. Nested store calls only
        join it, which is what makes a semantic mutation and its audit event
        atomic. ``BEGIN IMMEDIATE`` is the write default: it also serializes
        the per-subject audit-head read with the following append so two
        connections cannot derive competing events from the same head.
        """
        if self._transaction_depth:
            self._transaction_depth += 1
            try:
                yield self
            finally:
                self._transaction_depth -= 1
            return

        self._conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        self._transaction_depth = 1
        try:
            yield self
        except BaseException:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()
        finally:
            self._transaction_depth = 0

    def reset_subject(self, subject_id: str) -> None:
        with self.transaction():
            preparation_ids = [
                str(row["preparation_id"])
                for row in self._conn.execute(
                    "SELECT preparation_id FROM protocol_preparations WHERE subject_id = ?",
                    (subject_id,),
                ).fetchall()
            ]
            if preparation_ids:
                placeholders = ",".join("?" for _ in preparation_ids)
                self._conn.execute(
                    f"DELETE FROM protocol_exposures WHERE preparation_id IN ({placeholders})",
                    preparation_ids,
                )
            self._conn.execute(
                "DELETE FROM protocol_preparations WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM protocol_candidate_sets WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM protocol_proposals WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM protocol_sources WHERE subject_id = ?", (subject_id,)
            )
            action_table = self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'action_transactions'"
            ).fetchone()
            if action_table is not None:
                self._conn.execute(
                    "DELETE FROM action_transactions WHERE subject_id = ?",
                    (subject_id,),
                )
            if self._fts_enabled:
                self._delete_records_fts_subject(subject_id)
            if self._graph_fts_enabled:
                self._delete_graph_fts_subject(subject_id)
            self._conn.execute(
                "DELETE FROM retrieval_exclusions WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM graph_merge_proposals WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM graph_archive_members WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM graph_archive_partitions WHERE subject_id = ?",
                (subject_id,),
            )
            self._conn.execute(
                "DELETE FROM media_observations WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM media_artifacts WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute("DELETE FROM edges WHERE subject_id = ?", (subject_id,))
            self._conn.execute(
                "DELETE FROM entity_aliases WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM entities WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM records WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM episodes WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM retrieval_events WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM investigation_access_log WHERE subject_id = ?",
                (subject_id,),
            )
            self._conn.execute(
                "DELETE FROM audit_verification_state WHERE subject_id = ?",
                (subject_id,),
            )
            self._conn.execute(
                "DELETE FROM audit_log WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM record_generations WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM pending_user_messages WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM memory_lineage WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM memory_reviews WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM memory_proposals WHERE subject_id = ?", (subject_id,)
            )
            task_rows = self._conn.execute(
                "SELECT task_id FROM governed_tasks WHERE subject_id = ?",
                (subject_id,),
            ).fetchall()
            task_ids = [str(row["task_id"]) for row in task_rows]
            if task_ids:
                placeholders = ",".join("?" for _ in task_ids)
                for table in (
                    "governed_task_deliveries",
                    "governed_task_steps",
                    "governed_task_proposals",
                    "governed_task_provenance",
                    "governed_task_revisions",
                ):
                    self._conn.execute(
                        f"DELETE FROM {table} WHERE task_id IN ({placeholders})",
                        task_ids,
                    )
            self._conn.execute(
                "DELETE FROM governed_tasks WHERE subject_id = ?", (subject_id,)
            )

    def stage_user_message(
        self,
        *,
        subject_id: str,
        aliases: list[str],
        message: str,
        run_id: str | None = None,
        ttl_seconds: int = 600,
    ) -> str:
        """Temporarily bind one typed host message to runtime session aliases."""
        clean_aliases = list(
            dict.fromkeys(value.strip() for value in aliases if value.strip())
        )
        if not clean_aliases:
            raise ValueError("at least one session alias is required")
        if len(clean_aliases) > 8 or any(len(value) > 1_024 for value in clean_aliases):
            raise ValueError("session aliases exceed the bounded handoff contract")
        if not message.strip():
            raise ValueError("staged user message must not be empty")
        if len(message) > 100_000:
            raise ValueError("staged user message exceeds 100,000 characters")
        source_id = _new_id("src")
        created_at = utc_now()
        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=max(30, min(ttl_seconds, 600)))
        ).isoformat()
        placeholders = ",".join("?" for _ in clean_aliases)
        with self.transaction():
            self._conn.execute(
                "DELETE FROM pending_user_messages WHERE expires_at <= ?", (created_at,)
            )
            old_rows = self._conn.execute(
                f"""
                SELECT DISTINCT source_id FROM pending_user_messages
                WHERE subject_id = ? AND alias IN ({placeholders})
                """,
                (subject_id, *clean_aliases),
            ).fetchall()
            for row in old_rows:
                self._conn.execute(
                    "DELETE FROM pending_user_messages WHERE source_id = ?",
                    (row["source_id"],),
                )
            self._conn.executemany(
                """
                INSERT INTO pending_user_messages (
                  source_id, subject_id, alias, message, run_id, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        source_id,
                        subject_id,
                        alias,
                        message,
                        run_id,
                        created_at,
                        expires_at,
                    )
                    for alias in clean_aliases
                ],
            )
        return source_id

    def resolve_user_message(
        self, *, subject_id: str, aliases: list[str]
    ) -> dict[str, Any] | None:
        clean_aliases = list(
            dict.fromkeys(value.strip() for value in aliases if value.strip())
        )
        if not clean_aliases:
            return None
        if len(clean_aliases) > 8 or any(len(value) > 1_024 for value in clean_aliases):
            raise ValueError("session aliases exceed the bounded handoff contract")
        now = utc_now()
        placeholders = ",".join("?" for _ in clean_aliases)
        with self.transaction():
            self._conn.execute(
                "DELETE FROM pending_user_messages WHERE expires_at <= ?", (now,)
            )
            row = self._conn.execute(
                f"""
                SELECT source_id, message, run_id, created_at, expires_at
                FROM pending_user_messages
                WHERE subject_id = ? AND alias IN ({placeholders})
                ORDER BY created_at DESC LIMIT 1
                """,
                (subject_id, *clean_aliases),
            ).fetchone()
        return dict(row) if row is not None else None

    def clear_user_message(self, *, subject_id: str, aliases: list[str]) -> int:
        clean_aliases = list(
            dict.fromkeys(value.strip() for value in aliases if value.strip())
        )
        if not clean_aliases:
            return 0
        if len(clean_aliases) > 8 or any(len(value) > 1_024 for value in clean_aliases):
            raise ValueError("session aliases exceed the bounded handoff contract")
        placeholders = ",".join("?" for _ in clean_aliases)
        with self.transaction():
            rows = self._conn.execute(
                f"""
                SELECT DISTINCT source_id FROM pending_user_messages
                WHERE subject_id = ? AND alias IN ({placeholders})
                """,
                (subject_id, *clean_aliases),
            ).fetchall()
            for row in rows:
                self._conn.execute(
                    "DELETE FROM pending_user_messages WHERE source_id = ?",
                    (row["source_id"],),
                )
        return len(rows)

    def insert_episode(
        self,
        *,
        subject_id: str,
        session_id: str | None,
        turn_id: str | None,
        message: str,
        source_type: str,
        raw: dict[str, Any] | None = None,
    ) -> str:
        episode_id = _new_id("ep")
        created_at = utc_now()
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO episodes (
                  id, subject_id, session_id, turn_id, message, source_type,
                  created_at, raw
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    subject_id,
                    session_id,
                    turn_id,
                    message,
                    source_type,
                    created_at,
                    _json(raw or {}),
                ),
            )
        return episode_id

    def insert_record(
        self,
        *,
        subject_id: str,
        content: str,
        source_type: str,
        trust_tier: str,
        source_session_id: str | None,
        source_turn_id: str | None,
        episode_id: str | None,
        confidence: float | None,
        scope: str,
        status: str = "active",
        supersedes_id: str | None = None,
        fact_key: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> str:
        record_id = _new_id("rec")
        created_at = utc_now()
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO records (
                  id, subject_id, content, content_normalized, source_type, trust_tier,
                  source_session_id, source_turn_id, episode_id, created_at,
                  updated_at, deleted_at, confidence, scope, status,
                  supersedes_id, fact_key, raw
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    subject_id,
                    content,
                    normalize_content(content),
                    source_type,
                    trust_tier,
                    source_session_id,
                    source_turn_id,
                    episode_id,
                    created_at,
                    confidence,
                    scope,
                    status,
                    supersedes_id,
                    fact_key,
                    _json(raw or {}),
                ),
            )
            if status == "active":
                self._upsert_fts(record_id, subject_id, content)
        return record_id

    def get_record(self, subject_id: str, record_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM records WHERE subject_id = ? AND id = ?",
            (subject_id, record_id),
        ).fetchone()
        return _record_from_row(row) if row else None

    def get_protocol_source(
        self, workspace_id: str, agent_id: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM protocol_sources
            WHERE workspace_id = ? AND agent_id = ? AND idempotency_key = ?
            """,
            (workspace_id, agent_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["request"] = _load_json(value.pop("request_json"), {})
        value["result"] = _load_json(value.pop("result_json"), {})
        return value

    def get_protocol_source_by_id(self, source_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM protocol_sources WHERE source_id = ?", (source_id,)
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["request"] = _load_json(value.pop("request_json"), {})
        value["result"] = _load_json(value.pop("result_json"), {})
        return value

    def insert_protocol_source(
        self,
        *,
        source_id: str,
        idempotency_key: str,
        payload_sha256: str,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        episode_id: str,
        source_sha256: str,
        request: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO protocol_sources(
              source_id, idempotency_key, payload_sha256, subject_id, agent_id,
              workspace_id, episode_id, source_sha256, request_json,
              result_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                idempotency_key,
                payload_sha256,
                subject_id,
                agent_id,
                workspace_id,
                episode_id,
                source_sha256,
                _json(request),
                _json(result),
                utc_now(),
            ),
        )

    def get_protocol_proposal(
        self, workspace_id: str, agent_id: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM protocol_proposals
            WHERE workspace_id = ? AND agent_id = ? AND idempotency_key = ?
            """,
            (workspace_id, agent_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["proposal"] = _load_json(value.pop("proposal_json"), {})
        value["admission"] = _load_json(value.pop("admission_json"), {})
        return value

    def insert_protocol_proposal(
        self,
        *,
        proposal_id: str,
        idempotency_key: str,
        payload_sha256: str,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        decision: str,
        proposal: dict[str, Any],
        admission: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO protocol_proposals(
              proposal_id, idempotency_key, payload_sha256, subject_id,
              agent_id, workspace_id, decision, proposal_json,
              admission_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                idempotency_key,
                payload_sha256,
                subject_id,
                agent_id,
                workspace_id,
                decision,
                _json(proposal),
                _json(admission),
                utc_now(),
            ),
        )

    def put_protocol_candidate_set(
        self,
        candidate_set_id: str,
        *,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        generation: int,
        expires_at: str,
        value: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO protocol_candidate_sets(
              candidate_set_id, subject_id, agent_id, workspace_id,
              generation, expires_at, value_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_set_id,
                subject_id,
                agent_id,
                workspace_id,
                generation,
                expires_at,
                _json(value),
                utc_now(),
            ),
        )

    def get_protocol_candidate_set(self, candidate_set_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM protocol_candidate_sets WHERE candidate_set_id = ?",
            (candidate_set_id,),
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["value"] = _load_json(value.pop("value_json"), {})
        return value

    def put_protocol_preparation(
        self,
        preparation_id: str,
        *,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        context_sha256: str,
        generation: int,
        expires_at: str,
        value: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO protocol_preparations(
              preparation_id, subject_id, agent_id, workspace_id,
              context_sha256, generation, expires_at, value_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                preparation_id,
                subject_id,
                agent_id,
                workspace_id,
                context_sha256,
                generation,
                expires_at,
                _json(value),
                utc_now(),
            ),
        )

    def get_protocol_preparation(self, preparation_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM protocol_preparations WHERE preparation_id = ?",
            (preparation_id,),
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["value"] = _load_json(value.pop("value_json"), {})
        return value

    def get_protocol_exposure(self, confirmation_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM protocol_exposures WHERE confirmation_id = ?",
            (confirmation_id,),
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["receipt"] = _load_json(value.pop("receipt_json"), {})
        return value

    def get_protocol_exposure_for_preparation(
        self, preparation_id: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM protocol_exposures WHERE preparation_id = ?",
            (preparation_id,),
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["receipt"] = _load_json(value.pop("receipt_json"), {})
        return value

    def put_protocol_exposure(
        self,
        confirmation_id: str,
        *,
        preparation_id: str,
        receipt: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO protocol_exposures(
              confirmation_id, preparation_id, receipt_json, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (confirmation_id, preparation_id, _json(receipt), utc_now()),
        )

    def set_retrieval_excluded(
        self,
        subject_id: str,
        record_id: str,
        excluded: bool,
        *,
        actor: str,
        reason: str = "",
    ) -> None:
        if excluded:
            now = utc_now()
            self._conn.execute(
                """
                INSERT INTO retrieval_exclusions(
                  subject_id, record_id, reason, actor, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject_id, record_id) DO UPDATE SET
                  reason = excluded.reason, actor = excluded.actor,
                  updated_at = excluded.updated_at
                """,
                (subject_id, record_id, reason[:500], actor, now, now),
            )
        else:
            self._conn.execute(
                "DELETE FROM retrieval_exclusions WHERE subject_id = ? AND record_id = ?",
                (subject_id, record_id),
            )

    def excluded_record_ids(self, subject_id: str) -> set[str]:
        rows = self._conn.execute(
            "SELECT record_id FROM retrieval_exclusions WHERE subject_id = ?",
            (subject_id,),
        ).fetchall()
        return {str(row["record_id"]) for row in rows}

    def get_records(
        self, subject_id: str, record_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Fetch canonical records in bounded batches, keyed by record ID."""
        ids = list(dict.fromkeys(str(value) for value in record_ids))
        records: dict[str, dict[str, Any]] = {}
        for start in range(0, len(ids), 900):
            batch = ids[start : start + 900]
            placeholders = ",".join("?" for _ in batch)
            rows = self._conn.execute(
                f"""
                SELECT * FROM records
                WHERE subject_id = ? AND id IN ({placeholders})
                """,
                (subject_id, *batch),
            ).fetchall()
            records.update((str(row["id"]), _record_from_row(row)) for row in rows)
        return records

    def record_generation(self, subject_id: str) -> int:
        row = self._conn.execute(
            "SELECT generation FROM record_generations WHERE subject_id = ?",
            (subject_id,),
        ).fetchone()
        return int(row["generation"]) if row else 0

    def record_preconditions(
        self, subject_id: str, record_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Current generation, status, and content digest per named record.

        This is the exact state a governed proposal must pin. It is read
        inside the committing transaction so a concurrent writer either loses
        the BEGIN IMMEDIATE race or is detected by the generation check.
        """
        result: dict[str, dict[str, Any]] = {}
        for record_id in dict.fromkeys(record_ids):
            row = self._conn.execute(
                """
                SELECT id, generation, status, content FROM records
                WHERE subject_id = ? AND id = ?
                """,
                (subject_id, record_id),
            ).fetchone()
            if row is None:
                continue
            result[str(row["id"])] = {
                "record_id": str(row["id"]),
                "generation": int(row["generation"] or 0),
                "status": str(row["status"]),
                "content_sha256": f"sha256:{sha256_hex(str(row['content']))}",
            }
        return result

    def insert_memory_proposal(
        self,
        *,
        proposal_id: str,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        idempotency_key: str,
        proposal_sha256: str,
        action: str,
        memory_class: str,
        confidence: float,
        fact_key: str | None,
        review_state: str,
        reason_codes: list[str],
        proposal: dict[str, Any],
        outcome: dict[str, Any] | None = None,
        decided_at: str | None = None,
    ) -> dict[str, Any]:
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO memory_proposals (
                  proposal_id, subject_id, agent_id, workspace_id,
                  idempotency_key, proposal_sha256, action, memory_class,
                  confidence, fact_key, review_state, reason_codes, proposal,
                  outcome, created_at, decided_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    subject_id,
                    agent_id,
                    workspace_id,
                    idempotency_key,
                    proposal_sha256,
                    action,
                    memory_class,
                    float(confidence),
                    fact_key,
                    review_state,
                    _json(list(reason_codes)),
                    _json(proposal),
                    _json(outcome or {}),
                    utc_now(),
                    decided_at,
                ),
            )
        stored = self.get_memory_proposal(proposal_id)
        assert stored is not None
        return stored

    def get_memory_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM memory_proposals WHERE proposal_id = ?", (proposal_id,)
        ).fetchone()
        return _memory_proposal_from_row(row) if row else None

    def find_memory_proposal(
        self, subject_id: str, agent_id: str, workspace_id: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM memory_proposals
            WHERE subject_id = ? AND agent_id = ? AND workspace_id = ?
              AND idempotency_key = ?
            """,
            (subject_id, agent_id, workspace_id, idempotency_key),
        ).fetchone()
        return _memory_proposal_from_row(row) if row else None

    def list_memory_proposals(
        self,
        subject_id: str | None = None,
        *,
        review_states: tuple[str, ...] | None = ("pending_review",),
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if subject_id is not None:
            clauses.append("subject_id = ?")
            params.append(subject_id)
        if review_states is not None:
            clauses.append(
                f"review_state IN ({','.join('?' for _ in review_states)})"
            )
            params.extend(review_states)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(int(limit), 1000)))
        rows = self._conn.execute(
            f"""
            SELECT * FROM memory_proposals {where}
            ORDER BY created_at ASC, proposal_id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [_memory_proposal_from_row(row) for row in rows]

    def settle_memory_proposal(
        self,
        proposal_id: str,
        *,
        review_state: str,
        outcome: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Move a proposal out of the queue exactly once.

        The pending guard is what makes two concurrent reviewers safe: the
        second decision matches no row and the caller fails closed.
        """
        with self.transaction():
            cursor = self._conn.execute(
                """
                UPDATE memory_proposals
                SET review_state = ?, outcome = ?, decided_at = ?
                WHERE proposal_id = ? AND review_state = 'pending_review'
                """,
                (review_state, _json(outcome), utc_now(), proposal_id),
            )
            if cursor.rowcount != 1:
                return None
        return self.get_memory_proposal(proposal_id)

    def insert_memory_review(
        self,
        *,
        proposal_id: str,
        subject_id: str,
        decision: str,
        actor: str,
        reason: str,
        edited_fact_sha256: str | None = None,
        record_ids: list[str] | None = None,
        audit_event_id: str | None = None,
    ) -> dict[str, Any]:
        review_id = _new_id("rev")
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO memory_reviews (
                  review_id, proposal_id, subject_id, decision, actor, reason,
                  edited_fact_sha256, record_ids, audit_event_id, decided_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    proposal_id,
                    subject_id,
                    decision,
                    actor,
                    reason,
                    edited_fact_sha256,
                    _json(list(record_ids or ())),
                    audit_event_id,
                    utc_now(),
                ),
            )
        rows = self.list_memory_reviews(proposal_id)
        return next(row for row in rows if row["review_id"] == review_id)

    def list_memory_reviews(self, proposal_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM memory_reviews WHERE proposal_id = ?
            ORDER BY decided_at ASC, review_id ASC
            """,
            (proposal_id,),
        ).fetchall()
        return [
            {
                "review_id": str(row["review_id"]),
                "proposal_id": str(row["proposal_id"]),
                "subject_id": str(row["subject_id"]),
                "decision": str(row["decision"]),
                "actor": str(row["actor"]),
                "reason": str(row["reason"]),
                "edited_fact_sha256": row["edited_fact_sha256"],
                "record_ids": _load_json(row["record_ids"], []),
                "audit_event_id": row["audit_event_id"],
                "decided_at": str(row["decided_at"]),
            }
            for row in rows
        ]

    def insert_memory_lineage(
        self,
        *,
        subject_id: str,
        relation: str,
        predecessor_record_id: str,
        successor_record_id: str,
        predecessor_content_sha256: str,
        predecessor_generation: int,
        proposal_id: str | None = None,
    ) -> str:
        lineage_id = _new_id("lin")
        with self.transaction():
            self._conn.execute(
                """
                INSERT OR IGNORE INTO memory_lineage (
                  lineage_id, subject_id, relation, predecessor_record_id,
                  successor_record_id, predecessor_content_sha256,
                  predecessor_generation, proposal_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lineage_id,
                    subject_id,
                    relation,
                    predecessor_record_id,
                    successor_record_id,
                    predecessor_content_sha256,
                    int(predecessor_generation),
                    proposal_id,
                    utc_now(),
                ),
            )
        return lineage_id

    def list_memory_lineage(
        self, subject_id: str, record_id: str | None = None
    ) -> list[dict[str, Any]]:
        params: list[Any] = [subject_id]
        clause = ""
        if record_id is not None:
            clause = "AND (predecessor_record_id = ? OR successor_record_id = ?)"
            params.extend([record_id, record_id])
        rows = self._conn.execute(
            f"""
            SELECT * FROM memory_lineage
            WHERE subject_id = ? {clause}
            ORDER BY created_at ASC, lineage_id ASC
            """,
            params,
        ).fetchall()
        return [
            {
                "lineage_id": str(row["lineage_id"]),
                "subject_id": str(row["subject_id"]),
                "relation": str(row["relation"]),
                "predecessor_record_id": str(row["predecessor_record_id"]),
                "successor_record_id": str(row["successor_record_id"]),
                "predecessor_content_sha256": str(row["predecessor_content_sha256"]),
                "predecessor_generation": int(row["predecessor_generation"]),
                "proposal_id": row["proposal_id"],
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    # --- Governed Task State (Spec 007) ------------------------------------
    #
    # Task state is a separate authority plane from durable memory. Every read
    # here takes the exact scope: a task is never found by id alone, so a
    # caller in one workspace cannot reach another workspace's work even if it
    # somehow learns the identifier.

    def insert_task_profile(
        self,
        *,
        version: str,
        profile_id: str,
        digest: str,
        profile: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO governed_task_profiles (
                  version, profile_id, digest, profile, actor, registered_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (version, profile_id, digest, _json(profile), actor, utc_now()),
            )
        stored = self.get_task_profile(version)
        assert stored is not None
        return stored

    def get_task_profile(self, version: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM governed_task_profiles WHERE version = ?", (version,)
        ).fetchone()
        return _task_profile_from_row(row) if row else None

    def list_task_profiles(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM governed_task_profiles ORDER BY version"
        ).fetchall()
        return [_task_profile_from_row(row) for row in rows]

    def insert_task(
        self,
        *,
        task_id: str,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        profile_id: str,
        profile_version: str,
        goal: str,
        lifecycle: str,
        head_revision: int,
        created_at_utc: str,
        last_progress_at_utc: str,
        expiry_rule: dict[str, Any],
        clock_source: str,
        idempotency_key: str,
        policy_generation: int = 1,
        continues_task_id: str | None = None,
    ) -> dict[str, Any]:
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO governed_tasks (
                  task_id, subject_id, agent_id, workspace_id, profile_id,
                  profile_version, goal, lifecycle, head_revision,
                  policy_generation, created_at_utc, updated_at_utc,
                  last_progress_at_utc, paused_at_utc, no_progress_paused_ms,
                  expiry_rule, clock_source, terminal_reason, continues_task_id,
                  idempotency_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, ?, ?,
                        NULL, ?, ?)
                """,
                (
                    task_id, subject_id, agent_id, workspace_id, profile_id,
                    profile_version, goal, lifecycle, int(head_revision),
                    int(policy_generation), created_at_utc, created_at_utc,
                    last_progress_at_utc, _json(expiry_rule), clock_source,
                    continues_task_id, idempotency_key,
                ),
            )
        stored = self.get_task(
            subject_id=subject_id, agent_id=agent_id,
            workspace_id=workspace_id, task_id=task_id,
        )
        assert stored is not None
        return stored

    def get_task(
        self,
        *,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        task_id: str,
    ) -> dict[str, Any] | None:
        """Read one task, and only within its exact authority scope."""
        row = self._conn.execute(
            """
            SELECT * FROM governed_tasks
            WHERE task_id = ? AND subject_id = ? AND agent_id = ?
              AND workspace_id = ?
            """,
            (task_id, subject_id, agent_id, workspace_id),
        ).fetchone()
        return _task_from_row(row) if row else None

    def find_task_by_idempotency_key(
        self,
        *,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM governed_tasks
            WHERE subject_id = ? AND agent_id = ? AND workspace_id = ?
              AND idempotency_key = ?
            """,
            (subject_id, agent_id, workspace_id, idempotency_key),
        ).fetchone()
        return _task_from_row(row) if row else None

    def list_tasks(
        self,
        *,
        subject_id: str | None = None,
        agent_id: str | None = None,
        workspace_id: str | None = None,
        lifecycles: tuple[str, ...] | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Deterministically ordered, cursor-paginated task listing."""
        clauses: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("subject_id", subject_id),
            ("agent_id", agent_id),
            ("workspace_id", workspace_id),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        if lifecycles:
            clauses.append(f"lifecycle IN ({','.join('?' for _ in lifecycles)})")
            params.extend(lifecycles)
        if cursor:
            # Ordering is (created_at, task_id), so the cursor is that pair.
            clauses.append("(created_at_utc, task_id) > (?, ?)")
            params.extend(cursor.split("|", 1) if "|" in cursor else [cursor, ""])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(int(limit), 500)))
        rows = self._conn.execute(
            f"""
            SELECT * FROM governed_tasks {where}
            ORDER BY created_at_utc ASC, task_id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [_task_from_row(row) for row in rows]

    def tasks_due_for_expiry_scan(
        self, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Non-terminal tasks, oldest first. Terminal tasks are never re-evaluated."""
        rows = self._conn.execute(
            """
            SELECT * FROM governed_tasks
            WHERE lifecycle IN ('open', 'paused')
            ORDER BY created_at_utc ASC, task_id ASC
            LIMIT ?
            """,
            (max(1, min(int(limit), 1000)),),
        ).fetchall()
        return [_task_from_row(row) for row in rows]

    def insert_task_revision(
        self,
        *,
        task_id: str,
        revision: int,
        parent_revision: int | None,
        state: dict[str, Any],
        state_sha256: str,
        semantic_sha256: str,
        actor: str,
        actor_role: str,
        reason_codes: list[str],
        evidence: list[dict[str, Any]],
        created_at_utc: str,
        is_progress: bool = False,
    ) -> None:
        """Append one immutable revision.

        The unique index on (task_id, parent_revision) is what enforces "at
        most one accepted successor": a second writer racing on the same base
        revision raises IntegrityError rather than forking history.
        """
        self._conn.execute(
            """
            INSERT INTO governed_task_revisions (
              task_id, revision, parent_revision, state, state_sha256,
              semantic_sha256, actor, actor_role, reason_codes, evidence,
              created_at_utc, is_progress
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id, int(revision),
                None if parent_revision is None else int(parent_revision),
                _json(state), state_sha256, semantic_sha256, actor, actor_role,
                _json(list(reason_codes)), _json(list(evidence)),
                created_at_utc, 1 if is_progress else 0,
            ),
        )

    def get_task_revision(
        self, task_id: str, revision: int
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM governed_task_revisions
            WHERE task_id = ? AND revision = ?
            """,
            (task_id, int(revision)),
        ).fetchone()
        return _task_revision_from_row(row) if row else None

    def list_task_revisions(
        self, task_id: str, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM governed_task_revisions
            WHERE task_id = ?
            ORDER BY revision ASC
            LIMIT ?
            """,
            (task_id, max(1, min(int(limit), 1000))),
        ).fetchall()
        return [_task_revision_from_row(row) for row in rows]

    def advance_task_head(
        self,
        *,
        task_id: str,
        expected_head: int,
        new_head: int,
        updated_at_utc: str,
        last_progress_at_utc: str | None = None,
        lifecycle: str | None = None,
        terminal_reason: str | None = None,
        paused_at_utc: str | None = None,
        clear_paused_at: bool = False,
        add_paused_ms: int = 0,
    ) -> bool:
        """Move the head exactly once, under an expected-head guard.

        Returns False when another writer already advanced past
        `expected_head`; the caller turns that into a `conflict` outcome
        rather than retrying, so a stale proposal never silently wins.
        """
        assignments = [
            "head_revision = ?",
            "updated_at_utc = ?",
        ]
        params: list[Any] = [int(new_head), updated_at_utc]
        if last_progress_at_utc is not None:
            assignments.append("last_progress_at_utc = ?")
            params.append(last_progress_at_utc)
        if lifecycle is not None:
            assignments.append("lifecycle = ?")
            params.append(lifecycle)
        if terminal_reason is not None:
            assignments.append("terminal_reason = ?")
            params.append(terminal_reason)
        if clear_paused_at:
            assignments.append("paused_at_utc = NULL")
        elif paused_at_utc is not None:
            assignments.append("paused_at_utc = ?")
            params.append(paused_at_utc)
        if add_paused_ms:
            assignments.append("no_progress_paused_ms = no_progress_paused_ms + ?")
            params.append(int(add_paused_ms))
        params.extend([task_id, int(expected_head)])
        cursor = self._conn.execute(
            f"""
            UPDATE governed_tasks SET {', '.join(assignments)}
            WHERE task_id = ? AND head_revision = ?
            """,
            params,
        )
        return cursor.rowcount == 1

    def insert_task_provenance(
        self,
        *,
        task_id: str,
        revision: int,
        target_kind: str,
        target_id: str,
        actor: str,
        actor_role: str,
        method: str,
        assurance: str,
        observed_at_utc: str,
        interpreter: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
        superseded_revision: int | None = None,
    ) -> str:
        provenance_id = _new_id("prov")
        self._conn.execute(
            """
            INSERT INTO governed_task_provenance (
              provenance_id, task_id, revision, target_kind, target_id, actor,
              actor_role, method, assurance, interpreter, evidence,
              observed_at_utc, superseded_revision
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provenance_id, task_id, int(revision), target_kind, target_id,
                actor, actor_role, method, assurance, interpreter,
                _json(list(evidence or ())), observed_at_utc,
                None if superseded_revision is None else int(superseded_revision),
            ),
        )
        return provenance_id

    def list_task_provenance(
        self,
        task_id: str,
        *,
        target_kind: str | None = None,
        target_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["task_id = ?"]
        params: list[Any] = [task_id]
        if target_kind is not None:
            clauses.append("target_kind = ?")
            params.append(target_kind)
        if target_id is not None:
            clauses.append("target_id = ?")
            params.append(target_id)
        rows = self._conn.execute(
            f"""
            SELECT * FROM governed_task_provenance
            WHERE {' AND '.join(clauses)}
            ORDER BY revision ASC, target_kind ASC, target_id ASC
            """,
            params,
        ).fetchall()
        return [_task_provenance_from_row(row) for row in rows]

    def find_task_proposal(
        self, task_id: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM governed_task_proposals
            WHERE task_id = ? AND idempotency_key = ?
            """,
            (task_id, idempotency_key),
        ).fetchone()
        return _task_proposal_from_row(row) if row else None

    def insert_task_proposal(
        self,
        *,
        proposal_id: str,
        task_id: str,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        idempotency_key: str,
        payload_sha256: str,
        base_revision: int,
        actor: str,
        actor_role: str,
        proposal: dict[str, Any],
        decision: dict[str, Any],
        outcome: str,
        resulting_revision: int | None,
        created_at_utc: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO governed_task_proposals (
              proposal_id, task_id, subject_id, agent_id, workspace_id,
              idempotency_key, payload_sha256, base_revision, actor, actor_role,
              proposal, decision, outcome, resulting_revision, created_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id, task_id, subject_id, agent_id, workspace_id,
                idempotency_key, payload_sha256, int(base_revision), actor,
                actor_role, _json(proposal), _json(decision), outcome,
                None if resulting_revision is None else int(resulting_revision),
                created_at_utc,
            ),
        )

    def list_task_proposals(
        self, task_id: str, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM governed_task_proposals
            WHERE task_id = ?
            ORDER BY created_at_utc ASC, proposal_id ASC
            LIMIT ?
            """,
            (task_id, max(1, min(int(limit), 1000))),
        ).fetchall()
        return [_task_proposal_from_row(row) for row in rows]

    def insert_task_step(
        self,
        *,
        task_id: str,
        step_kind: str,
        outcome: str,
        base_revision: int,
        actor: str,
        recorded_at_utc: str,
        proposal_id: str | None = None,
        resulting_revision: int | None = None,
        reason_codes: list[str] | None = None,
        action_fingerprint: str | None = None,
        duration_ms: int = 0,
    ) -> str:
        step_id = _new_id("step")
        self._conn.execute(
            """
            INSERT INTO governed_task_steps (
              step_id, task_id, step_kind, outcome, proposal_id, base_revision,
              resulting_revision, reason_codes, action_fingerprint, actor,
              duration_ms, recorded_at_utc, sequence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    (SELECT COALESCE(MAX(sequence), 0) + 1
                     FROM governed_task_steps WHERE task_id = ?))
            """,
            (
                step_id, task_id, step_kind, outcome, proposal_id,
                int(base_revision),
                None if resulting_revision is None else int(resulting_revision),
                _json(list(reason_codes or ())), action_fingerprint, actor,
                max(0, int(duration_ms)), recorded_at_utc, task_id,
            ),
        )
        return step_id

    def list_task_steps(
        self, task_id: str, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM governed_task_steps
            WHERE task_id = ?
            ORDER BY sequence ASC
            LIMIT ?
            """,
            (task_id, max(1, min(int(limit), 1000))),
        ).fetchall()
        return [_task_step_from_row(row) for row in rows]

    def count_recent_equivalent_actions(
        self, task_id: str, action_fingerprint: str, *, since_utc: str
    ) -> int:
        """How many equivalent actions ran since the last accepted progress."""
        row = self._conn.execute(
            """
            SELECT COUNT(*) AS total FROM governed_task_steps
            WHERE task_id = ? AND action_fingerprint = ?
              AND recorded_at_utc >= ?
            """,
            (task_id, action_fingerprint, since_utc),
        ).fetchone()
        return int(row["total"]) if row else 0

    def insert_task_delivery(
        self,
        *,
        task_id: str,
        revision: int,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        disposition: str,
        prepared_at_utc: str,
        reason_codes: list[str] | None = None,
        context_sha256: str | None = None,
        cache_key: str | None = None,
        preparation_id: str | None = None,
        exposure_id: str | None = None,
    ) -> str:
        delivery_id = _new_id("del")
        self._conn.execute(
            """
            INSERT INTO governed_task_deliveries (
              delivery_id, task_id, revision, subject_id, agent_id,
              workspace_id, disposition, reason_codes, context_sha256,
              cache_key, preparation_id, exposure_id, exposed, prepared_at_utc,
              sequence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?,
                    (SELECT COALESCE(MAX(sequence), 0) + 1
                     FROM governed_task_deliveries WHERE task_id = ?))
            """,
            (
                delivery_id, task_id, int(revision), subject_id, agent_id,
                workspace_id, disposition, _json(list(reason_codes or ())),
                context_sha256, cache_key, preparation_id, exposure_id,
                prepared_at_utc, task_id,
            ),
        )
        return delivery_id

    def mark_task_delivery_exposed(self, delivery_id: str) -> bool:
        """Confirm exposure exactly once; a repeat is not a second exposure."""
        cursor = self._conn.execute(
            "UPDATE governed_task_deliveries SET exposed = 1 "
            "WHERE delivery_id = ? AND exposed = 0",
            (delivery_id,),
        )
        return cursor.rowcount == 1

    def list_task_deliveries(
        self, task_id: str, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM governed_task_deliveries
            WHERE task_id = ?
            ORDER BY sequence ASC
            LIMIT ?
            """,
            (task_id, max(1, min(int(limit), 1000))),
        ).fetchall()
        return [_task_delivery_from_row(row) for row in rows]

    def rebuild_task_pause_accounting(self, task_id: str) -> int:
        """Recompute completed paused milliseconds from the revision chain.

        The stored accumulator is the fast path. This is the audit: it derives
        the same number from immutable lifecycle revisions, so a restart or a
        suspected drift can be checked against history rather than trusted.
        """
        from atmem.core.time import elapsed_ms, from_iso

        revisions = self.list_task_revisions(task_id, limit=1000)
        total = 0
        paused_since: str | None = None
        for row in revisions:
            lifecycle = str((row["state"] or {}).get("lifecycle") or "")
            moment = str(row["created_at_utc"])
            if lifecycle == "paused" and paused_since is None:
                paused_since = moment
            elif lifecycle != "paused" and paused_since is not None:
                total += elapsed_ms(from_iso(paused_since), from_iso(moment))
                paused_since = None
        return total

    def delete_task(
        self,
        *,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        """Remove one task and everything derived from it, in scope."""
        task = self.get_task(
            subject_id=subject_id, agent_id=agent_id,
            workspace_id=workspace_id, task_id=task_id,
        )
        if task is None:
            return {"deleted": False, "task_id": task_id, "removed": {}}
        removed: dict[str, int] = {}
        with self.transaction():
            for table in (
                "governed_task_deliveries",
                "governed_task_steps",
                "governed_task_proposals",
                "governed_task_provenance",
            ):
                cursor = self._conn.execute(
                    f"DELETE FROM {table} WHERE task_id = ?", (task_id,)
                )
                removed[table] = cursor.rowcount
            # Revisions carry an immutability trigger on UPDATE, not DELETE:
            # verified deletion may remove history, but nothing may rewrite it.
            cursor = self._conn.execute(
                "DELETE FROM governed_task_revisions WHERE task_id = ?", (task_id,)
            )
            removed["governed_task_revisions"] = cursor.rowcount
            cursor = self._conn.execute(
                "DELETE FROM governed_tasks WHERE task_id = ?", (task_id,)
            )
            removed["governed_tasks"] = cursor.rowcount
        return {"deleted": True, "task_id": task_id, "removed": removed}

    def delete_subject_tasks(self, subject_id: str) -> dict[str, Any]:
        """Remove every governed task belonging to one subject."""
        rows = self._conn.execute(
            "SELECT task_id, agent_id, workspace_id FROM governed_tasks "
            "WHERE subject_id = ?",
            (subject_id,),
        ).fetchall()
        results = [
            self.delete_task(
                subject_id=subject_id,
                agent_id=str(row["agent_id"]),
                workspace_id=str(row["workspace_id"]),
                task_id=str(row["task_id"]),
            )
            for row in rows
        ]
        return {"task_ids": [row["task_id"] for row in results], "deleted": len(results)}

    def get_media_artifact(
        self,
        subject_id: str,
        *,
        artifact_id: str | None = None,
        media_sha256: str | None = None,
    ) -> dict[str, Any] | None:
        if artifact_id:
            row = self._conn.execute(
                """
                SELECT * FROM media_artifacts
                WHERE subject_id = ? AND id = ?
                """,
                (subject_id, artifact_id),
            ).fetchone()
        elif media_sha256:
            row = self._conn.execute(
                """
                SELECT * FROM media_artifacts
                WHERE subject_id = ? AND media_sha256 = ?
                """,
                (subject_id, media_sha256),
            ).fetchone()
        else:
            raise ValueError("artifact_id or media_sha256 is required")
        return dict(row) if row else None

    def insert_media_artifact(
        self,
        *,
        subject_id: str,
        media_sha256: str,
        modality: str,
        host_reference: str,
        host_reference_sha256: str,
        digest_assurance: str,
    ) -> dict[str, Any]:
        artifact_id = _new_id("media")
        created_at = utc_now()
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO media_artifacts(
                  id, subject_id, media_sha256, modality, host_reference,
                  host_reference_sha256, digest_assurance, status,
                  first_seen_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, NULL)
                """,
                (
                    artifact_id,
                    subject_id,
                    media_sha256,
                    modality,
                    host_reference,
                    host_reference_sha256,
                    digest_assurance,
                    created_at,
                ),
            )
        artifact = self.get_media_artifact(subject_id, artifact_id=artifact_id)
        assert artifact is not None
        return artifact

    def get_media_observation(
        self, subject_id: str, observation_id: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM media_observations
            WHERE subject_id = ? AND id = ?
            """,
            (subject_id, observation_id),
        ).fetchone()
        return _media_observation_from_row(row) if row else None

    def get_media_observation_for_record(
        self, subject_id: str, record_id: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM media_observations
            WHERE subject_id = ? AND record_id = ?
            """,
            (subject_id, record_id),
        ).fetchone()
        return _media_observation_from_row(row) if row else None

    def active_media_records_for_lineage(
        self,
        subject_id: str,
        lineage_sha256: str,
        *,
        exclude_record_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [subject_id, lineage_sha256]
        exclusion = ""
        if exclude_record_id is not None:
            exclusion = "AND r.id != ?"
            params.append(exclude_record_id)
        rows = self._conn.execute(
            f"""
            SELECT r.*, o.id AS media_observation_id
            FROM media_observations o
            JOIN records r
              ON r.subject_id = o.subject_id AND r.id = o.record_id
            WHERE o.subject_id = ? AND o.lineage_sha256 = ?
              AND r.status = 'active' {exclusion}
            ORDER BY r.created_at, r.id
            """,
            params,
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            record = _record_from_row(row)
            record["media_observation_id"] = row["media_observation_id"]
            result.append(record)
        return result

    def find_media_observation_by_envelope(
        self, subject_id: str, envelope_sha256: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM media_observations
            WHERE subject_id = ? AND envelope_sha256 = ?
            """,
            (subject_id, envelope_sha256),
        ).fetchone()
        return _media_observation_from_row(row) if row else None

    def current_media_observations(
        self, subject_id: str, lineage_sha256: str
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM media_observations
            WHERE subject_id = ? AND lineage_sha256 = ? AND status = 'current'
            ORDER BY created_at, id
            """,
            (subject_id, lineage_sha256),
        ).fetchall()
        return [_media_observation_from_row(row) for row in rows]

    def insert_media_observation(
        self,
        *,
        subject_id: str,
        artifact_id: str,
        episode_id: str,
        record_id: str,
        text_sha256: str,
        segment: dict[str, Any],
        segment_sha256: str,
        extractor: dict[str, Any],
        extractor_sha256: str,
        confidence: float | None,
        digest_assurance: str,
        lineage_sha256: str,
        envelope_sha256: str,
        observed_at: str | None,
        supersedes_observation_id: str | None,
    ) -> dict[str, Any]:
        observation_id = _new_id("obs")
        created_at = utc_now()
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO media_observations(
                  id, subject_id, artifact_id, episode_id, record_id,
                  text_sha256, segment_json, segment_sha256,
                  extractor_identity_json, extractor_identity_sha256,
                  confidence, digest_assurance, lineage_sha256,
                  envelope_sha256, status, supersedes_observation_id,
                  observed_at, created_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'current',
                          ?, ?, ?, NULL)
                """,
                (
                    observation_id,
                    subject_id,
                    artifact_id,
                    episode_id,
                    record_id,
                    text_sha256,
                    _json(segment),
                    segment_sha256,
                    _json(extractor),
                    extractor_sha256,
                    confidence,
                    digest_assurance,
                    lineage_sha256,
                    envelope_sha256,
                    supersedes_observation_id,
                    observed_at,
                    created_at,
                ),
            )
        observation = self.get_media_observation(subject_id, observation_id)
        assert observation is not None
        return observation

    def supersede_media_observations(
        self, subject_id: str, observation_ids: list[str], new_observation_id: str
    ) -> list[str]:
        superseded_records: list[str] = []
        if not observation_ids:
            return superseded_records
        now = utc_now()
        with self.transaction():
            for observation_id in observation_ids:
                row = self._conn.execute(
                    """
                    SELECT record_id FROM media_observations
                    WHERE subject_id = ? AND id = ? AND status = 'current'
                    """,
                    (subject_id, observation_id),
                ).fetchone()
                if row is None:
                    continue
                self._conn.execute(
                    """
                    UPDATE media_observations
                    SET status = 'superseded'
                    WHERE subject_id = ? AND id = ?
                    """,
                    (subject_id, observation_id),
                )
                record_id = str(row["record_id"])
                record = self._conn.execute(
                    """
                    SELECT status, raw FROM records
                    WHERE subject_id = ? AND id = ?
                    """,
                    (subject_id, record_id),
                ).fetchone()
                if record is None or record["status"] != "quarantined":
                    continue
                raw = _load_json(record["raw"], {})
                raw["superseded_by_observation_id"] = new_observation_id
                self._conn.execute(
                    """
                    UPDATE records
                    SET status = 'superseded', updated_at = ?, raw = ?
                    WHERE subject_id = ? AND id = ? AND status = 'quarantined'
                    """,
                    (now, _json(raw), subject_id, record_id),
                )
                superseded_records.append(record_id)
        return superseded_records

    def list_media_artifacts(
        self, subject_id: str, *, include_tombstoned: bool = False
    ) -> list[dict[str, Any]]:
        status_clause = "" if include_tombstoned else "AND status = 'active'"
        rows = self._conn.execute(
            f"""
            SELECT * FROM media_artifacts
            WHERE subject_id = ? {status_clause}
            ORDER BY first_seen_at, id
            """,
            (subject_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_media_observations(
        self,
        subject_id: str,
        *,
        artifact_id: str | None = None,
        include_tombstoned: bool = False,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [subject_id]
        artifact_clause = ""
        if artifact_id:
            artifact_clause = "AND artifact_id = ?"
            params.append(artifact_id)
        status_clause = "" if include_tombstoned else "AND status != 'tombstoned'"
        rows = self._conn.execute(
            f"""
            SELECT * FROM media_observations
            WHERE subject_id = ? {artifact_clause} {status_clause}
            ORDER BY created_at, id
            """,
            params,
        ).fetchall()
        return [_media_observation_from_row(row) for row in rows]

    def media_provenance_for_records(
        self, subject_id: str, record_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        ids = list(dict.fromkeys(str(value) for value in record_ids))
        result: dict[str, dict[str, Any]] = {}
        for start in range(0, len(ids), 900):
            batch = ids[start : start + 900]
            placeholders = ",".join("?" for _ in batch)
            rows = self._conn.execute(
                f"""
                SELECT o.*, a.media_sha256, a.modality, a.host_reference,
                       a.host_reference_sha256, a.status AS artifact_status
                FROM media_observations o
                JOIN media_artifacts a ON a.id = o.artifact_id
                WHERE o.subject_id = ? AND o.record_id IN ({placeholders})
                """,
                (subject_id, *batch),
            ).fetchall()
            for row in rows:
                observation = _media_observation_from_row(row)
                observation["media_sha256"] = row["media_sha256"]
                observation["modality"] = row["modality"]
                observation["host_reference"] = row["host_reference"]
                observation["host_reference_sha256"] = row["host_reference_sha256"]
                observation["artifact_status"] = row["artifact_status"]
                result[str(row["record_id"])] = observation
        return result

    def tombstone_media_artifact(
        self, subject_id: str, artifact_id: str
    ) -> dict[str, Any]:
        deleted_at = utc_now()
        with self.transaction():
            self._conn.execute(
                """
                UPDATE media_observations
                SET status = 'tombstoned', segment_json = '{}',
                    extractor_identity_json = '{}', confidence = NULL,
                    deleted_at = ?
                WHERE subject_id = ? AND artifact_id = ?
                """,
                (deleted_at, subject_id, artifact_id),
            )
            self._conn.execute(
                """
                UPDATE media_artifacts
                SET status = 'tombstoned', host_reference = '', deleted_at = ?
                WHERE subject_id = ? AND id = ?
                """,
                (deleted_at, subject_id, artifact_id),
            )
        observations = self.list_media_observations(
            subject_id, artifact_id=artifact_id, include_tombstoned=True
        )
        artifact = self.get_media_artifact(subject_id, artifact_id=artifact_id)
        return {
            "artifact_tombstoned": bool(
                artifact
                and artifact["status"] == "tombstoned"
                and artifact["host_reference"] == ""
            ),
            "observation_ids": [str(item["id"]) for item in observations],
            "observations_tombstoned": all(
                item["status"] == "tombstoned"
                and item["segment"] == {}
                and item["extractor"] == {}
                and item["confidence"] is None
                for item in observations
            ),
            "verified_at": utc_now(),
        }

    def tombstone_media_observations_for_records(
        self, subject_id: str, record_ids: list[str]
    ) -> dict[str, Any]:
        ids = list(dict.fromkeys(str(value) for value in record_ids))
        if not ids:
            return {"observation_ids": [], "artifact_ids": []}
        observations: list[sqlite3.Row] = []
        for start in range(0, len(ids), 900):
            batch = ids[start : start + 900]
            placeholders = ",".join("?" for _ in batch)
            observations.extend(
                self._conn.execute(
                    f"""
                    SELECT id, artifact_id FROM media_observations
                    WHERE subject_id = ? AND record_id IN ({placeholders})
                      AND status != 'tombstoned'
                    """,
                    (subject_id, *batch),
                ).fetchall()
            )
        observation_ids = [str(row["id"]) for row in observations]
        artifact_ids = list(
            dict.fromkeys(str(row["artifact_id"]) for row in observations)
        )
        if not observation_ids:
            return {"observation_ids": [], "artifact_ids": []}
        deleted_at = utc_now()
        with self.transaction():
            for start in range(0, len(observation_ids), 900):
                batch = observation_ids[start : start + 900]
                placeholders = ",".join("?" for _ in batch)
                self._conn.execute(
                    f"""
                    UPDATE media_observations
                    SET status = 'tombstoned', segment_json = '{{}}',
                        extractor_identity_json = '{{}}', confidence = NULL,
                        deleted_at = ?
                    WHERE subject_id = ? AND id IN ({placeholders})
                    """,
                    (deleted_at, subject_id, *batch),
                )
            tombstoned_artifact_ids: list[str] = []
            for artifact_id in artifact_ids:
                remaining = self._conn.execute(
                    """
                    SELECT 1 FROM media_observations
                    WHERE subject_id = ? AND artifact_id = ?
                      AND status != 'tombstoned'
                    LIMIT 1
                    """,
                    (subject_id, artifact_id),
                ).fetchone()
                if remaining is not None:
                    continue
                self._conn.execute(
                    """
                    UPDATE media_artifacts
                    SET status = 'tombstoned', host_reference = '',
                        deleted_at = ?
                    WHERE subject_id = ? AND id = ?
                    """,
                    (deleted_at, subject_id, artifact_id),
                )
                tombstoned_artifact_ids.append(artifact_id)
        return {
            "observation_ids": observation_ids,
            "artifact_ids": tombstoned_artifact_ids,
        }

    def find_duplicate_record(
        self,
        subject_id: str,
        content: str,
        *,
        statuses: tuple[str, ...],
    ) -> dict[str, Any] | None:
        normalized = normalize_content(content)
        if not normalized or not statuses:
            return None
        placeholders = ",".join("?" for _ in statuses)
        row = self._conn.execute(
            f"""
            SELECT * FROM records
            WHERE subject_id = ? AND content_normalized = ?
              AND status IN ({placeholders})
            ORDER BY created_at, id
            LIMIT 1
            """,
            (subject_id, normalized, *statuses),
        ).fetchone()
        return _record_from_row(row) if row else None

    def active_records_for_fact_key(
        self,
        subject_id: str,
        fact_key: str | None,
        *,
        exclude_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not fact_key:
            return []
        params: list[Any] = [subject_id, fact_key]
        exclusion = ""
        if exclude_id is not None:
            exclusion = "AND id != ?"
            params.append(exclude_id)
        rows = self._conn.execute(
            f"""
            SELECT * FROM records
            WHERE subject_id = ? AND fact_key = ? AND status = 'active'
              {exclusion}
            ORDER BY created_at, id
            """,
            params,
        ).fetchall()
        return [_record_from_row(row) for row in rows]

    def promote_record(
        self,
        *,
        subject_id: str,
        record_id: str,
        trust_tier: str = "user_confirmed",
    ) -> dict[str, Any] | None:
        """Activate a quarantined record. Returns the record, or None if it
        was not quarantined (promotion is only meaningful from quarantine)."""
        updated_at = utc_now()
        with self.transaction():
            row = self._conn.execute(
                """
                SELECT * FROM records
                WHERE subject_id = ? AND id = ? AND status = 'quarantined'
                """,
                (subject_id, record_id),
            ).fetchone()
            if row is None:
                return None
            self._conn.execute(
                """
                UPDATE records
                SET status = 'active', trust_tier = ?, updated_at = ?
                WHERE subject_id = ? AND id = ?
                """,
                (trust_tier, updated_at, subject_id, record_id),
            )
            self._upsert_fts(record_id, subject_id, row["content"])
        return self.get_record(subject_id, record_id)

    def supersede_records(
        self,
        *,
        subject_id: str,
        record_ids: list[str],
        superseded_by_id: str,
    ) -> None:
        if not record_ids:
            return
        updated_at = utc_now()
        with self.transaction():
            for record_id in record_ids:
                row = self._conn.execute(
                    """
                    SELECT raw FROM records
                    WHERE subject_id = ? AND id = ? AND status = 'active'
                    """,
                    (subject_id, record_id),
                ).fetchone()
                if row is None:
                    continue
                raw = _load_json(row["raw"], {})
                raw["superseded_by_id"] = superseded_by_id
                self._conn.execute(
                    """
                    UPDATE records
                    SET status = 'superseded', updated_at = ?, raw = ?
                    WHERE subject_id = ? AND id = ? AND status = 'active'
                    """,
                    (updated_at, _json(raw), subject_id, record_id),
                )
                self._delete_fts(record_id)

    def tombstone_records(
        self, *, subject_id: str, record_ids: list[str]
    ) -> tuple[list[str], list[str]]:
        """Tombstone + purge records; returns (record_ids, episode_ids) purged.

        Applies to active, quarantined, and superseded records alike. Purging
        clears content *and* fact_key, since the fact slot name itself can
        reveal what was stored.
        """
        if not record_ids:
            return [], []
        deleted_at = utc_now()
        changed: list[str] = []
        with self.transaction():
            for record_id in record_ids:
                row = self._conn.execute(
                    """
                    SELECT id FROM records
                    WHERE subject_id = ? AND id = ?
                      AND status IN ('active', 'quarantined', 'superseded')
                    """,
                    (subject_id, record_id),
                ).fetchone()
                if row is None:
                    continue
                self._conn.execute(
                    """
                    UPDATE records
                    SET status = 'tombstoned',
                        content = '',
                        content_normalized = NULL,
                        fact_key = NULL,
                        updated_at = ?,
                        deleted_at = ?,
                        raw = ?
                    WHERE subject_id = ? AND id = ?
                    """,
                    (
                        deleted_at,
                        deleted_at,
                        _json({"purged": True}),
                        subject_id,
                        record_id,
                    ),
                )
                self._delete_fts(record_id)
                changed.append(record_id)
            episode_ids: list[str] = []
            if changed:
                placeholders = ",".join("?" for _ in changed)
                episode_rows = self._conn.execute(
                    f"""
                    SELECT DISTINCT episode_id FROM records
                    WHERE subject_id = ? AND id IN ({placeholders})
                      AND episode_id IS NOT NULL
                    """,
                    (subject_id, *changed),
                ).fetchall()
                episode_ids = [row["episode_id"] for row in episode_rows]
            if episode_ids:
                placeholders = ",".join("?" for _ in episode_ids)
                self._conn.execute(
                    f"""
                    UPDATE episodes
                    SET message = '[purged]', raw = ?
                    WHERE subject_id = ? AND id IN ({placeholders})
                    """,
                    (_json({"purged": True}), subject_id, *episode_ids),
                )
        return changed, episode_ids

    def list_records(
        self,
        subject_id: str,
        *,
        statuses: tuple[str, ...] | None = ("active",),
    ) -> list[dict[str, Any]]:
        params: list[Any] = [subject_id]
        status_clause = ""
        if statuses is not None:
            status_clause = f"AND status IN ({','.join('?' for _ in statuses)})"
            params.extend(statuses)
        rows = self._conn.execute(
            f"""
            SELECT * FROM records
            WHERE subject_id = ? {status_clause}
            ORDER BY created_at ASC, id ASC
            """,
            params,
        ).fetchall()
        return [_record_from_row(row) for row in rows]

    def recall_candidates(
        self,
        subject_id: str,
        terms: list[str],
        *,
        limit: int = 200,
    ) -> tuple[list[dict[str, Any]], dict[str, float]]:
        """Bound recall work to FTS matches plus the most recent actives."""
        limit = max(1, min(int(limit), 2000))
        scores = self.fts_match_scores(subject_id, terms, limit=limit)
        matched_ids = list(scores)
        rows: list[sqlite3.Row] = []
        if matched_ids:
            placeholders = ",".join("?" for _ in matched_ids)
            rows.extend(
                self._conn.execute(
                    f"SELECT * FROM records WHERE subject_id = ? AND status = 'active' "
                    f"AND id IN ({placeholders})",
                    (subject_id, *matched_ids),
                ).fetchall()
            )
        seen = {str(row["id"]) for row in rows}
        if len(rows) < limit:
            recent = self._conn.execute(
                """
                SELECT * FROM records
                WHERE subject_id = ? AND status = 'active'
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (subject_id, limit + len(seen)),
            ).fetchall()
            for row in recent:
                if str(row["id"]) not in seen:
                    rows.append(row)
                    seen.add(str(row["id"]))
                    if len(rows) >= limit:
                        break
        records = [_record_from_row(row) for row in rows]
        records.sort(key=lambda record: (record["created_at"], record["id"]))
        return records, scores

    def list_episodes(self, subject_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM episodes
            WHERE subject_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (subject_id,),
        ).fetchall()
        return [_episode_from_row(row) for row in rows]

    def insert_retrieval_event(
        self,
        *,
        subject_id: str,
        session_id: str | None,
        query: str,
        query_sha256: str,
        candidates: list[dict[str, Any]],
        returned_ids: list[str],
        raw: dict[str, Any] | None = None,
    ) -> str:
        event_id = _new_id("ret")
        created_at = utc_now()
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO retrieval_events (
                  id, subject_id, session_id, query, query_sha256, candidates,
                  returned_ids, created_at, raw
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    subject_id,
                    session_id,
                    query,
                    query_sha256,
                    _json(candidates),
                    _json(returned_ids),
                    created_at,
                    _json(raw or {}),
                ),
            )
        return event_id

    def list_retrieval_events(
        self,
        subject_id: str,
        *,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [subject_id]
        session_clause = ""
        if session_id is not None:
            session_clause = "AND session_id = ?"
            params.append(session_id)
        rows = self._conn.execute(
            f"""
            SELECT * FROM retrieval_events
            WHERE subject_id = ? {session_clause}
            ORDER BY created_at ASC, id ASC
            """,
            params,
        ).fetchall()
        return [_retrieval_from_row(row) for row in rows]

    def append_audit_event(
        self,
        *,
        subject_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        actor: str = "system",
        session_id: str | None = None,
        turn_id: str | None = None,
        record_id: str | None = None,
    ) -> str:
        event_id = _new_id("aud")
        created_at = utc_now()
        payload_json = _json(payload or {})
        with self.transaction(immediate=True):
            previous = self._conn.execute(
                """
                SELECT event_hash FROM audit_log
                WHERE subject_id = ?
                ORDER BY sequence DESC
                LIMIT 1
                """,
                (subject_id,),
            ).fetchone()
            prev_hash = previous["event_hash"] if previous else None
            event_hash = _event_hash(
                {
                    "event_id": event_id,
                    "subject_id": subject_id,
                    "event_type": event_type,
                    "created_at": created_at,
                    "actor": actor,
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "record_id": record_id,
                    "payload": json.loads(payload_json),
                    "prev_hash": prev_hash,
                }
            )
            self._conn.execute(
                """
                INSERT INTO audit_log (
                  event_id, subject_id, event_type, created_at, actor,
                  session_id, turn_id, record_id, payload, prev_hash, event_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    subject_id,
                    event_type,
                    created_at,
                    actor,
                    session_id,
                    turn_id,
                    record_id,
                    payload_json,
                    prev_hash,
                    event_hash,
                ),
            )
        return event_id

    def fts_match_scores(
        self, subject_id: str, terms: list[str], *, limit: int | None = None
    ) -> dict[str, float]:
        """Full-text relevance for active records, higher is better.

        Returns {} when FTS5 is unavailable or the query has no usable terms,
        in which case callers fall back to a lexical overlap scorer.
        """
        if not self._fts_enabled or not terms:
            return {}
        match_expr = " OR ".join(
            '"' + term.replace('"', "") + '"' for term in terms if term.strip()
        )
        if not match_expr:
            return {}
        try:
            sql = """
                SELECT record_id, bm25(records_fts) AS rank
                FROM records_fts
                WHERE records_fts MATCH ? AND subject_id = ?
                ORDER BY bm25(records_fts), record_id
                """
            params: tuple[Any, ...] = (match_expr, subject_id)
            if limit is not None:
                sql += " LIMIT ?"
                params = (*params, max(1, int(limit)))
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return {}
        # SQLite bm25() is lower-is-better (usually negative); negate it.
        return {row["record_id"]: -float(row["rank"]) for row in rows}

    def list_audit_events(self, subject_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM audit_log
            WHERE subject_id = ?
            ORDER BY sequence ASC
            """,
            (subject_id,),
        ).fetchall()
        return [_audit_from_row(row) for row in rows]

    def query_audit_events(
        self,
        subject_id: str,
        *,
        query: str = "",
        event_type: str = "",
        actor: str = "",
        session_id: str = "",
        record_id: str = "",
        since: str = "",
        until: str = "",
        cursor: int | None = None,
        limit: int = 100,
        direction: str = "desc",
    ) -> dict[str, Any]:
        """Indexed, cursor-paginated audit discovery for investigation UIs."""
        if direction not in {"asc", "desc"}:
            raise ValueError("direction must be asc or desc")
        page_size = max(1, min(int(limit), 500))
        clauses = ["subject_id = ?"]
        params: list[Any] = [subject_id]
        if event_type:
            clauses.append("event_type GLOB ?")
            params.append(event_type)
        if actor:
            clauses.append("actor = ?")
            params.append(actor)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if record_id:
            clauses.append(
                "(record_id = ? OR EXISTS ("
                "SELECT 1 FROM json_tree(audit_log.payload) "
                "WHERE json_tree.value = ?))"
            )
            params.extend([record_id, record_id])
        if since:
            clauses.append("created_at >= ?")
            params.append(since)
        if until:
            clauses.append("created_at <= ?")
            params.append(until)
        if query:
            if self._audit_fts_enabled:
                clauses.append(
                    "sequence IN (SELECT rowid FROM audit_fts "
                    "WHERE audit_fts MATCH ? AND subject_id = ?)"
                )
                params.extend([_audit_fts_query(query), subject_id])
            else:
                escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                pattern = f"%{escaped}%"
                clauses.append(
                    "(event_id LIKE ? ESCAPE '\\' OR event_type LIKE ? ESCAPE '\\' "
                    "OR actor LIKE ? ESCAPE '\\' OR COALESCE(session_id, '') LIKE ? ESCAPE '\\' "
                    "OR COALESCE(turn_id, '') LIKE ? ESCAPE '\\' "
                    "OR COALESCE(record_id, '') LIKE ? ESCAPE '\\' "
                    "OR payload LIKE ? ESCAPE '\\')"
                )
                params.extend([pattern] * 7)
        count_where = " AND ".join(clauses)
        count_params = list(params)
        if cursor is not None:
            clauses.append(f"sequence {'<' if direction == 'desc' else '>'} ?")
            params.append(int(cursor))
        where = " AND ".join(clauses)
        rows = self._conn.execute(
            f"""
            SELECT * FROM audit_log
            WHERE {where}
            ORDER BY sequence {direction.upper()}
            LIMIT ?
            """,
            (*params, page_size + 1),
        ).fetchall()
        has_more = len(rows) > page_size
        rows = rows[:page_size]
        events = [_audit_from_row(row) for row in rows]
        matched_total = int(
            self._conn.execute(
                f"SELECT COUNT(*) AS count FROM audit_log WHERE {count_where}",
                count_params,
            ).fetchone()["count"]
        )
        return {
            "events": events,
            "matched_total": matched_total,
            "has_more": has_more,
            "next_cursor": int(rows[-1]["sequence"]) if has_more and rows else None,
            "direction": direction,
            "limit": page_size,
        }

    def audit_event_facets(self, subject_id: str) -> dict[str, list[dict[str, Any]]]:
        """Low-cardinality facets used by the audit explorer."""
        event_types = self._conn.execute(
            """
            SELECT event_type AS value, COUNT(*) AS count
            FROM audit_log WHERE subject_id = ?
            GROUP BY event_type ORDER BY count DESC, value ASC LIMIT 250
            """,
            (subject_id,),
        ).fetchall()
        actors = self._conn.execute(
            """
            SELECT actor AS value, COUNT(*) AS count
            FROM audit_log WHERE subject_id = ?
            GROUP BY actor ORDER BY count DESC, value ASC LIMIT 100
            """,
            (subject_id,),
        ).fetchall()
        return {
            "event_types": [dict(row) for row in event_types],
            "actors": [dict(row) for row in actors],
        }

    def audit_event_histogram(
        self,
        subject_id: str,
        *,
        query: str = "",
        event_type: str = "",
        actor: str = "",
        session_id: str = "",
        record_id: str = "",
        since: str = "",
        until: str = "",
        bucket: str = "hour",
    ) -> list[dict[str, Any]]:
        if bucket not in {"hour", "day"}:
            raise ValueError("bucket must be hour or day")
        clauses = ["subject_id = ?"]
        params: list[Any] = [subject_id]
        if event_type:
            clauses.append("event_type GLOB ?")
            params.append(event_type)
        if actor:
            clauses.append("actor = ?")
            params.append(actor)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if record_id:
            clauses.append(
                "(record_id = ? OR EXISTS (SELECT 1 FROM json_tree(audit_log.payload) "
                "WHERE json_tree.value = ?))"
            )
            params.extend([record_id, record_id])
        if query:
            if self._audit_fts_enabled:
                clauses.append(
                    "sequence IN (SELECT rowid FROM audit_fts "
                    "WHERE audit_fts MATCH ? AND subject_id = ?)"
                )
                params.extend([_audit_fts_query(query), subject_id])
            else:
                escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                pattern = f"%{escaped}%"
                clauses.append(
                    "(event_id LIKE ? ESCAPE '\\' OR event_type LIKE ? ESCAPE '\\' "
                    "OR actor LIKE ? ESCAPE '\\' OR COALESCE(session_id, '') LIKE ? ESCAPE '\\' "
                    "OR COALESCE(turn_id, '') LIKE ? ESCAPE '\\' "
                    "OR COALESCE(record_id, '') LIKE ? ESCAPE '\\' "
                    "OR payload LIKE ? ESCAPE '\\')"
                )
                params.extend([pattern] * 7)
        if since:
            clauses.append("created_at >= ?")
            params.append(since)
        if until:
            clauses.append("created_at <= ?")
            params.append(until)
        width = 13 if bucket == "hour" else 10
        rows = self._conn.execute(
            f"""
            SELECT substr(created_at, 1, {width}) AS bucket, COUNT(*) AS count
            FROM audit_log WHERE {' AND '.join(clauses)}
            GROUP BY bucket ORDER BY bucket ASC LIMIT 1000
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def get_audit_event(self, subject_id: str, event_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM audit_log WHERE subject_id = ? AND event_id = ?",
            (subject_id, event_id),
        ).fetchone()
        return _audit_from_row(row) if row else None

    def event_at_sequence(
        self, subject_id: str, sequence: int
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM audit_log WHERE subject_id = ? AND sequence = ?",
            (subject_id, sequence),
        ).fetchone()
        return _audit_from_row(row) if row else None

    def chain_heads(self) -> dict[str, dict[str, Any]]:
        """Latest audit event per subject: {subject_id: {sequence, event_hash,
        event_count}}. This is what a checkpoint anchors."""
        rows = self._conn.execute("""
            SELECT a.subject_id, a.sequence, a.event_hash,
                   (SELECT COUNT(*) FROM audit_log b
                    WHERE b.subject_id = a.subject_id) AS event_count
            FROM audit_log a
            WHERE a.sequence = (
              SELECT MAX(c.sequence) FROM audit_log c
              WHERE c.subject_id = a.subject_id
            )
            """).fetchall()
        return {
            row["subject_id"]: {
                "sequence": row["sequence"],
                "event_hash": row["event_hash"],
                "event_count": row["event_count"],
            }
            for row in rows
        }

    def verify_audit_chain(self, subject_id: str) -> bool:
        previous_hash: str | None = None
        for event in self.list_audit_events(subject_id):
            expected = _event_hash(
                {
                    "event_id": event["event_id"],
                    "subject_id": event["subject_id"],
                    "event_type": event["event_type"],
                    "created_at": event["created_at"],
                    "actor": event["actor"],
                    "session_id": event["session_id"],
                    "turn_id": event["turn_id"],
                    "record_id": event["record_id"],
                    "payload": event["payload"],
                    "prev_hash": previous_hash,
                }
            )
            if event["prev_hash"] != previous_hash or event["event_hash"] != expected:
                return False
            previous_hash = event["event_hash"]
        return True

    def verify_audit_chain_incremental(
        self, subject_id: str, *, reset: bool = False
    ) -> dict[str, Any]:
        """Verify only the suffix after a locally cached, hash-checked head.

        This is a performance cache, not an external trust anchor. The cached
        event is re-read and hash-compared on every run; externally anchored
        checkpoints remain necessary against whole-database replacement.
        """
        if reset:
            with self.transaction():
                self._conn.execute(
                    "DELETE FROM audit_verification_state WHERE subject_id = ?",
                    (subject_id,),
                )
        state = (
            None
            if reset
            else self._conn.execute(
                "SELECT * FROM audit_verification_state WHERE subject_id = ?",
                (subject_id,),
            ).fetchone()
        )
        previous_hash: str | None = None
        start_sequence = 0
        if state is not None:
            anchor = self.event_at_sequence(subject_id, int(state["sequence"]))
            anchor_expected = (
                _event_hash(
                    {
                        "event_id": anchor["event_id"],
                        "subject_id": anchor["subject_id"],
                        "event_type": anchor["event_type"],
                        "created_at": anchor["created_at"],
                        "actor": anchor["actor"],
                        "session_id": anchor["session_id"],
                        "turn_id": anchor["turn_id"],
                        "record_id": anchor["record_id"],
                        "payload": anchor["payload"],
                        "prev_hash": anchor["prev_hash"],
                    }
                )
                if anchor is not None
                else None
            )
            if (
                anchor is None
                or anchor["event_hash"] != state["event_hash"]
                or anchor_expected != anchor["event_hash"]
            ):
                return {
                    "valid": False,
                    "cached_from_sequence": int(state["sequence"]),
                    "verified_events": 0,
                    "failure": "cached verification anchor is missing or changed",
                }
            start_sequence = int(state["sequence"])
            previous_hash = str(state["event_hash"])

        rows = self._conn.execute(
            """
            SELECT * FROM audit_log
            WHERE subject_id = ? AND sequence > ?
            ORDER BY sequence ASC
            """,
            (subject_id, start_sequence),
        ).fetchall()
        verified = 0
        last_sequence = start_sequence
        for row in rows:
            event = _audit_from_row(row)
            expected = _event_hash(
                {
                    "event_id": event["event_id"],
                    "subject_id": event["subject_id"],
                    "event_type": event["event_type"],
                    "created_at": event["created_at"],
                    "actor": event["actor"],
                    "session_id": event["session_id"],
                    "turn_id": event["turn_id"],
                    "record_id": event["record_id"],
                    "payload": event["payload"],
                    "prev_hash": previous_hash,
                }
            )
            if event["prev_hash"] != previous_hash or event["event_hash"] != expected:
                return {
                    "valid": False,
                    "cached_from_sequence": start_sequence,
                    "verified_events": verified,
                    "failure": f"audit mismatch at sequence {event['sequence']}",
                }
            previous_hash = str(event["event_hash"])
            last_sequence = int(event["sequence"])
            verified += 1

        if last_sequence:
            with self.transaction():
                self._conn.execute(
                    """
                    INSERT INTO audit_verification_state (
                      subject_id, sequence, event_hash, verified_at
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(subject_id) DO UPDATE SET
                      sequence = excluded.sequence,
                      event_hash = excluded.event_hash,
                      verified_at = excluded.verified_at
                    """,
                    (subject_id, last_sequence, previous_hash, utc_now()),
                )
        return {
            "valid": True,
            "cached_from_sequence": start_sequence,
            "verified_through_sequence": last_sequence,
            "verified_events": verified,
            "failure": None,
        }

    def subject_ids(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT subject_id FROM audit_log ORDER BY subject_id"
        ).fetchall()
        return [str(row["subject_id"]) for row in rows]

    def register_semantic_index(
        self,
        subject_id: str,
        index_path: str,
        *,
        active_epoch_id: str | None = None,
    ) -> None:
        normalized = str(Path(index_path).expanduser().resolve())
        path_sha256 = sha256_hex(normalized)
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO semantic_index_registry(
                  subject_id, index_path, index_path_sha256, active_epoch_id,
                  registered_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject_id, index_path_sha256) DO UPDATE SET
                  index_path = excluded.index_path,
                  active_epoch_id = COALESCE(
                    excluded.active_epoch_id,
                    semantic_index_registry.active_epoch_id
                  ),
                  updated_at = excluded.updated_at
                """,
                (
                    subject_id,
                    normalized,
                    path_sha256,
                    active_epoch_id,
                    utc_now(),
                    utc_now(),
                ),
            )

    def semantic_index_paths(self, subject_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT index_path, index_path_sha256, active_epoch_id,
                   registered_at, updated_at
            FROM semantic_index_registry
            WHERE subject_id = ?
            ORDER BY index_path_sha256
            """,
            (subject_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def append_investigation_access(
        self,
        *,
        subject_id: str,
        operation: str,
        actor: str,
        query_digest: str,
        filters_digest: str,
        result_digest: str,
        result_count: int,
        index_epoch: str | None = None,
        verification_report_digest: str | None = None,
    ) -> str:
        """Append to the access chain without changing the agent evidence chain."""
        access_id = _new_id("access")
        created_at = utc_now()
        with self.transaction(immediate=True):
            previous = self._conn.execute(
                """
                SELECT event_hash FROM investigation_access_log
                WHERE subject_id = ? ORDER BY sequence DESC LIMIT 1
                """,
                (subject_id,),
            ).fetchone()
            prev_hash = str(previous["event_hash"]) if previous else None
            event = {
                "access_id": access_id,
                "subject_id": subject_id,
                "operation": operation,
                "actor": actor,
                "query_digest": query_digest,
                "filters_digest": filters_digest,
                "result_digest": result_digest,
                "result_count": int(result_count),
                "index_epoch": index_epoch,
                "verification_report_digest": verification_report_digest,
                "created_at": created_at,
                "prev_hash": prev_hash,
            }
            event_hash = _event_hash(event)
            self._conn.execute(
                """
                INSERT INTO investigation_access_log(
                  access_id, subject_id, operation, actor, query_digest,
                  filters_digest, result_digest, result_count, index_epoch,
                  verification_report_digest, created_at, prev_hash, event_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    access_id,
                    subject_id,
                    operation,
                    actor,
                    query_digest,
                    filters_digest,
                    result_digest,
                    int(result_count),
                    index_epoch,
                    verification_report_digest,
                    created_at,
                    prev_hash,
                    event_hash,
                ),
            )
        return access_id

    def list_investigation_access(self, subject_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM investigation_access_log
            WHERE subject_id = ? ORDER BY sequence
            """,
            (subject_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def verify_investigation_access(self, subject_id: str) -> dict[str, Any]:
        events = self.list_investigation_access(subject_id)
        previous_hash: str | None = None
        for event in events:
            expected = _event_hash(
                {
                    key: event[key]
                    for key in (
                        "access_id",
                        "subject_id",
                        "operation",
                        "actor",
                        "query_digest",
                        "filters_digest",
                        "result_digest",
                        "result_count",
                        "index_epoch",
                        "verification_report_digest",
                        "created_at",
                        "prev_hash",
                    )
                }
            )
            if event["prev_hash"] != previous_hash or event["event_hash"] != expected:
                return {
                    "valid": False,
                    "events": len(events),
                    "failed_access_id": event["access_id"],
                }
            previous_hash = str(event["event_hash"])
        return {
            "valid": True,
            "events": len(events),
            "failed_access_id": None,
        }

    def optimize(self) -> None:
        self._conn.execute("PRAGMA optimize")

    def _migrate(self) -> None:
        with self.transaction():
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS episodes (
                  id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  session_id TEXT,
                  turn_id TEXT,
                  message TEXT NOT NULL,
                  source_type TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  raw TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS pending_user_messages (
                  source_id TEXT NOT NULL,
                  subject_id TEXT NOT NULL,
                  alias TEXT NOT NULL,
                  message TEXT NOT NULL,
                  run_id TEXT,
                  created_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  PRIMARY KEY (subject_id, alias)
                );

                CREATE INDEX IF NOT EXISTS idx_pending_user_messages_source
                  ON pending_user_messages(source_id);

                CREATE INDEX IF NOT EXISTS idx_pending_user_messages_expiry
                  ON pending_user_messages(expires_at);

                CREATE TABLE IF NOT EXISTS records (
                  id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  content TEXT NOT NULL,
                  content_normalized TEXT,
                  source_type TEXT NOT NULL,
                  trust_tier TEXT NOT NULL,
                  source_session_id TEXT,
                  source_turn_id TEXT,
                  episode_id TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT,
                  deleted_at TEXT,
                  confidence REAL,
                  scope TEXT NOT NULL,
                  status TEXT NOT NULL CHECK (
                    status IN ('active', 'superseded', 'quarantined', 'tombstoned')
                  ),
                  supersedes_id TEXT,
                  fact_key TEXT,
                  raw TEXT NOT NULL DEFAULT '{}',
                  FOREIGN KEY (episode_id) REFERENCES episodes(id),
                  FOREIGN KEY (supersedes_id) REFERENCES records(id)
                );

                CREATE INDEX IF NOT EXISTS idx_records_subject_status
                  ON records(subject_id, status);

                CREATE INDEX IF NOT EXISTS idx_records_subject_key
                  ON records(subject_id, fact_key, status);

                CREATE TABLE IF NOT EXISTS protocol_sources (
                  source_id TEXT PRIMARY KEY,
                  idempotency_key TEXT NOT NULL,
                  payload_sha256 TEXT NOT NULL,
                  subject_id TEXT NOT NULL,
                  agent_id TEXT NOT NULL,
                  workspace_id TEXT NOT NULL,
                  episode_id TEXT NOT NULL,
                  source_sha256 TEXT NOT NULL,
                  request_json TEXT NOT NULL,
                  result_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  UNIQUE(workspace_id, agent_id, idempotency_key),
                  FOREIGN KEY(episode_id) REFERENCES episodes(id)
                );

                CREATE TABLE IF NOT EXISTS protocol_proposals (
                  proposal_id TEXT PRIMARY KEY,
                  idempotency_key TEXT NOT NULL,
                  payload_sha256 TEXT NOT NULL,
                  subject_id TEXT NOT NULL,
                  agent_id TEXT NOT NULL,
                  workspace_id TEXT NOT NULL,
                  decision TEXT NOT NULL,
                  proposal_json TEXT NOT NULL,
                  admission_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  UNIQUE(workspace_id, agent_id, idempotency_key)
                );

                CREATE TABLE IF NOT EXISTS protocol_candidate_sets (
                  candidate_set_id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  agent_id TEXT NOT NULL,
                  workspace_id TEXT NOT NULL,
                  generation INTEGER NOT NULL,
                  expires_at TEXT NOT NULL,
                  value_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS protocol_preparations (
                  preparation_id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  agent_id TEXT NOT NULL,
                  workspace_id TEXT NOT NULL,
                  context_sha256 TEXT NOT NULL,
                  generation INTEGER NOT NULL,
                  expires_at TEXT NOT NULL,
                  value_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS protocol_exposures (
                  confirmation_id TEXT PRIMARY KEY,
                  preparation_id TEXT NOT NULL UNIQUE,
                  receipt_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(preparation_id) REFERENCES protocol_preparations(preparation_id)
                );

                CREATE TABLE IF NOT EXISTS retrieval_exclusions (
                  subject_id TEXT NOT NULL,
                  record_id TEXT NOT NULL,
                  reason TEXT NOT NULL DEFAULT '',
                  actor TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY (subject_id, record_id),
                  FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS media_artifacts (
                  id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  media_sha256 TEXT NOT NULL CHECK (
                    length(media_sha256) = 64
                    AND media_sha256 NOT GLOB '*[^0-9a-f]*'
                  ),
                  modality TEXT NOT NULL CHECK (
                    modality IN ('image', 'audio', 'video', 'document')
                  ),
                  host_reference TEXT NOT NULL,
                  host_reference_sha256 TEXT NOT NULL CHECK (
                    length(host_reference_sha256) = 64
                    AND host_reference_sha256 NOT GLOB '*[^0-9a-f]*'
                  ),
                  digest_assurance TEXT NOT NULL CHECK (
                    digest_assurance IN (
                      'verified_by_atmem', 'host_asserted', 'caller_asserted'
                    )
                  ),
                  status TEXT NOT NULL CHECK (
                    status IN ('active', 'tombstoned')
                  ),
                  first_seen_at TEXT NOT NULL,
                  deleted_at TEXT,
                  UNIQUE(subject_id, media_sha256)
                );

                CREATE INDEX IF NOT EXISTS idx_media_artifacts_subject_digest
                  ON media_artifacts(subject_id, media_sha256, status);

                CREATE TABLE IF NOT EXISTS media_observations (
                  id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  artifact_id TEXT NOT NULL,
                  episode_id TEXT NOT NULL,
                  record_id TEXT NOT NULL UNIQUE,
                  text_sha256 TEXT NOT NULL CHECK (length(text_sha256) = 64),
                  segment_json TEXT NOT NULL DEFAULT '{}',
                  segment_sha256 TEXT NOT NULL CHECK (
                    length(segment_sha256) = 64
                  ),
                  extractor_identity_json TEXT NOT NULL,
                  extractor_identity_sha256 TEXT NOT NULL CHECK (
                    length(extractor_identity_sha256) = 64
                  ),
                  confidence REAL CHECK (
                    confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
                  ),
                  digest_assurance TEXT NOT NULL CHECK (
                    digest_assurance IN (
                      'verified_by_atmem', 'host_asserted', 'caller_asserted'
                    )
                  ),
                  lineage_sha256 TEXT NOT NULL CHECK (
                    length(lineage_sha256) = 64
                  ),
                  envelope_sha256 TEXT NOT NULL CHECK (
                    length(envelope_sha256) = 64
                  ),
                  status TEXT NOT NULL CHECK (
                    status IN ('current', 'superseded', 'tombstoned')
                  ),
                  supersedes_observation_id TEXT,
                  observed_at TEXT,
                  created_at TEXT NOT NULL,
                  deleted_at TEXT,
                  UNIQUE(subject_id, envelope_sha256),
                  FOREIGN KEY(artifact_id) REFERENCES media_artifacts(id),
                  FOREIGN KEY(episode_id) REFERENCES episodes(id),
                  FOREIGN KEY(record_id) REFERENCES records(id),
                  FOREIGN KEY(supersedes_observation_id)
                    REFERENCES media_observations(id)
                );

                CREATE INDEX IF NOT EXISTS idx_media_observations_artifact
                  ON media_observations(subject_id, artifact_id, status);

                CREATE INDEX IF NOT EXISTS idx_media_observations_lineage
                  ON media_observations(subject_id, lineage_sha256, status);

                CREATE INDEX IF NOT EXISTS idx_media_observations_record
                  ON media_observations(subject_id, record_id);

                CREATE TABLE IF NOT EXISTS record_generations (
                  subject_id TEXT PRIMARY KEY,
                  generation INTEGER NOT NULL DEFAULT 0
                );

                CREATE TRIGGER IF NOT EXISTS records_generation_insert
                AFTER INSERT ON records BEGIN
                  INSERT INTO record_generations(subject_id, generation)
                  VALUES (NEW.subject_id, 1)
                  ON CONFLICT(subject_id) DO UPDATE
                    SET generation = generation + 1;
                END;

                CREATE TRIGGER IF NOT EXISTS records_generation_delete
                AFTER DELETE ON records BEGIN
                  INSERT INTO record_generations(subject_id, generation)
                  VALUES (OLD.subject_id, 1)
                  ON CONFLICT(subject_id) DO UPDATE
                    SET generation = generation + 1;
                END;

                CREATE TRIGGER IF NOT EXISTS records_generation_update_same_subject
                AFTER UPDATE ON records
                WHEN OLD.subject_id = NEW.subject_id BEGIN
                  INSERT INTO record_generations(subject_id, generation)
                  VALUES (NEW.subject_id, 1)
                  ON CONFLICT(subject_id) DO UPDATE
                    SET generation = generation + 1;
                END;

                CREATE TRIGGER IF NOT EXISTS records_generation_update_subject
                AFTER UPDATE ON records
                WHEN OLD.subject_id <> NEW.subject_id BEGIN
                  INSERT INTO record_generations(subject_id, generation)
                  VALUES (OLD.subject_id, 1)
                  ON CONFLICT(subject_id) DO UPDATE
                    SET generation = generation + 1;
                  INSERT INTO record_generations(subject_id, generation)
                  VALUES (NEW.subject_id, 1)
                  ON CONFLICT(subject_id) DO UPDATE
                    SET generation = generation + 1;
                END;

                CREATE TABLE IF NOT EXISTS records_fts_map (
                  record_id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  fts_rowid INTEGER NOT NULL UNIQUE
                );

                CREATE INDEX IF NOT EXISTS idx_records_fts_map_subject
                  ON records_fts_map(subject_id);

                CREATE TABLE IF NOT EXISTS retrieval_events (
                  id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  session_id TEXT,
                  query TEXT NOT NULL,
                  query_sha256 TEXT,
                  candidates TEXT NOT NULL DEFAULT '[]',
                  returned_ids TEXT NOT NULL DEFAULT '[]',
                  created_at TEXT NOT NULL,
                  raw TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  event_id TEXT NOT NULL UNIQUE,
                  subject_id TEXT NOT NULL,
                  event_type TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  actor TEXT NOT NULL,
                  session_id TEXT,
                  turn_id TEXT,
                  record_id TEXT,
                  payload TEXT NOT NULL DEFAULT '{}',
                  prev_hash TEXT,
                  event_hash TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_subject_sequence
                  ON audit_log(subject_id, sequence);

                CREATE INDEX IF NOT EXISTS idx_audit_subject_created
                  ON audit_log(subject_id, created_at, sequence);

                CREATE INDEX IF NOT EXISTS idx_audit_subject_type_created
                  ON audit_log(subject_id, event_type, created_at, sequence);

                CREATE INDEX IF NOT EXISTS idx_audit_subject_actor_created
                  ON audit_log(subject_id, actor, created_at, sequence);

                CREATE INDEX IF NOT EXISTS idx_audit_subject_session_created
                  ON audit_log(subject_id, session_id, created_at, sequence);

                CREATE INDEX IF NOT EXISTS idx_audit_subject_record_created
                  ON audit_log(subject_id, record_id, created_at, sequence);

                CREATE INDEX IF NOT EXISTS idx_retrieval_subject_created
                  ON retrieval_events(subject_id, created_at, id);

                CREATE INDEX IF NOT EXISTS idx_retrieval_subject_session_created
                  ON retrieval_events(subject_id, session_id, created_at, id);

                CREATE TABLE IF NOT EXISTS investigation_access_log (
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  access_id TEXT NOT NULL UNIQUE,
                  subject_id TEXT NOT NULL,
                  operation TEXT NOT NULL,
                  actor TEXT NOT NULL,
                  query_digest TEXT NOT NULL,
                  filters_digest TEXT NOT NULL,
                  result_digest TEXT NOT NULL,
                  result_count INTEGER NOT NULL,
                  index_epoch TEXT,
                  verification_report_digest TEXT,
                  created_at TEXT NOT NULL,
                  prev_hash TEXT,
                  event_hash TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_investigation_access_subject
                  ON investigation_access_log(subject_id, sequence);

                CREATE TABLE IF NOT EXISTS semantic_index_registry (
                  subject_id TEXT NOT NULL,
                  index_path TEXT NOT NULL,
                  index_path_sha256 TEXT NOT NULL,
                  active_epoch_id TEXT,
                  registered_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY(subject_id, index_path_sha256)
                );

                CREATE TABLE IF NOT EXISTS entities (
                  id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  canonical TEXT NOT NULL,
                  normalized TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  status TEXT NOT NULL CHECK (
                    status IN ('active', 'quarantined', 'merged', 'tombstoned')
                  ),
                  merged_into TEXT,
                  source_record TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT,
                  UNIQUE (subject_id, normalized, kind),
                  FOREIGN KEY (merged_into) REFERENCES entities(id),
                  FOREIGN KEY (source_record) REFERENCES records(id)
                );

                CREATE INDEX IF NOT EXISTS idx_entities_subject_status
                  ON entities(subject_id, status, kind);

                CREATE TABLE IF NOT EXISTS entity_aliases (
                  id TEXT PRIMARY KEY,
                  entity_id TEXT NOT NULL,
                  subject_id TEXT NOT NULL,
                  surface TEXT NOT NULL,
                  normalized TEXT NOT NULL,
                  source_record TEXT,
                  trust_tier TEXT NOT NULL,
                  status TEXT NOT NULL CHECK (
                    status IN ('active', 'quarantined', 'superseded', 'tombstoned')
                  ),
                  created_at TEXT NOT NULL,
                  UNIQUE (subject_id, entity_id, normalized, source_record),
                  FOREIGN KEY (entity_id) REFERENCES entities(id),
                  FOREIGN KEY (source_record) REFERENCES records(id)
                );

                CREATE INDEX IF NOT EXISTS idx_aliases_subject_surface
                  ON entity_aliases(subject_id, normalized, status);

                CREATE TABLE IF NOT EXISTS edges (
                  id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  src_entity TEXT NOT NULL,
                  relation TEXT NOT NULL,
                  relation_label TEXT NOT NULL,
                  dst_entity TEXT,
                  dst_value TEXT,
                  record_id TEXT NOT NULL,
                  trust_tier TEXT NOT NULL,
                  confidence REAL,
                  status TEXT NOT NULL CHECK (
                    status IN ('active', 'superseded', 'quarantined', 'tombstoned')
                  ),
                  supersedes_id TEXT,
                  extractor_version TEXT NOT NULL DEFAULT 'graph-rules-v1',
                  created_at TEXT NOT NULL,
                  updated_at TEXT,
                  UNIQUE (subject_id, record_id),
                  FOREIGN KEY (record_id) REFERENCES records(id),
                  FOREIGN KEY (src_entity) REFERENCES entities(id),
                  FOREIGN KEY (dst_entity) REFERENCES entities(id),
                  FOREIGN KEY (supersedes_id) REFERENCES edges(id)
                );

                CREATE INDEX IF NOT EXISTS idx_edges_src
                  ON edges(subject_id, src_entity, relation, status);

                CREATE INDEX IF NOT EXISTS idx_edges_dst
                  ON edges(subject_id, dst_entity, status);

                CREATE INDEX IF NOT EXISTS idx_edges_record
                  ON edges(subject_id, record_id, status);

                CREATE TABLE IF NOT EXISTS graph_fts_map (
                  object_type TEXT NOT NULL,
                  object_id TEXT NOT NULL,
                  subject_id TEXT NOT NULL,
                  fts_rowid INTEGER NOT NULL UNIQUE,
                  PRIMARY KEY (object_type, object_id)
                );

                CREATE INDEX IF NOT EXISTS idx_graph_fts_map_subject
                  ON graph_fts_map(subject_id);

                CREATE TABLE IF NOT EXISTS graph_merge_proposals (
                  id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  left_entity TEXT NOT NULL,
                  right_entity TEXT NOT NULL,
                  confidence REAL NOT NULL,
                  reason TEXT NOT NULL,
                  evidence_record_ids TEXT NOT NULL DEFAULT '[]',
                  status TEXT NOT NULL CHECK (
                    status IN ('pending', 'approved', 'rejected', 'reverted')
                  ),
                  winner_entity TEXT,
                  proposed_at TEXT NOT NULL,
                  decided_at TEXT,
                  decided_by TEXT,
                  UNIQUE (subject_id, left_entity, right_entity),
                  FOREIGN KEY (left_entity) REFERENCES entities(id),
                  FOREIGN KEY (right_entity) REFERENCES entities(id),
                  FOREIGN KEY (winner_entity) REFERENCES entities(id)
                );

                CREATE INDEX IF NOT EXISTS idx_graph_merge_status
                  ON graph_merge_proposals(subject_id, status, proposed_at);

                CREATE TABLE IF NOT EXISTS graph_archive_partitions (
                  id TEXT PRIMARY KEY,
                  subject_id TEXT NOT NULL,
                  partition_year INTEGER NOT NULL,
                  path TEXT NOT NULL,
                  cutoff TEXT NOT NULL,
                  row_count INTEGER NOT NULL,
                  content_sha256 TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  UNIQUE (subject_id, partition_year, path)
                );

                CREATE INDEX IF NOT EXISTS idx_graph_archive_subject
                  ON graph_archive_partitions(subject_id, partition_year);

                CREATE TABLE IF NOT EXISTS graph_archive_members (
                  subject_id TEXT NOT NULL,
                  object_type TEXT NOT NULL,
                  object_id TEXT NOT NULL,
                  source_record_id TEXT NOT NULL,
                  partition_id TEXT NOT NULL,
                  archived_at TEXT NOT NULL,
                  PRIMARY KEY (object_type, object_id),
                  FOREIGN KEY (partition_id) REFERENCES graph_archive_partitions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_graph_archive_record
                  ON graph_archive_members(subject_id, source_record_id);

                CREATE TABLE IF NOT EXISTS audit_verification_state (
                  subject_id TEXT PRIMARY KEY,
                  sequence INTEGER NOT NULL,
                  event_hash TEXT NOT NULL,
                  verified_at TEXT NOT NULL
                );

                CREATE TRIGGER IF NOT EXISTS invalidate_audit_verification_update
                AFTER UPDATE ON audit_log
                BEGIN
                  DELETE FROM audit_verification_state
                  WHERE subject_id IN (OLD.subject_id, NEW.subject_id);
                END;

                CREATE TRIGGER IF NOT EXISTS invalidate_audit_verification_delete
                AFTER DELETE ON audit_log
                BEGIN
                  DELETE FROM audit_verification_state
                  WHERE subject_id = OLD.subject_id;
                END;
                """)
            self._ensure_column("records", "fact_key", "TEXT")
            self._ensure_column("records", "content_normalized", "TEXT")
            self._ensure_column("retrieval_events", "query_sha256", "TEXT")
            self._ensure_column(
                "edges", "extractor_version", "TEXT NOT NULL DEFAULT 'graph-rules-v1'"
            )
            self._migrate_alias_status()
            self._backfill_record_normalization()
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_records_subject_normalized
                ON records(subject_id, status, content_normalized)
                """)
            self._migrate_fts()
            self._migrate_graph_fts()
            self._migrate_audit_fts()
            self._apply_bootstrap_migrations()

    def _apply_bootstrap_migrations(self) -> None:
        """Apply the reserved, append-only bootstrap steps exactly once.

        The unnumbered initializer above remains the pre-registry baseline.
        Numbered steps are recorded in ``schema_migrations`` so the future
        canonical registry (Spec 010) can import these identifiers without
        renumbering or replaying them. Every step is written to be safe to run
        against a database that already contains its objects, so an interrupted
        upgrade re-runs forward instead of needing repair.
        """
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
              identifier TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL
            )
            """)
        applied = {
            str(row["identifier"])
            for row in self._conn.execute(
                "SELECT identifier FROM schema_migrations"
            ).fetchall()
        }
        # Column additions cannot be expressed idempotently in a script, so
        # they are ensured here instead. 0063's trigger and 0077's indexes are
        # compiled against these columns, so they are added before any script
        # runs -- and each `_ensure_column` is safe to repeat.
        self._ensure_column("records", "generation", "INTEGER NOT NULL DEFAULT 0")
        for identifier, script in _BOOTSTRAP_MIGRATIONS:
            if identifier in applied:
                continue
            if identifier == "0077_governed_task_sequences":
                for table in ("governed_task_steps", "governed_task_deliveries"):
                    self._ensure_column(
                        table, "sequence", "INTEGER NOT NULL DEFAULT 0"
                    )
            self._conn.executescript(script)
            self._conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(identifier, applied_at) "
                "VALUES (?, ?)",
                (identifier, utc_now()),
            )

    def applied_migrations(self) -> list[str]:
        """Bootstrap identifiers this database has already applied, in order."""
        return [
            str(row["identifier"])
            for row in self._conn.execute(
                "SELECT identifier FROM schema_migrations ORDER BY identifier"
            ).fetchall()
        ]

    def _ensure_column(self, table: str, column: str, column_type: str) -> None:
        """Add a column if it is missing, tolerating a concurrent first open.

        `executescript` commits any open transaction, so migration steps after
        one are not serialized by the outer BEGIN IMMEDIATE. Two processes
        opening a new database at the same moment can therefore both decide the
        column is missing. Losing that race is not an error: the column exists
        either way, which is exactly what this method promises.
        """
        columns = {
            row["name"]
            for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column in columns:
            return
        try:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise

    def _backfill_record_normalization(self) -> None:
        rows = self._conn.execute("""
            SELECT id, content FROM records
            WHERE content_normalized IS NULL AND status != 'tombstoned'
            """).fetchall()
        for row in rows:
            self._conn.execute(
                "UPDATE records SET content_normalized = ? WHERE id = ?",
                (normalize_content(str(row["content"])), row["id"]),
            )

    def _migrate_alias_status(self) -> None:
        schema = self._conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'entity_aliases'"
        ).fetchone()
        if schema is None or "'superseded'" in str(schema["sql"]):
            return
        self._conn.execute("ALTER TABLE entity_aliases RENAME TO entity_aliases_legacy")
        self._conn.execute("""
            CREATE TABLE entity_aliases (
              id TEXT PRIMARY KEY,
              entity_id TEXT NOT NULL,
              subject_id TEXT NOT NULL,
              surface TEXT NOT NULL,
              normalized TEXT NOT NULL,
              source_record TEXT,
              trust_tier TEXT NOT NULL,
              status TEXT NOT NULL CHECK (
                status IN ('active', 'quarantined', 'superseded', 'tombstoned')
              ),
              created_at TEXT NOT NULL,
              UNIQUE (subject_id, entity_id, normalized, source_record),
              FOREIGN KEY (entity_id) REFERENCES entities(id),
              FOREIGN KEY (source_record) REFERENCES records(id)
            )
            """)
        self._conn.execute("""
            INSERT INTO entity_aliases (
              id, entity_id, subject_id, surface, normalized, source_record,
              trust_tier, status, created_at
            )
            SELECT id, entity_id, subject_id, surface, normalized, source_record,
                   trust_tier, status, created_at
            FROM entity_aliases_legacy
            """)
        self._conn.execute("DROP TABLE entity_aliases_legacy")
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_aliases_subject_surface
            ON entity_aliases(subject_id, normalized, status)
            """)

    def _migrate_fts(self) -> None:
        try:
            existing = self._conn.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'records_fts'"
            ).fetchone()
            if existing is not None and "porter" not in (existing["sql"] or ""):
                self._conn.execute("DROP TABLE records_fts")
                existing = None
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS records_fts
                USING fts5(
                  record_id UNINDEXED, subject_id UNINDEXED, content,
                  tokenize='porter unicode61'
                )
                """)
            self._fts_enabled = True
            if existing is None:
                self._rebuild_fts()
            elif (
                self._conn.execute("SELECT 1 FROM records_fts LIMIT 1").fetchone()
                is not None
                and self._conn.execute(
                    "SELECT 1 FROM records_fts_map LIMIT 1"
                ).fetchone()
                is None
            ):
                self._rebuild_fts()
        except sqlite3.OperationalError:
            self._fts_enabled = False

    def _migrate_graph_fts(self) -> None:
        try:
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS graph_fts
                USING fts5(
                  object_type UNINDEXED, object_id UNINDEXED,
                  subject_id UNINDEXED, text,
                  tokenize='porter unicode61'
                )
                """)
            self._graph_fts_enabled = True
            if (
                self._conn.execute("SELECT 1 FROM graph_fts LIMIT 1").fetchone()
                is not None
                and self._conn.execute("SELECT 1 FROM graph_fts_map LIMIT 1").fetchone()
                is None
            ):
                self._conn.execute("""
                    INSERT INTO graph_fts_map (
                      object_type, object_id, subject_id, fts_rowid
                    )
                    SELECT object_type, object_id, subject_id, rowid
                    FROM graph_fts
                    """)
        except sqlite3.OperationalError:
            self._graph_fts_enabled = False

    def _migrate_audit_fts(self) -> None:
        try:
            self._conn.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS audit_fts
                USING fts5(
                  event_id, subject_id UNINDEXED, event_type, actor,
                  session_id, turn_id, record_id, payload,
                  content='audit_log', content_rowid='sequence',
                  tokenize='porter unicode61'
                );
                CREATE TABLE IF NOT EXISTS audit_fts_state(
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS audit_fts_insert AFTER INSERT ON audit_log BEGIN
                  INSERT INTO audit_fts(
                    rowid, event_id, subject_id, event_type, actor,
                    session_id, turn_id, record_id, payload
                  ) VALUES (
                    new.sequence, new.event_id, new.subject_id, new.event_type, new.actor,
                    new.session_id, new.turn_id, new.record_id, new.payload
                  );
                END;
                CREATE TRIGGER IF NOT EXISTS audit_fts_delete AFTER DELETE ON audit_log BEGIN
                  INSERT INTO audit_fts(audit_fts, rowid, event_id, subject_id, event_type,
                    actor, session_id, turn_id, record_id, payload)
                  VALUES('delete', old.sequence, old.event_id, old.subject_id, old.event_type,
                    old.actor, old.session_id, old.turn_id, old.record_id, old.payload);
                END;
                CREATE TRIGGER IF NOT EXISTS audit_fts_update AFTER UPDATE ON audit_log BEGIN
                  INSERT INTO audit_fts(audit_fts, rowid, event_id, subject_id, event_type,
                    actor, session_id, turn_id, record_id, payload)
                  VALUES('delete', old.sequence, old.event_id, old.subject_id, old.event_type,
                    old.actor, old.session_id, old.turn_id, old.record_id, old.payload);
                  INSERT INTO audit_fts(
                    rowid, event_id, subject_id, event_type, actor,
                    session_id, turn_id, record_id, payload
                  ) VALUES (
                    new.sequence, new.event_id, new.subject_id, new.event_type, new.actor,
                    new.session_id, new.turn_id, new.record_id, new.payload
                  );
                END;
                """)
            version = self._conn.execute(
                "SELECT value FROM audit_fts_state WHERE key = 'version'"
            ).fetchone()
            if version is None or version["value"] != "1":
                self._conn.execute("INSERT INTO audit_fts(audit_fts) VALUES('rebuild')")
                self._conn.execute(
                    "INSERT INTO audit_fts_state(key, value) VALUES('version', '1') "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
                )
            self._audit_fts_enabled = True
        except sqlite3.OperationalError:
            self._audit_fts_enabled = False

    def _rebuild_fts(self) -> None:
        self._conn.execute("DELETE FROM records_fts_map")
        self._conn.execute("DELETE FROM records_fts")
        self._conn.execute("""
            INSERT INTO records_fts(record_id, subject_id, content)
            SELECT id, subject_id, content FROM records WHERE status = 'active'
            """)
        self._conn.execute("""
            INSERT INTO records_fts_map(record_id, subject_id, fts_rowid)
            SELECT record_id, subject_id, rowid FROM records_fts
            """)

    def _upsert_fts(self, record_id: str, subject_id: str, content: str) -> None:
        if not self._fts_enabled:
            return
        mapped = self._conn.execute(
            "SELECT fts_rowid FROM records_fts_map WHERE record_id = ?", (record_id,)
        ).fetchone()
        if mapped is None:
            cursor = self._conn.execute(
                "INSERT INTO records_fts(record_id, subject_id, content) VALUES (?, ?, ?)",
                (record_id, subject_id, content),
            )
            self._conn.execute(
                "INSERT INTO records_fts_map(record_id, subject_id, fts_rowid) VALUES (?, ?, ?)",
                (record_id, subject_id, cursor.lastrowid),
            )
            return
        rowid = int(mapped["fts_rowid"])
        self._conn.execute("DELETE FROM records_fts WHERE rowid = ?", (rowid,))
        self._conn.execute(
            "INSERT INTO records_fts(rowid, record_id, subject_id, content) VALUES (?, ?, ?, ?)",
            (rowid, record_id, subject_id, content),
        )
        self._conn.execute(
            "UPDATE records_fts_map SET subject_id = ? WHERE record_id = ?",
            (subject_id, record_id),
        )

    def _delete_fts(self, record_id: str) -> None:
        if not self._fts_enabled:
            return
        mapped = self._conn.execute(
            "SELECT fts_rowid FROM records_fts_map WHERE record_id = ?", (record_id,)
        ).fetchone()
        if mapped is None:
            return
        self._conn.execute(
            "DELETE FROM records_fts WHERE rowid = ?", (mapped["fts_rowid"],)
        )
        self._conn.execute(
            "DELETE FROM records_fts_map WHERE record_id = ?", (record_id,)
        )

    def _delete_records_fts_subject(self, subject_id: str) -> None:
        rows = self._conn.execute(
            "SELECT fts_rowid FROM records_fts_map WHERE subject_id = ?", (subject_id,)
        ).fetchall()
        for row in rows:
            self._conn.execute(
                "DELETE FROM records_fts WHERE rowid = ?", (row["fts_rowid"],)
            )
        self._conn.execute(
            "DELETE FROM records_fts_map WHERE subject_id = ?", (subject_id,)
        )

    def _upsert_graph_fts(
        self, object_type: str, object_id: str, subject_id: str, text: str
    ) -> None:
        if not self._graph_fts_enabled:
            return
        mapped = self._conn.execute(
            """
            SELECT fts_rowid FROM graph_fts_map
            WHERE object_type = ? AND object_id = ?
            """,
            (object_type, object_id),
        ).fetchone()
        if mapped is None:
            cursor = self._conn.execute(
                """
                INSERT INTO graph_fts(object_type, object_id, subject_id, text)
                VALUES (?, ?, ?, ?)
                """,
                (object_type, object_id, subject_id, text),
            )
            self._conn.execute(
                """
                INSERT INTO graph_fts_map (
                  object_type, object_id, subject_id, fts_rowid
                ) VALUES (?, ?, ?, ?)
                """,
                (object_type, object_id, subject_id, cursor.lastrowid),
            )
            return
        rowid = int(mapped["fts_rowid"])
        self._conn.execute("DELETE FROM graph_fts WHERE rowid = ?", (rowid,))
        self._conn.execute(
            """
            INSERT INTO graph_fts(rowid, object_type, object_id, subject_id, text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rowid, object_type, object_id, subject_id, text),
        )
        self._conn.execute(
            """
            UPDATE graph_fts_map SET subject_id = ?
            WHERE object_type = ? AND object_id = ?
            """,
            (subject_id, object_type, object_id),
        )

    def _delete_graph_fts(self, object_type: str, object_id: str) -> None:
        if not self._graph_fts_enabled:
            return
        mapped = self._conn.execute(
            """
            SELECT fts_rowid FROM graph_fts_map
            WHERE object_type = ? AND object_id = ?
            """,
            (object_type, object_id),
        ).fetchone()
        if mapped is None:
            return
        self._conn.execute(
            "DELETE FROM graph_fts WHERE rowid = ?", (mapped["fts_rowid"],)
        )
        self._conn.execute(
            "DELETE FROM graph_fts_map WHERE object_type = ? AND object_id = ?",
            (object_type, object_id),
        )

    def _delete_graph_fts_subject(self, subject_id: str) -> None:
        rows = self._conn.execute(
            "SELECT object_type, object_id FROM graph_fts_map WHERE subject_id = ?",
            (subject_id,),
        ).fetchall()
        for row in rows:
            self._delete_graph_fts(str(row["object_type"]), str(row["object_id"]))


# Reserved bootstrap identifiers: 0060-0069 belong to Spec 006 and 0070-0079
# to Spec 007 (see specs/integration-ownership.md). Steps are append-only:
# never renumber, reuse, or edit an identifier that has shipped -- add a new
# one instead.
_BOOTSTRAP_MIGRATIONS: tuple[tuple[str, str], ...] = (
    (
        "0060_memory_proposals",
        """
        CREATE TABLE IF NOT EXISTS memory_proposals (
          proposal_id TEXT PRIMARY KEY,
          subject_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          proposal_sha256 TEXT NOT NULL,
          action TEXT NOT NULL,
          memory_class TEXT NOT NULL,
          confidence REAL NOT NULL,
          fact_key TEXT,
          review_state TEXT NOT NULL CHECK (
            review_state IN (
              'committed', 'pending_review', 'rejected', 'noop', 'stale'
            )
          ),
          reason_codes TEXT NOT NULL DEFAULT '[]',
          proposal TEXT NOT NULL,
          outcome TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          decided_at TEXT,
          UNIQUE (subject_id, agent_id, workspace_id, idempotency_key)
        );

        CREATE INDEX IF NOT EXISTS idx_memory_proposals_queue
          ON memory_proposals(subject_id, review_state, created_at);
        """,
    ),
    (
        "0061_memory_reviews",
        """
        CREATE TABLE IF NOT EXISTS memory_reviews (
          review_id TEXT PRIMARY KEY,
          proposal_id TEXT NOT NULL REFERENCES memory_proposals(proposal_id),
          subject_id TEXT NOT NULL,
          decision TEXT NOT NULL CHECK (
            decision IN ('approved', 'edited_approved', 'rejected')
          ),
          actor TEXT NOT NULL,
          reason TEXT NOT NULL,
          edited_fact_sha256 TEXT,
          record_ids TEXT NOT NULL DEFAULT '[]',
          audit_event_id TEXT,
          decided_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_memory_reviews_proposal
          ON memory_reviews(proposal_id, decided_at);
        """,
    ),
    (
        "0062_memory_lineage",
        """
        CREATE TABLE IF NOT EXISTS memory_lineage (
          lineage_id TEXT PRIMARY KEY,
          subject_id TEXT NOT NULL,
          relation TEXT NOT NULL CHECK (
            relation IN ('corrects', 'supersedes', 'refines')
          ),
          predecessor_record_id TEXT NOT NULL,
          successor_record_id TEXT NOT NULL,
          predecessor_content_sha256 TEXT NOT NULL,
          predecessor_generation INTEGER NOT NULL,
          proposal_id TEXT,
          created_at TEXT NOT NULL,
          UNIQUE (predecessor_record_id, successor_record_id, relation)
        );

        CREATE INDEX IF NOT EXISTS idx_memory_lineage_successor
          ON memory_lineage(subject_id, successor_record_id);

        CREATE INDEX IF NOT EXISTS idx_memory_lineage_predecessor
          ON memory_lineage(subject_id, predecessor_record_id);

        -- Lineage is history, not state: it may be purged by verifiable
        -- deletion, but an existing row can never be rewritten in place.
        CREATE TRIGGER IF NOT EXISTS memory_lineage_is_immutable
        BEFORE UPDATE ON memory_lineage BEGIN
          SELECT RAISE(ABORT, 'memory lineage rows are immutable');
        END;
        """,
    ),
    (
        "0063_record_generation",
        """
        -- Optimistic concurrency for governed updates. Any writer that changes
        -- a record without setting the column explicitly advances it, so a
        -- proposal built against an older read fails its precondition instead
        -- of silently overwriting a newer value.
        CREATE TRIGGER IF NOT EXISTS records_row_generation
        AFTER UPDATE ON records
        WHEN NEW.generation = OLD.generation BEGIN
          UPDATE records SET generation = OLD.generation + 1 WHERE id = NEW.id;
        END;
        """,
    ),
    (
        "0070_governed_task_profiles",
        """
        CREATE TABLE IF NOT EXISTS governed_task_profiles (
          version TEXT PRIMARY KEY,
          profile_id TEXT NOT NULL,
          digest TEXT NOT NULL,
          profile TEXT NOT NULL,
          actor TEXT NOT NULL,
          registered_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_governed_task_profiles_id
          ON governed_task_profiles(profile_id, version);
        """,
    ),
    (
        "0071_governed_tasks",
        """
        CREATE TABLE IF NOT EXISTS governed_tasks (
          task_id TEXT PRIMARY KEY,
          subject_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          profile_id TEXT NOT NULL,
          profile_version TEXT NOT NULL,
          goal TEXT NOT NULL,
          lifecycle TEXT NOT NULL CHECK (
            lifecycle IN ('open', 'paused', 'completed', 'cancelled', 'expired')
          ),
          head_revision INTEGER NOT NULL CHECK (head_revision >= 1),
          policy_generation INTEGER NOT NULL DEFAULT 1,
          created_at_utc TEXT NOT NULL,
          updated_at_utc TEXT NOT NULL,
          last_progress_at_utc TEXT NOT NULL,
          -- Pause accounting. `paused_at_utc` is set while a task is paused;
          -- `no_progress_paused_ms` accumulates completed paused intervals.
          -- Together they make the no-progress clock exact after a restart
          -- without replaying the revision chain.
          paused_at_utc TEXT,
          no_progress_paused_ms INTEGER NOT NULL DEFAULT 0
            CHECK (no_progress_paused_ms >= 0),
          expiry_rule TEXT NOT NULL DEFAULT '{}',
          clock_source TEXT NOT NULL DEFAULT 'system-utc-v1',
          terminal_reason TEXT,
          continues_task_id TEXT,
          idempotency_key TEXT NOT NULL,
          UNIQUE (subject_id, agent_id, workspace_id, idempotency_key)
        );

        CREATE INDEX IF NOT EXISTS idx_governed_tasks_scope
          ON governed_tasks(subject_id, agent_id, workspace_id, lifecycle);

        -- Expiry scans read only non-terminal tasks ordered by age.
        CREATE INDEX IF NOT EXISTS idx_governed_tasks_expiry
          ON governed_tasks(lifecycle, created_at_utc, last_progress_at_utc);
        """,
    ),
    (
        "0072_governed_task_revisions",
        """
        CREATE TABLE IF NOT EXISTS governed_task_revisions (
          task_id TEXT NOT NULL,
          revision INTEGER NOT NULL CHECK (revision >= 1),
          parent_revision INTEGER,
          state TEXT NOT NULL,
          state_sha256 TEXT NOT NULL,
          semantic_sha256 TEXT NOT NULL,
          actor TEXT NOT NULL,
          actor_role TEXT NOT NULL,
          reason_codes TEXT NOT NULL DEFAULT '[]',
          evidence TEXT NOT NULL DEFAULT '[]',
          created_at_utc TEXT NOT NULL,
          is_progress INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (task_id, revision),
          FOREIGN KEY (task_id) REFERENCES governed_tasks(task_id)
        );

        -- At most one successor per parent: this is the optimistic-concurrency
        -- guarantee expressed as a database constraint rather than a hope.
        CREATE UNIQUE INDEX IF NOT EXISTS idx_governed_task_one_successor
          ON governed_task_revisions(task_id, parent_revision)
          WHERE parent_revision IS NOT NULL;

        CREATE TRIGGER IF NOT EXISTS governed_task_revisions_are_immutable
        BEFORE UPDATE ON governed_task_revisions BEGIN
          SELECT RAISE(ABORT, 'governed task revisions are immutable');
        END;
        """,
    ),
    (
        "0073_governed_task_provenance",
        """
        CREATE TABLE IF NOT EXISTS governed_task_provenance (
          provenance_id TEXT PRIMARY KEY,
          task_id TEXT NOT NULL,
          revision INTEGER NOT NULL,
          target_kind TEXT NOT NULL CHECK (
            target_kind IN ('task', 'field', 'item', 'status', 'constraint',
                            'transition', 'delivery', 'lifecycle')
          ),
          target_id TEXT NOT NULL,
          actor TEXT NOT NULL,
          actor_role TEXT NOT NULL,
          method TEXT NOT NULL,
          assurance TEXT NOT NULL,
          interpreter TEXT,
          evidence TEXT NOT NULL DEFAULT '[]',
          observed_at_utc TEXT NOT NULL,
          superseded_revision INTEGER,
          FOREIGN KEY (task_id) REFERENCES governed_tasks(task_id)
        );

        CREATE INDEX IF NOT EXISTS idx_governed_task_provenance_target
          ON governed_task_provenance(task_id, target_kind, target_id, revision);

        CREATE TRIGGER IF NOT EXISTS governed_task_provenance_is_immutable
        BEFORE UPDATE OF task_id, revision, target_kind, target_id, actor,
                         method, assurance, observed_at_utc
        ON governed_task_provenance BEGIN
          SELECT RAISE(ABORT, 'governed task provenance is immutable');
        END;
        """,
    ),
    (
        "0074_governed_task_proposals",
        """
        CREATE TABLE IF NOT EXISTS governed_task_proposals (
          proposal_id TEXT PRIMARY KEY,
          task_id TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL,
          base_revision INTEGER NOT NULL,
          actor TEXT NOT NULL,
          actor_role TEXT NOT NULL,
          proposal TEXT NOT NULL,
          decision TEXT NOT NULL,
          outcome TEXT NOT NULL CHECK (
            outcome IN ('accepted', 'rejected', 'conflict', 'no_change')
          ),
          resulting_revision INTEGER,
          created_at_utc TEXT NOT NULL,
          UNIQUE (task_id, idempotency_key)
        );

        CREATE INDEX IF NOT EXISTS idx_governed_task_proposals_task
          ON governed_task_proposals(task_id, created_at_utc);
        """,
    ),
    (
        "0075_governed_task_steps",
        """
        CREATE TABLE IF NOT EXISTS governed_task_steps (
          step_id TEXT PRIMARY KEY,
          task_id TEXT NOT NULL,
          step_kind TEXT NOT NULL,
          outcome TEXT NOT NULL CHECK (
            outcome IN ('accepted', 'rejected', 'conflict', 'no_change')
          ),
          proposal_id TEXT,
          base_revision INTEGER NOT NULL,
          resulting_revision INTEGER,
          reason_codes TEXT NOT NULL DEFAULT '[]',
          action_fingerprint TEXT,
          actor TEXT NOT NULL,
          duration_ms INTEGER NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
          recorded_at_utc TEXT NOT NULL,
          FOREIGN KEY (task_id) REFERENCES governed_tasks(task_id)
        );

        CREATE INDEX IF NOT EXISTS idx_governed_task_steps_task
          ON governed_task_steps(task_id, recorded_at_utc);

        -- The no-progress guard counts recent equivalent actions.
        CREATE INDEX IF NOT EXISTS idx_governed_task_steps_fingerprint
          ON governed_task_steps(task_id, action_fingerprint, recorded_at_utc);
        """,
    ),
    (
        "0076_governed_task_deliveries",
        """
        CREATE TABLE IF NOT EXISTS governed_task_deliveries (
          delivery_id TEXT PRIMARY KEY,
          task_id TEXT NOT NULL,
          revision INTEGER NOT NULL,
          subject_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          disposition TEXT NOT NULL CHECK (disposition IN ('injected', 'withheld')),
          reason_codes TEXT NOT NULL DEFAULT '[]',
          context_sha256 TEXT,
          cache_key TEXT,
          preparation_id TEXT,
          exposure_id TEXT,
          exposed INTEGER NOT NULL DEFAULT 0,
          prepared_at_utc TEXT NOT NULL,
          FOREIGN KEY (task_id) REFERENCES governed_tasks(task_id)
        );

        CREATE INDEX IF NOT EXISTS idx_governed_task_deliveries_task
          ON governed_task_deliveries(task_id, prepared_at_utc);
        """,
    ),
    (
        "0077_governed_task_sequences",
        """
        -- The `sequence` columns these indexes cover are added through
        -- `_ensure_column` rather than here: ALTER TABLE ADD COLUMN is not
        -- idempotent, and every migration script must be safe to replay
        -- against a database that already has its objects.
        CREATE INDEX IF NOT EXISTS idx_governed_task_steps_sequence
          ON governed_task_steps(task_id, sequence);

        CREATE INDEX IF NOT EXISTS idx_governed_task_deliveries_sequence
          ON governed_task_deliveries(task_id, sequence);
        """,
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value: Any) -> str:
    return canonical_json(value)


def _load_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _event_hash(event: dict[str, Any]) -> str:
    return sha256_hex(_json(event))


def _task_profile_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "version": str(row["version"]),
        "profile_id": str(row["profile_id"]),
        "digest": str(row["digest"]),
        "profile": _load_json(row["profile"], {}),
        "actor": str(row["actor"]),
        "registered_at": str(row["registered_at"]),
    }


def _task_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "task_id": str(row["task_id"]),
        "subject_id": str(row["subject_id"]),
        "agent_id": str(row["agent_id"]),
        "workspace_id": str(row["workspace_id"]),
        "profile_id": str(row["profile_id"]),
        "profile_version": str(row["profile_version"]),
        "goal": str(row["goal"]),
        "lifecycle": str(row["lifecycle"]),
        "head_revision": int(row["head_revision"]),
        "policy_generation": int(row["policy_generation"]),
        "created_at_utc": str(row["created_at_utc"]),
        "updated_at_utc": str(row["updated_at_utc"]),
        "last_progress_at_utc": str(row["last_progress_at_utc"]),
        "paused_at_utc": row["paused_at_utc"],
        "no_progress_paused_ms": int(row["no_progress_paused_ms"]),
        "expiry_rule": _load_json(row["expiry_rule"], {}),
        "clock_source": str(row["clock_source"]),
        "terminal_reason": row["terminal_reason"],
        "continues_task_id": row["continues_task_id"],
        "idempotency_key": str(row["idempotency_key"]),
    }


def _task_revision_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "task_id": str(row["task_id"]),
        "revision": int(row["revision"]),
        "parent_revision": row["parent_revision"],
        "state": _load_json(row["state"], {}),
        "state_sha256": str(row["state_sha256"]),
        "semantic_sha256": str(row["semantic_sha256"]),
        "actor": str(row["actor"]),
        "actor_role": str(row["actor_role"]),
        "reason_codes": _load_json(row["reason_codes"], []),
        "evidence": _load_json(row["evidence"], []),
        "created_at_utc": str(row["created_at_utc"]),
        "is_progress": bool(row["is_progress"]),
    }


def _task_provenance_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "provenance_id": str(row["provenance_id"]),
        "task_id": str(row["task_id"]),
        "revision": int(row["revision"]),
        "target_kind": str(row["target_kind"]),
        "target_id": str(row["target_id"]),
        "actor": str(row["actor"]),
        "actor_role": str(row["actor_role"]),
        "method": str(row["method"]),
        "assurance": str(row["assurance"]),
        "interpreter": row["interpreter"],
        "evidence": _load_json(row["evidence"], []),
        "observed_at_utc": str(row["observed_at_utc"]),
        "superseded_revision": row["superseded_revision"],
    }


def _task_proposal_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "proposal_id": str(row["proposal_id"]),
        "task_id": str(row["task_id"]),
        "subject_id": str(row["subject_id"]),
        "agent_id": str(row["agent_id"]),
        "workspace_id": str(row["workspace_id"]),
        "idempotency_key": str(row["idempotency_key"]),
        "payload_sha256": str(row["payload_sha256"]),
        "base_revision": int(row["base_revision"]),
        "actor": str(row["actor"]),
        "actor_role": str(row["actor_role"]),
        "proposal": _load_json(row["proposal"], {}),
        "decision": _load_json(row["decision"], {}),
        "outcome": str(row["outcome"]),
        "resulting_revision": row["resulting_revision"],
        "created_at_utc": str(row["created_at_utc"]),
    }


def _task_step_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "step_id": str(row["step_id"]),
        "task_id": str(row["task_id"]),
        "step_kind": str(row["step_kind"]),
        "outcome": str(row["outcome"]),
        "proposal_id": row["proposal_id"],
        "base_revision": int(row["base_revision"]),
        "resulting_revision": row["resulting_revision"],
        "reason_codes": _load_json(row["reason_codes"], []),
        "action_fingerprint": row["action_fingerprint"],
        "actor": str(row["actor"]),
        "duration_ms": int(row["duration_ms"]),
        "recorded_at_utc": str(row["recorded_at_utc"]),
        "sequence": int(row["sequence"]),
    }


def _task_delivery_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "delivery_id": str(row["delivery_id"]),
        "task_id": str(row["task_id"]),
        "revision": int(row["revision"]),
        "subject_id": str(row["subject_id"]),
        "agent_id": str(row["agent_id"]),
        "workspace_id": str(row["workspace_id"]),
        "disposition": str(row["disposition"]),
        "reason_codes": _load_json(row["reason_codes"], []),
        "context_sha256": row["context_sha256"],
        "cache_key": row["cache_key"],
        "preparation_id": row["preparation_id"],
        "exposure_id": row["exposure_id"],
        "exposed": bool(row["exposed"]),
        "prepared_at_utc": str(row["prepared_at_utc"]),
        "sequence": int(row["sequence"]),
    }


def _memory_proposal_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "proposal_id": str(row["proposal_id"]),
        "subject_id": str(row["subject_id"]),
        "agent_id": str(row["agent_id"]),
        "workspace_id": str(row["workspace_id"]),
        "idempotency_key": str(row["idempotency_key"]),
        "proposal_sha256": str(row["proposal_sha256"]),
        "action": str(row["action"]),
        "memory_class": str(row["memory_class"]),
        "confidence": float(row["confidence"]),
        "fact_key": row["fact_key"],
        "review_state": str(row["review_state"]),
        "reason_codes": _load_json(row["reason_codes"], []),
        "proposal": _load_json(row["proposal"], {}),
        "outcome": _load_json(row["outcome"], {}),
        "created_at": str(row["created_at"]),
        "decided_at": row["decided_at"],
    }


def _record_from_row(row: sqlite3.Row) -> dict[str, Any]:
    raw = _load_json(row["raw"], {})
    return {
        "id": row["id"],
        "memory_id": row["id"],
        "framework": "atmem",
        "subject_id": row["subject_id"],
        "subject_id_hash": f"plain:{row['subject_id']}",
        "tenant_id_hash": None,
        "content": row["content"],
        "source_type": row["source_type"],
        "trust_tier": row["trust_tier"],
        "source_session_id": row["source_session_id"],
        "source_turn_id": row["source_turn_id"],
        "episode_id": row["episode_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "deleted_at": row["deleted_at"],
        "confidence": row["confidence"],
        "scope": row["scope"],
        "status": row["status"],
        "supersedes_id": row["supersedes_id"],
        "fact_key": row["fact_key"],
        "generation": int(row["generation"] or 0),
        "raw": raw,
    }


def _episode_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "subject_id": row["subject_id"],
        "session_id": row["session_id"],
        "turn_id": row["turn_id"],
        "message": row["message"],
        "source_type": row["source_type"],
        "created_at": row["created_at"],
        "raw": _load_json(row["raw"], {}),
    }


def _media_observation_from_row(row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    value["segment"] = _load_json(value.pop("segment_json"), {})
    value["extractor"] = _load_json(value.pop("extractor_identity_json"), {})
    return value


def _retrieval_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "subject_id": row["subject_id"],
        "session_id": row["session_id"],
        "query": row["query"],
        "query_sha256": row["query_sha256"],
        "candidates": _load_json(row["candidates"], []),
        "returned_ids": _load_json(row["returned_ids"], []),
        "memory_ids": _load_json(row["returned_ids"], []),
        "created_at": row["created_at"],
        "raw": _load_json(row["raw"], {}),
    }


def _audit_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "sequence": row["sequence"],
        "event_id": row["event_id"],
        "subject_id": row["subject_id"],
        "event_type": row["event_type"],
        "created_at": row["created_at"],
        "actor": row["actor"],
        "session_id": row["session_id"],
        "turn_id": row["turn_id"],
        "record_id": row["record_id"],
        "payload": _load_json(row["payload"], {}),
        "prev_hash": row["prev_hash"],
        "event_hash": row["event_hash"],
    }


def _audit_fts_query(query: str) -> str:
    """Treat investigator input as literal terms, never executable FTS syntax."""
    terms = [term for term in re.split(r"[^\w]+", query, flags=re.UNICODE) if term]
    if not terms:
        return '""'
    return " AND ".join('"' + term.replace('"', '""') + '"' for term in terms)
