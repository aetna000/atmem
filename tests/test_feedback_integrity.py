"""Ciphertext authenticity alone cannot detect policy deletion or DB rollback."""
import json
import shutil
import sqlite3

import pytest

from atmem.feedback.checkpoint import FeedbackCheckpoint
from atmem.feedback.store import FeedbackError, FeedbackStore
from test_feedback_store import ALICE, evidence


def test_deleted_policy_row_and_database_only_rollback_fail_closed(evidence,tmp_path):
    service=FeedbackStore(evidence)
    with service.transaction(ALICE) as tx:
        original=tx.put('rule_lifecycle','policy',{'state':'active','private':'PRIVATE-SOURCE-BODY'},expected_revision=0)
    snapshot=tmp_path/'old.db'
    shutil.copyfile(evidence.vault_path,snapshot)
    with service.transaction(ALICE) as tx:
        tx.put('rule_lifecycle','policy',{'state':'revoked'},expected_revision=1)
    current=tmp_path/'current.db'
    shutil.copyfile(evidence.vault_path,current)
    # An older genuine database still has valid row AEAD. Its independent
    # current Home anchor must nevertheless reject it.
    shutil.copyfile(snapshot,evidence.vault_path)
    with pytest.raises(FeedbackError,match='feedback_integrity_mismatch'):
        with service.transaction(ALICE):pass
    shutil.copyfile(current,evidence.vault_path)
    connection=sqlite3.connect(evidence.vault_path)
    connection.execute('DELETE FROM sealed_objects WHERE object_id=?',(original['object_id'],))
    connection.commit()
    connection.close()
    with pytest.raises(FeedbackError,match='feedback_integrity_mismatch'):
        with service.transaction(ALICE):pass


@pytest.mark.parametrize('crash_stage',['pending','committed'])
def test_checkpoint_commit_crashes_recover_exactly_the_durable_database(evidence,monkeypatch,crash_stage):
    service=FeedbackStore(evidence)
    original=FeedbackCheckpoint.write
    crashed=[False]
    def crash(self,value):
        if not crashed[0] and value['state']==crash_stage:
            crashed[0]=True
            if crash_stage=='pending':original(self,value)
            raise OSError('simulated process loss at checkpoint boundary')
        return original(self,value)
    with monkeypatch.context() as patch:
        patch.setattr(FeedbackCheckpoint,'write',crash)
        with pytest.raises(OSError):
            with service.transaction(ALICE) as tx:
                tx.put('outcome','o',{'body':'retained exact bytes'},expected_revision=0)
    with service.transaction(ALICE) as tx:
        value=tx.get('outcome','o')
        assert value==({'body':'retained exact bytes'} if crash_stage=='committed' else None)
    checkpoint=FeedbackCheckpoint(evidence,ALICE)
    assert checkpoint.load()['state']=='committed'


def test_missing_anchor_never_silently_trusts_existing_feedback(evidence):
    service=FeedbackStore(evidence)
    with service.transaction(ALICE) as tx:
        tx.put('outcome','o',{'body':'PLANTED-PRIVATE-CHECKPOINT-PASSAGE'},expected_revision=0)
    checkpoint=FeedbackCheckpoint(evidence,ALICE)
    assert b'PLANTED-PRIVATE-CHECKPOINT-PASSAGE' not in checkpoint.path.read_bytes()
    checkpoint.path.unlink()
    with pytest.raises(FeedbackError,match='feedback_checkpoint_missing'):
        with service.transaction(ALICE):pass
