"""Real encrypted-container integration, migration, failure and concurrency."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sqlite3

import pytest

from atmem.contracts.feedback import FeedbackScope
from atmem.evidence.service import EvidenceService
from atmem.evidence.store import EncryptedEvidenceStore
from atmem.feedback.store import FeedbackError, FeedbackStore


ALICE = FeedbackScope("local", "alice", "writer", "project")
BOB = FeedbackScope("local", "bob", "writer", "project")


@pytest.fixture
def evidence(tmp_path):
    return EvidenceService(tmp_path / "control", vault_id="feedback", home_root=tmp_path)


def test_same_real_vault_preserves_existing_evidence_and_protects_semantics(evidence):
    with evidence._store() as existing:
        original = existing.append({"record_type": "fixture_original", "content": "original retained bytes"})
    store = FeedbackStore(evidence)
    with store.transaction(ALICE) as tx:
        receipt = tx.put("outcome", "outcome-private", {"body": "PLANTED-PRIVATE-PASSAGE", "user": "ALICE-PRIVATE"}, expected_revision=0)
        tx.audit("owner", "record", allowed=True)
    # A fresh process/service can read the extension without the original host.
    reopened = EvidenceService(evidence.root, vault_id="feedback", home_root=evidence.home_root)
    with FeedbackStore(reopened).transaction(ALICE) as tx:
        assert tx.get("outcome", "outcome-private")["body"] == "PLANTED-PRIVATE-PASSAGE"
        assert tx.revision("outcome", "outcome-private") == receipt["revision"]
    with reopened._store() as vault:
        assert next(d for d in vault.documents() if d["object_id"] == original["object_id"])["content"] == "original retained bytes"
    for path in evidence.root.glob("protected-evidence.db*"):
        data = path.read_bytes()
        assert b"PLANTED-PRIVATE-PASSAGE" not in data
        assert b"ALICE-PRIVATE" not in data
        assert b"outcome-private" not in data


def test_scope_selected_before_decryption_of_another_users_corrupt_object(evidence):
    store = FeedbackStore(evidence)
    with store.transaction(ALICE) as tx:
        tx.put("outcome", "a", {"body": "alice"}, expected_revision=0)
    with store.transaction(BOB) as tx:
        bob = tx.put("outcome", "b", {"body": "bob"}, expected_revision=0)
    connection = sqlite3.connect(evidence.vault_path)
    connection.execute("UPDATE sealed_objects SET ciphertext=? WHERE object_id=?", (os.urandom(40), bob["object_id"]))
    connection.commit()
    connection.close()
    with store.transaction(ALICE) as tx:
        assert tx.get("outcome", "a") == {"body": "alice"}
        assert tx.get("outcome", "b") is None
    with pytest.raises(Exception):
        with store.transaction(BOB):
            pass


def test_failed_transaction_rolls_back_data_and_idempotency(evidence):
    store = FeedbackStore(evidence)
    with pytest.raises(RuntimeError):
        with store.transaction(ALICE) as tx:
            tx.once("record", "retry", {"x": 1},
                    lambda: tx.put("outcome", "o", {"body": "x"}, expected_revision=0))
            raise RuntimeError("simulated process failure before commit")
    with store.transaction(ALICE) as tx:
        assert tx.get("outcome", "o") is None
        assert tx.list("idempotency") == []
        assert tx.once("record", "retry", {"x": 1},
                       lambda: tx.put("outcome", "o", {"body": "x"}, expected_revision=0))["revision"] == 1


def test_concurrent_idempotent_writers_have_one_receipt_and_reject_changed_payload(evidence):
    store = FeedbackStore(evidence)
    def write(_):
        with store.transaction(ALICE) as tx:
            return tx.once("record", "retry", {"body": "same"},
                           lambda: tx.put("outcome", "o", {"body": "same"}, expected_revision=0))
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(write, range(8)))
    assert all(r == receipts[0] for r in receipts)
    with store.transaction(ALICE) as tx:
        assert tx.revision("outcome", "o") == 1
        with pytest.raises(FeedbackError, match="conflicting_retry"):
            tx.once("record", "retry", {"body": "different"}, lambda: {})
        with pytest.raises(FeedbackError, match="stale_revision"):
            tx.put("outcome", "o", {"body": "different"}, expected_revision=0)


def test_key_rotation_keeps_multiple_feedback_partitions_separate(evidence):
    store = FeedbackStore(evidence)
    for scope in (ALICE, BOB):
        with store.transaction(scope) as tx:
            tx.put("outcome", "o", {"subject": scope.subject_id}, expected_revision=0)
    key = os.urandom(32)
    # Exercise the actual existing vault rotation algorithm, not a feedback-only copy.
    with evidence._store() as vault:
        vault.rotate_key(key)
    with EncryptedEvidenceStore(evidence.vault_path, key) as rotated:
        a = list(rotated.documents(partition_id=ALICE.partition))
        b = list(rotated.documents(partition_id=BOB.partition))
        assert [d["value"]["subject"] for d in a] == ["alice"]
        assert [d["value"]["subject"] for d in b] == ["bob"]


def test_locked_existing_vault_cannot_be_reopened_with_a_new_key(evidence):
    store = FeedbackStore(evidence)
    with store.transaction(ALICE) as tx:
        tx.put("outcome", "o", {"secret": "original"}, expected_revision=0)
    evidence.key_path.unlink()
    with pytest.raises(FeedbackError, match="evidence_locked"):
        with store.transaction(ALICE):
            pass
    assert not evidence.key_path.exists()
