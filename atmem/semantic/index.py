"""Versioned-epoch exact vector index derived from canonical memory records."""

from __future__ import annotations

from array import array
from contextlib import contextmanager
import json
import math
from pathlib import Path
import sqlite3
import sys
from typing import Any, Callable, Iterator, Sequence
import uuid

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.core.storage import HouseholdLock, HouseholdPolicy, connect, row_factory_for
from atmem.memory import Memory
from atmem.semantic.providers import Embedder
from atmem.store.sqlite import utc_now


INDEX_SCHEMA_VERSION = "2"
INDEX_FORMAT = "atmem-semantic-index-v1"
INDEXABLE_STATUSES = ("active", "quarantined", "superseded")


class SemanticIndexIntegrityError(ValueError):
    """The derived index is inconsistent with its declared epoch."""


def default_index_path(memory_path: str | Path) -> Path:
    path = str(memory_path)
    if path == ":memory:":
        raise ValueError("semantic indexing requires a persistent memory database")
    return Path(f"{path}.vectors.db")


class SemanticIndex:
    def __init__(
        self, path: str | Path, *, policy: HouseholdPolicy | None = None
    ) -> None:
        self.path = str(Path(path).expanduser().resolve())
        self.policy = policy or HouseholdPolicy.load(path)
        self._household_lock = HouseholdLock(self.policy).acquire()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = connect(
                self.path, policy=self.policy, isolation_level=None
            )
        except Exception:
            self._household_lock.close()
            raise
        self._conn.row_factory = row_factory_for(self.policy)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA secure_delete = ON")
        self._migrate()

    def close(self) -> None:
        try:
            self._conn.close()
        finally:
            self._household_lock.close()

    def policy_fingerprint(self) -> str:
        """Digest the household policy identity that derived vectors depend on.

        Only non-secret identifiers are hashed; key material never reaches the
        digest, the epoch identity, or any health report.
        """

        return sha256_hex(
            canonical_json(
                {
                    "state": str(self.policy.state),
                    "backend": str(self.policy.backend or ""),
                    "key_id": str(self.policy.key_id or ""),
                }
            )
        )

    def invalidate_for_policy_change(self, subject_id: str) -> dict[str, Any]:
        """Mark epochs built under a different household policy as dirty."""

        current = self.policy_fingerprint()
        invalidated: list[str] = []
        rows = self._conn.execute(
            "SELECT epoch_id, identity_json FROM vector_epochs WHERE subject_id = ? AND dirty = 0",
            (subject_id,),
        ).fetchall()
        for row in rows:
            try:
                identity = json.loads(str(row["identity_json"]))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            recorded = identity.get("policy_sha256") if isinstance(identity, dict) else None
            if recorded and str(recorded) != current:
                invalidated.append(str(row["epoch_id"]))
        if invalidated:
            placeholders = ",".join("?" for _ in invalidated)
            with self.transaction():
                self._conn.execute(
                    f"UPDATE vector_epochs SET dirty = 1 WHERE epoch_id IN ({placeholders})",
                    invalidated,
                )
        return {
            "format": "atmem-semantic-policy-invalidation-v1",
            "subject_id": subject_id,
            "policy_sha256": current,
            "invalidated_epoch_ids": invalidated,
        }

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()

    def build(
        self,
        memory: Memory,
        subject_id: str,
        embedder: Embedder,
        *,
        batch_size: int = 64,
        fault_hook: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Build or resume an inactive epoch, then activate it after validation."""

        memory.store.register_semantic_index(subject_id, self.path)
        verify_identity = getattr(embedder, "verify_identity", None)
        if callable(verify_identity):
            verify_identity()
        records = memory.store.list_records(subject_id, statuses=INDEXABLE_STATUSES)
        if not records:
            raise ValueError(f"no indexable memory records for subject {subject_id!r}")
        identity = dict(embedder.identity)
        # Bind the household policy the vectors were derived under, so a policy
        # change cannot resume onto, or silently keep serving, an old epoch.
        identity["policy_sha256"] = self.policy_fingerprint()
        identity_sha256 = sha256_hex(canonical_json(identity))
        snapshot = _record_snapshot(records)
        source_sha256 = sha256_hex(canonical_json(sorted(snapshot)))
        canonical_generation = memory.store.record_generation(subject_id)
        checkpoint = self._resumable_checkpoint(
            subject_id, identity_sha256, source_sha256, canonical_generation
        )
        resumed = checkpoint is not None
        if checkpoint is None:
            checkpoint = self._start_rebuild(
                subject_id,
                identity,
                identity_sha256,
                source_sha256,
                canonical_generation,
                len(records),
            )
        epoch_id = str(checkpoint["epoch_id"])
        _call_fault(fault_hook, "epoch_staged", dict(checkpoint))

        completed = {
            str(row["object_id"])
            for row in self._conn.execute(
                "SELECT object_id FROM vector_entries WHERE epoch_id = ?",
                (epoch_id,),
            ).fetchall()
        }
        remaining = [row for row in records if str(row["id"]) not in completed]
        size = max(1, int(batch_size))
        dimensions = int(checkpoint.get("dimensions") or 0)
        checkpointed_batches = 0
        for start in range(0, len(remaining), size):
            batch = remaining[start : start + size]
            vectors = embedder.embed_documents(
                [str(record["content"]) for record in batch]
            )
            if len(vectors) != len(batch):
                raise ValueError("embedder returned the wrong number of vectors")
            prepared: list[tuple[dict[str, Any], list[float]]] = []
            for record, vector in zip(batch, vectors):
                normalized = _normalize(vector)
                dimensions = dimensions or len(normalized)
                if len(normalized) != dimensions:
                    raise ValueError("embedder returned inconsistent dimensions")
                prepared.append((record, normalized))
            now = utc_now()
            with self.transaction():
                for record, vector in prepared:
                    self._conn.execute(
                        """
                        INSERT INTO vector_entries(
                          epoch_id, subject_id, object_type, object_id,
                          content_sha256, status_at_index, dimensions, vector,
                          created_at
                        ) VALUES (?, ?, 'memory', ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            epoch_id,
                            subject_id,
                            record["id"],
                            sha256_hex(str(record["content"])),
                            record["status"],
                            dimensions,
                            _pack(vector),
                            now,
                        ),
                    )
                count = int(
                    self._conn.execute(
                        "SELECT COUNT(*) AS count FROM vector_entries WHERE epoch_id = ?",
                        (epoch_id,),
                    ).fetchone()["count"]
                )
                self._conn.execute(
                    "UPDATE vector_epochs SET dimensions = ?, entry_count = ? WHERE epoch_id = ?",
                    (dimensions, count, epoch_id),
                )
                self._conn.execute(
                    """
                    UPDATE semantic_rebuilds
                    SET completed_records = ?, dimensions = ?, updated_at = ?
                    WHERE epoch_id = ?
                    """,
                    (count, dimensions, now, epoch_id),
                )
            _call_fault(
                fault_hook,
                "batch_checkpointed",
                {"epoch_id": epoch_id, "completed_records": count},
            )
            checkpointed_batches += 1

        _call_fault(fault_hook, "before_activation", {"epoch_id": epoch_id})
        with memory.store.transaction(immediate=True):
            current_records = memory.store.list_records(
                subject_id, statuses=INDEXABLE_STATUSES
            )
            if (
                memory.store.record_generation(subject_id) != canonical_generation
                or _record_snapshot(current_records) != snapshot
            ):
                self._mark_rebuild(epoch_id, "stale")
                raise RuntimeError(
                    "canonical memory changed while embeddings were built; retry the index build"
                )
            self._validate_staged_epoch(epoch_id, subject_id, snapshot, dimensions)
            previous = self.active_epoch(subject_id)
            activated_at = utc_now()
            with self.transaction():
                if previous is not None and previous["epoch_id"] != epoch_id:
                    self._conn.execute(
                        "UPDATE vector_epochs SET status = 'retired', retired_at = ? WHERE epoch_id = ?",
                        (activated_at, previous["epoch_id"]),
                    )
                self._conn.execute(
                    """
                    INSERT INTO vector_subjects(subject_id, active_epoch_id, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(subject_id) DO UPDATE SET
                      active_epoch_id = excluded.active_epoch_id,
                      updated_at = excluded.updated_at
                    """,
                    (subject_id, epoch_id, activated_at),
                )
                self._conn.execute(
                    "UPDATE vector_epochs SET status = 'active', activated_at = ? WHERE epoch_id = ?",
                    (activated_at, epoch_id),
                )
                self._conn.execute(
                    "UPDATE semantic_rebuilds SET status = 'activated', updated_at = ? WHERE epoch_id = ?",
                    (activated_at, epoch_id),
                )
        _call_fault(fault_hook, "activated", {"epoch_id": epoch_id})
        with self.transaction():
            self._conn.execute(
                "DELETE FROM vector_entries WHERE subject_id = ? AND epoch_id <> ?",
                (subject_id, epoch_id),
            )
        verification_report = self.verify(memory, subject_id)
        if not verification_report["valid"]:
            raise ValueError(
                "semantic index failed post-cleanup verification: "
                f"{verification_report['failures']}"
            )
        self.checkpoint_storage()
        memory.store.register_semantic_index(
            subject_id, self.path, active_epoch_id=epoch_id
        )
        report = {
            "format": "atmem-index-build-v1",
            "subject_id": subject_id,
            "index_path": self.path,
            "epoch_id": epoch_id,
            "entry_count": len(prepared),
            "dimensions": dimensions,
            "embedder": identity,
            "identity_sha256": identity_sha256,
            "source_sha256": f"sha256:{source_sha256}",
            "canonical_generation": canonical_generation,
            "resumed": resumed,
            "rebuild_receipt": {
                "format": "atmem-semantic-rebuild-receipt-v1",
                "checkpointed_batches": checkpointed_batches,
                "completed_records": len(records),
                "coverage_valid": True,
                "dimensions_valid": True,
                "canonical_generation": canonical_generation,
                "source_sha256": f"sha256:{source_sha256}",
                "activation": "activated",
            },
            "verification_report_sha256": verification_report["report_sha256"],
        }
        report["audit_event_id"] = memory.log_action(
            subject_id,
            "semantic.index_built",
            {
                "epoch_id": epoch_id,
                "entry_count": len(prepared),
                "dimensions": dimensions,
                "identity_sha256": identity_sha256,
                "index_path_sha256": sha256_hex(self.path),
                "verification_report_sha256": report[
                    "verification_report_sha256"
                ],
            },
            actor="indexer",
        )
        return report

    def _resumable_checkpoint(
        self,
        subject_id: str,
        identity_sha256: str,
        source_sha256: str,
        canonical_generation: int,
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT r.*, e.dimensions FROM semantic_rebuilds r
            JOIN vector_epochs e ON e.epoch_id = r.epoch_id
            WHERE r.subject_id = ? AND r.identity_sha256 = ?
              AND r.source_sha256 = ? AND r.canonical_generation = ?
              AND r.status = 'building' AND e.status = 'building'
            ORDER BY r.created_at DESC LIMIT 1
            """,
            (subject_id, identity_sha256, source_sha256, canonical_generation),
        ).fetchone()
        return dict(row) if row else None

    def _start_rebuild(
        self,
        subject_id: str,
        identity: dict[str, Any],
        identity_sha256: str,
        source_sha256: str,
        canonical_generation: int,
        total_records: int,
    ) -> dict[str, Any]:
        epoch_id = f"vidx_{uuid.uuid4().hex}"
        created_at = utc_now()
        with self.transaction():
            self._conn.execute(
                """
                UPDATE semantic_rebuilds SET status = 'abandoned', updated_at = ?
                WHERE subject_id = ? AND status = 'building'
                """,
                (created_at, subject_id),
            )
            self._conn.execute(
                """
                UPDATE vector_epochs SET status = 'retired', retired_at = ?
                WHERE subject_id = ? AND status = 'building'
                """,
                (created_at, subject_id),
            )
            self._conn.execute(
                """
                INSERT INTO vector_epochs(
                  epoch_id, subject_id, format, provider, model, model_version,
                  identity_json, identity_sha256, dimensions, status, dirty,
                  entry_count, created_at, activated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'building', 0, 0, ?, NULL)
                """,
                (
                    epoch_id,
                    subject_id,
                    INDEX_FORMAT,
                    str(identity.get("provider", "unknown")),
                    str(identity.get("model", "unknown")),
                    str(identity.get("version", "unknown")),
                    json.dumps(identity, sort_keys=True, separators=(",", ":")),
                    identity_sha256,
                    created_at,
                ),
            )
            self._conn.execute(
                """
                INSERT INTO semantic_rebuilds(
                  epoch_id, subject_id, identity_sha256, source_sha256,
                  canonical_generation, total_records, completed_records,
                  dimensions, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'building', ?, ?)
                """,
                (
                    epoch_id,
                    subject_id,
                    identity_sha256,
                    source_sha256,
                    canonical_generation,
                    total_records,
                    created_at,
                    created_at,
                ),
            )
        return {
            "epoch_id": epoch_id,
            "completed_records": 0,
            "dimensions": 0,
            "created_at": created_at,
        }

    def _mark_rebuild(self, epoch_id: str, status: str) -> None:
        with self.transaction():
            self._conn.execute(
                "UPDATE semantic_rebuilds SET status = ?, updated_at = ? WHERE epoch_id = ?",
                (status, utc_now(), epoch_id),
            )

    def _validate_staged_epoch(
        self,
        epoch_id: str,
        subject_id: str,
        snapshot: set[tuple[str, str, str]],
        dimensions: int,
    ) -> None:
        if dimensions < 1:
            raise SemanticIndexIntegrityError("staged epoch has no vector dimensions")
        rows = self._conn.execute(
            "SELECT * FROM vector_entries WHERE epoch_id = ? ORDER BY object_id",
            (epoch_id,),
        ).fetchall()
        actual = {
            (str(row["object_id"]), str(row["status_at_index"]), str(row["content_sha256"]))
            for row in rows
            if str(row["subject_id"]) == subject_id
            and int(row["dimensions"]) == dimensions
        }
        if actual != snapshot or len(rows) != len(snapshot):
            raise SemanticIndexIntegrityError(
                "staged epoch coverage, scope, digest, or dimensions are invalid"
            )

    def search(
        self,
        memory: Memory,
        subject_id: str,
        query: str,
        embedder: Embedder,
        *,
        statuses: Sequence[str] | None = None,
        limit: int = 100,
        min_similarity: float = 0.2,
    ) -> list[dict[str, Any]]:
        epoch = self.active_epoch(subject_id)
        if epoch is None:
            raise ValueError(f"no active semantic index for subject {subject_id!r}")
        verify_identity = getattr(embedder, "verify_identity", None)
        if callable(verify_identity):
            verify_identity()
        self._assert_embedder(epoch, embedder)
        query_vector = _normalize(embedder.embed_query(query))
        if len(query_vector) != int(epoch["dimensions"]):
            raise ValueError(
                f"query embedding has {len(query_vector)} dimensions; "
                f"index expects {epoch['dimensions']}"
            )
        rows = self._conn.execute(
            """
            SELECT * FROM vector_entries
            WHERE epoch_id = ? AND subject_id = ?
            ORDER BY object_id
            """,
            (epoch["epoch_id"], subject_id),
        ).fetchall()
        epoch_dimensions = int(epoch["dimensions"])
        records = memory.store.get_records(
            subject_id, [str(row["object_id"]) for row in rows]
        )
        status_filter = set(statuses or INDEXABLE_STATUSES)
        eligible: list[tuple[sqlite3.Row, dict[str, Any]]] = []
        for row in rows:
            record_id = str(row["object_id"])
            row_dimensions = int(row["dimensions"])
            if row_dimensions != epoch_dimensions:
                raise SemanticIndexIntegrityError(
                    "stored vector dimensions do not match the active epoch: "
                    f"record={record_id!r}, stored={row_dimensions}, "
                    f"epoch={epoch_dimensions}"
                )
            record = records.get(record_id)
            validation = _canonical_validation(row, record, subject_id, status_filter)
            if not validation["eligible"]:
                continue
            eligible.append((row, validation))

        similarities = _exact_similarities(
            query_vector,
            [row["vector"] for row, _ in eligible],
            epoch_dimensions,
        )
        candidates: list[dict[str, Any]] = []
        for (row, validation), similarity in zip(eligible, similarities):
            if similarity < float(min_similarity):
                continue
            candidates.append(
                {
                    "record_id": row["object_id"],
                    "similarity": float(similarity),
                    "epoch_id": epoch["epoch_id"],
                    "content_sha256": row["content_sha256"],
                    "canonical_validation": validation,
                }
            )
        candidates.sort(key=lambda item: (-item["similarity"], str(item["record_id"])))
        return [
            {**item, "semantic_rank": rank}
            for rank, item in enumerate(candidates[: max(1, int(limit))], start=1)
        ]

    def active_epoch(self, subject_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT e.* FROM vector_subjects s
            JOIN vector_epochs e ON e.epoch_id = s.active_epoch_id
            WHERE s.subject_id = ?
            """,
            (subject_id,),
        ).fetchone()
        return _epoch(row) if row else None

    def status(self, subject_id: str | None = None) -> dict[str, Any]:
        if subject_id:
            rows = self._conn.execute(
                "SELECT * FROM vector_epochs WHERE subject_id = ? ORDER BY created_at",
                (subject_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM vector_epochs ORDER BY subject_id, created_at"
            ).fetchall()
        return {
            "format": "atmem-index-status-v1",
            "index_path": self.path,
            "subjects": {
                str(row["subject_id"]): self.active_epoch(str(row["subject_id"]))
                for row in rows
                if self.active_epoch(str(row["subject_id"])) is not None
            },
            "epochs": [_epoch(row) for row in rows],
        }

    def verify(
        self,
        memory: Memory,
        subject_id: str,
        *,
        _allow_retired_entries: bool = False,
    ) -> dict[str, Any]:
        epoch = self.active_epoch(subject_id)
        if epoch is not None and not _allow_retired_entries:
            canonical_generation = memory.store.record_generation(subject_id)
            index_generation = self._index_generation(subject_id)
            cached = self._conn.execute(
                """
                SELECT report_json FROM verification_cache
                WHERE subject_id = ? AND epoch_id = ?
                  AND canonical_generation = ? AND index_generation = ?
                """,
                (
                    subject_id,
                    epoch["epoch_id"],
                    canonical_generation,
                    index_generation,
                ),
            ).fetchone()
            if cached is not None:
                return json.loads(str(cached["report_json"]))
        failures: list[str] = []
        orphaned: list[str] = []
        tombstoned: list[str] = []
        stale: list[str] = []
        cross_subject: list[str] = []
        coverage_gaps: list[str] = []
        retired_entries: list[str] = []
        if epoch is None:
            failures.append("no active epoch")
            entries: list[sqlite3.Row] = []
        else:
            entries = self._conn.execute(
                "SELECT * FROM vector_entries WHERE epoch_id = ? ORDER BY object_id",
                (epoch["epoch_id"],),
            ).fetchall()
        records = memory.store.get_records(
            subject_id, [str(row["object_id"]) for row in entries]
        )
        indexed_ids: set[str] = set()
        for row in entries:
            record_id = str(row["object_id"])
            indexed_ids.add(record_id)
            record = records.get(record_id)
            if str(row["subject_id"]) != subject_id:
                cross_subject.append(record_id)
                continue
            if record is None:
                orphaned.append(record_id)
                continue
            if record["subject_id"] != subject_id:
                cross_subject.append(record_id)
            if record["status"] == "tombstoned":
                tombstoned.append(record_id)
            if record["status"] != "tombstoned" and sha256_hex(str(record["content"])) != row["content_sha256"]:
                stale.append(record_id)
            if epoch and int(row["dimensions"]) != int(epoch["dimensions"]):
                stale.append(record_id)
        expected = {
            str(record["id"])
            for record in memory.store.list_records(subject_id, statuses=INDEXABLE_STATUSES)
        }
        coverage_gaps = sorted(expected - indexed_ids)
        retired_rows = self._conn.execute(
            """
            SELECT v.object_id FROM vector_entries v
            JOIN vector_epochs e ON e.epoch_id = v.epoch_id
            WHERE v.subject_id = ? AND e.status = 'retired'
            ORDER BY v.object_id
            """,
            (subject_id,),
        ).fetchall()
        retired_entries = [str(row["object_id"]) for row in retired_rows]
        categories = {
            "orphaned_vectors": sorted(set(orphaned)),
            "tombstoned_vectors": sorted(set(tombstoned)),
            "stale_vectors": sorted(set(stale)),
            "cross_subject_vectors": sorted(set(cross_subject)),
            "coverage_gaps": coverage_gaps,
            "retired_epoch_vectors": sorted(set(retired_entries)),
        }
        for name, values in categories.items():
            if name == "retired_epoch_vectors" and _allow_retired_entries:
                continue
            if values:
                failures.append(f"{name}: {len(values)}")
        body = {
            "format": "atmem-index-verification-v1",
            "subject_id": subject_id,
            "index_path": self.path,
            "epoch_id": epoch["epoch_id"] if epoch else None,
            "valid": not failures,
            **categories,
            "failures": failures,
            "verified_at": utc_now(),
        }
        body["report_sha256"] = sha256_hex(canonical_json(body))
        if epoch is not None and not _allow_retired_entries:
            # Re-read both counters after verification. If either changed
            # during the scan, do not cache a report for a mixed snapshot.
            ending_canonical_generation = memory.store.record_generation(subject_id)
            ending_index_generation = self._index_generation(subject_id)
            if (
                ending_canonical_generation == canonical_generation
                and ending_index_generation == index_generation
            ):
                self._conn.execute(
                    """
                    INSERT INTO verification_cache(
                      subject_id, epoch_id, canonical_generation,
                      index_generation, report_json, report_sha256, verified_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(
                      subject_id, epoch_id, canonical_generation, index_generation
                    ) DO UPDATE SET
                      report_json = excluded.report_json,
                      report_sha256 = excluded.report_sha256,
                      verified_at = excluded.verified_at
                    """,
                    (
                        subject_id,
                        epoch["epoch_id"],
                        canonical_generation,
                        index_generation,
                        json.dumps(body, sort_keys=True, separators=(",", ":")),
                        body["report_sha256"],
                        body["verified_at"],
                    ),
                )
        return body

    def purge(self, subject_id: str, record_ids: Sequence[str]) -> dict[str, Any]:
        ids = sorted({str(value) for value in record_ids})
        if not ids:
            return {
                "status": "not_required",
                "removed_entries": 0,
                "record_ids": [],
                "epochs_touched": [],
                "verified_absent": True,
            }
        placeholders = ",".join("?" for _ in ids)
        rows = self._conn.execute(
            f"""
            SELECT DISTINCT epoch_id FROM vector_entries
            WHERE subject_id = ? AND object_id IN ({placeholders})
            ORDER BY epoch_id
            """,
            (subject_id, *ids),
        ).fetchall()
        epochs = [str(row["epoch_id"]) for row in rows]
        with self.transaction():
            cursor = self._conn.execute(
                f"""
                DELETE FROM vector_entries
                WHERE subject_id = ? AND object_id IN ({placeholders})
                """,
                (subject_id, *ids),
            )
            if epochs:
                epoch_placeholders = ",".join("?" for _ in epochs)
                self._conn.execute(
                    f"""
                    UPDATE vector_epochs SET dirty = 1,
                      entry_count = (
                        SELECT COUNT(*) FROM vector_entries
                        WHERE vector_entries.epoch_id = vector_epochs.epoch_id
                      )
                    WHERE epoch_id IN ({epoch_placeholders})
                    """,
                    epochs,
                )
        remaining = self._conn.execute(
            f"""
            SELECT COUNT(*) AS count FROM vector_entries
            WHERE subject_id = ? AND object_id IN ({placeholders})
            """,
            (subject_id, *ids),
        ).fetchone()
        result = {
            "status": "verified_absent" if int(remaining["count"]) == 0 else "failed",
            "removed_entries": int(cursor.rowcount),
            "record_ids": ids,
            "epochs_touched": epochs,
            "verified_absent": int(remaining["count"]) == 0,
            "verified_at": utc_now(),
        }
        result["result_sha256"] = sha256_hex(canonical_json(result))
        return result

    def checkpoint_storage(self) -> None:
        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def _assert_embedder(self, epoch: dict[str, Any], embedder: Embedder) -> None:
        current = dict(embedder.identity)
        stored = epoch["identity"]
        for key in (
            "provider",
            "model",
            "version",
            "model_digest",
            "endpoint",
            "normalization",
        ):
            if str(current.get(key)) != str(stored.get(key)):
                raise ValueError(
                    f"embedder {key} mismatch: index={stored.get(key)!r}, "
                    f"query={current.get(key)!r}"
                )

    def _index_generation(self, subject_id: str) -> int:
        row = self._conn.execute(
            "SELECT generation FROM vector_generations WHERE subject_id = ?",
            (subject_id,),
        ).fetchone()
        return int(row["generation"]) if row else 0

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS vector_epochs (
              epoch_id TEXT PRIMARY KEY,
              subject_id TEXT NOT NULL,
              format TEXT NOT NULL,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              model_version TEXT NOT NULL,
              identity_json TEXT NOT NULL,
              identity_sha256 TEXT NOT NULL,
              dimensions INTEGER NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('building', 'active', 'retired')),
              dirty INTEGER NOT NULL DEFAULT 0,
              entry_count INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              activated_at TEXT,
              retired_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_vector_epochs_subject
              ON vector_epochs(subject_id, status, created_at);

            CREATE TABLE IF NOT EXISTS semantic_rebuilds (
              epoch_id TEXT PRIMARY KEY,
              subject_id TEXT NOT NULL,
              identity_sha256 TEXT NOT NULL,
              source_sha256 TEXT NOT NULL,
              canonical_generation INTEGER NOT NULL,
              total_records INTEGER NOT NULL,
              completed_records INTEGER NOT NULL DEFAULT 0,
              dimensions INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL CHECK(status IN ('building', 'stale', 'abandoned', 'activated')),
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(epoch_id) REFERENCES vector_epochs(epoch_id)
            );

            CREATE INDEX IF NOT EXISTS idx_semantic_rebuilds_resume
              ON semantic_rebuilds(
                subject_id, identity_sha256, source_sha256,
                canonical_generation, status, created_at
              );

            CREATE TABLE IF NOT EXISTS vector_subjects (
              subject_id TEXT PRIMARY KEY,
              active_epoch_id TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(active_epoch_id) REFERENCES vector_epochs(epoch_id)
            );

            CREATE TABLE IF NOT EXISTS vector_entries (
              epoch_id TEXT NOT NULL,
              subject_id TEXT NOT NULL,
              object_type TEXT NOT NULL,
              object_id TEXT NOT NULL,
              content_sha256 TEXT NOT NULL,
              status_at_index TEXT NOT NULL,
              dimensions INTEGER NOT NULL,
              vector BLOB NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY(epoch_id, object_type, object_id),
              FOREIGN KEY(epoch_id) REFERENCES vector_epochs(epoch_id)
            );

            CREATE INDEX IF NOT EXISTS idx_vector_entries_subject
              ON vector_entries(subject_id, epoch_id, object_id);

            CREATE TABLE IF NOT EXISTS vector_generations (
              subject_id TEXT PRIMARY KEY,
              generation INTEGER NOT NULL DEFAULT 0
            );

            CREATE TRIGGER IF NOT EXISTS vector_generation_insert
            AFTER INSERT ON vector_entries BEGIN
              INSERT INTO vector_generations(subject_id, generation)
              VALUES (NEW.subject_id, 1)
              ON CONFLICT(subject_id) DO UPDATE
                SET generation = generation + 1;
            END;

            CREATE TRIGGER IF NOT EXISTS vector_generation_delete
            AFTER DELETE ON vector_entries BEGIN
              INSERT INTO vector_generations(subject_id, generation)
              VALUES (OLD.subject_id, 1)
              ON CONFLICT(subject_id) DO UPDATE
                SET generation = generation + 1;
            END;

            CREATE TRIGGER IF NOT EXISTS vector_generation_update_same_subject
            AFTER UPDATE ON vector_entries
            WHEN OLD.subject_id = NEW.subject_id BEGIN
              INSERT INTO vector_generations(subject_id, generation)
              VALUES (NEW.subject_id, 1)
              ON CONFLICT(subject_id) DO UPDATE
                SET generation = generation + 1;
            END;

            CREATE TRIGGER IF NOT EXISTS vector_generation_update_subject
            AFTER UPDATE ON vector_entries
            WHEN OLD.subject_id <> NEW.subject_id BEGIN
              INSERT INTO vector_generations(subject_id, generation)
              VALUES (OLD.subject_id, 1)
              ON CONFLICT(subject_id) DO UPDATE
                SET generation = generation + 1;
              INSERT INTO vector_generations(subject_id, generation)
              VALUES (NEW.subject_id, 1)
              ON CONFLICT(subject_id) DO UPDATE
                SET generation = generation + 1;
            END;

            CREATE TABLE IF NOT EXISTS verification_cache (
              subject_id TEXT NOT NULL,
              epoch_id TEXT NOT NULL,
              canonical_generation INTEGER NOT NULL,
              index_generation INTEGER NOT NULL,
              report_json TEXT NOT NULL,
              report_sha256 TEXT NOT NULL,
              verified_at TEXT NOT NULL,
              PRIMARY KEY(
                subject_id, epoch_id, canonical_generation, index_generation
              ),
              FOREIGN KEY(epoch_id) REFERENCES vector_epochs(epoch_id)
            );
            """
        )
        self._conn.execute(
            """
            INSERT INTO schema_meta(key, value) VALUES ('semantic_index_schema', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (INDEX_SCHEMA_VERSION,),
        )


def _canonical_validation(
    row: sqlite3.Row,
    record: dict[str, Any] | None,
    subject_id: str,
    statuses: set[str],
) -> dict[str, Any]:
    exists = record is not None
    subject_matched = bool(record and record.get("subject_id") == subject_id)
    status = str(record.get("status")) if record else None
    status_eligible = status in statuses if status is not None else False
    digest_matched = bool(
        record
        and status != "tombstoned"
        and sha256_hex(str(record.get("content") or "")) == row["content_sha256"]
    )
    return {
        "exists": exists,
        "subject_matched": subject_matched,
        "status": status,
        "status_eligible": status_eligible,
        "digest_matched": digest_matched,
        "eligible": exists and subject_matched and status_eligible and digest_matched,
    }


def _epoch(row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    value["dirty"] = bool(value["dirty"])
    value["identity"] = json.loads(value.pop("identity_json"))
    return value


def _record_snapshot(records: Sequence[dict[str, Any]]) -> set[tuple[str, str, str]]:
    return {
        (
            str(record["id"]),
            str(record["status"]),
            sha256_hex(str(record["content"])),
        )
        for record in records
    }


def _call_fault(
    hook: Callable[[str, dict[str, Any]], None] | None,
    phase: str,
    evidence: dict[str, Any],
) -> None:
    if hook is not None:
        hook(phase, evidence)


def _pack(vector: Sequence[float]) -> bytes:
    values = array("f", [float(value) for value in vector])
    if sys.byteorder != "little":
        values.byteswap()
    return values.tobytes()


def _unpack(blob: bytes, dimensions: int) -> list[float]:
    values = array("f")
    values.frombytes(blob)
    if sys.byteorder != "little":
        values.byteswap()
    if len(values) != dimensions:
        raise ValueError("stored vector dimensions do not match its payload")
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result):
        raise ValueError("stored vector contains a non-finite value")
    return result


def _normalize(vector: Sequence[float]) -> list[float]:
    values = [float(value) for value in vector]
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("embedding must be a finite, non-empty vector")
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 0:
        raise ValueError("embedding vector has zero magnitude")
    return [value / norm for value in values]


def _exact_similarities(
    query_vector: Sequence[float],
    blobs: Sequence[bytes],
    dimensions: int,
) -> list[float]:
    """Compute exact dot products, using an optional vectorized block at scale."""
    if len(blobs) >= 256:
        try:
            import numpy as np
        except ImportError:
            pass
        else:
            matrix = np.frombuffer(b"".join(blobs), dtype="<f4")
            expected = len(blobs) * dimensions
            if int(matrix.size) != expected:
                raise SemanticIndexIntegrityError(
                    "stored vector payload length does not match the active epoch"
                )
            matrix = matrix.reshape((len(blobs), dimensions))
            if not bool(np.isfinite(matrix).all()):
                raise SemanticIndexIntegrityError(
                    "stored vector contains a non-finite value"
                )
            query = np.asarray(query_vector, dtype=np.float64)
            return [float(value) for value in matrix.dot(query)]
    return [
        sum(
            left * right
            for left, right in zip(query_vector, _unpack(blob, dimensions))
        )
        for blob in blobs
    ]
