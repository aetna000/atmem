"""Optional PostgreSQL canonical backend with explicit capability boundaries."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from typing import Any, Callable, Iterator

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.core.storage import BackendCapabilities, StorageUnavailable


POSTGRES_SCHEMA_VERSION = "atmem-postgres-v1"


class PostgreSQLStore:
    """Small canonical PostgreSQL adapter used through the storage protocol.

    Importing this module has no driver side effect. A connection can be
    injected for tests or `psycopg` is loaded only when an instance connects.
    """

    def __init__(self, dsn: str | None = None, *, connection: Any | None = None, connect: Callable[[str], Any] | None = None) -> None:
        if connection is not None:
            self._conn = connection
        else:
            if not dsn:
                raise ValueError("a PostgreSQL DSN or connection is required")
            if connect is None:
                try:
                    import psycopg
                except ImportError as exc:
                    raise StorageUnavailable("PostgreSQL requires the 'postgres' extra") from exc
                connect = psycopg.connect
            self._conn = connect(dsn)
        self._migrate()

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities("postgres-v1", "canonical", True, True, False, True, True, True, True)

    @contextmanager
    def transaction(self, **_kwargs: Any) -> Iterator["PostgreSQLStore"]:
        try:
            yield self
        except BaseException:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        with self._conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS atmem_records (
                  subject_id TEXT NOT NULL,
                  record_id TEXT NOT NULL,
                  generation BIGINT NOT NULL,
                  status TEXT NOT NULL,
                  value_json JSONB NOT NULL,
                  content_sha256 TEXT NOT NULL,
                  updated_at TIMESTAMPTZ NOT NULL,
                  PRIMARY KEY(subject_id, record_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS atmem_subject_generations (
                  subject_id TEXT PRIMARY KEY,
                  generation BIGINT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_atmem_records_scope ON atmem_records(subject_id,status,record_id)")
        self._conn.commit()

    def put_record(self, subject_id: str, record_id: str, value: dict[str, Any], *, expected_generation: int | None = None) -> dict[str, Any]:
        payload = canonical_json(value)
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction(), self._conn.cursor() as cursor:
            cursor.execute("SELECT generation FROM atmem_records WHERE subject_id=%s AND record_id=%s FOR UPDATE", (subject_id, record_id))
            row = cursor.fetchone()
            current = int(row[0]) if row else 0
            if expected_generation is not None and current != expected_generation:
                raise RuntimeError("canonical generation precondition failed")
            generation = current + 1
            cursor.execute(
                """INSERT INTO atmem_records(subject_id,record_id,generation,status,value_json,content_sha256,updated_at)
                   VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s)
                   ON CONFLICT(subject_id,record_id) DO UPDATE SET generation=EXCLUDED.generation,status=EXCLUDED.status,value_json=EXCLUDED.value_json,content_sha256=EXCLUDED.content_sha256,updated_at=EXCLUDED.updated_at""",
                (subject_id, record_id, generation, str(value.get("status", "active")), payload, sha256_hex(str(value.get("content", ""))), now),
            )
            cursor.execute("""INSERT INTO atmem_subject_generations(subject_id,generation) VALUES(%s,1)
                ON CONFLICT(subject_id) DO UPDATE SET generation=atmem_subject_generations.generation+1 RETURNING generation""", (subject_id,))
            subject_generation = int(cursor.fetchone()[0])
        return {"record_id": record_id, "record_generation": generation, "canonical_generation": subject_generation, "content_sha256": sha256_hex(str(value.get("content", "")))}

    def get_record(self, subject_id: str, record_id: str) -> dict[str, Any] | None:
        with self._conn.cursor() as cursor:
            cursor.execute("SELECT value_json,generation,status FROM atmem_records WHERE subject_id=%s AND record_id=%s", (subject_id, record_id))
            row = cursor.fetchone()
        if row is None:
            return None
        value = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return {**value, "id": record_id, "generation": int(row[1]), "status": str(row[2])}

    def list_records(self, subject_id: str, *, statuses: tuple[str, ...] = ("active",)) -> list[dict[str, Any]]:
        with self._conn.cursor() as cursor:
            cursor.execute("SELECT record_id,value_json,generation,status FROM atmem_records WHERE subject_id=%s AND status=ANY(%s) ORDER BY record_id", (subject_id, list(statuses)))
            rows = cursor.fetchall()
        return [{**(row[1] if isinstance(row[1], dict) else json.loads(row[1])), "id": str(row[0]), "generation": int(row[2]), "status": str(row[3])} for row in rows]

    def record_generation(self, subject_id: str) -> int:
        with self._conn.cursor() as cursor:
            cursor.execute("SELECT generation FROM atmem_subject_generations WHERE subject_id=%s", (subject_id,))
            row = cursor.fetchone()
        return int(row[0]) if row else 0

    def delete_record(self, subject_id: str, record_id: str) -> bool:
        with self.transaction(), self._conn.cursor() as cursor:
            cursor.execute("DELETE FROM atmem_records WHERE subject_id=%s AND record_id=%s", (subject_id, record_id))
            deleted = cursor.rowcount == 1
            if deleted:
                cursor.execute("""INSERT INTO atmem_subject_generations(subject_id,generation) VALUES(%s,1)
                    ON CONFLICT(subject_id) DO UPDATE SET generation=atmem_subject_generations.generation+1""", (subject_id,))
        return deleted
