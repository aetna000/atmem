"""Atomic scoped records inside AtMem's existing encrypted evidence container.

All payloads, indexes and semantic keys stay inside ciphertext. Bounded inline
records share one SQLite transaction, so no external artifact/outbox split is
needed. This is a ledger extension, not a second memory authority or database.
The service must authorize the fixed scope before opening a transaction.
An encrypted Home checkpoint anchors committed ciphertext outside the DB. Backups
must include it; external effects may run only after this context exits normally.
"""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
from typing import Any, Callable

from atmem.contracts.feedback import FeedbackScope, MAX_BYTES, identifier, json_data
from atmem.core.canonical import canonical_json
from atmem.evidence.crypto import load_existing_key
from atmem.evidence.store import EncryptedEvidenceStore


class FeedbackError(RuntimeError):
    """Content-free stable errors may safely cross the tool boundary."""

    def __init__(self, code: str):
        self.code = identifier(code)
        super().__init__(code)


def snapshot(value: Any) -> Any:
    json_data(value)
    encoded = canonical_json(value)
    if len(encoded.encode()) > MAX_BYTES:
        raise ValueError("record exceeds byte bound")
    return json.loads(encoded)


class FeedbackTransaction:
    def __init__(self, store: EncryptedEvidenceStore, scope: FeedbackScope):
        self.store, self.scope = store, scope
        self.rows: dict[tuple[str, str], dict] = {}
        for n, row in enumerate(store.documents(partition_id=scope.partition)):
            if n >= 10_000:
                raise FeedbackError("scope_record_budget_exhausted")
            if row.get("record_type") != "feedback" or row.get("scope") != scope.to_dict():
                raise FeedbackError("invalid_scope_partition")
            self.rows[(row["kind"], row["key"])] = row

    def revision(self, kind: str, key: str) -> int:
        row = self.rows.get((identifier(kind), identifier(key)))
        return row["revision"] if row else 0

    def get(self, kind: str, key: str) -> dict | None:
        row = self.rows.get((identifier(kind), identifier(key)))
        return snapshot(row["value"]) if row and not row["deleted"] else None

    def list(self, kind: str, *, limit: int = 100) -> list[dict]:
        identifier(kind)
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError("bounded list limit required")
        return [snapshot(row["value"]) for (k, _), row in sorted(self.rows.items())
                if k == kind and not row["deleted"]][:limit]

    def iter_kind(self, kind: str):
        identifier(kind)
        for (k, _), row in sorted(self.rows.items()):
            if k == kind and not row["deleted"]:
                yield snapshot(row["value"])

    def cached(self, operation: str, key: str, payload: dict) -> dict | None:
        identifier(operation)
        identifier(key)
        payload = snapshot(payload)
        identity = sha256((operation + "\0" + key).encode()).hexdigest()
        previous = self.get("idempotency", identity)
        if previous is None:
            return None
        if previous["payload_sha256"] != sha256(canonical_json(payload).encode()).hexdigest():
            raise FeedbackError("conflicting_retry")
        if previous.get("tombstone"):
            raise FeedbackError("forgotten_operation")
        return snapshot(previous["result"])

    def put(self, kind: str, key: str, value: dict, *, expected_revision: int, deleted: bool = False) -> dict:
        identifier(kind)
        identifier(key)
        if type(expected_revision) is not int or expected_revision != self.revision(kind, key):
            raise FeedbackError("stale_revision")
        if type(value) is not dict or type(deleted) is not bool:
            raise ValueError("object and boolean required")
        row = {"record_type": "feedback", "scope": self.scope.to_dict(),
               "kind": kind, "key": key, "revision": expected_revision + 1,
               "value": snapshot(value), "deleted": deleted}
        receipt = self.store.append(row, partition_id=self.scope.partition)
        self.rows[(kind, key)] = {**row, **receipt}
        return {"object_id": receipt["object_id"], "revision": row["revision"]}

    def once(self, operation: str, key: str, payload: dict, perform: Callable[[], dict]) -> dict:
        identifier(operation)
        identifier(key)
        payload = snapshot(payload)
        identity = sha256((operation + "\0" + key).encode()).hexdigest()
        payload_digest = sha256(canonical_json(payload).encode()).hexdigest()
        previous = self.cached(operation, key, payload)
        if previous is not None:
            return previous
        result = snapshot(perform())
        self.put("idempotency", identity,
                 {"payload_sha256": payload_digest, "result": result}, expected_revision=0)
        return result

    def audit(self, principal_id: str, operation: str, *, allowed: bool, detail: dict | None = None) -> None:
        # Audit keys contain no session content and their semantic meaning stays sealed.
        import uuid

        self.put("audit", "event-" + uuid.uuid4().hex,
                 {"principal_id": identifier(principal_id), "operation": identifier(operation),
                  "allowed": allowed, "detail": detail or {}}, expected_revision=0)


class FeedbackStore:
    def __init__(self, evidence):
        self.evidence = evidence

    @contextmanager
    def transaction(self, scope: FeedbackScope):
        if type(scope) is not FeedbackScope:
            raise TypeError("fixed authenticated feedback scope required")
        # Serialize with existing evidence key lock/rotation. Always reload the
        # current key; a stale service instance cannot survive application lock.
        with self.evidence.key_transition_lock():
            try:
                key = load_existing_key(self.evidence.key_path)
            except FileNotFoundError as exc:
                raise FeedbackError("evidence_locked") from exc
            from atmem.feedback.checkpoint import FeedbackCheckpoint
            checkpoint = FeedbackCheckpoint(self.evidence, scope)
            with EncryptedEvidenceStore(self.evidence.vault_path, key) as store:
                with store.atomic():
                    previous = checkpoint.verify(store)
                    yield FeedbackTransaction(store, scope)
                    current = checkpoint.fingerprint(store)
                    if current != previous:
                        store.enable_feedback_format()
                        checkpoint.write({"scope": scope.to_dict(), "state": "pending", "previous": previous, "root": current})
                if current != previous:
                    checkpoint.write({"scope": scope.to_dict(), "state": "committed", "root": current})
