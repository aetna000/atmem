"""Independent operational classifications using real stores and destination I/O.

These are contract tests, not evidence of model learning or of mental causality.
"""
from dataclasses import replace
import json

import pytest

from atmem.contracts.feedback import ActionCheck
from atmem.feedback.store import FeedbackError
from atmem.feedback.verification import ATTRIBUTION_CHECKS, AttributionReadback
from test_feedback_verification import verifier_fixture, verify


def classification_fixture(tmp_path):
    f, outcome, service, reader, destination = verifier_fixture(tmp_path)
    checked = verify(service, reader, outcome)
    proposal = service.propose_attribution(f.session, outcome_sha256=outcome.content_digest,
        invocation_id='call-write', failure_class='wrong_argument_value',
        reason='Compare the retained source, exact argument and independently read destination.',
        evidence_ids=(checked['evidence_id'],))

    def callback(record, observation, proposed, retained, *, deadline):
        source = f.provider.inspect(f.source, 'fictional-act', 'current', deadline=deadline)
        actual = destination.read_text()
        proofs = {
            'authoritative_value_captured': {'method':'exact_frozen_source', 'observed':source.to_dict(),
                                           'expected':f.hits[0].to_dict()},
            'wrong_argument': {'method':'exact_value', 'observed':observation.arguments['body'], 'expected':'ten days'},
            'effect_correlated': {'method':'destination_and_operation_readback',
                'observed':{'body':actual, 'readback':retained[0]['value']}, 'expected':observation.arguments['body']},
        }
        results = (source == f.hits[0], observation.arguments['body'] != 'ten days',
                   actual == observation.arguments['body'] == retained[0]['value']['evidence']['observed'])
        return AttributionReadback('wrong_argument_value', tuple(
            ActionCheck(name, 'mechanical', 'pass' if passed else 'fail', 'Exact retained source/call/destination comparison')
            for name, passed in zip(ATTRIBUTION_CHECKS['wrong_argument_value'], results)),
            {'scope':record.scope.to_dict(), 'outcome_sha256':record.content_digest,
             'invocation_id':observation.invocation_id, 'proofs':proofs,
             'sources':[{'kind':'rag','source':f.source.to_dict()}]})

    def register(callback=callback, version='v1'):
        service.register_attribution_verifier(f.owner['token'], f.scope, principal_id='destination-reader',
            version=version, tool='fixture.write', schema_version='v1',
            failure_classes=('wrong_argument_value',), readback=callback)
    register()
    return f, outcome, service, reader, proposal, callback, register


def scheduled_classification_fixture(tmp_path):
    f, original, service, reader, _, _, _ = classification_fixture(tmp_path)
    outcome = replace(original, outcome_id='classified-quality')
    f.feedback.schedule(f.owner['token'], f.scope, schedule_id='classified-quality', tasks=(
        {'outcome_id':outcome.outcome_id, 'episode_id':'episode', 'answerable':True},))
    f.simulated_write(outcome, outcome.observations[1])
    f.feedback.report_outcome(f.session, outcome, idempotency_key='classified-quality')
    checked = verify(service, reader, outcome, 'classified-quality')
    proposal = service.propose_attribution(f.session, outcome_sha256=outcome.content_digest,
        invocation_id='call-write', failure_class='wrong_argument_value', reason='Independently compare the source and the write.',
        evidence_ids=(checked['evidence_id'],))
    service.verify_attribution(reader, attribution_id=proposal['attribution_id'], idempotency_key='classified-quality')
    return f, outcome


def test_frozen_quality_keeps_independent_failure_class_on_its_exact_write(tmp_path):
    f, _ = scheduled_classification_fixture(tmp_path)
    report = f.feedback.quality(f.session, schedule_id='classified-quality')
    read, write = report['tasks'][0]['actions']
    assert 'failure_classifications' not in read
    classification = write['failure_classifications'][0]
    assert classification['status'] == 'verified' and classification['failure_class'] == 'wrong_argument_value'
    assert classification['verified_causality'] is False
    assert not write['verified_success'] and report['verified_full_task_success']['numerator'] == 0


def test_independent_source_argument_and_destination_classification_is_retained(tmp_path):
    f, outcome, service, reader, proposal, _, _ = classification_fixture(tmp_path)
    assert proposal['status'] == 'proposed' and not proposal['verified_causality']
    receipt = service.verify_attribution(reader, attribution_id=proposal['attribution_id'], idempotency_key='classify')
    assert receipt['status'] == 'verified'
    assert receipt['claim'] == 'bounded_operational_classification'
    assert receipt['verified_causality'] is False and receipt['qualifies_policy'] is False
    assert receipt['verification_ids']
    assert service.verify_attribution(reader, attribution_id=proposal['attribution_id'], idempotency_key='classify') == receipt
    with f.feedback.store.transaction(f.scope) as tx:
        assert tx.get('attribution', proposal['attribution_id']) == proposal
        assert tx.get('attribution_verification', receipt['receipt_id']) == receipt
    assert receipt['evidence']['proofs']['wrong_argument']['observed'] == 'five days'
    model_view = f.feedback.outcome(f.session, outcome.outcome_id, include_attributions=True)
    assert model_view['attributions'][0]['status'] == 'verified'
    assert 'evidence' not in model_view['attributions'][0]['verifications'][0]
    from atmem.mcp.governed import GovernedMCPServer
    from test_governed_mcp import initialize, request
    server = GovernedMCPServer(f.feedback, f.rag, f.session)
    initialize(server)
    called = server.handle(request('tools/call', {'name':'feedback_outcome',
                                                'arguments':{'outcome_id':outcome.outcome_id}}))
    assert called['result']['structuredContent']['attributions'][0]['status'] == 'verified'
    tools = {v['name'] for v in server.handle(request('tools/list'))['result']['tools']}
    assert 'verify_attribution' not in tools and 'register_attribution_verifier' not in tools


@pytest.mark.parametrize('defect', ['missing_material', 'missing_checks', 'foreign_scope', 'model_judgement'])
def test_labels_partial_checks_and_foreign_material_cannot_certify_attribution(tmp_path, defect):
    f, outcome, service, reader, proposal, callback, register = classification_fixture(tmp_path)
    def invalid(*args, **kwargs):
        result = callback(*args, **kwargs)
        if defect == 'missing_material': return replace(result, evidence={'assertion':True})
        if defect == 'missing_checks': return replace(result, checks=result.checks[:1])
        if defect == 'foreign_scope':
            return replace(result, evidence={**result.evidence, 'scope':{**f.scope.to_dict(), 'subject_id':'bob'}})
        return replace(result, checks=tuple(replace(c, kind='judged') for c in result.checks))
    register(invalid, 'invalid')
    with pytest.raises(FeedbackError, match='missing_evidence|incomplete_attribution_proof'):
        service.verify_attribution(reader, attribution_id=proposal['attribution_id'], idempotency_key='invalid')
    with f.feedback.store.transaction(f.scope) as tx:
        assert not list(tx.iter_kind('attribution_verification'))


def test_writer_cannot_verify_its_own_classification(tmp_path):
    f, _, service, _, proposal, _, _ = classification_fixture(tmp_path)
    f.feedback.grant_agent(f.owner['token'], f.scope, principal_id=f.user['principal_id'],
        operations=('read','report','propose','verify'), expires_at=1_700_010_000)
    with pytest.raises(FeedbackError, match='not_independent'):
        service.verify_attribution(f.session, attribution_id=proposal['attribution_id'], idempotency_key='self')


def test_unrelated_retained_readback_cannot_be_reused_as_source_of_a_label(tmp_path):
    f, outcome, service, reader, proposal, _, _ = classification_fixture(tmp_path)
    other = replace(outcome, outcome_id='other')
    f.feedback.report_outcome(f.session, other, idempotency_key='other')
    wrong = service.propose_attribution(f.session, outcome_sha256=other.content_digest,
        invocation_id='call-write', failure_class='wrong_argument_value', reason='Unbound source',
        evidence_ids=tuple(proposal['evidence_ids']))
    with pytest.raises(FeedbackError, match='unbound_attribution_evidence'):
        service.verify_attribution(reader, attribution_id=wrong['attribution_id'], idempotency_key='unbound')


def test_verifier_revoked_during_readback_cannot_commit_a_classification(tmp_path):
    f, _, service, reader, proposal, callback, register = classification_fixture(tmp_path)
    def revoked(*args, **kwargs):
        result = callback(*args, **kwargs)
        service.revoke_attribution_verifier(f.owner['token'], f.scope, principal_id='destination-reader',
                                            tool='fixture.write', schema_version='v1')
        return result
    register(revoked, 'revoked')
    with pytest.raises(FeedbackError, match='verifier_changed'):
        service.verify_attribution(reader, attribution_id=proposal['attribution_id'], idempotency_key='revoked')


def test_no_call_requires_independent_complete_operation_capture(tmp_path):
    f, original, service, reader, _ = verifier_fixture(tmp_path)
    outcome = replace(original, outcome_id='no-call', run_id='no-call-run', observations=original.observations[:1])
    f.feedback.report_outcome(f.session, outcome, idempotency_key='no-call')
    proposal = service.propose_attribution(f.session, outcome_sha256=outcome.content_digest,
        action_id='write', failure_class='no_call', reason='No call in host report; independent capture required.')
    journal = tmp_path/'closed-independent-operation-journal.json'
    journal.write_text(json.dumps({'run_id':'no-call-run', 'complete':True, 'invocations':[]}))
    def capture(record, observation, proposed, retained, *, deadline):
        assert observation is None
        actual = json.loads(journal.read_text())
        results = {'capture_complete':actual['complete'] and actual['run_id'] == record.run_id,
                   'no_matching_invocation':not actual['invocations']}
        return AttributionReadback('no_call', tuple(ActionCheck(name, 'mechanical',
            'pass' if results[name] else 'fail', 'Read closed independent operation journal')
            for name in ATTRIBUTION_CHECKS['no_call']), {'scope':record.scope.to_dict(),
            'outcome_sha256':record.content_digest, 'invocation_id':None, 'sources':[],
            'proofs':{name:{'method':'closed_operation_journal', 'observed':actual, 'expected':True}
                      for name in results}})
    service.register_attribution_verifier(f.owner['token'], f.scope, principal_id='destination-reader',
        version='capture-v1', tool='fixture.write', schema_version='v1', failure_classes=('no_call',), readback=capture)
    receipt = service.verify_attribution(reader, attribution_id=proposal['attribution_id'], idempotency_key='empty')
    assert receipt['status'] == 'verified' and receipt['invocation_id'] is None
    # Host omission cannot turn an actual backend operation into verified absence.
    journal.write_text(json.dumps({'run_id':'no-call-run', 'complete':True, 'invocations':['hidden-call']}))
    disagreement = service.verify_attribution(reader, attribution_id=proposal['attribution_id'], idempotency_key='hidden')
    assert disagreement['status'] == 'disputed'
    assert service.attributions(reader, outcome_sha256=outcome.content_digest)['classifications'][0]['status'] == 'disputed'
    options = dict(attribution_id=proposal['attribution_id'], receipt_ids=(receipt['receipt_id'],disagreement['receipt_id']),
                   chosen_receipt_id=disagreement['receipt_id'], reason='The complete journal reveals the omitted call.', expected_generation=0)
    with pytest.raises(FeedbackError, match='denied'):
        service.resolve_attribution(f.user['token'],f.scope,**options)
    decision = service.resolve_attribution(f.owner['token'],f.scope,**options)
    assert decision['assurance']=='human_attestation' and decision['qualifies_policy'] is False
    assert decision['selected_verdict'] is False
    assert service.resolve_attribution(f.owner['token'],f.scope,**options)==decision
    view = service.attributions(reader,outcome_sha256=outcome.content_digest)['classifications'][0]
    assert view['status']=='resolved_human' and len(view['verifications'])==2
    with pytest.raises(FeedbackError,match='stale_revision'):
        service.resolve_attribution(f.owner['token'],f.scope,**{**options,'chosen_receipt_id':receipt['receipt_id']})


def test_source_forgetting_removes_classification_lineage_without_deleting_the_outcome(tmp_path):
    from atmem.feedback.recovery import FeedbackRecovery
    f, outcome, service, reader, proposal, _, _ = classification_fixture(tmp_path)
    receipt = service.verify_attribution(reader, attribution_id=proposal['attribution_id'], idempotency_key='classify')
    recovery = FeedbackRecovery(f.feedback)
    preview = recovery.preview_forget(f.owner['token'], f.scope, source_id='law', source_kind='rag')
    recovery.forget(f.owner['token'], f.scope, source_id='law', source_kind='rag',
        preview_sha256=preview['preview_sha256'], confirm_sha256=preview['preview_sha256'])
    assert f.feedback.outcome(f.session, outcome.outcome_id)['outcome'] == outcome.to_dict()
    with f.feedback.store.transaction(f.scope) as tx:
        assert tx.get('attribution', proposal['attribution_id']) is None
        assert tx.get('attribution_verification', receipt['receipt_id']) is None
        assert not list(tx.iter_kind('attribution_lineage'))
    with pytest.raises(FeedbackError, match='denied|forgotten_operation'):
        service.verify_attribution(reader, attribution_id=proposal['attribution_id'], idempotency_key='classify')


@pytest.mark.parametrize('include_fact', [True, False])
def test_delivered_fact_and_application_failure_require_actual_core_exposure(tmp_path, include_fact):
    from hashlib import sha256
    from atmem import Memory
    from atmem.contracts import SourceCaptureRequest, RecallRequest, ContextRequest, ExposureConfirmation
    from atmem.contracts.feedback import SourceRevision
    from test_contracts_v1 import _proposal
    f, original, service, reader, destination = verifier_fixture(tmp_path)
    memory = f.feedback.memory = Memory(':memory:', auto_vectors=False)
    try:
        scope = f.scope.authority_scope()
        fact = 'The fictional filing deadline is ten days.'
        captured = memory.capture_source(SourceCaptureRequest('source-1','capture',scope,fact,
                                                              session_id='session',turn_id='source-turn'))
        admitted = memory.submit_proposal(_proposal(captured.source_sha256, scope=scope,
            fact=fact, fact_key='fictional::filing', sensitivity='personal'))
        record_id = (admitted.record_ids or admitted.candidate_ids)[0]
        record = memory.store.get_record('alice', record_id)
        if record['status'] == 'quarantined':
            memory.promote('alice', record_id, actor='synthetic-owner-confirmation')
            record = memory.store.get_record('alice', record_id)
        candidates = memory.eligible_candidates(RecallRequest('candidates',scope,'filing deadline',signals=('lexical',)))
        assert record_id in [v.record_id for v in candidates.candidates]
        package = memory.prepare_context_v1(ContextRequest('context',candidates.candidate_set_id,scope,
                                                           (record_id,) if include_fact else ()))
        exposure = memory.confirm_exposure_v1(ExposureConfirmation('delivered',package.preparation_id,
                                                                   scope,package.context_sha256,'run'))
        f.feedback.retain_context(f.session, confirmation_id='delivered')
        outcome = replace(original,outcome_id='delivered',context_receipt_id=exposure.receipt_id,delivery='delivered')
        f.simulated_write(outcome, outcome.observations[1])
        f.feedback.report_outcome(f.session,outcome,idempotency_key='delivered')
        checked = verify(service,reader,outcome,'delivered-write')
        proposed = service.propose_attribution(f.session,outcome_sha256=outcome.content_digest,
            invocation_id='call-write',failure_class='delivered_but_not_applied',reason='Compare actual delivered bytes to the write.',
            evidence_ids=(exposure.receipt_id,checked['evidence_id']))
        source = SourceRevision(record_id,record['generation'],sha256(record['content'].encode()).hexdigest())
        def delivered(recorded, observation, proposal, retained, *, deadline):
            context = next(v['value'] for v in retained if 'package' in v['value'])
            actual = destination.read_text()
            results = {'delivery_receipt_valid':context['assurance']=='host_confirmed_exposure',
                'required_fact_delivered':'ten days' in context['package']['context'],
                'fact_missing_from_write':'ten days' not in observation.arguments['body'],
                'effect_correlated':actual == observation.arguments['body']}
            return AttributionReadback('delivered_but_not_applied',tuple(ActionCheck(name,'mechanical',
                'pass' if passed else 'fail','Compare original delivered bytes and exact write') for name,passed in results.items()),
                {'scope':recorded.scope.to_dict(),'outcome_sha256':recorded.content_digest,
                 'invocation_id':observation.invocation_id,'sources':[{'kind':'memory','source':source.to_dict()}],
                 'proofs':{name:{'method':'delivered_bytes_and_destination','observed':{
                     'context':context,'arguments':observation.arguments,'destination':actual},'expected':'ten days'} for name in results}})
        service.register_attribution_verifier(f.owner['token'],f.scope,principal_id='destination-reader',
            version='delivered-v1',tool='fixture.write',schema_version='v1',
            failure_classes=('delivered_but_not_applied',),readback=delivered)
        result = service.verify_attribution(reader,attribution_id=proposed['attribution_id'],idempotency_key='delivered')
        assert result['status'] == ('verified' if include_fact else 'inconclusive')
        assert result['verified_causality'] is False
    finally:
        memory.close()


@pytest.mark.parametrize('complete,target', [(True,'holiday exception'),(False,'holiday exception'),(True,'ten days')])
def test_absence_requires_complete_frozen_scoped_corpus_before_the_actual_operation(tmp_path, complete, target):
    import time
    from atmem.contracts.feedback import ActionRequirement
    from atmem.feedback.verification import Readback
    f, original, service, reader, destination = verifier_fixture(tmp_path)
    with f.feedback.owner_transaction(f.owner['token'],f.scope) as (tx,_):
        documents = [v for v in tx.iter_kind('rag_document') if v['hit']['source_id']==f.source.source_id]
        frozen = {'scope':f.scope.to_dict(),'source':f.source.to_dict(),'documents':documents,
                  'captured_at':time.time(),'complete':complete}
        tx.put('classification_snapshot','before-turn',frozen,expected_revision=0)
    observation = replace(original.observations[1],checks=(ActionCheck('missing_fact','mechanical','fail','Required phrase absent'),))
    outcome = replace(original,outcome_id='absence',required=(ActionRequirement('write','fixture.write','v1','write',('missing_fact',)),),
                      observations=(observation,))
    marker = tmp_path/'actual-operation-start.json'
    marker.write_text(json.dumps({'run_id':outcome.run_id,'turn_id':outcome.turn_id,'started_at':time.time()}))
    f.simulated_write(outcome,observation)
    f.feedback.report_outcome(f.session,outcome,idempotency_key='absence')
    journal = tmp_path/'simulated-backend-journal.json'
    service.register(f.owner['token'],f.scope,principal_id='destination-reader',version='missing-v1',tool='fixture.write',
        schema_version='v1',check_ids=('missing_fact',),binding='effect_receipt',readback=lambda *a,**k:Readback(
            (ActionCheck('missing_fact','mechanical','pass' if target in destination.read_text() else 'fail','Exact required phrase'),),
            {**json.loads(journal.read_text()),'observed':destination.read_text(),'expected':target}))
    checked = service.verify(reader,outcome_id=outcome.outcome_id,outcome_sha256=outcome.content_digest,
                             invocation_id='call-write',idempotency_key='absence')
    proposed = service.propose_attribution(f.session,outcome_sha256=outcome.content_digest,invocation_id='call-write',
        failure_class='source_fact_absent',reason='Absence only within the complete declared fictional corpus.',
        evidence_ids=(checked['evidence_id'],))
    def absence(record,call,proposal,retained,*,deadline):
        with f.feedback._authorized(reader,'verify') as (tx,_):
            snapshot = tx.get('classification_snapshot','before-turn')
        started = json.loads(marker.read_text())
        results = {'complete_authorized_snapshot':snapshot['complete'] and len(snapshot['documents'])==4,
                   'snapshot_precedes_turn':snapshot['captured_at']<=started['started_at'],
                   'required_fact_absent':not any(target in d['hit']['text'] for d in snapshot['documents'])}
        return AttributionReadback('source_fact_absent',tuple(ActionCheck(name,'mechanical','pass' if passed else 'fail',
            'Closed fictional corpus and independently recorded operation start') for name,passed in results.items()),
            {'scope':record.scope.to_dict(),'outcome_sha256':record.content_digest,'invocation_id':call.invocation_id,
             'sources':[{'kind':'rag','source':f.source.to_dict()}],
             'proofs':{name:{'method':'complete_frozen_corpus','observed':{'snapshot':snapshot,'operation_start':started},
                             'expected':target} for name in results}})
    service.register_attribution_verifier(f.owner['token'],f.scope,principal_id='destination-reader',version='absence-v1',
        tool='fixture.write',schema_version='v1',failure_classes=('source_fact_absent',),readback=absence)
    result = service.verify_attribution(reader,attribution_id=proposed['attribution_id'],idempotency_key='absence')
    assert result['status'] == ('verified' if complete and target=='holiday exception' else 'inconclusive')
    assert result['claim']=='bounded_operational_classification' and result['verified_causality'] is False

