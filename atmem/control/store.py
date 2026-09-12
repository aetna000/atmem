from __future__ import annotations

from contextlib import contextmanager
import base64
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterator
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from atmem.control.evidence import ZERO_SHA256, evidence_entry_sha256
from atmem.core.canonical import canonical_json, sha256_hex
from atmem.core.storage import HouseholdLock, HouseholdPolicy, connect, row_factory_for
from atmem.execution.events import CoverageGap
from atmem.store.sqlite import utc_now


SCHEMA_VERSION = 6
ENCRYPTED_CONTROL_MAGIC = b"ATMEM-CONTROL-DB-V1\n"


def _portable_sqlite_image(value: bytes) -> bytes:
    """Force a serialized image out of WAL header mode for in-memory restore."""

    if len(value) >= 20 and value.startswith(b"SQLite format 3\x00"):
        mutable = bytearray(value)
        mutable[18] = 1
        mutable[19] = 1
        return bytes(mutable)
    return value


def reencrypt_control_container(path: str | Path, old_key: bytes, new_key: bytes) -> bool:
    """Atomically re-encrypt an application control container without plaintext disk."""

    target = Path(path)
    if not target.is_file():
        return False
    raw = target.read_bytes()
    if not raw.startswith(ENCRYPTED_CONTROL_MAGIC):
        raise RuntimeError("control database must be migrated before key rotation")
    nonce = raw[len(ENCRYPTED_CONTROL_MAGIC):len(ENCRYPTED_CONTROL_MAGIC) + 12]
    ciphertext = raw[len(ENCRYPTED_CONTROL_MAGIC) + 12:]
    try:
        AESGCM(new_key).decrypt(nonce, ciphertext, ENCRYPTED_CONTROL_MAGIC)
        return False
    except Exception:
        serialized = AESGCM(old_key).decrypt(nonce, ciphertext, ENCRYPTED_CONTROL_MAGIC)
    new_nonce = os.urandom(12)
    sealed = AESGCM(new_key).encrypt(new_nonce, serialized, ENCRYPTED_CONTROL_MAGIC)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.rotate")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(ENCRYPTED_CONTROL_MAGIC + new_nonce + sealed)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return True


class _PersistingConnection(sqlite3.Connection):
    persist_callback: Any = None

    def commit(self) -> None:
        super().commit()
        if self.persist_callback is not None:
            self.persist_callback()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        result = super().__exit__(exc_type, exc, traceback)
        if exc_type is None and self.persist_callback is not None:
            self.persist_callback()
        return result


class ControlStore:
    """Separate memory control plane evidence store; never part of live agent recall."""

    def __init__(
        self, path: str | Path, *, policy: HouseholdPolicy | None = None,
        encryption_key: bytes | None = None,
    ) -> None:
        self.path = str(Path(path).expanduser().resolve())
        self.policy = policy or HouseholdPolicy.load(path)
        self._household_lock = HouseholdLock(self.policy).acquire()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        raw = Path(self.path).read_bytes() if Path(self.path).is_file() else b""
        if encryption_key is None and raw.startswith(ENCRYPTED_CONTROL_MAGIC):
            inferred = Path(self.path).parent.parent / ".evidence-keys" / f"{Path(self.path).parent.name}.key"
            from atmem.evidence.crypto import load_existing_key

            encryption_key = load_existing_key(inferred)
        self._encryption_key = encryption_key
        try:
            if self._encryption_key is None:
                self._conn = connect(self.path, policy=self.policy)
            else:
                if len(self._encryption_key) != 32:
                    raise ValueError("encrypted control storage requires a 256-bit key")
                self._conn = sqlite3.connect(":memory:", factory=_PersistingConnection)
                if raw.startswith(ENCRYPTED_CONTROL_MAGIC):
                    nonce = raw[len(ENCRYPTED_CONTROL_MAGIC):len(ENCRYPTED_CONTROL_MAGIC) + 12]
                    ciphertext = raw[len(ENCRYPTED_CONTROL_MAGIC) + 12:]
                    serialized = AESGCM(self._encryption_key).decrypt(
                        nonce, ciphertext, ENCRYPTED_CONTROL_MAGIC
                    )
                    self._conn.deserialize(_portable_sqlite_image(serialized))
                elif raw:
                    source = connect(self.path, policy=self.policy)
                    try:
                        source.backup(self._conn)
                    finally:
                        source.close()
        except Exception:
            self._household_lock.close()
            raise
        self._conn.row_factory = row_factory_for(self.policy)
        self._conn.execute("PRAGMA foreign_keys = ON")
        if self._encryption_key is None:
            self._conn.execute("PRAGMA journal_mode = WAL")
        else:
            self._conn.execute("PRAGMA journal_mode = MEMORY")
        self._init_schema()
        if self._encryption_key is not None:
            self._conn.persist_callback = self._persist_encrypted
            self._persist_encrypted()

    def _persist_encrypted(self) -> None:
        if self._encryption_key is None:
            return
        serialized = _portable_sqlite_image(self._conn.serialize())
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._encryption_key).encrypt(
            nonce, serialized, ENCRYPTED_CONTROL_MAGIC
        )
        target = Path(self.path)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(ENCRYPTED_CONTROL_MAGIC + nonce + ciphertext)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            for suffix in ("-wal", "-shm", "-journal"):
                Path(self.path + suffix).unlink(missing_ok=True)
        finally:
            temporary.unlink(missing_ok=True)

    def close(self) -> None:
        try:
            if self._encryption_key is not None:
                self._persist_encrypted()
            self._conn.close()
        finally:
            self._household_lock.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._conn:
            yield

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS migrations (
                migration_id TEXT PRIMARY KEY,
                host TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                content TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                fact_key TEXT,
                confidence REAL NOT NULL,
                source_type TEXT NOT NULL,
                trust_tier TEXT NOT NULL,
                source_message_sha256 TEXT NOT NULL,
                source_session_id TEXT,
                status TEXT NOT NULL CHECK(status IN ('candidate','approved','rejected')),
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                UNIQUE(migration_id, content_sha256)
            );
            CREATE TABLE IF NOT EXISTS turns (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                session_id TEXT,
                host_run_id TEXT,
                query_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS previews (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                turn_id TEXT NOT NULL REFERENCES turns(id),
                candidate_ids_json TEXT NOT NULL,
                context_text TEXT NOT NULL,
                context_sha256 TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL,
                context_chars INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS exposures (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                turn_id TEXT NOT NULL REFERENCES turns(id),
                preview_id TEXT NOT NULL REFERENCES previews(id),
                session_id TEXT,
                mode TEXT NOT NULL CHECK(mode = 'active'),
                requested_at TEXT NOT NULL,
                shown INTEGER,
                shown_at TEXT
            );
            CREATE TABLE IF NOT EXISTS transitions (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                revision INTEGER NOT NULL,
                old_mode TEXT NOT NULL,
                new_mode TEXT NOT NULL,
                actor TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(migration_id, revision)
            );
            CREATE TABLE IF NOT EXISTS host_snapshots (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                host TEXT NOT NULL,
                config_path TEXT,
                config_sha256 TEXT,
                backup_path TEXT,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS comparisons (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                status TEXT NOT NULL,
                registration_sha256 TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                evidence_label TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        row = self._conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            with self._conn:
                self._ensure_multiagent_schema()
                self._create_evidence_schema()
                self._create_delegated_schema()
                self._create_execution_schema()
                self._conn.execute(
                    "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
            return
        try:
            version = int(row["value"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"unsupported migration database schema: {row['value']}"
            ) from exc
        if version > SCHEMA_VERSION or version < 1:
            raise ValueError(f"unsupported migration database schema: {version}")
        if version < SCHEMA_VERSION:
            with self._conn:
                self._ensure_multiagent_schema()
                self._create_evidence_schema()
                self._create_delegated_schema()
                self._create_execution_schema()
                self._conn.execute(
                    "UPDATE schema_meta SET value = ? WHERE key = 'schema_version'",
                    (str(SCHEMA_VERSION),),
                )
            return
        self._ensure_multiagent_schema()
        self._create_evidence_schema()
        self._create_delegated_schema()
        self._create_execution_schema()

    def _create_execution_schema(self) -> None:
        """Allocate M0 delivery/checkpoint state in the control-store registry."""
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS execution_deliveries (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                producer_instance_id TEXT NOT NULL,
                producer_epoch TEXT NOT NULL,
                producer_sequence INTEGER NOT NULL CHECK(producer_sequence > 0),
                event_id TEXT NOT NULL,
                body_sha256 TEXT NOT NULL,
                evidence_id TEXT NOT NULL REFERENCES evidence(id),
                subject_id TEXT,
                execution_id TEXT,
                run_id TEXT,
                received_at TEXT NOT NULL,
                UNIQUE(migration_id, producer_instance_id, producer_epoch, producer_sequence),
                UNIQUE(migration_id, event_id)
            );
            CREATE TABLE IF NOT EXISTS execution_delivery_conflicts (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                producer_instance_id TEXT NOT NULL,
                producer_epoch TEXT NOT NULL,
                producer_sequence INTEGER NOT NULL,
                event_id TEXT NOT NULL,
                accepted_body_sha256 TEXT NOT NULL,
                conflicting_body_sha256 TEXT NOT NULL,
                received_at TEXT NOT NULL,
                UNIQUE(migration_id, producer_instance_id, producer_epoch,
                       producer_sequence, conflicting_body_sha256)
            );
            CREATE TABLE IF NOT EXISTS execution_coverage_gaps (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                producer_instance_id TEXT NOT NULL,
                producer_epoch TEXT NOT NULL,
                reason TEXT NOT NULL,
                first_sequence INTEGER,
                last_sequence INTEGER,
                detail TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        columns = {
            str(row["name"])
            for row in self._conn.execute("PRAGMA table_info(execution_deliveries)").fetchall()
        }
        for name in ("subject_id", "execution_id", "run_id"):
            if name not in columns:
                self._conn.execute(f"ALTER TABLE execution_deliveries ADD COLUMN {name} TEXT")
        self._conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS execution_deliveries_migration_received
            ON execution_deliveries(migration_id, received_at);
            CREATE INDEX IF NOT EXISTS execution_deliveries_scope_execution
            ON execution_deliveries(migration_id, subject_id, execution_id,
                                    producer_sequence, received_at);
            CREATE INDEX IF NOT EXISTS execution_deliveries_scope_run
            ON execution_deliveries(migration_id, subject_id, run_id,
                                    producer_sequence, received_at);
            """
        )

    def _ensure_multiagent_schema(self) -> None:
        candidate_columns = {
            str(row["name"])
            for row in self._conn.execute("PRAGMA table_info(candidates)").fetchall()
        }
        if "subject_id" not in candidate_columns:
            self._conn.executescript(
                """
                ALTER TABLE candidates RENAME TO candidates_single_scope;
                CREATE TABLE candidates (
                    id TEXT PRIMARY KEY,
                    migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                    subject_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    fact_key TEXT,
                    confidence REAL NOT NULL,
                    source_type TEXT NOT NULL,
                    trust_tier TEXT NOT NULL,
                    source_message_sha256 TEXT NOT NULL,
                    source_session_id TEXT,
                    status TEXT NOT NULL CHECK(status IN ('candidate','approved','rejected')),
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    UNIQUE(migration_id, subject_id, content_sha256)
                );
                INSERT INTO candidates(
                    id, migration_id, subject_id, content, content_sha256, fact_key,
                    confidence, source_type, trust_tier, source_message_sha256,
                    source_session_id, status, created_at, reviewed_at
                )
                SELECT c.id, c.migration_id, m.subject_id, c.content, c.content_sha256,
                       c.fact_key, c.confidence, c.source_type, c.trust_tier,
                       c.source_message_sha256, c.source_session_id, c.status,
                       c.created_at, c.reviewed_at
                FROM candidates_single_scope c
                JOIN migrations m ON m.migration_id = c.migration_id;
                DROP TABLE candidates_single_scope;
                """
            )
        turn_columns = {
            str(row["name"])
            for row in self._conn.execute("PRAGMA table_info(turns)").fetchall()
        }
        if "subject_id" not in turn_columns:
            self._conn.execute("ALTER TABLE turns ADD COLUMN subject_id TEXT")
            self._conn.execute(
                """UPDATE turns SET subject_id = (
                    SELECT subject_id FROM migrations
                    WHERE migrations.migration_id = turns.migration_id
                ) WHERE subject_id IS NULL"""
            )
        if "agent_id" not in turn_columns:
            self._conn.execute("ALTER TABLE turns ADD COLUMN agent_id TEXT")

    def _create_evidence_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                kind TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK(sequence > 0),
                created_at TEXT NOT NULL,
                body_json TEXT NOT NULL,
                body_sha256 TEXT NOT NULL,
                prev_sha256 TEXT NOT NULL,
                entry_sha256 TEXT NOT NULL,
                UNIQUE(migration_id, kind, sequence)
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS evidence_migration_kind_created
            ON evidence(migration_id, kind, created_at, sequence)
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attention_acknowledgements (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                run_id TEXT NOT NULL,
                attention_code TEXT NOT NULL,
                attention_sha256 TEXT NOT NULL,
                actor TEXT NOT NULL,
                point_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(migration_id, run_id, attention_code, attention_sha256)
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS attention_ack_migration_run
            ON attention_acknowledgements(migration_id, run_id, created_at)
            """
        )

    def _create_delegated_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS delegated_context_acceptances (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                envelope_sha256 TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                provider_version TEXT NOT NULL,
                provider_instance_id TEXT NOT NULL,
                key_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                turn_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                decision TEXT NOT NULL CHECK(decision IN ('inject','withhold')),
                receipt_id TEXT NOT NULL,
                receipt_contract_id TEXT NOT NULL,
                receipt_sha256 TEXT NOT NULL,
                context_sha256 TEXT,
                context_byte_length INTEGER NOT NULL,
                nonce_sha256 TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                provider_created_at TEXT NOT NULL,
                provider_expires_at TEXT NOT NULL,
                withhold_reason_json TEXT,
                accepted_at TEXT NOT NULL,
                UNIQUE(migration_id, run_id, turn_id, session_id, agent_id, user_id, workspace_id),
                UNIQUE(provider_id, provider_instance_id, nonce_sha256),
                UNIQUE(provider_id, provider_instance_id, idempotency_key)
            );
            CREATE INDEX IF NOT EXISTS delegated_acceptance_migration_time
            ON delegated_context_acceptances(migration_id, accepted_at);
            CREATE TABLE IF NOT EXISTS delegated_context_deliveries (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                acceptance_id TEXT NOT NULL REFERENCES delegated_context_acceptances(id),
                context_sha256 TEXT,
                context_byte_length INTEGER NOT NULL,
                requested_at TEXT NOT NULL,
                shown INTEGER,
                shown_at TEXT,
                failure_code TEXT,
                UNIQUE(acceptance_id)
            );
            CREATE INDEX IF NOT EXISTS delegated_delivery_migration_time
            ON delegated_context_deliveries(migration_id, requested_at);
            CREATE TABLE IF NOT EXISTS delegated_turn_reservations (
                id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL REFERENCES migrations(migration_id),
                run_id TEXT NOT NULL,
                turn_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                disposition TEXT NOT NULL CHECK(disposition IN ('accepted','provider_failure','native_fallback')),
                envelope_sha256 TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(migration_id, run_id, turn_id, session_id, agent_id, user_id, workspace_id)
            );
            """
        )

    def create_migration(self, migration_id: str, host: str, subject_id: str) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO migrations(migration_id, host, subject_id, created_at)
            VALUES(?, ?, ?, ?)
            """,
            (migration_id, host, subject_id, utc_now()),
        )
        self._conn.commit()

    def append_evidence(
        self,
        migration_id: str,
        *,
        kind: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Append one canonical body to a migration- and kind-scoped chain."""

        if not kind.strip():
            raise ValueError("evidence kind is required")
        if not isinstance(body.get("format"), str) or not body["format"]:
            raise ValueError("evidence body requires a format")
        body_json = canonical_json(body)
        body_sha256 = sha256_hex(body_json)
        evidence_id = f"ev_{uuid.uuid4().hex}"
        created_at = utc_now()
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            previous = self._conn.execute(
                """
                SELECT sequence, entry_sha256 FROM evidence
                WHERE migration_id = ? AND kind = ?
                ORDER BY sequence DESC LIMIT 1
                """,
                (migration_id, kind),
            ).fetchone()
            sequence = int(previous["sequence"]) + 1 if previous else 1
            prev_sha256 = str(previous["entry_sha256"]) if previous else ZERO_SHA256
            entry_sha256 = evidence_entry_sha256(
                previous_sha256=prev_sha256,
                migration_id=migration_id,
                kind=kind,
                sequence=sequence,
                body_sha256=body_sha256,
            )
            self._conn.execute(
                """
                INSERT INTO evidence(
                    id, migration_id, kind, sequence, created_at, body_json,
                    body_sha256, prev_sha256, entry_sha256
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    migration_id,
                    kind,
                    sequence,
                    created_at,
                    body_json,
                    body_sha256,
                    prev_sha256,
                    entry_sha256,
                ),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return {
            "id": evidence_id,
            "migration_id": migration_id,
            "kind": kind,
            "sequence": sequence,
            "created_at": created_at,
            "body": body,
            "body_sha256": body_sha256,
            "prev_sha256": prev_sha256,
            "entry_sha256": entry_sha256,
        }

    def accept_execution_delivery(
        self,
        migration_id: str,
        *,
        body: dict[str, Any],
        producer_instance_id: str,
        producer_epoch: str,
        producer_sequence: int,
        event_id: str,
    ) -> dict[str, Any]:
        """Durably accept or classify one replayed producer event.

        The delivery identity is checked before the append-only evidence chain.
        Same bytes replay idempotently; different bytes at the same producer
        position are retained as an integrity finding and never replace the
        accepted event.
        """
        body_json = canonical_json(body)
        evidence_body_sha256 = sha256_hex(body_json)
        delivery_body = {key: value for key, value in body.items() if key != "received_at"}
        delivery_body_sha256 = sha256_hex(canonical_json(delivery_body))
        key = (migration_id, producer_instance_id, producer_epoch, producer_sequence)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            existing = self._conn.execute(
                """SELECT * FROM execution_deliveries
                   WHERE migration_id = ? AND (
                     (producer_instance_id = ? AND producer_epoch = ? AND producer_sequence = ?)
                     OR event_id = ?
                   ) ORDER BY producer_sequence LIMIT 1""",
                (*key, event_id),
            ).fetchone()
            if existing is not None:
                same_position = (
                    existing["producer_instance_id"] == producer_instance_id
                    and existing["producer_epoch"] == producer_epoch
                    and int(existing["producer_sequence"]) == producer_sequence
                )
                decision = (
                    "replayed"
                    if same_position and existing["body_sha256"] == delivery_body_sha256
                    else "conflict"
                )
                if decision == "conflict":
                    self._conn.execute(
                        """INSERT OR IGNORE INTO execution_delivery_conflicts(
                               id, migration_id, producer_instance_id, producer_epoch,
                               producer_sequence, event_id, accepted_body_sha256,
                               conflicting_body_sha256, received_at
                           ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            f"conflict_{uuid.uuid4().hex}", *key, event_id,
                            existing["body_sha256"], delivery_body_sha256, utc_now(),
                        ),
                    )
                self._conn.commit()
                return {
                    "decision": decision,
                    "durably_accepted": decision == "replayed",
                    "durably_classified": True,
                    "event_id": existing["event_id"],
                    "evidence_id": existing["evidence_id"],
                    "producer_sequence": producer_sequence,
                }

            previous = self._conn.execute(
                """SELECT sequence, entry_sha256 FROM evidence
                   WHERE migration_id = ? AND kind = 'agent_blackbox'
                   ORDER BY sequence DESC LIMIT 1""",
                (migration_id,),
            ).fetchone()
            sequence = int(previous["sequence"]) + 1 if previous else 1
            prev_sha256 = str(previous["entry_sha256"]) if previous else ZERO_SHA256
            entry_sha256 = evidence_entry_sha256(
                previous_sha256=prev_sha256,
                migration_id=migration_id,
                kind="agent_blackbox",
                sequence=sequence,
                body_sha256=evidence_body_sha256,
            )
            evidence_id = f"ev_{uuid.uuid4().hex}"
            created_at = utc_now()
            self._conn.execute(
                """INSERT INTO evidence(
                       id, migration_id, kind, sequence, created_at, body_json,
                       body_sha256, prev_sha256, entry_sha256
                   ) VALUES(?, ?, 'agent_blackbox', ?, ?, ?, ?, ?, ?)""",
                (evidence_id, migration_id, sequence, created_at, body_json,
                 evidence_body_sha256, prev_sha256, entry_sha256),
            )
            self._conn.execute(
                """INSERT INTO execution_deliveries(
                       id, migration_id, producer_instance_id, producer_epoch,
                       producer_sequence, event_id, body_sha256, evidence_id, received_at,
                       subject_id, execution_id, run_id
                   ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"delivery_{uuid.uuid4().hex}", *key, event_id,
                    delivery_body_sha256, evidence_id, created_at,
                    body.get("subject_id"), body.get("execution_id"), body.get("run_id"),
                ),
            )
            if body.get("event_type") == "capture.gap":
                payload = body.get("payload") or {}
                gap = CoverageGap(
                    reason=str(payload.get("reason") or "capture_gap"),
                    producer_instance_id=producer_instance_id,
                    producer_epoch=producer_epoch,
                    first_sequence=payload.get("first_sequence"),
                    last_sequence=payload.get("last_sequence"),
                    detail=payload.get("error_reason") or payload.get("reason"),
                )
                self._insert_execution_gap(migration_id, gap=gap, event_id=event_id)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return {
            "decision": "accepted",
            "durably_accepted": True,
            "durably_classified": True,
            "event_id": event_id,
            "evidence_id": evidence_id,
            "sequence": sequence,
            "entry_sha256": entry_sha256,
            "producer_sequence": producer_sequence,
        }

    def record_execution_gap(
        self, migration_id: str, *, producer_instance_id: str,
        producer_epoch: str, reason: str, first_sequence: int | None = None,
        last_sequence: int | None = None, detail: str | None = None,
    ) -> dict[str, Any]:
        gap = CoverageGap(
            reason=reason,
            producer_instance_id=producer_instance_id,
            producer_epoch=producer_epoch,
            first_sequence=first_sequence,
            last_sequence=last_sequence,
            detail=detail,
        )
        gap_id, created_at = self._insert_execution_gap(
            migration_id, gap=gap, event_id=uuid.uuid4().hex
        )
        self._conn.commit()
        return {"id": gap_id, "reason": gap.reason, "created_at": created_at}

    def _insert_execution_gap(
        self, migration_id: str, *, gap: CoverageGap, event_id: str
    ) -> tuple[str, str]:
        gap_id = f"gap_{sha256_hex(f'{migration_id}:{event_id}')[:32]}"
        created_at = utc_now()
        self._conn.execute(
            """INSERT OR IGNORE INTO execution_coverage_gaps(
                   id, migration_id, producer_instance_id, producer_epoch, reason,
                   first_sequence, last_sequence, detail, created_at
               ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                gap_id,
                migration_id,
                gap.producer_instance_id,
                gap.producer_epoch,
                gap.reason,
                gap.first_sequence,
                gap.last_sequence,
                gap.detail,
                created_at,
            ),
        )
        return gap_id, created_at

    def execution_delivery_state(self, migration_id: str) -> dict[str, Any]:
        deliveries = [dict(row) for row in self._conn.execute(
            "SELECT * FROM execution_deliveries WHERE migration_id = ? ORDER BY received_at, id",
            (migration_id,),
        ).fetchall()]
        conflicts = [dict(row) for row in self._conn.execute(
            "SELECT * FROM execution_delivery_conflicts WHERE migration_id = ? ORDER BY received_at, id",
            (migration_id,),
        ).fetchall()]
        gaps = [dict(row) for row in self._conn.execute(
            "SELECT * FROM execution_coverage_gaps WHERE migration_id = ? ORDER BY created_at, id",
            (migration_id,),
        ).fetchall()]
        return {"deliveries": deliveries, "conflicts": conflicts, "gaps": gaps}

    def execution_delivery_counts(self, migration_id: str) -> dict[str, int]:
        """Return dashboard counters without materializing delivery tables."""

        queries = {
            "durable_deliveries": "execution_deliveries",
            "conflicts": "execution_delivery_conflicts",
            "reported_gaps": "execution_coverage_gaps",
        }
        return {
            name: int(
                self._conn.execute(
                    f"SELECT COUNT(*) AS count FROM {table} WHERE migration_id = ?",
                    (migration_id,),
                ).fetchone()["count"]
            )
            for name, table in queries.items()
        }

    def execution_events(
        self, migration_id: str, *, subject_id: str, execution_id: str,
        limit: int = 100, offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Read one authorized first-page timeline through the M0 index."""
        bounded_limit = max(1, min(int(limit), 500))
        bounded_offset = max(0, int(offset))
        has_exact_execution = self._conn.execute(
            """SELECT 1 FROM execution_deliveries
               WHERE migration_id = ? AND subject_id = ? AND execution_id = ?
               LIMIT 1""",
            (migration_id, subject_id, execution_id),
        ).fetchone() is not None
        rows = []
        if has_exact_execution:
            rows = self._conn.execute(
                """SELECT e.* FROM execution_deliveries d
                   JOIN evidence e ON e.id = d.evidence_id
                   WHERE d.migration_id = ? AND d.subject_id = ?
                     AND d.execution_id = ?
                   ORDER BY d.producer_sequence, d.received_at, d.id
                   LIMIT ? OFFSET ?""",
                (migration_id, subject_id, execution_id, bounded_limit, bounded_offset),
            ).fetchall()
        # Pre-v6 flights have only a run ID. Keep that compatibility branch
        # separate so the normal exact-execution path stays indexable.
        if not has_exact_execution:
            rows = self._conn.execute(
                """SELECT e.* FROM execution_deliveries d
                   JOIN evidence e ON e.id = d.evidence_id
                   WHERE d.migration_id = ? AND d.subject_id = ?
                     AND d.execution_id IS NULL AND d.run_id = ?
                   ORDER BY d.producer_sequence, d.received_at, d.id
                   LIMIT ? OFFSET ?""",
                (migration_id, subject_id, execution_id, bounded_limit, bounded_offset),
            ).fetchall()
        return [{**dict(row), "body": json.loads(str(row["body_json"]))} for row in rows]

    def prune_execution_projections(self, migration_id: str, *, before: str) -> dict[str, int]:
        """Delete derived delivery indexes without rewriting signed evidence."""
        with self._conn:
            conflicts = self._conn.execute(
                "DELETE FROM execution_delivery_conflicts WHERE migration_id = ? AND received_at < ?",
                (migration_id, before),
            ).rowcount
            gaps = self._conn.execute(
                "DELETE FROM execution_coverage_gaps WHERE migration_id = ? AND created_at < ?",
                (migration_id, before),
            ).rowcount
            deliveries = self._conn.execute(
                "DELETE FROM execution_deliveries WHERE migration_id = ? AND received_at < ?",
                (migration_id, before),
            ).rowcount
        return {"deliveries": deliveries, "conflicts": conflicts, "gaps": gaps}

    def evidence_revision(self, migration_id: str, *, kind: str) -> dict[str, Any]:
        """Cheap refresh hint; never a substitute for chain verification."""
        row = self._conn.execute(
            "SELECT sequence, entry_sha256 FROM evidence WHERE migration_id = ? AND kind = ? ORDER BY sequence DESC LIMIT 1",
            (migration_id, kind),
        ).fetchone()
        ack = self._conn.execute(
            "SELECT COUNT(*) AS count FROM attention_acknowledgements WHERE migration_id = ?",
            (migration_id,),
        ).fetchone()
        return {"migration_id": migration_id, "sequence": row["sequence"] if row else 0,
                "entry_sha256": row["entry_sha256"] if row else None,
                "acknowledgements": ack["count"]}

    def list_evidence(self, migration_id: str, *, kind: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM evidence
            WHERE migration_id = ? AND kind = ?
            ORDER BY sequence
            """,
            (migration_id, kind),
        ).fetchall()
        return [
            {**dict(row), "body": json.loads(str(row["body_json"]))}
            for row in rows
        ]

    def latest_evidence(
        self, migration_id: str, *, kind: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM evidence
            WHERE migration_id = ? AND kind = ?
            ORDER BY sequence DESC LIMIT 1
            """,
            (migration_id, kind),
        ).fetchone()
        if row is None:
            return None
        return {**dict(row), "body": json.loads(str(row["body_json"]))}

    def acknowledge_attention(
        self,
        migration_id: str,
        *,
        run_id: str,
        attention_point: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        """Retain an immutable operator acknowledgement outside flight evidence."""

        code = str(attention_point.get("code") or "").strip()
        if not run_id.strip() or not code:
            raise ValueError("run ID and attention code are required")
        point_json = canonical_json(attention_point)
        attention_sha256 = sha256_hex(point_json)
        acknowledgement_id = f"ack_{uuid.uuid4().hex}"
        created_at = utc_now()
        self._conn.execute(
            """
            INSERT OR IGNORE INTO attention_acknowledgements(
                id, migration_id, run_id, attention_code, attention_sha256,
                actor, point_json, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                acknowledgement_id,
                migration_id,
                run_id,
                code,
                attention_sha256,
                actor,
                point_json,
                created_at,
            ),
        )
        self._conn.commit()
        row = self._conn.execute(
            """
            SELECT * FROM attention_acknowledgements
            WHERE migration_id = ? AND run_id = ? AND attention_code = ?
              AND attention_sha256 = ?
            """,
            (migration_id, run_id, code, attention_sha256),
        ).fetchone()
        assert row is not None
        return {**dict(row), "point": json.loads(str(row["point_json"]))}

    def list_attention_acknowledgements(
        self, migration_id: str, *, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        params: list[Any] = [migration_id]
        run_clause = ""
        if run_id is not None:
            run_clause = "AND run_id = ?"
            params.append(run_id)
        rows = self._conn.execute(
            f"""
            SELECT * FROM attention_acknowledgements
            WHERE migration_id = ? {run_clause}
            ORDER BY created_at, id
            """,
            params,
        ).fetchall()
        return [
            {**dict(row), "point": json.loads(str(row["point_json"]))}
            for row in rows
        ]

    def verify_evidence_chain(self, migration_id: str, *, kind: str) -> dict[str, Any]:
        rows = self._conn.execute(
            """
            SELECT * FROM evidence
            WHERE migration_id = ? AND kind = ?
            ORDER BY sequence
            """,
            (migration_id, kind),
        ).fetchall()
        previous = ZERO_SHA256
        errors: list[str] = []
        for expected_sequence, row in enumerate(rows, start=1):
            sequence = int(row["sequence"])
            if sequence != expected_sequence:
                errors.append(
                    f"sequence {sequence}: expected position {expected_sequence}"
                )
            body_sha256 = sha256_hex(str(row["body_json"]))
            if row["body_sha256"] != body_sha256:
                errors.append(f"sequence {sequence}: body digest mismatch")
            if row["prev_sha256"] != previous:
                errors.append(f"sequence {sequence}: previous digest mismatch")
            expected_entry = evidence_entry_sha256(
                previous_sha256=previous,
                migration_id=str(row["migration_id"]),
                kind=str(row["kind"]),
                sequence=sequence,
                body_sha256=body_sha256,
            )
            if row["entry_sha256"] != expected_entry:
                errors.append(f"sequence {sequence}: entry digest mismatch")
            previous = expected_entry
        return {
            "valid": not errors,
            "kind": kind,
            "events": len(rows),
            "head": previous,
            "errors": errors,
        }

    def insert_candidate(
        self,
        migration_id: str,
        *,
        content: str,
        fact_key: str | None,
        confidence: float,
        source_type: str,
        trust_tier: str,
        source_message_sha256: str,
        source_session_id: str | None,
        subject_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        subject_id = subject_id or str(
            self._conn.execute(
                "SELECT subject_id FROM migrations WHERE migration_id = ?", (migration_id,)
            ).fetchone()["subject_id"]
        )
        content_sha256 = sha256_hex(content)
        existing = self._conn.execute(
            "SELECT * FROM candidates WHERE migration_id = ? AND subject_id = ? AND content_sha256 = ?",
            (migration_id, subject_id, content_sha256),
        ).fetchone()
        if existing is not None:
            return dict(existing), True
        candidate_id = f"tc_{uuid.uuid4().hex}"
        now = utc_now()
        self._conn.execute(
            """
            INSERT INTO candidates(
                id, migration_id, subject_id, content, content_sha256, fact_key, confidence,
                source_type, trust_tier, source_message_sha256,
                source_session_id, status, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'candidate', ?)
            """,
            (
                candidate_id,
                migration_id,
                subject_id,
                content,
                content_sha256,
                fact_key,
                confidence,
                source_type,
                trust_tier,
                source_message_sha256,
                source_session_id,
                now,
            ),
        )
        self._conn.commit()
        return dict(
            self._conn.execute(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
        ), False

    def list_candidates(
        self, migration_id: str, *, statuses: tuple[str, ...] | None = None,
        subject_id: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM candidates WHERE migration_id = ?"
        values: list[Any] = [migration_id]
        if subject_id:
            sql += " AND subject_id = ?"
            values.append(subject_id)
        if statuses:
            sql += f" AND status IN ({','.join('?' for _ in statuses)})"
            values.extend(statuses)
        sql += " ORDER BY created_at DESC, id"
        return [
            dict(row) for row in self._conn.execute(sql, values).fetchall()
        ]

    def review_candidates(
        self, migration_id: str, candidate_ids: list[str], *, approve: bool
    ) -> list[dict[str, Any]]:
        if not candidate_ids:
            return []
        status = "approved" if approve else "rejected"
        now = utc_now()
        placeholders = ",".join("?" for _ in candidate_ids)
        with self._conn:
            rows = self._conn.execute(
                f"""
                SELECT id FROM candidates
                WHERE migration_id = ? AND id IN ({placeholders})
                """,
                [migration_id, *candidate_ids],
            ).fetchall()
            found = {str(row["id"]) for row in rows}
            missing = sorted(set(candidate_ids) - found)
            if missing:
                raise ValueError(f"unknown migration candidate(s): {', '.join(missing)}")
            self._conn.execute(
                f"""
                UPDATE candidates SET status = ?, reviewed_at = ?
                WHERE migration_id = ? AND id IN ({placeholders})
                """,
                [status, now, migration_id, *candidate_ids],
            )
        return [
            row
            for row in self.list_candidates(migration_id)
            if row["id"] in set(candidate_ids)
        ]

    def insert_turn(
        self,
        migration_id: str,
        *,
        query_sha256: str,
        session_id: str | None,
        host_run_id: str | None,
        subject_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        turn_id = f"tt_{uuid.uuid4().hex}"
        self._conn.execute(
            """
            INSERT INTO turns(id, migration_id, session_id, host_run_id, query_sha256, created_at, subject_id, agent_id)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (turn_id, migration_id, session_id, host_run_id, query_sha256, utc_now(), subject_id, agent_id),
        )
        self._conn.commit()
        return dict(
            self._conn.execute("SELECT * FROM turns WHERE id = ?", (turn_id,)).fetchone()
        )

    def insert_preview(
        self,
        migration_id: str,
        turn_id: str,
        *,
        candidate_ids: list[str],
        context_text: str,
        manifest_sha256: str,
    ) -> dict[str, Any]:
        preview_id = f"tp_{uuid.uuid4().hex}"
        self._conn.execute(
            """
            INSERT INTO previews(
                id, migration_id, turn_id, candidate_ids_json, context_text,
                context_sha256, manifest_sha256, context_chars, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                preview_id,
                migration_id,
                turn_id,
                json.dumps(candidate_ids, separators=(",", ":")),
                context_text,
                sha256_hex(context_text),
                manifest_sha256,
                len(context_text),
                utc_now(),
            ),
        )
        self._conn.commit()
        return dict(
            self._conn.execute(
                "SELECT * FROM previews WHERE id = ?", (preview_id,)
            ).fetchone()
        )

    def insert_exposure(
        self,
        migration_id: str,
        *,
        turn_id: str,
        preview_id: str,
        session_id: str | None,
        mode: str,
    ) -> dict[str, Any]:
        exposure_id = f"tx_{uuid.uuid4().hex}"
        self._conn.execute(
            """
            INSERT INTO exposures(
                id, migration_id, turn_id, preview_id, session_id, mode, requested_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exposure_id,
                migration_id,
                turn_id,
                preview_id,
                session_id,
                mode,
                utc_now(),
            ),
        )
        self._conn.commit()
        return dict(
            self._conn.execute(
                "SELECT * FROM exposures WHERE id = ?", (exposure_id,)
            ).fetchone()
        )

    def count_exposures(self, migration_id: str, *, mode: str | None = None) -> int:
        if mode is None:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM exposures WHERE migration_id = ?",
                (migration_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS n FROM exposures
                WHERE migration_id = ? AND mode = ?
                """,
                (migration_id, mode),
            ).fetchone()
        return int(row["n"])

    def count_shown_exposures(
        self, migration_id: str, *, mode: str | None = None
    ) -> int:
        if mode is None:
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS n FROM exposures
                WHERE migration_id = ? AND shown = 1
                """,
                (migration_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS n FROM exposures
                WHERE migration_id = ? AND mode = ? AND shown = 1
                """,
                (migration_id, mode),
            ).fetchone()
        return int(row["n"])

    def mark_exposure_shown(self, migration_id: str, exposure_id: str) -> bool:
        with self._conn:
            cursor = self._conn.execute(
                """
                UPDATE exposures SET shown = 1, shown_at = ?
                WHERE migration_id = ? AND id = ?
                """,
                (utc_now(), migration_id, exposure_id),
            )
            if cursor.rowcount == 1:
                return True
            delegated = self._conn.execute(
                """
                UPDATE delegated_context_deliveries SET shown = 1, shown_at = ?
                WHERE migration_id = ? AND id = ?
                """,
                (utc_now(), migration_id, exposure_id),
            )
        return delegated.rowcount == 1

    def accept_delegated_context(self, migration_id: str, result: Any) -> dict[str, Any]:
        """Atomically reserve one verified result without retaining its content."""
        binding = result.binding
        nonce_sha256 = sha256_hex(result.nonce)
        identity = (
            migration_id,
            binding.run_id,
            binding.turn_id,
            binding.session_id,
            binding.agent_id,
            binding.user_id,
            binding.workspace_id,
        )
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            existing = self._conn.execute(
                """
                SELECT * FROM delegated_context_acceptances
                WHERE migration_id = ? AND run_id = ? AND turn_id = ?
                  AND session_id = ? AND agent_id = ? AND user_id = ?
                  AND workspace_id = ?
                """,
                identity,
            ).fetchone()
            reservation = self._conn.execute(
                """
                SELECT * FROM delegated_turn_reservations
                WHERE migration_id = ? AND run_id = ? AND turn_id = ?
                  AND session_id = ? AND agent_id = ? AND user_id = ?
                  AND workspace_id = ?
                """,
                identity,
            ).fetchone()
            if existing is not None:
                if str(existing["envelope_sha256"]) != result.envelope_sha256:
                    raise ValueError("another delegated result already reserved this turn")
                self._conn.commit()
                return {**dict(existing), "idempotent": True}
            if reservation is not None:
                if reservation["disposition"] == "accepted":
                    raise ValueError("another delegated result already reserved this turn")
                raise ValueError("delegated turn was already closed")
            for column, value, label in (
                ("nonce_sha256", nonce_sha256, "nonce"),
                ("idempotency_key", result.idempotency_key, "idempotency key"),
            ):
                reused = self._conn.execute(
                    f"""
                    SELECT envelope_sha256 FROM delegated_context_acceptances
                    WHERE provider_id = ? AND provider_instance_id = ? AND {column} = ?
                    """,
                    (result.provider_id, result.provider_instance_id, value),
                ).fetchone()
                if reused is not None:
                    raise ValueError(f"delegated {label} was already used")
            acceptance_id = f"dca_{uuid.uuid4().hex}"
            accepted_at = utc_now()
            self._conn.execute(
                """
                INSERT INTO delegated_context_acceptances(
                    id, migration_id, envelope_sha256, provider_id, provider_version,
                    provider_instance_id, key_id, run_id, turn_id, session_id,
                    agent_id, user_id, workspace_id, decision, receipt_id,
                    receipt_contract_id, receipt_sha256, context_sha256,
                    context_byte_length, nonce_sha256, idempotency_key,
                    provider_created_at, provider_expires_at, withhold_reason_json,
                    accepted_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    acceptance_id, migration_id, result.envelope_sha256,
                    result.provider_id, result.provider_version,
                    result.provider_instance_id, result.key_id, binding.run_id,
                    binding.turn_id, binding.session_id, binding.agent_id,
                    binding.user_id, binding.workspace_id, result.decision,
                    result.receipt_id, result.receipt_contract_id,
                    result.receipt_sha256, result.context_sha256,
                    result.context_byte_length, nonce_sha256,
                    result.idempotency_key, result.created_at, result.expires_at,
                    canonical_json(result.withhold_reason)
                    if result.withhold_reason is not None else None,
                    accepted_at,
                ),
            )
            if reservation is None:
                self._conn.execute(
                    """
                    INSERT INTO delegated_turn_reservations(
                        id, migration_id, run_id, turn_id, session_id, agent_id,
                        user_id, workspace_id, disposition, envelope_sha256, created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        f"dtr_{uuid.uuid4().hex}", migration_id, binding.run_id,
                        binding.turn_id, binding.session_id, binding.agent_id,
                        binding.user_id, binding.workspace_id, "accepted",
                        result.envelope_sha256, accepted_at,
                    ),
                )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        row = self._conn.execute(
            "SELECT * FROM delegated_context_acceptances WHERE id = ?",
            (acceptance_id,),
        ).fetchone()
        assert row is not None
        return {**dict(row), "idempotent": False}

    def reserve_delegated_failure(
        self,
        migration_id: str,
        binding: Any,
        *,
        native_fallback: bool,
    ) -> dict[str, Any]:
        """Close a delegated turn so a late provider result cannot replace it."""
        identity = (
            migration_id, binding.run_id, binding.turn_id, binding.session_id,
            binding.agent_id, binding.user_id, binding.workspace_id,
        )
        disposition = "native_fallback" if native_fallback else "provider_failure"
        with self._conn:
            existing = self._conn.execute(
                """
                SELECT * FROM delegated_turn_reservations
                WHERE migration_id = ? AND run_id = ? AND turn_id = ?
                  AND session_id = ? AND agent_id = ? AND user_id = ?
                  AND workspace_id = ?
                """,
                identity,
            ).fetchone()
            if existing is not None:
                if existing["disposition"] != disposition:
                    raise ValueError("delegated turn was already closed differently")
                return {**dict(existing), "idempotent": True}
            reservation_id = f"dtr_{uuid.uuid4().hex}"
            self._conn.execute(
                """
                INSERT INTO delegated_turn_reservations(
                    id, migration_id, run_id, turn_id, session_id, agent_id,
                    user_id, workspace_id, disposition, envelope_sha256, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (reservation_id, *identity, disposition, None, utc_now()),
            )
        row = self._conn.execute(
            "SELECT * FROM delegated_turn_reservations WHERE id = ?",
            (reservation_id,),
        ).fetchone()
        assert row is not None
        return {**dict(row), "idempotent": False}

    def request_delegated_delivery(
        self,
        migration_id: str,
        acceptance_id: str,
        *,
        context_sha256: str | None,
        context_byte_length: int,
    ) -> dict[str, Any]:
        delivery_id = f"dcd_{uuid.uuid4().hex}"
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO delegated_context_deliveries(
                    id, migration_id, acceptance_id, context_sha256,
                    context_byte_length, requested_at
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    delivery_id, migration_id, acceptance_id, context_sha256,
                    int(context_byte_length), utc_now(),
                ),
            )
        row = self._conn.execute(
            "SELECT * FROM delegated_context_deliveries WHERE acceptance_id = ?",
            (acceptance_id,),
        ).fetchone()
        assert row is not None
        return dict(row)

    def delegated_acceptance(self, acceptance_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM delegated_context_acceptances WHERE id = ?",
            (acceptance_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def list_record_exposures(
        self, migration_id: str, record_id: str
    ) -> list[dict[str, Any]]:
        """Return previews and confirmed exposures that name one exact record."""

        rows = self._conn.execute(
            """
            SELECT
                p.id AS preview_id,
                p.candidate_ids_json,
                p.context_sha256,
                p.manifest_sha256,
                p.created_at AS preview_created_at,
                t.id AS turn_id,
                t.session_id,
                t.host_run_id,
                e.id AS exposure_id,
                e.requested_at,
                e.shown,
                e.shown_at
            FROM previews p
            JOIN turns t ON t.id = p.turn_id
            LEFT JOIN exposures e ON e.preview_id = p.id
            WHERE p.migration_id = ?
            ORDER BY p.created_at ASC, e.requested_at ASC
            """,
            (migration_id,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            value = dict(row)
            try:
                record_ids = list(json.loads(value.pop("candidate_ids_json")))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if record_id not in {str(item) for item in record_ids}:
                continue
            value["record_ids"] = record_ids
            value["shown"] = bool(value.get("shown"))
            result.append(value)
        return result

    def append_transition(
        self,
        migration_id: str,
        *,
        revision: int,
        old_mode: str,
        new_mode: str,
        actor: str,
    ) -> dict[str, Any]:
        previous = self._conn.execute(
            """
            SELECT event_hash FROM transitions
            WHERE migration_id = ? ORDER BY revision DESC LIMIT 1
            """,
            (migration_id,),
        ).fetchone()
        previous_hash = str(previous["event_hash"]) if previous else "0" * 64
        payload = {
            "migration_id": migration_id,
            "revision": revision,
            "old_mode": old_mode,
            "new_mode": new_mode,
            "actor": actor,
            "previous_hash": previous_hash,
            "created_at": utc_now(),
        }
        event_hash = sha256_hex(canonical_json(payload))
        transition_id = f"tr_{uuid.uuid4().hex}"
        self._conn.execute(
            """
            INSERT INTO transitions(
                id, migration_id, revision, old_mode, new_mode, actor,
                previous_hash, event_hash, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transition_id,
                migration_id,
                revision,
                old_mode,
                new_mode,
                actor,
                previous_hash,
                event_hash,
                payload["created_at"],
            ),
        )
        self._conn.commit()
        return {**payload, "id": transition_id, "event_hash": event_hash}

    def verify_transitions(self, migration_id: str) -> dict[str, Any]:
        rows = self._conn.execute(
            """
            SELECT * FROM transitions
            WHERE migration_id = ? ORDER BY revision, id
            """,
            (migration_id,),
        ).fetchall()
        previous = "0" * 64
        errors: list[str] = []
        for row in rows:
            payload = {
                "migration_id": row["migration_id"],
                "revision": row["revision"],
                "old_mode": row["old_mode"],
                "new_mode": row["new_mode"],
                "actor": row["actor"],
                "previous_hash": row["previous_hash"],
                "created_at": row["created_at"],
            }
            expected = sha256_hex(canonical_json(payload))
            if row["previous_hash"] != previous:
                errors.append(f"revision {row['revision']}: previous hash mismatch")
            if row["event_hash"] != expected:
                errors.append(f"revision {row['revision']}: event hash mismatch")
            previous = str(row["event_hash"])
        return {
            "valid": not errors,
            "events": len(rows),
            "head": previous,
            "errors": errors,
        }

    def add_host_snapshot(
        self,
        migration_id: str,
        *,
        host: str,
        config_path: str | None,
        config_sha256: str | None,
        backup_path: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        snapshot_id = f"ths_{uuid.uuid4().hex}"
        self._conn.execute(
            """
            INSERT INTO host_snapshots(
                id, migration_id, host, config_path, config_sha256,
                backup_path, metadata_json, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                migration_id,
                host,
                config_path,
                config_sha256,
                backup_path,
                canonical_json(metadata),
                utc_now(),
            ),
        )
        self._conn.commit()
        return dict(
            self._conn.execute(
                "SELECT * FROM host_snapshots WHERE id = ?", (snapshot_id,)
            ).fetchone()
        )

    def latest_snapshot(self, migration_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM host_snapshots
            WHERE migration_id = ? ORDER BY created_at DESC, id DESC LIMIT 1
            """,
            (migration_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def summary(self, migration_id: str) -> dict[str, Any]:
        counts = {
            row["status"]: int(row["n"])
            for row in self._conn.execute(
                """
                SELECT status, COUNT(*) AS n FROM candidates
                WHERE migration_id = ? GROUP BY status
                """,
                (migration_id,),
            ).fetchall()
        }
        turn_count = int(
            self._conn.execute(
                "SELECT COUNT(*) AS n FROM turns WHERE migration_id = ?", (migration_id,)
            ).fetchone()["n"]
        )
        preview_count = int(
            self._conn.execute(
                "SELECT COUNT(*) AS n FROM previews WHERE migration_id = ?", (migration_id,)
            ).fetchone()["n"]
        )
        return {
            "candidates": counts,
            "turns": turn_count,
            "previews": preview_count,
            "exposures": self.count_exposures(migration_id),
            "shown_exposures": self.count_shown_exposures(migration_id),
            "transition_chain": self.verify_transitions(migration_id),
        }
