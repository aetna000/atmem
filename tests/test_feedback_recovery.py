"""Standalone encrypted-store recovery; no original host/provider required."""
import shutil

import pytest

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
        with pytest.raises(FeedbackError,match='restore_reconciliation_required'):
            review.propose_feedback_rule(f.feedback,f.session,replace(rule,rule_id='new-rule'),idempotency_key='restored')
        recovery.reconcile_after_restore(f.owner['token'],f.scope,restore_id='canonical-restored')
        f.feedback.grant_agent(f.owner['token'],f.scope,principal_id=f.user['principal_id'],
                               operations=('read','report','propose'),expires_at=1_700_010_000)
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


def test_real_home_restore_and_adoption_block_feedback_until_scoped_reconciliation(tmp_path):
    import pytest
    from atmem.control.manager import ControlPlaneManager
    from atmem.feedback.recovery import FeedbackRecovery
    from atmem.feedback.store import FeedbackError
    from atmem.home.service import HomeService
    from rag_fixtures import setup_rag
    f = setup_rag(tmp_path)
    home = HomeService(tmp_path)
    home.initialize()
    ControlPlaneManager.start(host="generic", state_path=tmp_path/"control-plane.json",
        control_root=tmp_path/"migrations", memory_db=tmp_path/"native-home.db")
    assert f.feedback.capabilities(f.session)["scope"] == f.scope.to_dict()
    recovery = FeedbackRecovery(f.feedback)
    home.prepare_restore()
    with pytest.raises(FeedbackError, match="restore_requires_adoption"):
        f.feedback.capabilities(f.session)
    with pytest.raises(FeedbackError, match="restore_requires_adoption"):
        recovery.reconcile_after_restore(f.owner["token"], f.scope, restore_id="too-early")
    home.adopt(administrator_confirmed=True)
    restarted = FeedbackService(f.evidence, clock=f.feedback.clock)
    with pytest.raises(FeedbackError, match="restore_reconciliation_required"):
        restarted.bind(f.user["token"], agent_id="writer", workspace_id="project")
    with pytest.raises(FeedbackError, match="restore_reconciliation_required"):
        restarted.grant_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
            operations=("read",), expires_at=1_700_010_000)
    restore = FeedbackRecovery(restarted)
    result = restore.reconcile_after_restore(f.owner["token"], f.scope, restore_id="adopted")
    assert result["disabled"]["agent_grant"] == 1 and result["disabled"]["rag_source"] == 1
    assert restore.reconcile_after_restore(f.owner["token"], f.scope, restore_id="adopted") == result
    with pytest.raises(FeedbackError, match="denied"):
        restarted.bind(f.user["token"], agent_id="writer", workspace_id="project")
    restarted.grant_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
        operations=("read",), expires_at=1_700_010_000)
    session = restarted.bind(f.user["token"], agent_id="writer", workspace_id="project")
    assert restarted.capabilities(session)["scope"] == f.scope.to_dict()
    # A second adoption is a different generation. Neither old reconciliation
    # nor a service restart may silently re-enable the copied grant.
    home.adopt(administrator_confirmed=True)
    with pytest.raises(FeedbackError, match="restore_reconciliation_required"):
        restarted.capabilities(session)
    with pytest.raises(FeedbackError, match="conflicting_retry"):
        restore.reconcile_after_restore(f.owner["token"], f.scope, restore_id="adopted")


def test_corrupt_or_removed_home_restore_binding_fails_closed(tmp_path):
    import json
    import pytest
    from atmem.feedback.recovery import FeedbackRecovery
    from atmem.feedback.store import FeedbackError
    from atmem.home.service import _atomic_json
    from rag_fixtures import setup_rag
    f = setup_rag(tmp_path)
    mode = tmp_path/"runtime/home-mode.json"
    _atomic_json(mode, {"format":"atmem-home-runtime-mode-v1", "mode":"adopted_writable", "binding_id":"synthetic-adoption"})
    FeedbackRecovery(f.feedback).reconcile_after_restore(f.owner["token"], f.scope, restore_id="adoption")
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
        operations=("read",), expires_at=1_700_010_000)
    mode.write_text("{}")
    with pytest.raises(FeedbackError, match="restore_state_unavailable"):
        f.feedback.capabilities(f.session)
    mode.unlink()
    with pytest.raises(FeedbackError, match="restore_reconciliation_required"):
        f.feedback.capabilities(f.session)


def test_source_cleanup_uses_typed_forward_links_not_colliding_business_ids_or_copied_results(tmp_path):
    from dataclasses import replace
    import pytest
    from atmem.feedback.recovery import FeedbackRecovery
    from atmem.feedback.store import FeedbackError
    from atmem.knowledge.rag.contracts import RagQuery
    from test_feedback_actions import actions_fixture
    f, original = actions_fixture(tmp_path)
    f.feedback.grant_agent(f.owner['token'], f.scope, principal_id=f.user['principal_id'],
        operations=('read','report','search'), expires_at=1_700_010_000)
    receipt=f.rag.search(f.session,RagQuery('law','deadline'),idempotency_key='linked-search')
    business=replace(original.observations[1],result={'business_record':{'source_id':'law'}})
    unrelated=replace(original,outcome_id='unrelated',required=(original.required[1],),observations=(business,))
    collision=replace(original,outcome_id='law')
    before={}
    for record in (unrelated,collision):
        before[record.outcome_id]=f.feedback.report_outcome(f.session,record,idempotency_key=record.outcome_id)
    linked_observation=replace(original.observations[1],evidence_id=receipt['receipt_id'],
        result={'copied_result':{'outcome_id':'unrelated'}})
    linked=replace(original,outcome_id='linked',required=(original.required[1],),observations=(linked_observation,))
    f.feedback.report_outcome(f.session,linked,idempotency_key='linked')
    recovery=FeedbackRecovery(f.feedback)
    preview=recovery.preview_forget(f.owner['token'],f.scope,source_id='law',source_kind='rag')
    assert preview['kinds']['outcome']==1
    recovery.forget(f.owner['token'],f.scope,source_id='law',source_kind='rag',
        preview_sha256=preview['preview_sha256'],confirm_sha256=preview['preview_sha256'])
    for key,record in before.items():
        assert f.feedback.outcome(f.session,key)==record
    with pytest.raises(FeedbackError,match='denied'):
        f.feedback.outcome(f.session,'linked')
    with f.feedback.store.transaction(f.scope) as tx:
        assert tx.list('rag_receipt')==[] and tx.list('rag_document')==[]


def test_forgetting_an_active_policy_source_requires_explicit_revocation_first(tmp_path):
    import pytest
    from atmem.feedback.recovery import FeedbackRecovery
    from atmem.feedback.store import FeedbackError
    from feedback_lifecycle_fixtures import reviewed_shadow, seed_trusted_test_receipt, VERSIONS
    f,memory,rule,lifecycle=reviewed_shadow(tmp_path)
    try:
        key=seed_trusted_test_receipt(f,rule)
        lifecycle.transition(f.owner['token'],f.scope,artifact_id='rule',state='active',expected_generation=1,
                             qualification_id=key,versions=VERSIONS)
        recovery=FeedbackRecovery(f.feedback)
        with pytest.raises(FeedbackError,match='dependent_policy_requires_revocation'):
            recovery.preview_forget(f.owner['token'],f.scope,source_id=rule.sources[0].source_id)
        assert memory.store.get_record('alice',rule.sources[0].source_id)['status']=='active'
        lifecycle.transition(f.owner['token'],f.scope,artifact_id='rule',state='revoked',expected_generation=2)
        preview=recovery.preview_forget(f.owner['token'],f.scope,source_id=rule.sources[0].source_id)
        result=recovery.forget(f.owner['token'],f.scope,source_id=rule.sources[0].source_id,
            preview_sha256=preview['preview_sha256'],confirm_sha256=preview['preview_sha256'])
        assert result['canonical_commit']=='verified'
    finally:
        memory.close()


def test_rag_source_and_canonical_memory_with_same_id_have_distinct_lineage(tmp_path):
    from dataclasses import replace
    from atmem.feedback.recovery import FeedbackRecovery
    from feedback_lifecycle_fixtures import reviewed_shadow, seed_trusted_test_receipt, VERSIONS
    from rag_fixtures import hit
    f,memory,rule,lifecycle=reviewed_shadow(tmp_path)
    try:
        key=seed_trusted_test_receipt(f,rule)
        lifecycle.transition(f.owner['token'],f.scope,artifact_id='rule',state='active',expected_generation=1,
                             qualification_id=key,versions=VERSIONS)
        source=replace(f.source,source_id=rule.sources[0].source_id,collection_id='separate-document-collection')
        f.rag.register(f.owner['token'],source,f.provider)
        f.provider.put_documents(f.owner['token'],source,(hit(source),))
        recovery=FeedbackRecovery(f.feedback)
        preview=recovery.preview_forget(f.owner['token'],f.scope,source_id=source.source_id,source_kind='rag')
        assert 'rule_proposal' not in preview['kinds'] and 'rule_lifecycle' not in preview['kinds']
        recovery.forget(f.owner['token'],f.scope,source_id=source.source_id,source_kind='rag',
            preview_sha256=preview['preview_sha256'],confirm_sha256=preview['preview_sha256'])
        assert memory.store.get_record('alice',source.source_id)['status']=='active'
        with f.feedback.store.transaction(f.scope) as tx:
            assert tx.get('rule_lifecycle','rule')['state']=='active'
            assert tx.get('rule_proposal','rule')['candidate_sha256']==rule.content_digest
    finally:
        memory.close()


@pytest.mark.parametrize('encrypted',[False,True])
def test_direct_canonical_restore_requires_reconciliation_across_restart(tmp_path,monkeypatch,encrypted):
    import pytest
    from atmem import Memory
    from atmem.feedback.recovery import FeedbackRecovery
    from atmem.feedback.store import FeedbackError
    from test_feedback_actions import actions_fixture
    f,_=actions_fixture(tmp_path)
    core=tmp_path/'synthetic-core.db'
    if encrypted:
        pytest.importorskip('sqlcipher3')
        from atmem.core.keys import initialize_encrypted_household
        monkeypatch.setattr('atmem.core.keys.DEFAULT_KEY_PATH',tmp_path/'keys'/'synthetic-db.key')
        monkeypatch.delenv('ATMEM_DB_KEY',raising=False)
        initialize_encrypted_household(core)
    memory=Memory(core,auto_vectors=False)
    f.feedback.memory=memory
    try:
        memory.remember('alice','My city is Sydney.')
        backup=tmp_path/'synthetic-core-backup.db'
        memory.store.backup_to(backup)
        if encrypted:
            assert not backup.read_bytes().startswith(b'SQLite format 3')
        assert f.feedback.capabilities(f.session)['scope']==f.scope.to_dict()
        memory.store.restore_from(backup)
        assert memory.recall('alice','Sydney')
        with pytest.raises(FeedbackError,match='restore_reconciliation_required'):
            f.feedback.capabilities(f.session)
        memory.close()
        memory=Memory(core,auto_vectors=False)
        restarted=FeedbackService(f.evidence,memory=memory,clock=f.feedback.clock)
        with pytest.raises(FeedbackError,match='restore_reconciliation_required'):
            restarted.bind(f.user['token'],agent_id='writer',workspace_id='project')
        recovery=FeedbackRecovery(restarted)
        result=recovery.reconcile_after_restore(f.owner['token'],f.scope,restore_id='canonical-restore')
        assert result['disabled']['agent_grant']==1
        with pytest.raises(FeedbackError,match='denied'):
            restarted.bind(f.user['token'],agent_id='writer',workspace_id='project')
        restarted.grant_agent(f.owner['token'],f.scope,principal_id=f.user['principal_id'],
                              operations=('read',),expires_at=1_700_010_000)
        session=restarted.bind(f.user['token'],agent_id='writer',workspace_id='project')
        assert restarted.capabilities(session)['scope']==f.scope.to_dict()
        # Restoring identical bytes again is still a new restore event; an old
        # reconciliation/idempotency key cannot silently adopt the new event.
        memory.store.restore_from(backup)
        with pytest.raises(FeedbackError,match='restore_reconciliation_required'):
            restarted.capabilities(session)
        with pytest.raises(FeedbackError,match='conflicting_retry'):
            recovery.reconcile_after_restore(f.owner['token'],f.scope,restore_id='canonical-restore')
    finally:
        memory.close()


@pytest.mark.parametrize('checkpoint',['before_backup','after_backup','before_complete'])
def test_interrupted_canonical_restore_cannot_reconcile_or_dispatch_until_retried(tmp_path,monkeypatch,checkpoint):
    from atmem import Memory
    from atmem.feedback.recovery import FeedbackRecovery
    from atmem.feedback.store import FeedbackError
    from atmem.store import restore_state
    from test_feedback_actions import actions_fixture
    f,_=actions_fixture(tmp_path)
    core=tmp_path/'synthetic-core.db'
    memory=Memory(core,auto_vectors=False)
    try:
        memory.remember('alice','My city is Sydney.')
        backup=tmp_path/'synthetic-core-backup.db'
        memory.store.backup_to(backup)
        f.feedback.memory=memory
        original_write=restore_state.write_restore_state
        def fail_witness(store,*,restore_id,state):
            if checkpoint=='before_complete' and state=='complete':
                raise KeyboardInterrupt('synthetic process loss before completion publication')
            original_write(store,restore_id=restore_id,state=state)
            if checkpoint=='before_backup' and state=='pending':
                raise KeyboardInterrupt('synthetic process loss before canonical replacement')
        with monkeypatch.context() as patch:
            patch.setattr(restore_state,'write_restore_state',fail_witness)
            if checkpoint=='after_backup':
                def fail_migration():
                    raise KeyboardInterrupt('synthetic process loss after canonical replacement')
                patch.setattr(memory.store,'_migrate',fail_migration)
            with pytest.raises(KeyboardInterrupt):
                memory.store.restore_from(backup)
        assert memory.store.restore_state()['state']=='pending'
        with pytest.raises(FeedbackError,match='canonical_restore_incomplete'):
            FeedbackRecovery(f.feedback).reconcile_after_restore(f.owner['token'],f.scope,restore_id='too-early')
        memory.close()
        memory=Memory(core,auto_vectors=False)
        restarted=FeedbackService(f.evidence,memory=memory,clock=f.feedback.clock)
        with pytest.raises(FeedbackError,match='canonical_restore_incomplete'):
            restarted.bind(f.user['token'],agent_id='writer',workspace_id='project')
        # Explicit retry from a known-good snapshot completes the restore, but
        # still does not re-enable restored grants or active policies.
        memory.store.restore_from(backup)
        with pytest.raises(FeedbackError,match='restore_reconciliation_required'):
            restarted.bind(f.user['token'],agent_id='writer',workspace_id='project')
        FeedbackRecovery(restarted).reconcile_after_restore(f.owner['token'],f.scope,restore_id='retried')
        assert memory.recall('alice','Sydney')
    finally:
        memory.close()
