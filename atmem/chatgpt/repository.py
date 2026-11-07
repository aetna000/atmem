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


class AccountClosed(RuntimeError):
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

    def assert_active(self, account: str, transaction=None) -> None:
        marker=self._doc('account',account).get(transaction=transaction,timeout=5,retry=None)
        if marker.exists:
            raise AccountClosed('account_deletion_in_progress_or_complete')

    def get_control(self, kind: str, key: str, *, deletion_retry: bool = False) -> dict[str, Any] | None:
        doc = self._doc(kind, key).get(timeout=5, retry=None)
        if not doc.exists:
            return None
        value = json.loads(self.open(kind + ":" + key, doc.to_dict()["envelope"]))
        if value.get("expires_at", time.time() + 1) <= time.time():
            return None
        account=value.get('subject') or (key if kind=='firebase-identity' else None)
        if account and not (kind=='account-deletion' and deletion_retry):
            try:self.assert_active(account)
            except AccountClosed:return None
        return value

    def put_control(self, kind: str, key: str, value: dict[str, Any]) -> None:
        document={"envelope": self.seal(kind + ":" + key, json.dumps(value, separators=(",", ":")).encode()),"kind":"control","control_type":kind}
        if "expires_at" in value:
            document["expires_at"]=datetime.fromtimestamp(value["expires_at"],timezone.utc)
        account=value.get('subject') or (key if kind=='firebase-identity' else None)
        if not account:
            self._doc(kind,key).set(document);return
        document['account']=self.settings.opaque_id('account-controls',account)
        @firestore.transactional
        def save(transaction):
            if kind=='account-deletion':
                marker=self._doc('account',account).get(transaction=transaction,timeout=5,retry=None)
                if marker.exists and marker.to_dict()['deletion_id']!=key:
                    raise AccountClosed('different_deletion_already_started')
            else:self.assert_active(account,transaction)
            transaction.set(self._doc(kind,key),document)
        save(self.client.transaction(max_attempts=3))

    def claim_email_slot(self, email: str, seconds: int = 120) -> bool:
        """Atomic per-address delivery throttle; stores no plaintext address."""
        doc=self._doc('email-limit',email.strip().casefold())
        @firestore.transactional
        def claim(transaction):
            row=doc.get(transaction=transaction,timeout=5,retry=None)
            now=datetime.now(timezone.utc)
            if row.exists and row.to_dict()['expires_at']>now:return False
            from datetime import timedelta
            transaction.set(doc,{'kind':'email-limit','expires_at':now+timedelta(seconds=seconds)})
            return True
        return claim(self.client.transaction(max_attempts=3))

    def claim_account_request(self, account: str) -> bool:
        """Durable per-account admission; restarts cannot reset the allowance."""
        doc=self._doc('account-quota',account)
        @firestore.transactional
        def admit(transaction):
            self.assert_active(account,transaction)
            row=doc.get(transaction=transaction,timeout=5,retry=None)
            window=int(time.time()//60)
            saved=row.to_dict() if row.exists else {}
            used=int(saved.get('count',0)) if saved.get('window')==window else 0
            if used>=self.settings.tool_requests_per_minute:return False
            transaction.set(doc,{'kind':'quota','account':self.settings.opaque_id('account-controls',account),
                'window':window,'count':used+1,'expires_at':datetime.fromtimestamp((window+2)*60,timezone.utc)})
            return True
        return admit(self.client.transaction(max_attempts=3))

    def consume_control(self, kind: str, key: str) -> dict[str, Any] | None:
        doc = self._doc(kind, key)
        @firestore.transactional
        def consume(transaction):
            row = doc.get(transaction=transaction, timeout=5, retry=None)
            if not row.exists:
                return None
            value = json.loads(self.open(kind + ":" + key, row.to_dict()["envelope"]))
            if value.get('subject'):
                self.assert_active(value['subject'],transaction)
            transaction.delete(doc)
            return value if value.get("expires_at", time.time() + 1) > time.time() else None
        return consume(self.client.transaction(max_attempts=3))

    def load(self, account: str) -> Snapshot:
        doc = self._doc("household", account)
        # Read the head and its chunks in one transaction: a writer may clean its
        # old generation immediately after a successful swap.
        @firestore.transactional
        def load(transaction):
            self.assert_active(account,transaction)
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
        pieces=[]
        for index, offset in enumerate(range(0, len(encrypted), self.CHUNK_BYTES)):
            chunk_id = f"{version}_{index:04d}"
            ids.append(chunk_id)
            pieces.append((chunk_id,encrypted[offset:offset+self.CHUNK_BYTES]))
        @firestore.transactional
        def stage(transaction):
            self.assert_active(account,transaction)
            for chunk_id,data in pieces:
                transaction.create(doc.collection('chunks').document(chunk_id),{'data':data,'created_at':firestore.SERVER_TIMESTAMP})
        stage(self.client.transaction(max_attempts=3))
        @firestore.transactional
        def swap(transaction):
            self.assert_active(account,transaction)
            row = doc.get(transaction=transaction, timeout=5, retry=None)
            generation = int(row.to_dict()["generation"]) if row.exists else 0
            if generation != previous.generation:
                raise Conflict("generation_conflict_retry_with_same_intent")
            transaction.set(doc, {"generation": generation + 1, "chunks": ids, "updated_at": firestore.SERVER_TIMESTAMP})
            return generation + 1
        try:
            generation = swap(self.client.transaction(max_attempts=3))
        except (Conflict,AccountClosed):
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

    def begin_account_deletion(self, account: str, deletion_id: str) -> dict:
        doc=self._doc('account',account)
        @firestore.transactional
        def begin(transaction):
            row=doc.get(transaction=transaction,timeout=5,retry=None)
            if row.exists:
                if row.to_dict()['deletion_id']!=deletion_id:
                    raise AccountClosed('different_deletion_already_started')
                return json.loads(self.open('account-receipt:'+account,row.to_dict()['envelope']))
            receipt={'format':'atmem-cloud-account-deletion-v1','deletion_id':deletion_id,
                     'access_revoked':True,'household_purged':False,'firebase_account_deleted':False,
                     'backup_deletion_verified':False,'chatgpt_copies_deleted':False,
                     'legacy_auth_controls_max_retention_seconds':86400,
                     'noncontent_deletion_fence_retained':True,'started_at':time.time()}
            transaction.set(doc,{'deletion_id':deletion_id,'state':'deleting','envelope':self.seal('account-receipt:'+account,json.dumps(receipt).encode())})
            return receipt
        return begin(self.client.transaction(max_attempts=3))

    def update_deletion_receipt(self, account: str, receipt: dict) -> None:
        doc=self._doc('account',account)
        @firestore.transactional
        def save(transaction):
            row=doc.get(transaction=transaction,timeout=5,retry=None)
            if not row.exists or row.to_dict()['deletion_id']!=receipt['deletion_id']:
                raise AccountClosed('deletion_receipt_mismatch')
            transaction.update(doc,{'state':'deleted' if receipt['firebase_account_deleted'] else 'deleting',
                'envelope':self.seal('account-receipt:'+account,json.dumps(receipt).encode())})
        save(self.client.transaction(max_attempts=3))

    def deletion_receipt(self, account: str, deletion_id: str) -> dict | None:
        row=self._doc('account',account).get(timeout=5,retry=None)
        if not row.exists or row.to_dict()['deletion_id']!=deletion_id:return None
        return json.loads(self.open('account-receipt:'+account,row.to_dict()['envelope']))

    def purge_account(self, account: str, deletion_id: str) -> dict:
        from google.cloud.firestore_v1.base_query import FieldFilter
        receipt=self.begin_account_deletion(account,deletion_id)
        doc=self._doc('household',account)
        self.client.recursive_delete(doc)
        if doc.get(timeout=5,retry=None).exists or list(doc.collection('chunks').limit(1).stream()):
            raise RuntimeError('account_purge_incomplete')
        query=self.root.where(filter=FieldFilter('account','==',self.settings.opaque_id('account-controls',account)))
        for row in query.stream():
            if row.to_dict().get('control_type')!='account-deletion':
                row.reference.delete(timeout=5,retry=None)
        self._doc('firebase-identity',account).delete(timeout=5,retry=None)
        receipt['household_purged']=True
        self.update_deletion_receipt(account,receipt)
        return receipt

    def export_snapshot(self, account: str) -> bytes:
        snapshot=self.load(account)
        if snapshot.payload is None:raise ValueError('no_household_to_export')
        return self.seal('recovery:'+account,snapshot.payload)

    def restore_snapshot(self, account: str, blob: bytes, *, expected_generation: int) -> dict:
        self.assert_active(account)
        if len(blob)>self.settings.max_snapshot_bytes+64:raise ValueError('recovery_snapshot_too_large')
        payload=self.open('recovery:'+account,blob)
        value=json.loads(payload)
        if value.get('format')!='atmem-cloud-household-v1':raise ValueError('unsupported_household_version')
        import base64,tempfile,re
        from pathlib import Path
        from atmem import Memory
        from atmem.core.storage import HouseholdPolicy
        with tempfile.TemporaryDirectory(prefix='restore-check-',dir=self.settings.home) as directory:
            path=Path(directory)/'memory.db';path.write_bytes(base64.b64decode(value['database'],validate=True))
            Path(str(path)+'.encryption.json').write_text(json.dumps(value['policy']))
            policy=HouseholdPolicy.load(path)
            if policy.state!='encrypted':raise ValueError('plaintext_recovery_refused')
            memory=Memory(path,policy=policy,auto_vectors=False)
            try:
                scopes=[row[0] for row in memory.store._conn.execute('SELECT scope FROM chatgpt_scopes LIMIT 51')]
                if not scopes or len(scopes)>50:raise ValueError('invalid_recovery_scopes')
                for scope in scopes:
                    if not re.fullmatch(r'personal|project:[a-z0-9][a-z0-9-]{0,47}',scope):raise ValueError('invalid_recovery_scope')
                    subject='chatgpt:'+self.settings.opaque_id('subject',account)+':'+scope
                    if not memory.verify(subject)['valid']:raise ValueError('recovery_audit_invalid')
            finally:memory.close()
        previous=self.load(account)
        if previous.generation!=expected_generation:raise Conflict('recovery_generation_changed')
        return self.commit(account,previous,payload)

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
