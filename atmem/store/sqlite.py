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
from atmem.core.storage import BackendCapabilities


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
        self._context_fts_enabled = False
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA secure_delete = ON")
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

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            backend_id="sqlite-v1",
            role="canonical",
            transactions=True,
            concurrency=True,
            rebuild=False,
            backup=True,
            restore=True,
            migration=True,
            verified_deletion=True,
        )

    def backup_to(self, destination: str | Path) -> dict[str, Any]:
        """Create and integrity-check a consistent SQLite backup."""
        target = Path(destination).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        backup = sqlite3.connect(str(target))
        try:
            self._conn.backup(backup)
            result = str(backup.execute("PRAGMA integrity_check").fetchone()[0])
        finally:
            backup.close()
        if result != "ok":
            raise RuntimeError(f"backup integrity check failed: {result}")
        return {"format": "atmem-storage-backup-v1", "backend_id": "sqlite-v1", "path": str(target), "integrity": result}

    def restore_from(self, source: str | Path) -> dict[str, Any]:
        """Replace this open database from a verified SQLite snapshot."""
        if self._transaction_depth:
            raise RuntimeError("restore cannot run inside a transaction")
        origin = sqlite3.connect(str(Path(source).expanduser().resolve()))
        try:
            integrity = str(origin.execute("PRAGMA integrity_check").fetchone()[0])
            if integrity != "ok":
                raise RuntimeError(f"restore source integrity check failed: {integrity}")
            origin.backup(self._conn)
        finally:
            origin.close()
        self._migrate()
        return {"format": "atmem-storage-restore-v1", "backend_id": "sqlite-v1", "integrity": integrity, "migrations": self.applied_migrations()}

    def lifecycle_generation(self, subject_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(generation), 0) AS generation FROM memory_lifecycle WHERE subject_id=?",
            (subject_id,),
        ).fetchone()
        return int(row["generation"] if row else 0)

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
            # Derived V3 state is deleted before its source ledger so every
            # range/link/vector row is removed by foreign-key cascade.
            if self._context_fts_enabled:
                generation_rows = self._conn.execute(
                    "SELECT generation_id FROM context_view_generations WHERE subject_id=?",
                    (subject_id,),
                ).fetchall()
                for generation_row in generation_rows:
                    self._delete_context_fts_generation(str(generation_row["generation_id"]))
            self._conn.execute(
                "DELETE FROM context_view_generations WHERE subject_id=?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM context_backfill_state WHERE subject_id=?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM context_source_episodes WHERE subject_id=?", (subject_id,)
            )
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
                "DELETE FROM protected_formation_media WHERE subject_id = ?",
                (subject_id,),
            )
            self._conn.execute(
                "DELETE FROM formation_receipts WHERE subject_id = ?", (subject_id,)
            )
            self._conn.execute(
                "DELETE FROM typed_identity_mappings WHERE subject_id = ?", (subject_id,)
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
                    # A binding records which conversation was working on a
                    # subject's task. Resetting the subject must not leave that
                    # behind any more than it leaves the task itself.
                    "governed_task_session_bindings",
                ):
                    self._conn.execute(
                        f"DELETE FROM {table} WHERE task_id IN ({placeholders})",
                        task_ids,
                    )
            # Bindings are also scoped directly, so any that outlived their task
            # go with the subject too rather than lingering unreferenced.
            self._conn.execute(
                "DELETE FROM governed_task_session_bindings WHERE subject_id = ?",
                (subject_id,),
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
        raw_value = raw or {}
        authority = raw_value.get("authority_scope") or {}
        authority_subject_id = authority.get("subject_id")
        authority_workspace_id = authority.get("workspace_id")
        sensitivity_class = str(raw_value.get("sensitivity") or "personal")
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO records (
                  id, subject_id, content, content_normalized, source_type, trust_tier,
                  source_session_id, source_turn_id, episode_id, created_at,
                  updated_at, deleted_at, confidence, scope, status,
                  supersedes_id, fact_key, raw, authority_subject_id, authority_workspace_id,
                  sensitivity_class, authority_materialized
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
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
                    _json(raw_value),
                    authority_subject_id,
                    authority_workspace_id,
                    sensitivity_class,
                ),
            )
            if status == "active":
                self._upsert_fts(record_id, subject_id, content)
                self._upsert_search_terms(
                    record_id=record_id,
                    subject_id=subject_id,
                    workspace_id=str(authority_workspace_id or ""),
                    content=content,
                    fact_key=fact_key,
                )
        return record_id

    def get_record(self, subject_id: str, record_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM records WHERE subject_id = ? AND id = ?",
            (subject_id, record_id),
        ).fetchone()
        return _record_from_row(row) if row else None

    def get_episode(self, subject_id: str, episode_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM episodes WHERE subject_id = ? AND id = ?",
            (subject_id, episode_id),
        ).fetchone()
        return _episode_from_row(row) if row is not None else None

    def context_engine_storage_ready(self) -> dict[str, Any]:
        """Report whether V3 may persist semantic source/view data."""
        if self.path == ":memory:":
            return {
                "ready": True, "encrypted": False, "ephemeral": True,
                "reason": "ephemeral_test_store",
            }
        if self.policy.state != "encrypted":
            return {
                "ready": False, "encrypted": False, "ephemeral": False,
                "reason": "encrypted_household_required",
            }
        return {
            "ready": True, "encrypted": True, "ephemeral": False, "reason": None,
        }

    def require_context_engine_storage(self) -> None:
        if not self.context_engine_storage_ready()["ready"]:
            raise RuntimeError(
                "Context Engine V3 requires an encrypted household; provision "
                "SQLCipher and complete `atmem household migrate` before formation"
            )

    def context_source_storage(self, source_id: str) -> dict[str, int]:
        row = self._conn.execute(
            """SELECT COUNT(*) AS rows, COALESCE(SUM(length(content_bytes)), 0) AS bytes
               FROM context_source_parts WHERE source_id = ?""",
            (source_id,),
        ).fetchone()
        return {
            "source_body_rows": int(row["rows"]),
            "source_body_bytes": int(row["bytes"]),
            "derived_source_body_bytes": 0,
        }

    def insert_typed_memory_unit(
        self,
        *,
        unit: dict[str, Any],
        record_id: str,
        semantic_identity: str,
    ) -> dict[str, Any]:
        """Index one active canonical typed unit without duplicating its payload."""
        scope = unit["scope"]
        evidence = unit["evidence"]
        source_ids = [str(row["source_id"]) for row in evidence]
        if source_ids:
            placeholders = ",".join("?" for _ in source_ids)
            linked = self._conn.execute(
                f"""
                SELECT source_id FROM protocol_sources
                WHERE subject_id = ? AND agent_id = ? AND workspace_id = ?
                  AND source_id IN ({placeholders})
                """,
                (
                    scope["subject_id"], scope["agent_id"], scope["workspace_id"],
                    *source_ids,
                ),
            ).fetchall()
            if {str(row["source_id"]) for row in linked} != set(source_ids):
                raise ValueError("typed unit evidence source is not durably linked")
        self._conn.execute(
            """
            INSERT INTO typed_memory_units(
              unit_id, subject_id, agent_id, workspace_id, record_id,
              formation_id, kind, semantic_identity, lifecycle, generation,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                unit["unit_id"], scope["subject_id"], scope["agent_id"],
                scope["workspace_id"], record_id, unit["formation_id"],
                unit["kind"], semantic_identity, unit["lifecycle"], utc_now(), utc_now(),
            ),
        )
        self._conn.executemany(
            """
            INSERT INTO typed_unit_evidence(
              subject_id, workspace_id, unit_id, source_id,
              start_offset, end_offset, excerpt_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scope["subject_id"], scope["workspace_id"],
                    unit["unit_id"], row["source_id"], row["start_offset"],
                    row["end_offset"], row["excerpt_sha256"],
                )
                for row in evidence
            ],
        )
        return self.get_typed_memory_unit(
            str(scope["subject_id"]), str(scope["workspace_id"]), str(unit["unit_id"])
        ) or {}

    def find_live_typed_identity(
        self, subject_id: str, workspace_id: str, semantic_identity: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT u.* FROM typed_memory_units u
            WHERE u.subject_id = ? AND u.workspace_id = ?
              AND u.lifecycle IN ('active', 'quarantined')
              AND (
                u.semantic_identity = ? OR u.semantic_identity IN (
                  SELECT m.legacy_identity FROM typed_identity_mappings m
                  WHERE m.subject_id = ? AND m.workspace_id = ?
                    AND m.identity_kind = 'semantic'
                    AND m.current_identity = ? AND m.resolution_state = 'mapped'
                )
              )
            ORDER BY CASE WHEN u.semantic_identity = ? THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (
                subject_id, workspace_id, semantic_identity,
                subject_id, workspace_id, semantic_identity, semantic_identity,
            ),
        ).fetchone()
        return dict(row) if row is not None else None

    def link_typed_occurrence_evidence(
        self, *, subject_id: str, workspace_id: str, unit_id: str,
        evidence: list[dict[str, Any]],
    ) -> None:
        """Link another observed occurrence to a deduplicated typed unit."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO typed_unit_evidence(
              subject_id, workspace_id, unit_id, source_id,
              start_offset, end_offset, excerpt_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [(
                subject_id, workspace_id, unit_id, row["source_id"],
                int(row["start_offset"]), int(row["end_offset"]),
                row["excerpt_sha256"],
            ) for row in evidence],
        )

    def scoped_typed_candidates(
        self,
        subject_id: str,
        workspace_id: str,
        kinds: set[str],
        *,
        limit: int,
        remote: bool = False,
    ) -> list[dict[str, Any]]:
        if not kinds:
            return []
        placeholders = ",".join("?" for _ in kinds)
        sensitivity = (
            "AND r.sensitivity_class NOT IN ('sensitive', 'restricted')"
            if remote else ""
        )
        rows = self._conn.execute(
            f"""
            SELECT r.id FROM typed_memory_units u
            JOIN records r ON r.id = u.record_id
            WHERE u.subject_id = ? AND u.workspace_id = ?
              AND u.kind IN ({placeholders})
              AND u.lifecycle = 'active' AND r.status = 'active'
              AND r.authority_materialized = 1
              AND r.authority_subject_id = ? AND r.authority_workspace_id = ?
              AND NOT EXISTS (
                SELECT 1 FROM retrieval_exclusions x
                WHERE x.subject_id = r.subject_id AND x.record_id = r.id
              )
              {sensitivity}
            ORDER BY r.updated_at DESC, r.created_at DESC, r.id DESC
            LIMIT ?
            """,
            (
                subject_id, workspace_id, *sorted(kinds), subject_id, workspace_id,
                max(1, min(int(limit), 1000)),
            ),
        ).fetchall()
        record_ids = [str(row["id"]) for row in rows]
        loaded = self.get_records(subject_id, record_ids)
        return [loaded[record_id] for record_id in record_ids if record_id in loaded]

    def typed_units_for_records(
        self, subject_id: str, workspace_id: str, record_ids: list[str],
        *, remote: bool = False, include_superseded: bool = False,
    ) -> list[dict[str, Any]]:
        if not record_ids:
            return []
        placeholders = ",".join("?" for _ in record_ids)
        sensitivity = (
            "AND r.sensitivity_class NOT IN ('sensitive', 'restricted')"
            if remote else ""
        )
        lifecycle_sql = (
            "u.lifecycle IN ('active', 'superseded') AND r.status IN ('active', 'superseded')"
            if include_superseded else "u.lifecycle = 'active' AND r.status = 'active'"
        )
        rows = self._conn.execute(
            f"""
            SELECT u.record_id FROM typed_memory_units u
            JOIN records r ON r.id = u.record_id
            WHERE u.subject_id = ? AND u.workspace_id = ?
              AND u.record_id IN ({placeholders})
              AND {lifecycle_sql}
              AND r.authority_materialized = 1
              AND r.authority_subject_id = ? AND r.authority_workspace_id = ?
              AND NOT EXISTS (
                SELECT 1 FROM retrieval_exclusions x
                WHERE x.subject_id = r.subject_id AND x.record_id = r.id
              )
              {sensitivity}
            """,
            (subject_id, workspace_id, *record_ids, subject_id, workspace_id),
        ).fetchall()
        result_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            record = self.get_record(subject_id, str(row["record_id"]))
            unit = ((record or {}).get("raw") or {}).get("typed_unit")
            if unit:
                linked = self.get_typed_memory_unit(
                    subject_id, workspace_id, str(unit["unit_id"])
                )
                unit = {
                    **unit,
                    "evidence": (linked or {}).get("evidence", unit.get("evidence", [])),
                }
                result_by_id[str(row["record_id"])] = {
                    "record_id": str(row["record_id"]),
                    "fact_key": str((record or {}).get("fact_key") or ""),
                    "unit": unit,
                }
        return [result_by_id[value] for value in record_ids if value in result_by_id]

    def adjacent_typed_records(
        self,
        subject_id: str,
        workspace_id: str,
        source_ids: list[str],
        *,
        limit: int,
        remote: bool = False,
    ) -> list[dict[str, Any]]:
        """Return one-hop, live, scoped typed neighbors without source bodies."""
        if not source_ids:
            return []
        placeholders = ",".join("?" for _ in source_ids)
        sensitivity = (
            "AND r.sensitivity_class NOT IN ('sensitive', 'restricted')"
            if remote else ""
        )
        rows = self._conn.execute(
            f"""
            WITH neighboring(source_id, seed_source_id, direction, ordinal) AS (
              SELECT to_source_id, from_source_id, 'next', ordinal
              FROM source_adjacency
              WHERE subject_id = ? AND workspace_id = ?
                AND from_source_id IN ({placeholders})
              UNION ALL
              SELECT from_source_id, to_source_id, 'previous', ordinal
              FROM source_adjacency
              WHERE subject_id = ? AND workspace_id = ?
                AND to_source_id IN ({placeholders})
            )
            SELECT DISTINCT u.record_id, n.source_id, n.seed_source_id,
                   n.direction, n.ordinal
            FROM neighboring n
            JOIN typed_unit_evidence e ON e.source_id = n.source_id
            JOIN typed_memory_units u
              ON u.subject_id = e.subject_id AND u.workspace_id = e.workspace_id
             AND u.unit_id = e.unit_id
            JOIN records r ON r.id = u.record_id
            WHERE u.subject_id = ? AND u.workspace_id = ?
              AND u.lifecycle = 'active' AND r.status = 'active'
              AND r.authority_materialized = 1
              AND r.authority_subject_id = ? AND r.authority_workspace_id = ?
              AND NOT EXISTS (
                SELECT 1 FROM retrieval_exclusions x
                WHERE x.subject_id = r.subject_id AND x.record_id = r.id
              )
              {sensitivity}
            ORDER BY n.ordinal, u.record_id
            LIMIT ?
            """,
            (
                subject_id, workspace_id, *source_ids,
                subject_id, workspace_id, *source_ids,
                subject_id, workspace_id, subject_id, workspace_id,
                max(1, min(int(limit), 1000)),
            ),
        ).fetchall()
        return [dict(row) for row in rows]

    def related_typed_records(
        self,
        subject_id: str,
        workspace_id: str,
        record_ids: list[str],
        *,
        limit: int,
        remote: bool = False,
    ) -> list[dict[str, Any]]:
        """Return bounded live typed neighbors from explicit provenance links.

        A shared formation or memory-lineage edge can nominate another already
        authorized canonical record. It never creates factual authority and it
        never reactivates superseded/revoked records.
        """
        if not record_ids:
            return []
        placeholders = ",".join("?" for _ in record_ids)
        sensitivity = (
            "AND r.sensitivity_class NOT IN ('sensitive', 'restricted')"
            if remote else ""
        )
        rows = self._conn.execute(
            f"""
            WITH related(record_id, seed_record_id, relation) AS (
              SELECT candidate.record_id, seed.record_id, 'same_formation'
              FROM typed_memory_units seed
              JOIN typed_memory_units candidate
                ON candidate.subject_id = seed.subject_id
               AND candidate.workspace_id = seed.workspace_id
               AND candidate.formation_id = seed.formation_id
               AND candidate.record_id != seed.record_id
              WHERE seed.subject_id = ? AND seed.workspace_id = ?
                AND seed.record_id IN ({placeholders})
              UNION ALL
              SELECT lineage.successor_record_id, lineage.predecessor_record_id,
                     'lineage_successor'
              FROM memory_lineage lineage
              WHERE lineage.subject_id = ?
                AND lineage.predecessor_record_id IN ({placeholders})
              UNION ALL
              SELECT lineage.predecessor_record_id, lineage.successor_record_id,
                     'lineage_predecessor'
              FROM memory_lineage lineage
              WHERE lineage.subject_id = ?
                AND lineage.successor_record_id IN ({placeholders})
            )
            SELECT related.record_id, related.seed_record_id, related.relation,
                   MIN(COALESCE(next_source.ordinal,
                                previous_source.ordinal + 1,
                                1000000)) AS source_ordinal,
                   MIN(e.start_offset) AS source_offset
            FROM related
            JOIN typed_memory_units u ON u.record_id = related.record_id
            JOIN typed_unit_evidence e
              ON e.subject_id = u.subject_id
             AND e.workspace_id = u.workspace_id
             AND e.unit_id = u.unit_id
            LEFT JOIN source_adjacency next_source
              ON next_source.subject_id = e.subject_id
             AND next_source.workspace_id = e.workspace_id
             AND next_source.from_source_id = e.source_id
            LEFT JOIN source_adjacency previous_source
              ON previous_source.subject_id = e.subject_id
             AND previous_source.workspace_id = e.workspace_id
             AND previous_source.to_source_id = e.source_id
            JOIN records r ON r.id = related.record_id
            WHERE u.subject_id = ? AND u.workspace_id = ?
              AND u.lifecycle = 'active' AND r.status = 'active'
              AND r.authority_materialized = 1
              AND r.authority_subject_id = ? AND r.authority_workspace_id = ?
              AND NOT EXISTS (
                SELECT 1 FROM retrieval_exclusions x
                WHERE x.subject_id = r.subject_id AND x.record_id = r.id
              )
              {sensitivity}
            GROUP BY related.record_id, related.seed_record_id, related.relation
            ORDER BY related.relation, source_ordinal, source_offset,
                     related.record_id
            LIMIT ?
            """,
            (
                subject_id, workspace_id, *record_ids,
                subject_id, *record_ids,
                subject_id, *record_ids,
                subject_id, workspace_id, subject_id, workspace_id,
                max(1, min(int(limit), 1000)),
            ),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_typed_memory_unit(
        self, subject_id: str, workspace_id: str, unit_id: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT u.*, r.raw FROM typed_memory_units u
            JOIN records r ON r.id = u.record_id
            WHERE u.subject_id = ? AND u.workspace_id = ? AND u.unit_id = ?
            """,
            (subject_id, workspace_id, unit_id),
        ).fetchone()
        if row is None:
            return None
        raw = _load_json(row["raw"], {})
        return {
            **{key: row[key] for key in row.keys() if key != "raw"},
            "unit": raw.get("typed_unit"),
            "evidence": [
                dict(value) for value in self._conn.execute(
                    "SELECT * FROM typed_unit_evidence WHERE subject_id = ? "
                    "AND workspace_id = ? AND unit_id = ? "
                    "ORDER BY source_id, start_offset, end_offset",
                    (subject_id, workspace_id, unit_id),
                ).fetchall()
            ],
        }

    def typed_derivative_identity(
        self, subject_id: str, workspace_id: str, record_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Content-free occurrence/lifecycle identity for immutable checkpoints."""
        if not record_ids:
            return []
        placeholders = ",".join("?" for _ in record_ids)
        rows = self._conn.execute(
            f"""
            SELECT u.record_id, u.unit_id, u.lifecycle, u.generation,
                   e.source_id, e.start_offset, e.end_offset, e.excerpt_sha256,
                   CASE WHEN x.record_id IS NULL THEN 0 ELSE 1 END AS excluded
            FROM typed_memory_units u
            LEFT JOIN typed_unit_evidence e
              ON e.subject_id = u.subject_id AND e.workspace_id = u.workspace_id
             AND e.unit_id = u.unit_id
            LEFT JOIN retrieval_exclusions x
              ON x.subject_id = u.subject_id AND x.record_id = u.record_id
            WHERE u.subject_id = ? AND u.workspace_id = ?
              AND u.record_id IN ({placeholders})
            ORDER BY u.record_id, e.source_id, e.start_offset, e.end_offset
            """,
            (subject_id, workspace_id, *record_ids),
        ).fetchall()
        return [dict(row) for row in rows]

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

    def get_record_validation(
        self, subject_id: str, record_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Reload only canonical fields needed to validate index nominations.

        This is not a delivery read: callers must still fetch full authorized
        records before constructing context. The content is loaded to verify
        exact digest equality with the derived vector entry.
        """
        ids = list(dict.fromkeys(str(value) for value in record_ids))
        records: dict[str, dict[str, Any]] = {}
        for start in range(0, len(ids), 900):
            batch = ids[start : start + 900]
            placeholders = ",".join("?" for _ in batch)
            rows = self._conn.execute(
                f"SELECT id, subject_id, status, content FROM records "
                f"WHERE subject_id = ? AND id IN ({placeholders})",
                (subject_id, *batch),
            ).fetchall()
            records.update((str(row["id"]), dict(row)) for row in rows)
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

    def link_memory_proposal_sources(
        self,
        proposal_id: str,
        subject_id: str,
        workspace_id: str,
        source_ids: list[str],
    ) -> None:
        """Retain source dependencies for pending, no-op, and committed proposals."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO memory_proposal_sources(
              proposal_id, subject_id, workspace_id, source_id
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (proposal_id, subject_id, workspace_id, source_id)
                for source_id in dict.fromkeys(source_ids)
            ],
        )

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

    def redact_memory_proposal(self, proposal_id: str) -> None:
        row = self._conn.execute(
            "SELECT proposal FROM memory_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            return
        value = _load_json(row["proposal"], {})
        unit = value.get("unit") or {}
        self._conn.execute(
            "UPDATE memory_proposals SET proposal = ?, fact_key = NULL WHERE proposal_id = ?",
            (
                _json({
                    "format": value.get("format"),
                    "proposal_id": proposal_id,
                    "scope": value.get("scope"),
                    "action": value.get("action"),
                    "memory_class": value.get("memory_class"),
                    "unit_id": unit.get("unit_id"),
                    "formation_id": unit.get("formation_id"),
                    "kind": unit.get("kind"),
                    "redacted": True,
                }),
                proposal_id,
            ),
        )

    def _source_in_use(self, source_id: str) -> bool:
        source = self.get_protocol_source_by_id(source_id)
        if source is None:
            return False
        if self._conn.execute(
            """
            SELECT 1 FROM typed_unit_evidence e
            JOIN typed_memory_units u
              ON u.subject_id = e.subject_id AND u.workspace_id = e.workspace_id
             AND u.unit_id = e.unit_id
            WHERE e.source_id = ? AND u.lifecycle != 'deleted' LIMIT 1
            """,
            (source_id,),
        ).fetchone() is not None:
            return True
        if self._conn.execute(
            "SELECT 1 FROM records WHERE episode_id = ? AND status != 'tombstoned' LIMIT 1",
            (source["episode_id"],),
        ).fetchone() is not None:
            return True
        if self._conn.execute(
            """
            SELECT 1 FROM memory_proposal_sources ps
            JOIN memory_proposals p ON p.proposal_id = ps.proposal_id
            WHERE ps.source_id = ? AND p.review_state = 'pending_review' LIMIT 1
            """,
            (source_id,),
        ).fetchone() is not None:
            return True
        rows = self._conn.execute(
            "SELECT raw FROM records WHERE subject_id = ? AND status != 'tombstoned'",
            (source["subject_id"],),
        ).fetchall()
        return any(
            source_id in set(_load_json(row["raw"], {}).get("source_ids") or ())
            for row in rows
        )

    def _purge_protocol_source(self, source_id: str) -> str | None:
        source = self.get_protocol_source_by_id(source_id)
        if source is None or self._source_in_use(source_id):
            return None
        linked = self._conn.execute(
            "SELECT proposal_id FROM memory_proposal_sources WHERE source_id = ?",
            (source_id,),
        ).fetchall()
        for row in linked:
            proposal_id = str(row["proposal_id"])
            self.redact_memory_proposal(proposal_id)
            self._conn.execute(
                """
                UPDATE memory_proposals
                SET review_state = CASE WHEN review_state = 'pending_review' THEN 'stale' ELSE review_state END,
                    decided_at = CASE WHEN review_state = 'pending_review' THEN ? ELSE decided_at END
                WHERE proposal_id = ?
                """,
                (utc_now(), proposal_id),
            )
        self._conn.execute(
            """
            UPDATE protocol_sources SET request_json = ?, result_json = ?
            WHERE source_id = ?
            """,
            (
                _json({"format": "atmem-source-capture-request-v1", "source_id": source_id, "redacted": True}),
                _json({"format": "atmem-source-capture-result-v1", "source_id": source_id, "episode_id": source["episode_id"], "source_sha256": source["source_sha256"], "retained": False, "redacted": True}),
                source_id,
            ),
        )
        return str(source["episode_id"])

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

    def insert_formation_receipt(self, receipt: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO formation_receipts(
              formation_id, subject_id, workspace_id, episode_id,
              receipt_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(formation_id) DO UPDATE SET
              receipt_json = excluded.receipt_json
            """,
            (
                receipt["formation_id"], receipt["scope_subject_id"],
                receipt["scope_workspace_id"], receipt["episode_id"],
                _json(receipt), utc_now(),
            ),
        )
        self._conn.execute(
            "DELETE FROM formation_media_references WHERE formation_id = ?",
            (receipt["formation_id"],),
        )
        for reference in receipt.get("media_references") or ():
            self._conn.execute(
                """
                INSERT INTO formation_media_references(
                  formation_id, subject_id, workspace_id, adjacent_source_id,
                  part_id, ordinal, reference_id, reference_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt["formation_id"], receipt["scope_subject_id"],
                    receipt["scope_workspace_id"], reference["adjacent_source_id"],
                    reference["part_id"], int(reference["ordinal"]),
                    reference["reference_id"], reference["reference_sha256"],
                ),
            )

    def get_formation_receipt(self, formation_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT receipt_json FROM formation_receipts WHERE formation_id = ?",
            (formation_id,),
        ).fetchone()
        return _load_json(row["receipt_json"], {}) if row is not None else None

    def formation_unit_statuses(self, formation_id: str) -> list[str]:
        receipt = self._conn.execute(
            "SELECT subject_id, workspace_id FROM formation_receipts WHERE formation_id = ?",
            (formation_id,),
        ).fetchone()
        if receipt is None:
            return []
        return [
            str(row["effective_status"])
            for row in self._conn.execute(
                """
                WITH receipt_sources(source_id) AS (
                  SELECT source.value
                  FROM formation_receipts f,
                       json_each(f.receipt_json, '$.source_ids') source
                  WHERE f.formation_id = ?
                ), target_units(unit_id) AS (
                  SELECT u.unit_id FROM typed_memory_units u
                  WHERE u.subject_id = ? AND u.workspace_id = ?
                    AND u.formation_id = ?
                  UNION
                  SELECT e.unit_id FROM typed_unit_evidence e
                  JOIN receipt_sources s ON s.source_id = e.source_id
                  WHERE e.subject_id = ? AND e.workspace_id = ?
                )
                SELECT CASE WHEN x.record_id IS NULL THEN r.status
                            ELSE 'retrieval_excluded' END AS effective_status
                FROM target_units target
                JOIN typed_memory_units u ON u.unit_id = target.unit_id
                JOIN records r ON r.id = u.record_id
                LEFT JOIN retrieval_exclusions x
                  ON x.subject_id = r.subject_id AND x.record_id = r.id
                ORDER BY u.unit_id
                """,
                (
                    formation_id,
                    receipt["subject_id"], receipt["workspace_id"],
                    formation_id,
                    receipt["subject_id"], receipt["workspace_id"],
                ),
            ).fetchall()
        ]

    def insert_protected_formation_media(
        self, *, media_id: str, formation_id: str, subject_id: str,
        workspace_id: str, part_id: str, content_sha256: str,
        content_bytes: bytes,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO protected_formation_media(
              media_id, formation_id, subject_id, workspace_id, part_id,
              content_sha256, content_bytes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(formation_id, part_id) DO UPDATE SET
              media_id = excluded.media_id,
              content_sha256 = excluded.content_sha256,
              content_bytes = excluded.content_bytes
            """,
            (
                media_id, formation_id, subject_id, workspace_id, part_id,
                content_sha256, sqlite3.Binary(content_bytes), utc_now(),
            ),
        )

    def protected_formation_media(
        self, subject_id: str, workspace_id: str, media_id: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT p.media_id, p.content_sha256, p.content_bytes,
                   length(p.content_bytes) AS content_size
            FROM protected_formation_media p
            JOIN formation_media_references f
              ON f.formation_id = p.formation_id AND f.part_id = p.part_id
            WHERE p.subject_id = ? AND p.workspace_id = ? AND p.media_id = ?
              AND EXISTS (
                SELECT 1 FROM typed_unit_evidence e
                JOIN typed_memory_units u
                  ON u.subject_id = e.subject_id
                 AND u.workspace_id = e.workspace_id AND u.unit_id = e.unit_id
                JOIN records r ON r.id = u.record_id
                WHERE e.source_id = f.adjacent_source_id
                  AND r.status = 'active' AND u.lifecycle = 'active'
                  AND NOT EXISTS (
                    SELECT 1 FROM retrieval_exclusions x
                    WHERE x.subject_id = r.subject_id AND x.record_id = r.id
                  )
              )
            """,
            (subject_id, workspace_id, media_id),
        ).fetchone()
        return dict(row) if row is not None else None

    def media_references_for_sources(
        self, subject_id: str, workspace_id: str, source_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Return original protected media locators adjacent to selected evidence."""
        wanted = set(source_ids)
        if not wanted:
            return []
        placeholders = ",".join("?" for _ in wanted)
        indexed = self._conn.execute(
            f"""
            SELECT r.adjacent_source_id, r.part_id, r.ordinal, r.reference_id,
                   r.reference_sha256, p.media_id
            FROM formation_media_references r
            LEFT JOIN protected_formation_media p
              ON p.formation_id = r.formation_id AND p.part_id = r.part_id
            WHERE r.subject_id = ? AND r.workspace_id = ?
              AND r.adjacent_source_id IN ({placeholders})
            ORDER BY r.formation_id, r.ordinal
            """,
            (subject_id, workspace_id, *sorted(wanted)),
        ).fetchall()
        return [dict(row) for row in indexed]

    def retrieval_quality_summary(self, subject_ids: list[str]) -> dict[str, Any]:
        """Return bounded, content-free formation and retrieval quality totals."""
        subjects = tuple(dict.fromkeys(str(value) for value in subject_ids if value))
        if not subjects:
            return {
                "typed_by_kind": [],
                "typed_by_lifecycle": [],
                "formations": {"total": 0, "complete": 0, "with_loss": 0},
                "context_preparations": [],
                "stage_events": [],
            }
        placeholders = ",".join("?" for _ in subjects)
        typed_by_kind = self._conn.execute(
            f"""
            SELECT kind AS value, COUNT(*) AS count
            FROM typed_memory_units
            WHERE subject_id IN ({placeholders})
            GROUP BY kind ORDER BY count DESC, value ASC
            """,
            subjects,
        ).fetchall()
        typed_by_lifecycle = self._conn.execute(
            f"""
            SELECT lifecycle AS value, COUNT(*) AS count
            FROM typed_memory_units
            WHERE subject_id IN ({placeholders})
            GROUP BY lifecycle ORDER BY count DESC, value ASC
            """,
            subjects,
        ).fetchall()
        formation_row = self._conn.execute(
            f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN json_extract(receipt_json, '$.complete') = 1
                            THEN 1 ELSE 0 END) AS complete
            FROM formation_receipts
            WHERE subject_id IN ({placeholders})
            """,
            subjects,
        ).fetchone()
        event_rows = self._conn.execute(
            f"""
            SELECT created_at, payload FROM audit_log
            WHERE subject_id IN ({placeholders})
              AND event_type = 'memory.context_prepared_v2'
            ORDER BY sequence DESC LIMIT 100
            """,
            subjects,
        ).fetchall()
        stage_rows = self._conn.execute(
            f"""
            SELECT created_at, payload FROM audit_log
            WHERE subject_id IN ({placeholders})
              AND event_type = 'memory.retrieval_stage_v1'
            ORDER BY sequence DESC LIMIT 200
            """,
            subjects,
        ).fetchall()
        preparations = []
        for row in event_rows:
            payload = _load_json(row["payload"], {})
            preparations.append({
                "created_at": row["created_at"],
                "information_need": payload.get("information_need"),
                "profile_id": payload.get("profile_id"),
                "sufficiency": payload.get("sufficiency"),
                "missing_slots": payload.get("missing_slots") or [],
                "neighborhood_visited": int(payload.get("neighborhood_visited") or 0),
                "neighborhood_truncated": bool(payload.get("neighborhood_truncated")),
            })
        stages = []
        for row in stage_rows:
            payload = _load_json(row["payload"], {})
            stages.append({
                "created_at": row["created_at"],
                "stage": payload.get("stage"),
                "status": payload.get("status"),
                "profile_id": payload.get("profile_id"),
                "information_need": payload.get("information_need"),
                "duration_ms": payload.get("duration_ms"),
                "input_count": payload.get("input_count"),
                "output_count": payload.get("output_count"),
                "context_bytes": payload.get("context_bytes"),
                "reason_codes": payload.get("reason_codes") or [],
            })
        formation_total = int(formation_row["total"] or 0)
        formation_complete = int(formation_row["complete"] or 0)
        return {
            "typed_by_kind": [dict(row) for row in typed_by_kind],
            "typed_by_lifecycle": [dict(row) for row in typed_by_lifecycle],
            "formations": {
                "total": formation_total,
                "complete": formation_complete,
                "with_loss": formation_total - formation_complete,
            },
            "context_preparations": preparations,
            "stage_events": stages,
        }

    def retrieval_activation(self, scope: Any) -> dict[str, Any]:
        key = _retrieval_activation_key(scope)
        row = self._conn.execute(
            "SELECT value, updated_at FROM retrieval_index_state WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return {
                "format": "atmem-retrieval-activation-v1",
                "mode": "legacy",
                "scope": scope.to_dict(),
                "updated_at": None,
            }
        value = _load_json(row["value"], {})
        return {**value, "updated_at": row["updated_at"]}

    def set_retrieval_activation(
        self, scope: Any, mode: str, *, actor: str
    ) -> dict[str, Any]:
        if mode not in {"legacy", "shadow", "active"}:
            raise ValueError("retrieval activation mode must be legacy, shadow, or active")
        if mode == "active" and self.policy.state != "encrypted":
            raise ValueError("typed retrieval activation requires an encrypted household")
        if mode == "active":
            count = int(self._conn.execute(
                """
                SELECT COUNT(*) AS count FROM typed_memory_units
                WHERE subject_id = ? AND agent_id = ? AND workspace_id = ?
                  AND lifecycle = 'active'
                """,
                (scope.subject_id, scope.agent_id, scope.workspace_id),
            ).fetchone()["count"])
            if count < 1:
                raise ValueError("typed retrieval activation requires at least one active typed unit")
        value = {
            "format": "atmem-retrieval-activation-v1",
            "mode": mode,
            "scope": scope.to_dict(),
            "actor": str(actor),
        }
        with self.transaction(immediate=True):
            self._conn.execute(
                """
                INSERT INTO retrieval_index_state(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value = excluded.value, updated_at = excluded.updated_at
                """,
                (_retrieval_activation_key(scope), _json(value), utc_now()),
            )
            self.append_audit_event(
                subject_id=scope.subject_id,
                event_type="memory.retrieval_activation_changed",
                actor=str(actor),
                payload={
                    "mode": mode,
                    "agent_id": scope.agent_id,
                    "workspace_id": scope.workspace_id,
                },
            )
        return self.retrieval_activation(scope)

    def link_source_sequence(
        self, *, subject_id: str, workspace_id: str, source_ids: list[str]
    ) -> None:
        """Persist ordered, source-authoritative adjacency for bounded expansion."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO source_adjacency(
              subject_id, workspace_id, from_source_id, to_source_id,
              relation, ordinal
            ) VALUES (?, ?, ?, ?, 'next', ?)
            """,
            [
                (subject_id, workspace_id, left, right, ordinal)
                for ordinal, (left, right) in enumerate(zip(source_ids, source_ids[1:]))
            ],
        )

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

    # --- session bindings (Amendment A, FR-042/FR-052) ---------------------

    def insert_session_binding(
        self,
        *,
        binding_id: str,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        host_type: str,
        session_key: str,
        session_epoch: str,
        task_id: str,
        actor: str,
        reason: str,
        source: str,
        evidence: list[dict[str, Any]],
        registered_at_utc: str,
        expires_at_utc: str | None,
    ) -> None:
        """Register one binding, or raise if an active one already holds the key.

        The partial unique index does the enforcing, so a concurrent second
        register loses at the database rather than in a read-then-write race.
        """
        self._conn.execute(
            """
            INSERT INTO governed_task_session_bindings (
              binding_id, subject_id, agent_id, workspace_id,
              host_type, session_key, session_epoch, task_id,
              actor, reason, source, evidence, registered_at_utc, expires_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                binding_id, subject_id, agent_id, workspace_id,
                host_type, session_key, session_epoch, task_id,
                actor, reason, source, _json(evidence), registered_at_utc,
                expires_at_utc,
            ),
        )
        self._conn.commit()

    def find_active_session_binding(
        self,
        *,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        host_type: str,
        session_key: str,
        session_epoch: str,
    ) -> dict[str, Any] | None:
        """The exact-key lookup. `session_epoch` is part of it, never optional.

        A caller that has no epoch has no binding to find; it must not fall
        back to matching on the remaining fields, which is why there is no
        variant of this method that omits one.
        """
        row = self._conn.execute(
            """
            SELECT * FROM governed_task_session_bindings
            WHERE subject_id = ? AND agent_id = ? AND workspace_id = ?
              AND host_type = ? AND session_key = ? AND session_epoch = ?
              AND revoked_at_utc IS NULL
            """,
            (subject_id, agent_id, workspace_id, host_type, session_key, session_epoch),
        ).fetchone()
        return _session_binding_from_row(row) if row else None

    def find_active_bindings_for_session_key(
        self,
        *,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        host_type: str,
        session_key: str,
    ) -> list[dict[str, Any]]:
        """Active bindings for a session key across every generation.

        Used only to tell "this conversation was bound under a different
        generation" apart from "this conversation was never bound", so the
        first can withhold as stale rather than as absent. It never selects a
        binding to use.
        """
        rows = self._conn.execute(
            """
            SELECT * FROM governed_task_session_bindings
            WHERE subject_id = ? AND agent_id = ? AND workspace_id = ?
              AND host_type = ? AND session_key = ? AND revoked_at_utc IS NULL
            ORDER BY registered_at_utc DESC
            """,
            (subject_id, agent_id, workspace_id, host_type, session_key),
        ).fetchall()
        return [_session_binding_from_row(row) for row in rows]

    def list_session_bindings(
        self,
        *,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        task_id: str | None = None,
        include_revoked: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = ["subject_id = ?", "agent_id = ?", "workspace_id = ?"]
        params: list[Any] = [subject_id, agent_id, workspace_id]
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if not include_revoked:
            clauses.append("revoked_at_utc IS NULL")
        rows = self._conn.execute(
            f"""
            SELECT * FROM governed_task_session_bindings
            WHERE {" AND ".join(clauses)}
            ORDER BY registered_at_utc DESC, binding_id ASC
            """,
            tuple(params),
        ).fetchall()
        return [_session_binding_from_row(row) for row in rows]

    def revoke_session_binding(
        self,
        *,
        binding_id: str,
        subject_id: str,
        agent_id: str,
        workspace_id: str,
        revoked_at_utc: str,
        revoked_by: str,
        revoked_reason: str,
    ) -> bool:
        """Mark one binding revoked. The row is retained; history is evidence."""
        cursor = self._conn.execute(
            """
            UPDATE governed_task_session_bindings
            SET revoked_at_utc = ?, revoked_by = ?, revoked_reason = ?
            WHERE binding_id = ? AND subject_id = ? AND agent_id = ?
              AND workspace_id = ? AND revoked_at_utc IS NULL
            """,
            (
                revoked_at_utc, revoked_by, revoked_reason,
                binding_id, subject_id, agent_id, workspace_id,
            ),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def revoke_session_bindings_for_task(
        self, *, task_id: str, revoked_at_utc: str, revoked_by: str, revoked_reason: str
    ) -> int:
        cursor = self._conn.execute(
            """
            UPDATE governed_task_session_bindings
            SET revoked_at_utc = ?, revoked_by = ?, revoked_reason = ?
            WHERE task_id = ? AND revoked_at_utc IS NULL
            """,
            (revoked_at_utc, revoked_by, revoked_reason, task_id),
        )
        self._conn.commit()
        return int(cursor.rowcount or 0)

    def delete_session_bindings_for_task(self, *, task_id: str) -> int:
        """Hard delete, for task forgetting only (FR-025)."""
        cursor = self._conn.execute(
            "DELETE FROM governed_task_session_bindings WHERE task_id = ?", (task_id,)
        )
        self._conn.commit()
        return int(cursor.rowcount or 0)

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
                # Bindings are derived from the task: once it is gone there is
                # nothing left to point a conversation at, and a surviving row
                # would name a task that no longer exists. Deleted rather than
                # revoked, because forgetting must leave no derivative behind.
                "governed_task_session_bindings",
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

    def active_records_for_typed_slot(
        self, subject_id: str, workspace_id: str, *, subject: str, relation: str
    ) -> list[dict[str, Any]]:
        """Resolve a durable slot independently of legacy fact-key spelling."""
        rows = self._conn.execute(
            """
            SELECT r.* FROM records r INDEXED BY idx_records_typed_subject_relation
            WHERE r.subject_id = ? AND r.status = 'active'
              AND r.authority_workspace_id = ?
              AND r.authority_subject_id = ? AND r.authority_materialized = 1
              AND lower(COALESCE(
                    json_extract(r.raw, '$.typed_unit.payload.subject'),
                    json_extract(r.raw, '$.typed_unit.payload.entity')
                  )) = lower(?)
              AND lower(json_extract(r.raw, '$.typed_unit.payload.relation')) = lower(?)
              AND EXISTS (
                SELECT 1 FROM typed_memory_units u
                WHERE u.record_id = r.id AND u.subject_id = r.subject_id
                  AND u.workspace_id = ? AND u.lifecycle = 'active'
              )
              AND NOT EXISTS (
                SELECT 1 FROM retrieval_exclusions x
                WHERE x.subject_id = r.subject_id AND x.record_id = r.id
              )
            ORDER BY r.created_at, r.id
            """,
            (
                subject_id, workspace_id, subject_id, subject, relation,
                workspace_id,
            ),
        ).fetchall()
        return [_record_from_row(row) for row in rows]

    def scoped_historical_typed_candidates(
        self, subject_id: str, workspace_id: str, *, subject: str | None,
        relation: str | None, temporal_target: str | None = None,
        limit: int = 200, remote: bool = False,
    ) -> list[dict[str, Any]]:
        """Bounded explicit-time candidates, including governed superseded history."""
        clauses = [
            "r.subject_id = ?", "u.workspace_id = ?",
            "r.status IN ('active', 'superseded')",
            "u.lifecycle IN ('active', 'superseded')",
            "r.authority_materialized = 1",
            "r.authority_subject_id = ?", "r.authority_workspace_id = ?",
        ]
        params: list[Any] = [subject_id, workspace_id, subject_id, workspace_id]
        if subject:
            clauses.append(
                "lower(COALESCE(json_extract(r.raw, '$.typed_unit.payload.subject'), "
                "json_extract(r.raw, '$.typed_unit.payload.entity'))) = lower(?)"
            )
            params.append(subject)
        if relation:
            clauses.append(
                "(lower(json_extract(r.raw, '$.typed_unit.payload.relation')) = lower(?) "
                "OR lower(json_extract(r.raw, '$.typed_unit.payload.relation')) "
                "LIKE ('% ' || lower(?)))"
            )
            params.extend((relation, relation))
        if remote:
            clauses.append("r.sensitivity_class NOT IN ('sensitive', 'restricted')")
        clauses.append(
            "NOT EXISTS (SELECT 1 FROM retrieval_exclusions x "
            "WHERE x.subject_id = r.subject_id AND x.record_id = r.id)"
        )
        target = str(temporal_target or "")
        params.extend((target, target, max(1, min(int(limit), 2_000))))
        rows = self._conn.execute(
            f"""
            SELECT r.* FROM records r
            JOIN typed_memory_units u ON u.record_id = r.id
            WHERE {' AND '.join(clauses)}
            ORDER BY CASE WHEN ? != '' AND COALESCE(
              json_extract(r.raw, '$.typed_unit.event_at'),
              json_extract(r.raw, '$.typed_unit.observed_at'), r.created_at
            ) LIKE (? || '%') THEN 0 ELSE 1 END,
            COALESCE(
              json_extract(r.raw, '$.typed_unit.event_at'),
              json_extract(r.raw, '$.typed_unit.observed_at'), r.created_at
            ) DESC, r.id DESC LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        return [_record_from_row(row) for row in rows]

    def bounded_resolution_context(
        self, subject_id: str, workspace_id: str | None, *, limit: int
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Load only the newest authorized rows used by proposal resolution."""
        bounded = max(0, min(int(limit), 100))
        if not bounded:
            return [], []
        if workspace_id is None:
            episode_rows = self._conn.execute(
                """SELECT * FROM episodes WHERE subject_id = ?
                   ORDER BY created_at DESC, id DESC LIMIT ?""",
                (subject_id, bounded),
            ).fetchall()
        else:
            episode_rows = self._conn.execute(
                """
                SELECT e.* FROM episodes e
                WHERE e.subject_id = ? AND (
                  EXISTS (
                    SELECT 1 FROM protocol_sources s
                    WHERE s.episode_id = e.id AND s.subject_id = ?
                      AND s.workspace_id = ?
                  )
                  OR (
                    NOT EXISTS (
                      SELECT 1 FROM protocol_sources any_source
                      WHERE any_source.episode_id = e.id
                    )
                    AND (
                      json_extract(e.raw, '$.authority_scope.workspace_id') IS NULL
                      OR json_extract(e.raw, '$.authority_scope.workspace_id') = ?
                    )
                  )
                )
                ORDER BY e.created_at DESC, e.id DESC LIMIT ?
                """,
                (subject_id, subject_id, workspace_id, workspace_id, bounded),
            ).fetchall()
        episodes = [_episode_from_row(row) for row in reversed(episode_rows)]
        workspace_clause = (
            "AND (r.authority_workspace_id IS NULL OR r.authority_workspace_id = ?)"
            if workspace_id is not None else ""
        )
        parameters: list[Any] = [subject_id]
        if workspace_id is not None:
            parameters.append(workspace_id)
        parameters.append(bounded)
        rows = self._conn.execute(
            f"""
            SELECT r.* FROM records r
            WHERE r.subject_id = ? AND r.status = 'active'
              {workspace_clause}
              AND NOT EXISTS (
                SELECT 1 FROM retrieval_exclusions x
                WHERE x.subject_id = r.subject_id AND x.record_id = r.id
              )
            ORDER BY r.created_at DESC, r.id DESC LIMIT ?
            """,
            tuple(parameters),
        ).fetchall()
        return episodes, [_record_from_row(row) for row in rows]

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
            raw = _load_json(row["raw"], {})
            if isinstance(raw.get("typed_unit"), dict):
                raw["typed_unit"]["lifecycle"] = "active"
            self._conn.execute(
                """
                UPDATE records
                SET status = 'active', trust_tier = ?, updated_at = ?, raw = ?
                WHERE subject_id = ? AND id = ?
                """,
                (trust_tier, updated_at, _json(raw), subject_id, record_id),
            )
            self._upsert_fts(record_id, subject_id, row["content"])
            authority = raw.get("authority_scope") or {}
            self._upsert_search_terms(
                record_id=record_id,
                subject_id=subject_id,
                workspace_id=str(authority.get("workspace_id") or ""),
                content=str(row["content"]),
                fact_key=row["fact_key"],
            )
            self._conn.execute(
                """
                UPDATE typed_memory_units
                SET lifecycle = 'active', generation = generation + 1,
                    updated_at = ?
                WHERE record_id = ? AND lifecycle = 'quarantined'
                """,
                (updated_at, record_id),
            )
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
                if isinstance(raw.get("typed_unit"), dict):
                    raw["typed_unit"]["lifecycle"] = "superseded"
                self._conn.execute(
                    """
                    UPDATE records
                    SET status = 'superseded', updated_at = ?, raw = ?
                    WHERE subject_id = ? AND id = ? AND status = 'active'
                    """,
                    (updated_at, _json(raw), subject_id, record_id),
                )
                self._delete_fts(record_id)
                self._delete_search_terms(record_id)
                self._conn.execute(
                    """
                    UPDATE typed_memory_units
                    SET lifecycle = 'superseded', generation = generation + 1,
                        updated_at = ?
                    WHERE record_id = ? AND lifecycle IN ('active', 'quarantined')
                    """,
                    (updated_at, record_id),
                )

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
        typed_source_ids: set[str] = set()
        typed_record_ids: set[str] = set()
        with self.transaction():
            for record_id in record_ids:
                row = self._conn.execute(
                    """
                    SELECT id, raw FROM records
                    WHERE subject_id = ? AND id = ?
                      AND status IN ('active', 'quarantined', 'superseded')
                    """,
                    (subject_id, record_id),
                ).fetchone()
                if row is None:
                    continue
                unit_rows = self._conn.execute(
                    """
                    SELECT u.subject_id, u.workspace_id, u.unit_id, e.source_id
                    FROM typed_memory_units u
                    JOIN typed_unit_evidence e
                      ON e.subject_id = u.subject_id
                     AND e.workspace_id = u.workspace_id
                     AND e.unit_id = u.unit_id
                    WHERE u.record_id = ?
                    """,
                    (record_id,),
                ).fetchall()
                typed_source_ids.update(str(value["source_id"]) for value in unit_rows)
                if unit_rows:
                    typed_record_ids.add(record_id)
                original_raw = _load_json(row["raw"], {})
                proposal_id = original_raw.get("proposal_id")
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
                self._delete_search_terms(record_id)
                self._conn.execute(
                    """
                    UPDATE typed_memory_units
                    SET lifecycle = 'deleted', semantic_identity = NULL,
                        generation = generation + 1,
                        updated_at = ?
                    WHERE record_id = ? AND lifecycle != 'deleted'
                    """,
                    (deleted_at, record_id),
                )
                for value in unit_rows:
                    self._conn.execute(
                        """
                        DELETE FROM typed_unit_evidence
                        WHERE subject_id = ? AND workspace_id = ? AND unit_id = ?
                        """,
                        (value["subject_id"], value["workspace_id"], value["unit_id"]),
                    )
                if proposal_id:
                    proposal_row = self._conn.execute(
                        "SELECT proposal FROM memory_proposals WHERE proposal_id = ?",
                        (proposal_id,),
                    ).fetchone()
                    if proposal_row is not None:
                        proposal_value = _load_json(proposal_row["proposal"], {})
                        unit_value = proposal_value.get("unit") or {}
                        self._conn.execute(
                            """
                            UPDATE memory_proposals SET proposal = ?
                            WHERE proposal_id = ?
                            """,
                            (
                                _json({
                                    "format": proposal_value.get("format"),
                                    "proposal_id": proposal_id,
                                    "scope": proposal_value.get("scope"),
                                    "action": proposal_value.get("action"),
                                    "memory_class": proposal_value.get("memory_class"),
                                    "unit_id": unit_value.get("unit_id"),
                                    "formation_id": unit_value.get("formation_id"),
                                    "kind": unit_value.get("kind"),
                                    "redacted": True,
                                }),
                                proposal_id,
                            ),
                        )
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
                if typed_record_ids:
                    typed_placeholders = ",".join("?" for _ in typed_record_ids)
                    typed_episodes = self._conn.execute(
                        f"SELECT episode_id FROM records WHERE id IN ({typed_placeholders})",
                        tuple(typed_record_ids),
                    ).fetchall()
                    typed_episode_ids = {
                        str(value["episode_id"]) for value in typed_episodes
                        if value["episode_id"] is not None
                    }
                    episode_ids = [
                        value for value in episode_ids if str(value) not in typed_episode_ids
                    ]
                if episode_ids:
                    placeholders = ",".join("?" for _ in episode_ids)
                    retained = self._conn.execute(
                        f"""
                        SELECT DISTINCT r.episode_id FROM records r
                        WHERE r.episode_id IN ({placeholders})
                          AND r.status != 'tombstoned'
                        """,
                        episode_ids,
                    ).fetchall()
                    retained_ids = {str(value["episode_id"]) for value in retained}
                    episode_ids = [value for value in episode_ids if value not in retained_ids]
            for source_id in typed_source_ids:
                if not self._source_in_use(source_id):
                    media_rows = self._conn.execute(
                        """SELECT formation_id, part_id
                           FROM formation_media_references
                           WHERE adjacent_source_id = ?""",
                        (source_id,),
                    ).fetchall()
                    for media_row in media_rows:
                        self._conn.execute(
                            """DELETE FROM protected_formation_media
                               WHERE formation_id = ? AND part_id = ?""",
                            (media_row["formation_id"], media_row["part_id"]),
                        )
                    self._conn.execute(
                        "DELETE FROM formation_media_references WHERE adjacent_source_id = ?",
                        (source_id,),
                    )
                episode_id = self._purge_protocol_source(source_id)
                if episode_id is not None:
                    episode_ids.append(episode_id)
            episode_ids = list(dict.fromkeys(episode_ids))
            if episode_ids:
                placeholders = ",".join("?" for _ in episode_ids)
                source_rows = self._conn.execute(
                    f"SELECT source_id, episode_id FROM protocol_sources WHERE episode_id IN ({placeholders})",
                    tuple(episode_ids),
                ).fetchall()
                retained_source_episodes = {
                    str(source_row["episode_id"])
                    for source_row in source_rows
                    if self._source_in_use(str(source_row["source_id"]))
                }
                episode_ids = [
                    value for value in episode_ids
                    if str(value) not in retained_source_episodes
                ]
                for source_row in source_rows:
                    if str(source_row["episode_id"]) in {str(value) for value in episode_ids}:
                        self._purge_protocol_source(str(source_row["source_id"]))
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

    def iter_records(self, subject_id: str):
        """Stream active records for scope-filtered bounded retrieval."""
        cursor = self._conn.execute(
            "SELECT * FROM records WHERE subject_id = ? AND status = 'active' ORDER BY id",
            (subject_id,),
        )
        try:
            for row in cursor:
                yield _record_from_row(row)
        finally:
            cursor.close()

    def recall_candidates(
        self,
        subject_id: str,
        terms: list[str],
        *,
        limit: int = 200,
    ) -> tuple[list[dict[str, Any]], dict[str, float]]:
        """Bound recall work to FTS, keyed-fact, and recent active candidates.

        ``records_fts`` indexes human-readable content, while ``fact_key`` is
        deliberately kept as structured metadata.  A query such as "use my
        age to ..." must still nominate ``user_age`` even when the content is
        phrased as "45 years old" and other query words produce FTS matches.
        """
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
        normalized_terms = {
            term.strip().lower() for term in terms if term.strip()
        }
        if normalized_terms:
            keyed = self._conn.execute(
                """
                SELECT * FROM records
                WHERE subject_id = ? AND status = 'active'
                  AND fact_key IS NOT NULL AND fact_key != ''
                ORDER BY created_at DESC, id DESC
                """,
                (subject_id,),
            ).fetchall()
            keyed_ids: set[str] = set()
            for row in keyed:
                key_terms = {
                    token for token in re.findall(r"[a-z0-9]+", str(row["fact_key"]).lower())
                }
                if not (normalized_terms & key_terms) or str(row["id"]) in seen:
                    continue
                if len(rows) >= limit:
                    evict_at = next(
                        (
                            index for index in range(len(rows) - 1, -1, -1)
                            if str(rows[index]["id"]) not in keyed_ids
                        ),
                        None,
                    )
                    if evict_at is None:
                        break
                    evicted = rows.pop(evict_at)
                    evicted_id = str(evicted["id"])
                    seen.discard(evicted_id)
                    scores.pop(evicted_id, None)
                rows.append(row)
                row_id = str(row["id"])
                seen.add(row_id)
                keyed_ids.add(row_id)
                if scores:
                    key_overlap = len(normalized_terms & key_terms) / len(normalized_terms)
                    scores[row_id] = max(scores.values()) * key_overlap
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

    def scoped_search_candidates(
        self,
        subject_id: str,
        workspace_id: str,
        terms: list[str],
        *,
        limit: int = 200,
        remote: bool = False,
        graph_floor: int = 256,
        include_superseded: bool = False,
        include_recency: bool = True,
        include_fact: bool = True,
    ) -> tuple[
        list[dict[str, Any]], dict[str, float], dict[str, float], int, dict[str, Any]
    ]:
        """Return bounded authorized candidates from FTS plus exact postings.

        Authorization predicates are applied in SQL before candidate limits or
        scores.  Workspace-private rows therefore cannot consume another
        workspace's quota or alter its ranking.  A bounded recency tail is
        included solely as graph input until typed adjacency is persisted.
        """
        limit = max(1, min(int(limit), 2_000))
        graph_limit = min(4_000, max(limit * 2, max(int(graph_floor), 1)))
        normalized_terms = sorted(
            {_search_stem(term) for term in terms if term.strip()}
        )[:64]
        status_sql = "r.status IN ('active', 'superseded')" if include_superseded else "r.status = 'active'"
        auth_sql = f"""
            r.subject_id = ? AND {status_sql}
            AND (
              r.authority_materialized = 1 AND (
              (r.authority_subject_id IS NULL AND r.authority_workspace_id IS NULL)
              OR (r.authority_subject_id = ? AND r.authority_workspace_id = ?)
              )
            )
            AND NOT EXISTS (
              SELECT 1 FROM retrieval_exclusions x
              WHERE x.subject_id = r.subject_id AND x.record_id = r.id
            )
        """
        auth_params: list[Any] = [subject_id, subject_id, workspace_id]
        if remote:
            auth_sql += " AND r.sensitivity_class NOT IN ('sensitive', 'restricted')"

        def lexical_fts() -> dict[str, float]:
            if not normalized_terms or not self._fts_enabled:
                return {}
            match_expr = " OR ".join(
                '"' + term.replace('"', '') + '"' for term in normalized_terms
            )
            try:
                rows = self._conn.execute(
                    f"""
                    SELECT f.record_id, bm25(records_fts) AS rank, r.created_at
                    FROM records_fts f JOIN records r ON r.id = f.record_id
                    WHERE records_fts MATCH ? AND f.subject_id = ? AND {auth_sql}
                    ORDER BY bm25(records_fts), r.created_at DESC, f.record_id
                    LIMIT ?
                    """,
                    (match_expr, subject_id, *auth_params, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                return {}
            # FTS owns term-frequency/document-frequency accounting.  Expose a
            # stable reciprocal rank to the cross-channel fusion layer rather
            # than persisting one redundant SQL row per content token.
            return {
                str(row["record_id"]): 1.0 / rank
                for rank, row in enumerate(rows, start=1)
            }

        def fact_postings() -> dict[str, float]:
            if not normalized_terms:
                return {}
            placeholders = ",".join("?" for _ in normalized_terms)
            rows = self._conn.execute(
                f"""
                WITH authorized AS (
                  SELECT r.id, r.created_at FROM records r WHERE {auth_sql}
                ), matched AS (
                  SELECT p.record_id, p.term, p.term_frequency, a.created_at
                  FROM record_search_terms p
                  JOIN authorized a ON a.id = p.record_id
                  WHERE p.subject_id = ? AND p.workspace_id IN ('', ?)
                    AND p.field = 'fact_key' AND p.term IN ({placeholders})
                ), term_df AS (
                  SELECT term, COUNT(DISTINCT record_id) AS document_frequency
                  FROM matched GROUP BY term
                )
                SELECT m.record_id,
                  SUM((1.0 / d.document_frequency) *
                      (1.0 + MIN(m.term_frequency, 3) * 0.05)) / ? AS score,
                  MAX(m.created_at) AS created_at
                FROM matched m JOIN term_df d ON d.term = m.term
                GROUP BY m.record_id
                ORDER BY score DESC, created_at DESC, m.record_id
                LIMIT ?
                """,
                (
                    *auth_params, subject_id, workspace_id,
                    *normalized_terms, len(normalized_terms), limit,
                ),
            ).fetchall()
            return {str(row["record_id"]): float(row["score"]) for row in rows}

        lexical_scores = lexical_fts()
        fact_scores = fact_postings() if include_fact else {}
        nominated_ids = list(dict.fromkeys((*lexical_scores, *fact_scores)))
        loaded = self.get_records(subject_id, nominated_ids)
        records = [loaded[record_id] for record_id in nominated_ids if record_id in loaded]
        seen = {str(record["id"]) for record in records}
        recent: list[sqlite3.Row] = []
        if include_recency and len(records) < graph_limit:
            recent = self._conn.execute(
                f"""
                SELECT r.* FROM records r
                WHERE {auth_sql}
                ORDER BY r.created_at DESC, r.id DESC LIMIT ?
                """,
                (*auth_params, graph_limit + 1),
            ).fetchall()
            for row in recent[:graph_limit]:
                if str(row["id"]) not in seen:
                    records.append(_record_from_row(row))
                    seen.add(str(row["id"]))
                    if len(records) >= graph_limit:
                        break
        withheld = int(
            self._conn.execute(
                """
                SELECT COUNT(*) AS count FROM records r
                WHERE r.subject_id = ? AND r.status = 'active' AND (
                  r.authority_materialized != 1
                  OR ((r.authority_subject_id IS NOT NULL OR r.authority_workspace_id IS NOT NULL)
                    AND NOT (r.authority_subject_id = ? AND r.authority_workspace_id = ?)
                  )
                  OR EXISTS (
                    SELECT 1 FROM retrieval_exclusions x
                    WHERE x.subject_id = r.subject_id AND x.record_id = r.id
                  )
                  OR (? = 1 AND r.sensitivity_class IN ('sensitive', 'restricted'))
                )
                """,
                (subject_id, subject_id, workspace_id, 1 if remote else 0),
            ).fetchone()["count"]
        )
        return (
            records,
            lexical_scores,
            fact_scores,
            withheld,
            {
                "graph_input_source": (
                    "persistent_fts_plus_bounded_recency"
                    if include_recency else "persistent_fts"
                ),
                "graph_input_records": len(records),
                "graph_input_limit": graph_limit,
                "graph_input_truncated": len(recent) > graph_limit,
            },
        )

    def authorized_record_ids(
        self,
        subject_id: str,
        workspace_id: str,
        record_ids: list[str],
        *,
        remote: bool = False,
    ) -> set[str]:
        """Authorize bounded candidate IDs without enumerating the corpus."""
        ids = list(dict.fromkeys(str(value) for value in record_ids))
        allowed: set[str] = set()
        for start in range(0, len(ids), 500):
            batch = ids[start : start + 500]
            if not batch:
                continue
            placeholders = ",".join("?" for _ in batch)
            remote_clause = (
                "AND r.sensitivity_class NOT IN ('sensitive', 'restricted')"
                if remote else ""
            )
            rows = self._conn.execute(
                f"""
                SELECT r.id FROM records r
                WHERE r.subject_id = ? AND r.status = 'active'
                  AND (
                    r.authority_materialized = 1 AND (
                    (r.authority_subject_id IS NULL AND r.authority_workspace_id IS NULL)
                    OR (r.authority_subject_id = ? AND r.authority_workspace_id = ?)
                    )
                  )
                  {remote_clause}
                  AND NOT EXISTS (
                    SELECT 1 FROM retrieval_exclusions x
                    WHERE x.subject_id = r.subject_id AND x.record_id = r.id
                  )
                  AND r.id IN ({placeholders})
                """,
                (subject_id, subject_id, workspace_id, *batch),
            ).fetchall()
            allowed.update(str(row["id"]) for row in rows)
        return allowed

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
            self._ensure_column("records", "authority_workspace_id", "TEXT")
            self._ensure_column("records", "authority_subject_id", "TEXT")
            self._ensure_column(
                "records", "authority_materialized", "INTEGER NOT NULL DEFAULT 0"
            )
            self._ensure_column(
                "records", "sensitivity_class", "TEXT NOT NULL DEFAULT 'personal'"
            )
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
            self._migrate_context_fts()
            while self._backfill_typed_identity_mappings():
                pass
            self._backfill_typed_exclusion_identities()
            self._backfill_search_terms_if_needed()

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
        for identifier, script in MIGRATION_REGISTRY:
            if identifier in applied:
                continue
            if identifier == "0077_governed_task_sequences":
                for table in ("governed_task_steps", "governed_task_deliveries"):
                    self._ensure_column(
                        table, "sequence", "INTEGER NOT NULL DEFAULT 0"
                    )
            if identifier == "0401_context_generation_revision":
                self._ensure_column(
                    "context_view_generations", "revision", "INTEGER NOT NULL DEFAULT 0"
                )
            self._conn.executescript(script)
            self._conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(identifier, applied_at) "
                "VALUES (?, ?)",
                (identifier, utc_now()),
            )

    def _migrate_context_fts(self) -> None:
        """Create the rebuildable V3 lexical index without copying source bodies."""
        try:
            self._conn.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS context_units_fts USING fts5(
                  generation_id UNINDEXED,
                  unit_id UNINDEXED,
                  text,
                  content=''
                );
                CREATE TABLE IF NOT EXISTS context_units_fts_map(
                  generation_id TEXT NOT NULL,
                  unit_id TEXT NOT NULL,
                  fts_rowid INTEGER NOT NULL UNIQUE,
                  PRIMARY KEY(generation_id, unit_id),
                  FOREIGN KEY(generation_id, unit_id)
                    REFERENCES context_evidence_units(generation_id, unit_id)
                    ON DELETE CASCADE
                );
                """)
            self._context_fts_enabled = True
        except Exception:
            self._context_fts_enabled = False

    def index_context_unit(
        self, generation_id: str, unit_id: str, text: str
    ) -> None:
        if not self._context_fts_enabled:
            return
        existing = self._conn.execute(
            "SELECT fts_rowid FROM context_units_fts_map WHERE generation_id=? AND unit_id=?",
            (generation_id, unit_id),
        ).fetchone()
        if existing is not None:
            rowid = int(existing["fts_rowid"])
            old_text = self._context_unit_search_text(generation_id, unit_id)
            self._conn.execute(
                "INSERT INTO context_units_fts(context_units_fts, rowid, generation_id, unit_id, text) VALUES('delete', ?, ?, ?, ?)",
                (rowid, generation_id, unit_id, old_text),
            )
            self._conn.execute("DELETE FROM context_units_fts_map WHERE fts_rowid=?", (rowid,))
        cursor = self._conn.execute(
            "INSERT INTO context_units_fts(generation_id, unit_id, text) VALUES (?, ?, ?)",
            (generation_id, unit_id, text),
        )
        self._conn.execute(
            "INSERT INTO context_units_fts_map(generation_id, unit_id, fts_rowid) VALUES (?, ?, ?)",
            (generation_id, unit_id, int(cursor.lastrowid)),
        )

    def _context_unit_search_text(self, generation_id: str, unit_id: str) -> str:
        rows = self._conn.execute(
            """SELECT p.content_bytes, r.start_offset, r.end_offset
               FROM context_unit_ranges ur
               JOIN context_source_ranges r USING(range_id)
               JOIN context_source_parts p
                 ON p.source_id=r.source_id AND p.part_id=r.part_id
               WHERE ur.generation_id=? AND ur.unit_id=? ORDER BY ur.ordinal""",
            (generation_id, unit_id),
        ).fetchall()
        return "\n".join(
            bytes(row["content_bytes"])[int(row["start_offset"]):int(row["end_offset"])].decode(
                "utf-8", errors="replace"
            )
            for row in rows
        )

    def _context_unit_search_text_for_range(self, range_id: str) -> str:
        row = self._conn.execute(
            """SELECT p.content_bytes, r.start_offset, r.end_offset
               FROM context_source_ranges r JOIN context_source_parts p
                 ON p.source_id=r.source_id AND p.part_id=r.part_id
               WHERE r.range_id=?""",
            (range_id,),
        ).fetchone()
        if row is None:
            raise ValueError("source range is unavailable")
        return bytes(row["content_bytes"])[
            int(row["start_offset"]):int(row["end_offset"])
        ].decode("utf-8", errors="replace")

    def _delete_context_fts_generation(self, generation_id: str) -> None:
        if not self._context_fts_enabled:
            return
        rows = self._conn.execute(
            "SELECT unit_id, fts_rowid FROM context_units_fts_map WHERE generation_id=?",
            (generation_id,),
        ).fetchall()
        for row in rows:
            text = self._context_unit_search_text(generation_id, str(row["unit_id"]))
            self._conn.execute(
                "INSERT INTO context_units_fts(context_units_fts, rowid, generation_id, unit_id, text) VALUES('delete', ?, ?, ?, ?)",
                (row["fts_rowid"], generation_id, row["unit_id"], text),
            )
        self._conn.execute(
            "DELETE FROM context_units_fts_map WHERE generation_id=?", (generation_id,)
        )

    def applied_migrations(self) -> list[str]:
        """Bootstrap identifiers this database has already applied, in order."""
        return [
            str(row["identifier"])
            for row in self._conn.execute(
                "SELECT identifier FROM schema_migrations ORDER BY identifier"
            ).fetchall()
        ]

    def _backfill_typed_identity_mappings(self) -> bool:
        """Advance a bounded, restart-safe old-to-current identity backfill."""
        table = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'typed_identity_mappings'"
        ).fetchone()
        if table is None:
            return False
        version = "3"
        state = self._conn.execute(
            "SELECT value FROM retrieval_index_state "
            "WHERE key = 'typed_identity_mapping_version'"
        ).fetchone()
        if state is not None and str(state["value"]) == version:
            return False
        from atmem.extract.models import MemoryUnit

        cursor_key = "typed_identity_mapping_cursor_v2"
        cursor_row = self._conn.execute(
            "SELECT value FROM retrieval_index_state WHERE key = ?", (cursor_key,)
        ).fetchone()
        cursor = int(cursor_row["value"]) if cursor_row is not None else 0
        rows = self._conn.execute(
            """SELECT u.rowid AS migration_rowid, u.subject_id, u.workspace_id,
                      u.semantic_identity, r.raw
               FROM typed_memory_units u JOIN records r ON r.id = u.record_id
               WHERE u.semantic_identity IS NOT NULL AND u.rowid > ?
               ORDER BY u.rowid LIMIT 500""",
            (cursor,),
        ).fetchall()
        for row in rows:
            raw = _load_json(row["raw"], {})
            unit_value = raw.get("typed_unit")
            if not isinstance(unit_value, dict):
                continue
            try:
                current = MemoryUnit.from_dict(unit_value).semantic_identity()
            except (KeyError, TypeError, ValueError):
                continue
            legacy = str(row["semantic_identity"])
            existing = self._conn.execute(
                """SELECT current_identity FROM typed_identity_mappings
                   WHERE subject_id = ? AND workspace_id = ?
                     AND identity_kind = 'semantic' AND legacy_identity = ?""",
                (row["subject_id"], row["workspace_id"], legacy),
            ).fetchone()
            if existing is not None and str(existing["current_identity"]) != current:
                self._conn.execute(
                    """UPDATE typed_identity_mappings SET resolution_state = 'ambiguous_review'
                       WHERE subject_id = ? AND workspace_id = ?
                         AND identity_kind = 'semantic' AND legacy_identity = ?""",
                    (row["subject_id"], row["workspace_id"], legacy),
                )
                self._conn.execute(
                    """INSERT OR IGNORE INTO typed_identity_review_queue(
                         subject_id, workspace_id, legacy_identity,
                         proposed_current_identity, reason, created_at
                       ) VALUES (?, ?, ?, ?, 'ambiguous_upgrade_identity', ?)""",
                    (
                        row["subject_id"], row["workspace_id"], legacy,
                        current, utc_now(),
                    ),
                )
                continue
            self._conn.execute(
                """INSERT OR IGNORE INTO typed_identity_mappings(
                     subject_id, workspace_id, identity_kind, legacy_identity,
                     current_identity, resolution_state, created_at
                   ) VALUES (?, ?, 'semantic', ?, ?, 'mapped', ?)""",
                (row["subject_id"], row["workspace_id"], legacy, current, utc_now()),
            )
        if rows:
            self._conn.execute(
                """INSERT INTO retrieval_index_state(key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                     updated_at=excluded.updated_at""",
                (cursor_key, str(max(int(row["migration_rowid"]) for row in rows)), utc_now()),
            )
            return True
        self._conn.execute(
            """INSERT INTO retrieval_index_state(key, value, updated_at)
               VALUES ('typed_identity_mapping_version', ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                 updated_at=excluded.updated_at""",
            (version, utc_now()),
        )
        self._conn.execute(
            "DELETE FROM retrieval_index_state WHERE key = ?", (cursor_key,)
        )
        return False

    def _backfill_typed_exclusion_identities(self) -> None:
        """Materialize stable typed identities for pre-existing exclusions."""
        from atmem.extract.models import MemoryUnit

        rows = self._conn.execute(
            """SELECT x.subject_id, x.record_id, r.raw
               FROM retrieval_exclusions x
               JOIN records r ON r.id = x.record_id
               LEFT JOIN typed_exclusion_identities t
                 ON t.subject_id = x.subject_id AND t.record_id = x.record_id
               WHERE t.record_id IS NULL"""
        ).fetchall()
        for row in rows:
            unit_value = _load_json(row["raw"], {}).get("typed_unit")
            if not isinstance(unit_value, dict):
                continue
            try:
                unit = MemoryUnit.from_dict(unit_value)
            except (KeyError, TypeError, ValueError):
                continue
            self.set_typed_exclusion_identity(
                subject_id=str(row["subject_id"]),
                workspace_id=unit.scope.workspace_id,
                record_id=str(row["record_id"]),
                exclusion_identity=unit.exclusion_identity(),
                excluded=True,
            )

    def set_typed_exclusion_identity(
        self, *, subject_id: str, workspace_id: str, record_id: str,
        exclusion_identity: str, excluded: bool,
    ) -> None:
        if excluded:
            self._conn.execute(
                """INSERT INTO typed_exclusion_identities(
                     subject_id, workspace_id, record_id, exclusion_identity, created_at
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(subject_id, record_id) DO UPDATE SET
                     workspace_id=excluded.workspace_id,
                     exclusion_identity=excluded.exclusion_identity""",
                (subject_id, workspace_id, record_id, exclusion_identity, utc_now()),
            )
        else:
            self._conn.execute(
                "DELETE FROM typed_exclusion_identities "
                "WHERE subject_id = ? AND record_id = ?",
                (subject_id, record_id),
            )

    def has_typed_exclusion_identity(
        self, subject_id: str, workspace_id: str, exclusion_identity: str
    ) -> bool:
        return self._conn.execute(
            """SELECT 1 FROM typed_exclusion_identities
               WHERE subject_id = ? AND workspace_id = ?
                 AND exclusion_identity = ? LIMIT 1""",
            (subject_id, workspace_id, exclusion_identity),
        ).fetchone() is not None

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
                CREATE TABLE IF NOT EXISTS audit_fts_state(
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                );
                """)
            version = self._conn.execute(
                "SELECT value FROM audit_fts_state WHERE key = 'version'"
            ).fetchone()
            if version is None or version["value"] != "2":
                self._conn.executescript("""
                    DROP TRIGGER IF EXISTS audit_fts_insert;
                    DROP TRIGGER IF EXISTS audit_fts_delete;
                    DROP TRIGGER IF EXISTS audit_fts_update;
                    DROP TABLE IF EXISTS audit_fts;
                    """)
            self._conn.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS audit_fts
                USING fts5(
                  event_id, subject_id UNINDEXED, event_type, actor,
                  session_id, turn_id, record_id, payload UNINDEXED,
                  content='audit_log', content_rowid='sequence',
                  tokenize='porter unicode61'
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
            if version is None or version["value"] != "2":
                self._conn.execute("INSERT INTO audit_fts(audit_fts) VALUES('rebuild')")
                self._conn.execute(
                    "INSERT INTO audit_fts_state(key, value) VALUES('version', '2') "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
                )
            self._audit_fts_enabled = True
        except Exception:
            # Audit search is a rebuildable derived index.  SQLCipher exposes
            # its own exception hierarchy (not sqlite3.DatabaseError), and an
            # older or interrupted FTS shadow table can fail the special
            # ``rebuild`` command even when the canonical audit_log passes
            # integrity checks.  Never make the authority-bearing household
            # unavailable because this optional index cannot be rebuilt.
            try:
                self._conn.executescript("""
                    DROP TRIGGER IF EXISTS audit_fts_insert;
                    DROP TRIGGER IF EXISTS audit_fts_delete;
                    DROP TRIGGER IF EXISTS audit_fts_update;
                    DROP TABLE IF EXISTS audit_fts;
                    """)
            except Exception:
                pass
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

    def _delete_search_terms(self, record_id: str) -> None:
        self._conn.execute(
            "DELETE FROM record_search_terms WHERE record_id = ?", (record_id,)
        )

    def _upsert_search_terms(
        self,
        *,
        record_id: str,
        subject_id: str,
        workspace_id: str,
        content: str,
        fact_key: str | None,
    ) -> None:
        self._conn.execute(
            "DELETE FROM record_search_terms WHERE record_id = ?", (record_id,)
        )
        rows: list[tuple[str, str, str, str, str, int]] = []
        # Content already lives in the FTS5 index.  Only the compact exact
        # fact-key channel needs explicit postings; duplicating every content
        # token here made UI trajectories grow by hundreds of rows per state.
        for field, value in (("fact_key", fact_key or ""),):
            counts: dict[str, int] = {}
            for term in _search_terms(value):
                counts[term] = counts.get(term, 0) + 1
            rows.extend(
                (record_id, subject_id, workspace_id, field, term, count)
                for term, count in counts.items()
            )
        if rows:
            self._conn.executemany(
                """
                INSERT INTO record_search_terms(
                  record_id, subject_id, workspace_id, field, term, term_frequency
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def _backfill_search_terms_if_needed(self) -> None:
        version = SEARCH_INDEX_VERSION
        state = self._conn.execute(
            "SELECT value FROM retrieval_index_state WHERE key = 'postings_version'"
        ).fetchone()
        if state is not None and state["value"] == version:
            return
        owns_transaction = not self._conn.in_transaction
        if owns_transaction:
            self._conn.execute("BEGIN IMMEDIATE")
        try:
            state = self._conn.execute(
                "SELECT value FROM retrieval_index_state WHERE key = 'postings_version'"
            ).fetchone()
            if state is not None and state["value"] == version:
                if owns_transaction:
                    self._conn.commit()
                return
            self._conn.execute("DELETE FROM record_search_terms")
            rows = self._conn.execute(
                "SELECT id, subject_id, content, fact_key, raw, authority_subject_id, "
                "authority_workspace_id, sensitivity_class, authority_materialized "
                "FROM records WHERE status = 'active'"
            ).fetchall()
            for row in rows:
                raw = _load_json(row["raw"], {})
                authority = raw.get("authority_scope") or {}
                authority_subject_id = authority.get("subject_id")
                authority_workspace_id = authority.get("workspace_id")
                sensitivity_class = str(raw.get("sensitivity") or "personal")
                if (
                    row["authority_subject_id"] != authority_subject_id
                    or row["authority_workspace_id"] != authority_workspace_id
                    or row["sensitivity_class"] != sensitivity_class
                    or int(row["authority_materialized"] or 0) != 1
                ):
                    self._conn.execute(
                        """
                        UPDATE records SET authority_subject_id = ?,
                          authority_workspace_id = ?, sensitivity_class = ?,
                          authority_materialized = 1
                        WHERE id = ?
                        """,
                        (
                            authority_subject_id, authority_workspace_id,
                            sensitivity_class, row["id"],
                        ),
                    )
                self._upsert_search_terms(
                    record_id=str(row["id"]), subject_id=str(row["subject_id"]),
                    workspace_id=str(authority_workspace_id or ""),
                    content=str(row["content"]), fact_key=row["fact_key"],
                )
            self._conn.execute(
                """
                INSERT INTO retrieval_index_state(key, value, updated_at)
                VALUES ('postings_version', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value = excluded.value, updated_at = excluded.updated_at
                """,
                (version, utc_now()),
            )
            if owns_transaction:
                self._conn.commit()
        except BaseException:
            if owns_transaction:
                self._conn.rollback()
            raise

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


# Global append-only migration registry. ``0000`` records the compatible
# pre-registry initializer; 0060-0069 and 0070-0079 retain the identifiers
# reserved by their owning specs. Never renumber or edit a shipped step.
MIGRATION_REGISTRY: tuple[tuple[str, str], ...] = (
    (
        "0000_pre_registry_baseline",
        """SELECT 1;""",
    ),
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
    (
        "0078_governed_task_session_bindings",
        """
        CREATE TABLE IF NOT EXISTS governed_task_session_bindings (
          binding_id TEXT PRIMARY KEY,
          subject_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          -- Namespaces the session key so an OpenClaw key and a LangGraph key
          -- cannot collide inside one scope.
          host_type TEXT NOT NULL,
          session_key TEXT NOT NULL,
          -- The host reset signal (FR-052). Part of the key, so a new
          -- conversation incarnation simply does not match an active row
          -- rather than inheriting the previous one's binding.
          session_epoch TEXT NOT NULL,
          -- The target, deliberately OUTSIDE the uniqueness key below. That is
          -- what makes bindings many-to-one and makes repointing a session
          -- impossible to express as an update: it must be a revoke and a
          -- register, each carrying its own authority and evidence.
          task_id TEXT NOT NULL,
          actor TEXT NOT NULL,
          reason TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT '',
          evidence TEXT NOT NULL DEFAULT '[]',
          registered_at_utc TEXT NOT NULL,
          -- Supplemental expiry only; absence of a reset signal is never
          -- covered by this. NULL means the profile declared no lifetime.
          expires_at_utc TEXT,
          -- Revoked rows are retained, not deleted: the history of what a
          -- conversation was pointed at is evidence.
          revoked_at_utc TEXT,
          revoked_by TEXT,
          revoked_reason TEXT
        );

        -- At most one ACTIVE binding per key. Partial, so revoked rows accumulate
        -- freely and a session can be re-bound after an explicit revoke.
        CREATE UNIQUE INDEX IF NOT EXISTS uq_governed_task_session_bindings_active
          ON governed_task_session_bindings(
            subject_id, agent_id, workspace_id, host_type, session_key, session_epoch
          )
          WHERE revoked_at_utc IS NULL;

        -- Resolution reads exactly this key on every turn.
        CREATE INDEX IF NOT EXISTS idx_governed_task_session_bindings_lookup
          ON governed_task_session_bindings(
            subject_id, agent_id, workspace_id, host_type, session_key
          );

        -- Deleting a task removes its bindings; listing a task's bindings reads this.
        CREATE INDEX IF NOT EXISTS idx_governed_task_session_bindings_task
          ON governed_task_session_bindings(task_id);
        """,
    ),
    (
        "0090_graph_generations_and_lineage",
        """
        CREATE TABLE IF NOT EXISTS graph_generations (
          generation_id TEXT PRIMARY KEY,
          subject_id TEXT NOT NULL,
          canonical_generation INTEGER NOT NULL,
          graph_sha256 TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('active','retired','repair_required')),
          created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_graph_generation_active
          ON graph_generations(subject_id) WHERE status='active';
        CREATE TABLE IF NOT EXISTS graph_identity_mutations (
          mutation_id TEXT PRIMARY KEY,
          subject_id TEXT NOT NULL,
          action TEXT NOT NULL,
          preview_sha256 TEXT NOT NULL,
          before_json TEXT NOT NULL,
          after_json TEXT NOT NULL,
          actor TEXT NOT NULL,
          reason TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          rolled_back_at TEXT
        );
        """,
    ),
    (
        "0100_storage_backend_metadata",
        """
        CREATE TABLE IF NOT EXISTS storage_backend_metadata (
          backend_id TEXT PRIMARY KEY,
          role TEXT NOT NULL CHECK (role IN ('canonical', 'derived')),
          capabilities_json TEXT NOT NULL,
          configuration_sha256 TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """,
    ),
    (
        "0120_api_idempotency_receipts",
        """
        CREATE TABLE IF NOT EXISTS api_idempotency_receipts (
          principal_scope_sha256 TEXT NOT NULL,
          operation TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL,
          response_json TEXT NOT NULL,
          status_code INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          PRIMARY KEY (principal_scope_sha256, operation, idempotency_key)
        );
        CREATE INDEX IF NOT EXISTS idx_api_idempotency_expiry
          ON api_idempotency_receipts(expires_at);
        """,
    ),
    (
        "0140_interchange_runs",
        """
        CREATE TABLE IF NOT EXISTS interchange_runs (
          run_id TEXT PRIMARY KEY,
          subject_id TEXT NOT NULL,
          archive_sha256 TEXT NOT NULL,
          options_sha256 TEXT NOT NULL,
          state TEXT NOT NULL,
          checkpoint INTEGER NOT NULL DEFAULT 0,
          counts_json TEXT NOT NULL DEFAULT '{}',
          affected_ids_json TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(subject_id, archive_sha256, options_sha256)
        );
        CREATE TABLE IF NOT EXISTS interchange_items (
          run_id TEXT NOT NULL,
          source_id TEXT NOT NULL,
          source_sha256 TEXT NOT NULL,
          outcome TEXT NOT NULL,
          record_ids_json TEXT NOT NULL DEFAULT '[]',
          committed_at TEXT NOT NULL,
          PRIMARY KEY(run_id, source_id),
          FOREIGN KEY(run_id) REFERENCES interchange_runs(run_id)
        );
        """,
    ),
    (
        "0150_memory_lifecycle",
        """
        CREATE TABLE IF NOT EXISTS memory_lifecycle (
          subject_id TEXT NOT NULL,
          record_id TEXT NOT NULL,
          state TEXT NOT NULL,
          generation INTEGER NOT NULL DEFAULT 1,
          learned_at TEXT NOT NULL,
          valid_from TEXT,
          valid_to TEXT,
          replaced_at TEXT,
          last_used_at TEXT,
          review_at TEXT,
          expires_at TEXT,
          archived_at TEXT,
          deleted_at TEXT,
          policy_json TEXT NOT NULL DEFAULT '{}',
          updated_at TEXT NOT NULL,
          PRIMARY KEY (subject_id, record_id),
          FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_memory_lifecycle_scan
          ON memory_lifecycle(subject_id, state, expires_at, review_at);
        CREATE TABLE IF NOT EXISTS memory_lifecycle_transitions (
          transition_id TEXT PRIMARY KEY,
          subject_id TEXT NOT NULL,
          record_id TEXT NOT NULL,
          from_state TEXT NOT NULL,
          to_state TEXT NOT NULL,
          base_generation INTEGER NOT NULL,
          resulting_generation INTEGER NOT NULL,
          actor TEXT NOT NULL,
          reason TEXT NOT NULL,
          evidence_json TEXT NOT NULL DEFAULT '[]',
          invalidation_json TEXT NOT NULL DEFAULT '{}',
          occurred_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memory_lifecycle_history
          ON memory_lifecycle_transitions(subject_id, record_id, occurred_at);
        CREATE TRIGGER IF NOT EXISTS memory_lifecycle_transitions_immutable
        BEFORE UPDATE ON memory_lifecycle_transitions BEGIN
          SELECT RAISE(ABORT, 'memory lifecycle transitions are immutable');
        END;
        """,
    ),
    (
        "0160_governed_media_references",
        """
        CREATE TABLE IF NOT EXISTS governed_media_references (
          artifact_id TEXT PRIMARY KEY,
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          media_kind TEXT NOT NULL,
          locator_sha256 TEXT NOT NULL,
          locator_json TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          custody TEXT NOT NULL,
          consent TEXT NOT NULL,
          consent_generation INTEGER NOT NULL,
          retention_json TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_governed_media_scope
          ON governed_media_references(subject_id,workspace_id,status,consent);
        CREATE TABLE IF NOT EXISTS governed_media_observations (
          observation_id TEXT PRIMARY KEY,
          artifact_id TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          text_sha256 TEXT NOT NULL,
          text TEXT NOT NULL,
          evidence_region_json TEXT NOT NULL,
          processor_json TEXT NOT NULL,
          prompt_config_sha256 TEXT NOT NULL,
          confidence REAL,
          consent_generation INTEGER NOT NULL,
          egress TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(artifact_id) REFERENCES governed_media_references(artifact_id)
        );
        CREATE INDEX IF NOT EXISTS idx_governed_media_observation_scope
          ON governed_media_observations(subject_id,workspace_id,status,artifact_id);
        """,
    ),
    (
        "0380_scoped_retrieval_postings",
        """
        CREATE TABLE IF NOT EXISTS record_search_terms (
          record_id TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT '',
          field TEXT NOT NULL CHECK (field IN ('content', 'fact_key')),
          term TEXT NOT NULL,
          term_frequency INTEGER NOT NULL CHECK (term_frequency > 0),
          PRIMARY KEY (record_id, field, term),
          FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_record_search_terms_lookup
          ON record_search_terms(subject_id, workspace_id, field, term, record_id);
        CREATE INDEX IF NOT EXISTS idx_records_authorized_recall
          ON records(subject_id, status, authority_subject_id, authority_workspace_id, sensitivity_class,
                     authority_materialized, created_at, id);
        CREATE INDEX IF NOT EXISTS idx_records_subject_recent
          ON records(subject_id, status, created_at DESC, id DESC);
        CREATE TABLE IF NOT EXISTS retrieval_index_state (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """,
    ),
    (
        "0381_typed_memory_sources",
        """
        CREATE TABLE IF NOT EXISTS typed_memory_units (
          subject_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          unit_id TEXT NOT NULL,
          record_id TEXT NOT NULL UNIQUE,
          formation_id TEXT NOT NULL,
          kind TEXT NOT NULL,
          semantic_identity TEXT,
          lifecycle TEXT NOT NULL CHECK (
            lifecycle IN ('active', 'quarantined', 'superseded', 'revoked', 'deleted')
          ),
          generation INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE,
          PRIMARY KEY(subject_id, workspace_id, unit_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_typed_units_live_identity
          ON typed_memory_units(subject_id, workspace_id, semantic_identity)
          WHERE lifecycle IN ('active', 'quarantined');
        CREATE INDEX IF NOT EXISTS idx_typed_units_scope_lifecycle
          ON typed_memory_units(subject_id, workspace_id, lifecycle, kind, unit_id);
        CREATE INDEX IF NOT EXISTS idx_typed_units_formation
          ON typed_memory_units(formation_id, unit_id);

        CREATE TABLE IF NOT EXISTS typed_unit_evidence (
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          unit_id TEXT NOT NULL,
          source_id TEXT NOT NULL,
          start_offset INTEGER NOT NULL,
          end_offset INTEGER NOT NULL,
          excerpt_sha256 TEXT NOT NULL,
          PRIMARY KEY(subject_id, workspace_id, unit_id, source_id, start_offset, end_offset),
          FOREIGN KEY (subject_id, workspace_id, unit_id)
            REFERENCES typed_memory_units(subject_id, workspace_id, unit_id)
            ON DELETE CASCADE,
          FOREIGN KEY (source_id) REFERENCES protocol_sources(source_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_typed_evidence_source
          ON typed_unit_evidence(subject_id, workspace_id, source_id, unit_id);
        """,
    ),
    (
        "0382_memory_proposal_sources",
        """
        CREATE TABLE IF NOT EXISTS memory_proposal_sources (
          proposal_id TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          source_id TEXT NOT NULL,
          PRIMARY KEY(proposal_id, source_id),
          FOREIGN KEY (proposal_id) REFERENCES memory_proposals(proposal_id) ON DELETE CASCADE,
          FOREIGN KEY (source_id) REFERENCES protocol_sources(source_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_memory_proposal_sources_source
          ON memory_proposal_sources(subject_id, workspace_id, source_id, proposal_id);
        """,
    ),
    (
        "0383_formation_receipts",
        """
        CREATE TABLE IF NOT EXISTS formation_receipts (
          formation_id TEXT PRIMARY KEY,
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          episode_id TEXT NOT NULL,
          receipt_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_formation_receipts_scope
          ON formation_receipts(subject_id, workspace_id, created_at, formation_id);
        """,
    ),
    (
        "0384_source_adjacency",
        """
        CREATE TABLE IF NOT EXISTS source_adjacency (
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          from_source_id TEXT NOT NULL,
          to_source_id TEXT NOT NULL,
          relation TEXT NOT NULL CHECK (relation IN ('next')),
          ordinal INTEGER NOT NULL,
          PRIMARY KEY(subject_id, workspace_id, from_source_id, to_source_id, relation),
          FOREIGN KEY (from_source_id) REFERENCES protocol_sources(source_id) ON DELETE CASCADE,
          FOREIGN KEY (to_source_id) REFERENCES protocol_sources(source_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_source_adjacency_reverse
          ON source_adjacency(subject_id, workspace_id, to_source_id, ordinal);
        """,
    ),
    (
        "0385_formation_media_references",
        """
        CREATE TABLE IF NOT EXISTS formation_media_references (
          formation_id TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          adjacent_source_id TEXT NOT NULL,
          part_id TEXT NOT NULL,
          ordinal INTEGER NOT NULL,
          reference_id TEXT NOT NULL,
          reference_sha256 TEXT NOT NULL,
          PRIMARY KEY(formation_id, part_id),
          FOREIGN KEY (formation_id) REFERENCES formation_receipts(formation_id) ON DELETE CASCADE,
          FOREIGN KEY (adjacent_source_id) REFERENCES protocol_sources(source_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_formation_media_source
          ON formation_media_references(
            subject_id, workspace_id, adjacent_source_id, formation_id, ordinal
          );
        """,
    ),
    (
        "0386_typed_identity_and_protected_media",
        """
        CREATE TABLE IF NOT EXISTS typed_identity_mappings (
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          identity_kind TEXT NOT NULL,
          legacy_identity TEXT NOT NULL,
          current_identity TEXT NOT NULL,
          resolution_state TEXT NOT NULL CHECK (
            resolution_state IN (
              'mapped', 'ambiguous_review', 'confirmed_superseded', 'rebuilt',
              'reinstated', 'pending_review', 'rebuilt_from_evidence'
            )
          ),
          created_at TEXT NOT NULL,
          PRIMARY KEY(subject_id, workspace_id, identity_kind, legacy_identity)
        );
        CREATE TABLE IF NOT EXISTS protected_formation_media (
          media_id TEXT PRIMARY KEY,
          formation_id TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          part_id TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          content_bytes BLOB NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(formation_id, part_id),
          FOREIGN KEY (formation_id) REFERENCES formation_receipts(formation_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_protected_formation_media_scope
          ON protected_formation_media(subject_id, workspace_id, formation_id, part_id);
        CREATE TABLE IF NOT EXISTS typed_identity_review_queue (
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          legacy_identity TEXT NOT NULL,
          proposed_current_identity TEXT NOT NULL,
          reason TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(subject_id, workspace_id, legacy_identity, proposed_current_identity)
        );
        """,
    ),
    (
        "0387_typed_slot_lookup_indexes",
        """
        CREATE INDEX IF NOT EXISTS idx_records_typed_subject_relation
          ON records(
            subject_id, status, authority_workspace_id,
            lower(COALESCE(
              json_extract(raw, '$.typed_unit.payload.subject'),
              json_extract(raw, '$.typed_unit.payload.entity')
            )),
            lower(json_extract(raw, '$.typed_unit.payload.relation')),
            id
          )
          WHERE authority_materialized = 1;
        CREATE INDEX IF NOT EXISTS idx_typed_units_formation_scope
          ON typed_memory_units(formation_id, subject_id, workspace_id, lifecycle, record_id);
        CREATE INDEX IF NOT EXISTS idx_typed_identity_current
          ON typed_identity_mappings(
            subject_id, workspace_id, identity_kind,
            current_identity, resolution_state, legacy_identity
          );
        """,
    ),
    (
        "0388_backfill_formation_media_references",
        """
        INSERT OR IGNORE INTO formation_media_references(
          formation_id, subject_id, workspace_id, adjacent_source_id,
          part_id, ordinal, reference_id, reference_sha256
        )
        SELECT f.formation_id, f.subject_id, f.workspace_id,
               json_extract(item.value, '$.adjacent_source_id'),
               json_extract(item.value, '$.part_id'),
               CAST(json_extract(item.value, '$.ordinal') AS INTEGER),
               json_extract(item.value, '$.reference_id'),
               json_extract(item.value, '$.reference_sha256')
        FROM formation_receipts f,
             json_each(f.receipt_json, '$.media_references') item
        WHERE json_extract(item.value, '$.adjacent_source_id') IS NOT NULL
          AND json_extract(item.value, '$.part_id') IS NOT NULL
          AND json_extract(item.value, '$.reference_id') IS NOT NULL
          AND json_extract(item.value, '$.reference_sha256') IS NOT NULL;
        """,
    ),
    (
        "0389_typed_exclusion_identities",
        """
        CREATE TABLE IF NOT EXISTS typed_exclusion_identities (
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          record_id TEXT NOT NULL,
          exclusion_identity TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(subject_id, record_id),
          FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_typed_exclusion_identity
          ON typed_exclusion_identities(
            subject_id, workspace_id, exclusion_identity, record_id
          );
        """,
    ),
    (
        "0400_context_engine_generations",
        """
        CREATE TABLE IF NOT EXISTS context_source_episodes (
          source_id TEXT PRIMARY KEY,
          legacy_episode_id TEXT UNIQUE,
          subject_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          source_sha256 TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(subject_id, agent_id, workspace_id, source_sha256)
        );
        CREATE INDEX IF NOT EXISTS idx_context_sources_scope
          ON context_source_episodes(subject_id, workspace_id, agent_id, source_id);
        CREATE TABLE IF NOT EXISTS context_source_parts (
          source_id TEXT NOT NULL,
          part_id TEXT NOT NULL,
          ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
          kind TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          content_bytes BLOB NOT NULL,
          PRIMARY KEY(source_id, part_id),
          UNIQUE(source_id, ordinal),
          FOREIGN KEY(source_id) REFERENCES context_source_episodes(source_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS context_source_ranges (
          range_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          part_id TEXT NOT NULL,
          start_offset INTEGER NOT NULL CHECK(start_offset >= 0),
          end_offset INTEGER NOT NULL CHECK(end_offset > start_offset),
          source_sha256 TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(source_id, part_id, start_offset, end_offset),
          FOREIGN KEY(source_id, part_id)
            REFERENCES context_source_parts(source_id, part_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS context_view_generations (
          generation_id TEXT PRIMARY KEY,
          subject_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          profile_id TEXT NOT NULL,
          state TEXT NOT NULL CHECK(state IN ('building','verified','active','retired')),
          canonical_generation INTEGER NOT NULL DEFAULT 0,
          configuration_sha256 TEXT NOT NULL,
          verification_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          verified_at TEXT,
          activated_at TEXT,
          retired_at TEXT
          ,revision INTEGER NOT NULL DEFAULT 0
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_context_one_active_generation
          ON context_view_generations(subject_id, workspace_id, agent_id)
          WHERE state = 'active';
        CREATE INDEX IF NOT EXISTS idx_context_generation_scope_state
          ON context_view_generations(subject_id, workspace_id, agent_id, state, created_at);
        CREATE TABLE IF NOT EXISTS context_evidence_units (
          generation_id TEXT NOT NULL,
          unit_id TEXT NOT NULL,
          kind TEXT NOT NULL CHECK(kind IN (
            'raw_state','transition','fact','entity','procedure','rule','gotcha','premise'
          )),
          compact_json TEXT NOT NULL,
          compact_sha256 TEXT NOT NULL,
          lifecycle TEXT NOT NULL CHECK(lifecycle IN (
            'active','superseded','conflicted','revoked','expired','deleted'
          )),
          created_at TEXT NOT NULL,
          PRIMARY KEY(generation_id, unit_id),
          FOREIGN KEY(generation_id) REFERENCES context_view_generations(generation_id)
            ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_context_units_generation_kind
          ON context_evidence_units(generation_id, lifecycle, kind, unit_id);
        CREATE TABLE IF NOT EXISTS context_unit_ranges (
          generation_id TEXT NOT NULL,
          unit_id TEXT NOT NULL,
          range_id TEXT NOT NULL,
          ordinal INTEGER NOT NULL,
          PRIMARY KEY(generation_id, unit_id, range_id),
          UNIQUE(generation_id, unit_id, ordinal),
          FOREIGN KEY(generation_id, unit_id)
            REFERENCES context_evidence_units(generation_id, unit_id) ON DELETE CASCADE,
          FOREIGN KEY(range_id) REFERENCES context_source_ranges(range_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS context_evidence_links (
          generation_id TEXT NOT NULL,
          from_unit_id TEXT NOT NULL,
          to_unit_id TEXT NOT NULL,
          relation TEXT NOT NULL,
          PRIMARY KEY(generation_id, from_unit_id, to_unit_id, relation),
          FOREIGN KEY(generation_id, from_unit_id)
            REFERENCES context_evidence_units(generation_id, unit_id) ON DELETE CASCADE,
          FOREIGN KEY(generation_id, to_unit_id)
            REFERENCES context_evidence_units(generation_id, unit_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS context_coverage (
          generation_id TEXT NOT NULL,
          range_id TEXT NOT NULL,
          disposition TEXT NOT NULL CHECK(disposition IN ('represented','unsupported','withheld')),
          reason_code TEXT,
          PRIMARY KEY(generation_id, range_id),
          FOREIGN KEY(generation_id) REFERENCES context_view_generations(generation_id) ON DELETE CASCADE,
          FOREIGN KEY(range_id) REFERENCES context_source_ranges(range_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS context_loss_receipts (
          generation_id TEXT NOT NULL,
          range_id TEXT NOT NULL,
          reason_code TEXT NOT NULL,
          detail_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          PRIMARY KEY(generation_id, range_id, reason_code),
          FOREIGN KEY(generation_id) REFERENCES context_view_generations(generation_id) ON DELETE CASCADE,
          FOREIGN KEY(range_id) REFERENCES context_source_ranges(range_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS context_vectors (
          generation_id TEXT NOT NULL,
          unit_id TEXT NOT NULL,
          model_id TEXT NOT NULL,
          dimensions INTEGER NOT NULL,
          vector_bytes BLOB NOT NULL,
          PRIMARY KEY(generation_id, unit_id, model_id),
          FOREIGN KEY(generation_id, unit_id)
            REFERENCES context_evidence_units(generation_id, unit_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS context_backfill_state (
          subject_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          cursor_episode_id TEXT,
          completed INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(subject_id, workspace_id, agent_id)
        );
        """,
    ),
    (
        "0401_context_generation_revision",
        """SELECT 1;""",
    ),
)

# Compatibility alias retained for downstream tests/extensions that imported
# the pre-Spec-010 private name. The tuple itself is now the global registry.
_BOOTSTRAP_MIGRATIONS = MIGRATION_REGISTRY


def _session_binding_from_row(row: Any) -> dict[str, Any]:
    value = dict(row)
    value["evidence"] = _load_json(value.get("evidence"), [])
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value: Any) -> str:
    return canonical_json(value)


_SEARCH_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
SEARCH_INDEX_VERSION = "scoped-postings-v3-fact-only"


def _search_stem(token: str) -> str:
    value = token.lower()
    if len(value) > 4 and value.endswith("ies"):
        return value[:-3] + "i"
    if len(value) > 3 and value.endswith("y"):
        return value[:-1] + "i"
    if len(value) > 4 and value.endswith("es"):
        return value[:-2]
    if len(value) > 3 and value.endswith("s"):
        return value[:-1]
    return value


def _search_terms(value: str) -> list[str]:
    return [_search_stem(token) for token in _SEARCH_TOKEN_RE.findall(value.lower())]


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


def _retrieval_activation_key(scope: Any) -> str:
    digest = sha256_hex(canonical_json(scope.to_dict()))
    return f"retrieval-v2-activation:{digest}"


def _audit_fts_query(query: str) -> str:
    """Treat investigator input as literal terms, never executable FTS syntax."""
    terms = [term for term in re.split(r"[^\w]+", query, flags=re.UNICODE) if term]
    if not terms:
        return '""'
    return " AND ".join('"' + term.replace('"', '""') + '"' for term in terms)
