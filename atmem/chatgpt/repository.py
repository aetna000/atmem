"""Firestore durability for encrypted real-engine households, with generation CAS.

Firestore stores encrypted chunks, not an alternate set of memory records.
Only committing the generation manifest makes an engine transaction durable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib
import json
import os
import secrets
import time
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore

from .config import Settings


class Conflict(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    generation: int
    payload: bytes | None
    chunks: tuple[str, ...] = ()


class Repository:
    CHUNK_BYTES = 256 * 1024

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = firestore.Client(project=settings.project, database=settings.database, credentials=AnonymousCredentials() if settings.emulator else None)
        self.root = self.client.collection(settings.collection)
        self.cipher = AESGCM(settings.derive("firestore-envelope-v1"))

    def seal(self, context: str, data: bytes) -> bytes:
        nonce = secrets.token_bytes(12)
        return b"ATMEMC1" + nonce + self.cipher.encrypt(nonce, data, context.encode())

    def open(self, context: str, data: bytes) -> bytes:
        if not data.startswith(b"ATMEMC1"):
            raise ValueError("unsupported or plaintext cloud envelope")
        return self.cipher.decrypt(data[7:19], data[19:], context.encode())

    def _doc(self, kind: str, key: str):
        return self.root.document(self.settings.opaque_id(kind, key))

    def get_control(self, kind: str, key: str) -> dict[str, Any] | None:
        doc = self._doc(kind, key).get(timeout=5, retry=None)
        if not doc.exists:
            return None
        value = json.loads(self.open(kind + ":" + key, doc.to_dict()["envelope"]))
        if value.get("expires_at", time.time() + 1) <= time.time():
            return None
        return value

    def put_control(self, kind: str, key: str, value: dict[str, Any]) -> None:
        document={"envelope": self.seal(kind + ":" + key, json.dumps(value, separators=(",", ":")).encode()),"kind":"control"}
        if "expires_at" in value:
            document["expires_at"]=datetime.fromtimestamp(value["expires_at"],timezone.utc)
        self._doc(kind, key).set(document)

    def consume_control(self, kind: str, key: str) -> dict[str, Any] | None:
        doc = self._doc(kind, key)
        @firestore.transactional
        def consume(transaction):
            row = doc.get(transaction=transaction, timeout=5, retry=None)
            if not row.exists:
                return None
            value = json.loads(self.open(kind + ":" + key, row.to_dict()["envelope"]))
            transaction.delete(doc)
            return value if value.get("expires_at", time.time() + 1) > time.time() else None
        return consume(self.client.transaction(max_attempts=3))

    def load(self, account: str) -> Snapshot:
        doc = self._doc("household", account)
        # Read the head and its chunks in one transaction: a writer may clean its
        # old generation immediately after a successful swap.
        @firestore.transactional
        def load(transaction):
            head = doc.get(transaction=transaction, timeout=5, retry=None)
            if not head.exists:
                return Snapshot(0, None)
            value = head.to_dict()
            ids = tuple(value["chunks"])
            if len(ids) > 70:
                raise ValueError("cloud snapshot exceeds chunk quota")
            pieces = []
            for chunk_id in ids:
                piece = doc.collection("chunks").document(chunk_id).get(transaction=transaction, timeout=5, retry=None)
                if not piece.exists:
                    raise RuntimeError("cloud snapshot is incomplete")
                pieces.append(piece.to_dict()["data"])
            data = b"".join(pieces)
            if len(data) > self.settings.max_snapshot_bytes + 64:
                raise ValueError("cloud snapshot exceeds byte quota")
            return Snapshot(int(value["generation"]), self.open("household:" + account, data), ids)
        return load(self.client.transaction(max_attempts=3))

    def commit(self, account: str, previous: Snapshot, payload: bytes) -> dict[str, Any]:
        if len(payload) > self.settings.max_snapshot_bytes:
            raise ValueError("snapshot_quota_exceeded")
        encrypted = self.seal("household:" + account, payload)
        doc = self._doc("household", account)
        version = secrets.token_hex(16)
        ids = []
        batch = self.client.batch()
        for index, offset in enumerate(range(0, len(encrypted), self.CHUNK_BYTES)):
            chunk_id = f"{version}_{index:04d}"
            ids.append(chunk_id)
            batch.create(doc.collection("chunks").document(chunk_id), {"data": encrypted[offset:offset+self.CHUNK_BYTES], "created_at": firestore.SERVER_TIMESTAMP})
        batch.commit(timeout=5, retry=None)
        @firestore.transactional
        def swap(transaction):
            row = doc.get(transaction=transaction, timeout=5, retry=None)
            generation = int(row.to_dict()["generation"]) if row.exists else 0
            if generation != previous.generation:
                raise Conflict("generation_conflict_retry_with_same_intent")
            transaction.set(doc, {"generation": generation + 1, "chunks": ids, "updated_at": firestore.SERVER_TIMESTAMP})
            return generation + 1
        try:
            generation = swap(self.client.transaction(max_attempts=3))
        except Conflict:
            self._delete_chunks(doc, ids)
            raise
        except Exception:
            # A lost commit response is ambiguous. Never delete possibly active
            # chunks; retry the intent and resolve through the durable manifest.
            raise
        cleaned = self._delete_chunks(doc, previous.chunks)
        return {"generation": generation, "obsolete_chunks_removed": cleaned,
                "snapshot_sha256": hashlib.sha256(encrypted).hexdigest(),
                "backup_deletion_verified": False}

    def _delete_chunks(self, doc, ids) -> bool:
        if not ids:
            return True
        try:
            batch = self.client.batch()
            for chunk_id in ids:
                batch.delete(doc.collection("chunks").document(chunk_id))
            batch.commit(timeout=5, retry=None)
            return True
        except Exception:
            return False

    def prune_orphan_chunks(self, account: str, *, older_than_seconds: int = 3600) -> int:
        if older_than_seconds < 3600:
            raise ValueError("orphan cleanup requires a one-hour safety interval")
        doc = self._doc("household", account)
        head = doc.get(timeout=5, retry=None)
        active = set(head.to_dict()["chunks"] if head.exists else [])
        removed = 0
        for row in doc.collection("chunks").stream():
            created = row.to_dict().get("created_at")
            if row.id not in active and created and created.timestamp() < time.time() - older_than_seconds:
                row.reference.delete(timeout=5, retry=None); removed += 1
        return removed

    def purge_expired_control(self, limit: int = 100) -> int:
        from google.cloud.firestore_v1.base_query import FieldFilter
        if not 1 <= limit <= 100:
            raise ValueError("cleanup limit must be 1–100")
        query=self.root.where(filter=FieldFilter("expires_at","<=",datetime.now(timezone.utc))).limit(limit)
        removed=0
        for row in query.stream():
            row.reference.delete(timeout=5,retry=None);removed+=1
        return removed
