"""Standalone encrypted-store recovery; no original host/provider required."""
import shutil

from atmem.evidence.service import EvidenceService
from atmem.feedback.service import FeedbackService
from atmem.feedback.verification import action_results
from atmem.contracts.feedback import OutcomeRecord
from atmem.private_paths import protect_private_path, private_path
from test_feedback_verification import verifier_fixture, verify


def test_retained_failed_write_is_reconstructable_after_host_and_destination_loss(tmp_path):
    live = tmp_path/"live"
    live.mkdir()
    f, outcome, verifier, reader, destination = verifier_fixture(live)
    receipt = verify(verifier, reader, outcome)
    token = f.user["token"]
    # The supported evidence backup includes encrypted DB, identity/account
    # records and required key material. A DB without its key is not recoverable.
    backup = tmp_path/"backup"
    backup.mkdir()
    # Restore into an owner-private root BEFORE copying keys or checkpoints.
    # copytree does not preserve Windows DACLs; descendants inherit this root's
    # private ACL. Do not weaken checkpoint validation to accept a public copy.
    protect_private_path(backup)
    shutil.copytree(live/"control", backup/"control")
    for folder in (".evidence-keys", ".evidence-identity-keys", ".evidence-accounts", ".feedback-checkpoints", "identity"):
        if (live/folder).exists():
            shutil.copytree(live/folder, backup/folder)
    assert all(private_path(path) for path in (backup/".feedback-checkpoints").rglob("*.json"))
    shutil.rmtree(live)
    recovered = FeedbackService(EvidenceService(backup/"control", vault_id="rag", home_root=backup), clock=lambda:1_700_000_000)
    session = recovered.bind(token, agent_id="writer", workspace_id="project")
    retained = recovered.outcome(session, outcome.outcome_id)
    assert retained["outcome"] == outcome.to_dict()
    with recovered._authorized(session, "read") as (tx, _):
        saved = tx.get("verification", receipt["receipt_id"])
        evidence = tx.get("readback_evidence", saved["evidence_id"])
        assert evidence["evidence"]["observed"] == "five days"
        assert evidence["evidence"]["expected"] == "ten days"
    assert action_results(OutcomeRecord.from_dict(retained["outcome"]), [saved])[1]["status"] == "fail"
    assert not destination.exists() and recovered.memory is None


def test_owner_previewed_rag_cleanup_removes_history_and_blocks_stale_retries(tmp_path):
    import pytest
    from dataclasses import replace
    from atmem.feedback.recovery import FeedbackRecovery
    from atmem.feedback.store import FeedbackError
    from atmem.knowledge.rag.contracts import RagQuery
    from rag_fixtures import setup_rag
    f=setup_rag(tmp_path)
    query=RagQuery('law','filing deadline')
    result=f.rag.search(f.session,query,idempotency_key='search')
    recovery=FeedbackRecovery(f.feedback)
    with pytest.raises(FeedbackError,match='denied'):
        recovery.preview_forget(f.user['token'],f.scope,source_id='law',source_kind='rag')
    preview=recovery.preview_forget(f.owner['token'],f.scope,source_id='law',source_kind='rag')
    options=dict(source_id='law',source_kind='rag',preview_sha256=preview['preview_sha256'],confirm_sha256=preview['preview_sha256'])
    receipt=recovery.forget(f.owner['token'],f.scope,**options)
    assert receipt['current_registered_rows_removed'] and receipt['removed_objects']>4
    assert recovery.forget(f.owner['token'],f.scope,**options)==receipt
    assert f.rag.sources(f.session)['sources']==[]
    with pytest.raises(FeedbackError):
        f.rag.inspect(f.session,receipt_id=result['receipt_id'],document_id='fictional-act',chunk_id='current')
    with f.feedback.store.transaction(f.scope) as tx:
        assert tx.list('rag_document')==[] and tx.list('rag_receipt')==[]
        assert 'ten days' not in str(list(tx.store.documents(partition_id=f.scope.partition)))
    with pytest.raises(FeedbackError,match='source_revoked'):
        f.rag.register(f.owner['token'],f.source,f.provider)
    new=replace(f.source,generation=3)
    f.rag.register(f.owner['token'],new,f.provider)
    f.provider.put_documents(f.owner['token'],new,(f.hits[0],))
    with pytest.raises(FeedbackError,match='conflicting_retry'):
        f.rag.search(f.session,query,idempotency_key='search')
    assert f.rag.search(f.session,query,idempotency_key='fresh')['source']['generation']==3


def test_core_forget_invalidates_proposals_and_cannot_revive_them_from_old_core_snapshot(tmp_path):
    import pytest
    from dataclasses import replace
    from atmem.feedback.recovery import FeedbackRecovery
    from atmem.feedback.store import FeedbackError
    from test_feedback_review import review_fixture
    f,memory,review,rule=review_fixture(tmp_path)
    try:
        review.propose_feedback_rule(f.feedback,f.session,rule,idempotency_key='proposal')
        backup=tmp_path/'synthetic-core-backup.db'
        memory.store.backup_to(backup)
        recovery=FeedbackRecovery(f.feedback)
        preview=recovery.preview_forget(f.owner['token'],f.scope,source_id=rule.sources[0].source_id)
        options=dict(source_id=rule.sources[0].source_id,preview_sha256=preview['preview_sha256'],confirm_sha256=preview['preview_sha256'])
        receipt=recovery.forget(f.owner['token'],f.scope,**options)
        assert receipt['canonical_commit']=='verified'
        assert recovery.forget(f.owner['token'],f.scope,**options)==receipt
        deleted=memory.store.get_record('alice',rule.sources[0].source_id)
        assert deleted['status']=='tombstoned' and 'project destination is staging' not in deleted['content']
        with f.feedback.store.transaction(f.scope) as tx:
            assert tx.get('rule_proposal','rule') is None
        memory.store.restore_from(backup)
        with pytest.raises(FeedbackError,match='source_revoked'):
            review.propose_feedback_rule(f.feedback,f.session,replace(rule,rule_id='new-rule'),idempotency_key='restored')
    finally:
        memory.close()


def test_forget_preview_is_invalidated_by_a_new_dependent_passage(tmp_path):
    import pytest
    from atmem.feedback.recovery import FeedbackRecovery
    from atmem.feedback.store import FeedbackError
    from rag_fixtures import setup_rag,hit
    f=setup_rag(tmp_path)
    recovery=FeedbackRecovery(f.feedback)
    preview=recovery.preview_forget(f.owner['token'],f.scope,source_id='law',source_kind='rag')
    f.provider.put_documents(f.owner['token'],f.source,(hit(f.source,'new'),))
    with pytest.raises(FeedbackError,match='stale_preview'):
        recovery.forget(f.owner['token'],f.scope,source_id='law',source_kind='rag',preview_sha256=preview['preview_sha256'],confirm_sha256=preview['preview_sha256'])
    assert len(f.rag.sources(f.session)['sources'])==1
