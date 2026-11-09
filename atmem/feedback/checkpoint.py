"""Encrypted integrity anchors for the opt-in feedback ledger.

The anchor is separate from the database so replacing/deleting rows or copying
an older DB into an existing Home cannot silently remove policy. Pending/new
roots recover crashes around SQLite commit. External effects must occur only
after the transaction context exits successfully (as in GuardedDispatcher).
A complete rollback of both Home and all its anchors/keys is not detectable
without an external monotonic authority; restored activation is not certified.
"""
from hashlib import sha256
import base64
import hmac
import json
import os
from pathlib import Path
import uuid

from atmem.evidence.crypto import open_json, seal_json
from atmem.feedback.store import FeedbackError
from atmem.private_paths import private_path, protect_private_path


MAX_SCOPE_CIPHERTEXT = 64 * 1024 * 1024


class FeedbackCheckpoint:
    def __init__(self, evidence, scope):
        self.scope = scope
        self.key = evidence._identity_key
        tag = hmac.digest(self.key,b'atmem-feedback-checkpoint-v1\0'+scope.partition.encode(),'sha256').hex()
        self.object_id = 'feedback-head-'+tag
        vault = sha256(evidence.vault_id.encode()).hexdigest()
        self.path = evidence.root.parent/'.feedback-checkpoints'/vault/(tag+'.json')

    def fingerprint(self, store):
        cursor = store._conn.execute('''SELECT o.object_id,o.sequence,o.nonce,o.ciphertext,o.slot_id
            FROM sealed_objects o JOIN key_slots s ON s.slot_id=o.slot_id
            WHERE s.lookup_tag=? ORDER BY o.sequence''',(store._lookup_tag(self.scope.partition),))
        digest = sha256()
        count = total = 0
        for row in cursor:
            count += 1
            total += len(row['ciphertext'])
            if count > 10000 or total > MAX_SCOPE_CIPHERTEXT:
                raise FeedbackError('scope_record_budget_exhausted')
            for value in (row['object_id'].encode(),str(row['sequence']).encode(),bytes(row['nonce']),
                          bytes(row['ciphertext']),row['slot_id'].encode()):
                digest.update(len(value).to_bytes(8,'big'))
                digest.update(value)
        return {'sha256':digest.hexdigest(),'objects':count}

    def load(self):
        if not self.path.exists() and not self.path.is_symlink():
            return None
        try:
            if not private_path(self.path) or self.path.stat().st_size > 8192:
                raise FeedbackError('feedback_checkpoint_unavailable')
            wrapper=json.loads(self.path.read_text())
            value=open_json(self.key,self.object_id,base64.b64decode(wrapper['nonce'],validate=True),
                            base64.b64decode(wrapper['ciphertext'],validate=True))
            if value['scope']!=self.scope.to_dict() or value['state'] not in ('pending','committed'):
                raise FeedbackError('feedback_integrity_mismatch')
            return value
        except FeedbackError:
            raise
        except Exception:
            raise FeedbackError('feedback_checkpoint_unavailable') from None

    def verify(self, store):
        actual=self.fingerprint(store)
        stored=self.load()
        if stored is None:
            if actual['objects']:
                raise FeedbackError('feedback_checkpoint_missing')
            return actual
        allowed=[stored['root']] if stored['state']=='committed' else [stored['previous'],stored['root']]
        if actual not in allowed:
            raise FeedbackError('feedback_integrity_mismatch')
        # A pending previous root can only precede transaction completion. The
        # service has not yet dispatched effects or returned committed results.
        if stored['state']=='pending':
            self.write({'scope':self.scope.to_dict(),'state':'committed','root':actual})
        return actual

    def write(self, value):
        created = not self.path.parent.exists()
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if created:
            protect_private_path(self.path.parent)
        if not private_path(self.path.parent):
            raise FeedbackError('feedback_checkpoint_unavailable')
        nonce,ciphertext=seal_json(self.key,self.object_id,value)
        wrapper={'format':'atmem-feedback-checkpoint-v1','nonce':base64.b64encode(nonce).decode(),
                 'ciphertext':base64.b64encode(ciphertext).decode()}
        temporary=self.path.with_name('.'+self.path.name+'.'+uuid.uuid4().hex+'.tmp')
        descriptor=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        try:
            protect_private_path(temporary)
            with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
                descriptor=None
                json.dump(wrapper,stream,separators=(',',':'))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary,self.path)
            if os.name!='nt':
                directory=os.open(self.path.parent,os.O_RDONLY)
                try:os.fsync(directory)
                finally:os.close(directory)
        finally:
            if descriptor is not None:os.close(descriptor)
            temporary.unlink(missing_ok=True)
