"""Opaque SQLite container whose semantic fields exist only inside ciphertext."""

from __future__ import annotations

import base64
from hashlib import sha256
import hmac
import os
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable
import uuid

from atmem.core.canonical import canonical_json
from atmem.evidence.crypto import open_json, seal_json, unwrap_data_key, wrap_data_key
from atmem.evidence.models import CaptureMode
from atmem.store.sqlite import utc_now


SCHEMA_VERSION = 2


def _content_descriptor(value: Any) -> dict[str, Any]:
    encoded = canonical_json(value).encode()
    return {
        "captured": False,
        "bytes": len(encoded),
        "sha256": sha256(encoded).hexdigest(),
        "value_type": type(value).__name__,
    }


_CONTENT_FIELDS = {
    "text",
    "content",
    "content_base64",
    "data",
    "data_base64",
    "bytes_base64",
    "prompt",
    "prompt_text",
    "system_prompt",
    "history_messages",
    "messages",
    "assistant_texts",
    "context",
    "params",
    "result",
    "error",
    "url",
    "path",
    "command",
}


def metadata_projection(value: Any, *, field: str | None = None) -> Any:
    """Remove exact content while retaining an encrypted structural descriptor."""

    if field in _CONTENT_FIELDS:
        return _content_descriptor(value)
    if isinstance(value, dict):
        return {str(key): metadata_projection(item, field=str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [metadata_projection(item) for item in value]
    return value


class EncryptedEvidenceStore:
    def __init__(self, path: str | Path, key: bytes) -> None:
        self.path = Path(path).expanduser().resolve(strict=False)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.key = key
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS vault_meta(
                format_version INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sealed_objects(
                object_id TEXT PRIMARY KEY,
                sequence INTEGER NOT NULL UNIQUE CHECK(sequence > 0),
                nonce BLOB NOT NULL CHECK(length(nonce) = 12),
                ciphertext BLOB NOT NULL,
                slot_id TEXT
            );
            CREATE TABLE IF NOT EXISTS key_slots(
                slot_id TEXT PRIMARY KEY,
                lookup_tag BLOB NOT NULL UNIQUE,
                wrap_nonce BLOB NOT NULL CHECK(length(wrap_nonce) = 12),
                wrapped_key BLOB NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS key_slot_wrap_nonce
            ON key_slots(wrap_nonce);
            """
        )
        row = self._conn.execute("SELECT format_version FROM vault_meta").fetchone()
        if row is None:
            self._conn.execute("INSERT INTO vault_meta VALUES(?)", (SCHEMA_VERSION,))
        elif int(row["format_version"]) == 1:
            columns = {str(value[1]) for value in self._conn.execute("PRAGMA table_info(sealed_objects)")}
            if "slot_id" not in columns:
                self._conn.execute("ALTER TABLE sealed_objects ADD COLUMN slot_id TEXT")
            self._conn.execute("UPDATE vault_meta SET format_version = ?", (SCHEMA_VERSION,))
        elif int(row["format_version"]) != SCHEMA_VERSION:
            raise RuntimeError("unsupported encrypted evidence vault version")
        self._conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS sealed_object_nonce_per_slot ON sealed_objects(slot_id, nonce)"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "EncryptedEvidenceStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _lookup_tag(self, partition_id: str) -> bytes:
        return hmac.digest(self.key, b"atmem-partition-v1\0" + partition_id.encode(), "sha256")

    def _data_key(self, partition_id: str) -> tuple[str, bytes]:
        lookup = self._lookup_tag(partition_id)
        row = self._conn.execute(
            "SELECT slot_id,wrap_nonce,wrapped_key FROM key_slots WHERE lookup_tag = ?",
            (lookup,),
        ).fetchone()
        if row is not None:
            slot_id = str(row["slot_id"])
            return slot_id, unwrap_data_key(
                self.key, slot_id, bytes(row["wrap_nonce"]), bytes(row["wrapped_key"])
            )
        slot_id = f"slot_{uuid.uuid4().hex}"
        data_key = os.urandom(32)
        nonce, wrapped = wrap_data_key(self.key, slot_id, data_key)
        self._conn.execute(
            "INSERT INTO key_slots(slot_id,lookup_tag,wrap_nonce,wrapped_key) VALUES(?,?,?,?)",
            (slot_id, lookup, nonce, wrapped),
        )
        return slot_id, data_key

    def append(self, document: dict[str, Any], *, partition_id: str = "vault") -> dict[str, Any]:
        object_id = f"obj_{uuid.uuid4().hex}"
        with self._conn:
            row = self._conn.execute("SELECT COALESCE(MAX(sequence), 0) AS value FROM sealed_objects").fetchone()
            sequence = int(row["value"]) + 1
            sealed = {
                "format": "atmem-evidence-document-v1",
                "object_id": object_id,
                "sequence": sequence,
                "recorded_at": utc_now(),
                **document,
            }
            slot_id, data_key = self._data_key(partition_id)
            nonce, ciphertext = seal_json(data_key, object_id, sealed)
            self._conn.execute(
                "INSERT INTO sealed_objects(object_id,sequence,nonce,ciphertext,slot_id) VALUES(?,?,?,?,?)",
                (object_id, sequence, nonce, ciphertext, slot_id),
            )
        return {"object_id": object_id, "sequence": sequence}

    def documents(self) -> Iterable[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT o.object_id,o.nonce,o.ciphertext,o.slot_id,
                      s.wrap_nonce,s.wrapped_key
                 FROM sealed_objects o LEFT JOIN key_slots s ON s.slot_id=o.slot_id
                 ORDER BY o.sequence"""
        ).fetchall()
        for row in rows:
            data_key = self.key if row["slot_id"] is None else unwrap_data_key(
                self.key, str(row["slot_id"]), bytes(row["wrap_nonce"]), bytes(row["wrapped_key"])
            )
            yield open_json(
                data_key,
                str(row["object_id"]),
                bytes(row["nonce"]),
                bytes(row["ciphertext"]),
            )

    def capture_mode(self) -> CaptureMode:
        mode = CaptureMode.FULL
        for document in self.documents():
            if document.get("record_type") == "settings":
                mode = CaptureMode(str(document.get("capture_mode") or CaptureMode.FULL.value))
        return mode

    def set_capture_mode(self, mode: CaptureMode, *, actor: str) -> dict[str, Any]:
        return self.append(
            {
                "record_type": "settings",
                "capture_mode": mode.value,
                "actor": actor,
            }, partition_id="settings"
        )

    def capture(self, envelope: dict[str, Any]) -> dict[str, Any] | None:
        mode = self.capture_mode()
        if mode is CaptureMode.OFF:
            return None
        event_id = str(envelope.get("event_id") or "")
        producer_instance_id = str(envelope.get("producer_instance_id") or "")
        producer_epoch = str(envelope.get("producer_epoch") or "")
        if event_id and producer_instance_id and producer_epoch:
            for existing in self.documents():
                existing_envelope = existing.get("envelope") or {}
                if (
                    existing.get("record_type") == "evidence"
                    and existing_envelope.get("event_id") == event_id
                    and existing_envelope.get("producer_instance_id") == producer_instance_id
                    and existing_envelope.get("producer_epoch") == producer_epoch
                ):
                    return {
                        "object_id": str(existing["object_id"]),
                        "sequence": int(existing["sequence"]),
                        "replayed": True,
                    }
        value = envelope if mode is CaptureMode.FULL else metadata_projection(envelope)
        partition = str(envelope.get("run_id") or envelope.get("event_id") or "unscoped")
        return self.append(
            {
                "record_type": "evidence",
                "capture_mode": mode.value,
                "reconstructable": mode is CaptureMode.FULL,
                "envelope": value,
            }, partition_id=f"run:{partition}"
        )

    def access_event(self, value: dict[str, Any]) -> dict[str, Any]:
        target = value.get("target_scope") or {}
        partition = str(target.get("run_id") or "access")
        return self.append({"record_type": "access", **value}, partition_id=f"audit:{partition}")

    def key_slot_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM key_slots").fetchone()[0])

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM sealed_objects").fetchone()[0])

    def raw_blobs(self) -> list[bytes]:
        return [bytes(row[0]) for row in self._conn.execute("SELECT ciphertext FROM sealed_objects")]

    def delete_run(self, run_id: str) -> dict[str, int]:
        object_ids: list[str] = []
        for document in self.documents():
            if document.get("record_type") != "evidence":
                continue
            envelope = document.get("envelope") or {}
            if str(envelope.get("run_id") or "") == run_id:
                object_ids.append(str(document["object_id"]))
        with self._conn:
            for object_id in object_ids:
                self._conn.execute("DELETE FROM sealed_objects WHERE object_id = ?", (object_id,))
            removed_slots = self._conn.execute(
                "DELETE FROM key_slots WHERE slot_id NOT IN (SELECT slot_id FROM sealed_objects WHERE slot_id IS NOT NULL)"
            ).rowcount
        return {"objects": len(object_ids), "key_slots": int(removed_slots)}

    @staticmethod
    def _partition_for_document(document: dict[str, Any]) -> str:
        record_type = str(document.get("record_type") or "")
        if record_type == "evidence":
            envelope = document.get("envelope") or {}
            return f"run:{envelope.get('run_id') or envelope.get('event_id') or 'unscoped'}"
        if record_type == "access":
            target = document.get("target_scope") or {}
            return f"audit:{target.get('run_id') or 'access'}"
        if record_type == "settings":
            return "settings"
        return "vault"

    def rotate_key(self, new_key: bytes) -> dict[str, int]:
        """Rewrap data keys and re-encrypt pre-envelope-key objects atomically."""

        if len(new_key) != 32:
            raise ValueError("evidence key must contain exactly 256 bits")
        slots = self._conn.execute(
            "SELECT slot_id,wrap_nonce,wrapped_key FROM key_slots ORDER BY slot_id"
        ).fetchall()
        legacy = self._conn.execute(
            "SELECT object_id,nonce,ciphertext FROM sealed_objects WHERE slot_id IS NULL"
        ).fetchall()
        with self._conn:
            for row in slots:
                slot_id = str(row["slot_id"])
                data_key = unwrap_data_key(
                    self.key, slot_id, bytes(row["wrap_nonce"]), bytes(row["wrapped_key"])
                )
                object_row = self._conn.execute(
                    "SELECT object_id,nonce,ciphertext FROM sealed_objects WHERE slot_id=? ORDER BY sequence LIMIT 1",
                    (slot_id,),
                ).fetchone()
                if object_row is None:
                    continue
                document = open_json(
                    data_key, str(object_row["object_id"]), bytes(object_row["nonce"]),
                    bytes(object_row["ciphertext"]),
                )
                partition = self._partition_for_document(document)
                new_lookup = hmac.digest(
                    new_key, b"atmem-partition-v1\0" + partition.encode(), "sha256"
                )
                nonce, wrapped = wrap_data_key(new_key, slot_id, data_key)
                self._conn.execute(
                    "UPDATE key_slots SET lookup_tag=?,wrap_nonce=?,wrapped_key=? WHERE slot_id=?",
                    (new_lookup, nonce, wrapped, slot_id),
                )
            for row in legacy:
                object_id = str(row["object_id"])
                document = open_json(self.key, object_id, bytes(row["nonce"]), bytes(row["ciphertext"]))
                nonce, ciphertext = seal_json(new_key, object_id, document)
                self._conn.execute(
                    "UPDATE sealed_objects SET nonce=?,ciphertext=? WHERE object_id=?",
                    (nonce, ciphertext, object_id),
                )
        self.key = new_key
        return {"rewrapped_slots": len(slots), "reencrypted_legacy_objects": len(legacy)}
