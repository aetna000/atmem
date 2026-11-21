from copy import deepcopy
import json
from pathlib import Path

import pytest

from atmem.feedback.baseline import BaselineError
from atmem.feedback.qualification import QualificationService
from atmem.feedback.store import FeedbackError
from test_feedback_actions import actions_fixture


def test_frozen_synthetic_qualification_is_inconclusive_and_bounded(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    manifest = json.loads((Path(__file__).parent/"fixtures/feedback/baseline-manifest.json").read_text())
    service = QualificationService(f.feedback)
    frozen = service.freeze(f.owner["token"], f.scope, manifest, artifact_sha256="a"*64)
    assert not frozen["execution_authorized"] and not frozen["paid_calls_authorized"]
    receipt = service.evaluate(f.owner["token"], f.scope, manifest_sha256=frozen["manifest_sha256"], idempotency_key="one")
    assert receipt["decision"] == "inconclusive"
    assert receipt["metrics"]["unknown_items"] == 18
    assert receipt["metrics"]["model_calls"] == 0
    assert service.evaluate(f.owner["token"], f.scope, manifest_sha256=frozen["manifest_sha256"], idempotency_key="one") == receipt
    for key in ("two", "three"):
        service.evaluate(f.owner["token"], f.scope, manifest_sha256=frozen["manifest_sha256"], idempotency_key=key)
    with pytest.raises(FeedbackError, match="attempt_budget_exhausted"):
        service.evaluate(f.owner["token"], f.scope, manifest_sha256=frozen["manifest_sha256"], idempotency_key="four")
    with pytest.raises(FeedbackError, match="denied"):
        service.evaluate(f.user["token"], f.scope, manifest_sha256=frozen["manifest_sha256"], idempotency_key="forged")


def test_freeze_does_not_accept_a_paid_budget_or_contaminated_split(tmp_path):
    f, _ = actions_fixture(tmp_path)
    manifest = json.loads((Path(__file__).parent/"fixtures/feedback/baseline-manifest.json").read_text())
    service = QualificationService(f.feedback)
    for mutate in (lambda m: m["budget"].update(usd=1),
                   lambda m: m["tasks"][1].update(episode=m["tasks"][0]["episode"]),
                   lambda m: m["tasks"][0].update(verified_success=True)):
        changed = deepcopy(manifest)
        mutate(changed)
        with pytest.raises(BaselineError):
            service.freeze(f.owner["token"], f.scope, changed, artifact_sha256="a"*64)


def test_failed_evaluations_are_charged_before_replay_and_same_key_cannot_retry_them(tmp_path, monkeypatch):
    f, _ = actions_fixture(tmp_path)
    manifest = json.loads((Path(__file__).parent/"fixtures/feedback/baseline-manifest.json").read_text())
    manifest["budget"]["seconds"] = 1
    ticks = [0]
    def timer():
        ticks[0] += 2
        return ticks[0]
    service = QualificationService(f.feedback, timer=timer)
    frozen = service.freeze(f.owner["token"], f.scope, manifest, artifact_sha256="a"*64)
    options = dict(manifest_sha256=frozen["manifest_sha256"], idempotency_key="one")
    with pytest.raises(FeedbackError, match="time_budget_exhausted"):
        service.evaluate(f.owner["token"], f.scope, **options)
    with monkeypatch.context() as patch:
        patch.setattr(service, "_compute", lambda *a,**k:pytest.fail("failed attempt was replayed"))
        with pytest.raises(FeedbackError, match="time_budget_exhausted"):
            service.evaluate(f.owner["token"], f.scope, **options)
    for key in ("two", "three"):
        with pytest.raises(FeedbackError, match="time_budget_exhausted"):
            service.evaluate(f.owner["token"], f.scope, **{**options, "idempotency_key":key})
    with pytest.raises(FeedbackError, match="attempt_budget_exhausted"):
        service.evaluate(f.owner["token"], f.scope, **{**options, "idempotency_key":"four"})
    with f.feedback.store.transaction(f.scope) as tx:
        assert tx.list("qualification") == []
        assert tx.list("evaluation_budget") == [{"attempts":3}]
        assert len(tx.list("evaluation_attempt")) == 3
        assert all(r["status"] == "failed" for r in tx.list("evaluation_attempt"))


def test_process_loss_after_reservation_stays_unknown_and_consumes_attempt_after_restart(tmp_path, monkeypatch):
    from atmem.feedback.service import FeedbackService
    f, _ = actions_fixture(tmp_path)
    manifest = json.loads((Path(__file__).parent/"fixtures/feedback/baseline-manifest.json").read_text())
    service = QualificationService(f.feedback)
    frozen = service.freeze(f.owner["token"], f.scope, manifest, artifact_sha256="a"*64)
    options = dict(manifest_sha256=frozen["manifest_sha256"], idempotency_key="process-loss")
    def crash(*args, **kwargs):
        raise KeyboardInterrupt("synthetic process loss after durable admission")
    monkeypatch.setattr(service, "_compute", crash)
    with pytest.raises(KeyboardInterrupt):
        service.evaluate(f.owner["token"], f.scope, **options)
    restored = QualificationService(FeedbackService(f.evidence, clock=f.feedback.clock))
    with pytest.raises(FeedbackError, match="evaluation_inflight_or_unknown"):
        restored.evaluate(f.owner["token"], f.scope, **options)
    with f.feedback.store.transaction(f.scope) as tx:
        assert tx.list("evaluation_budget") == [{"attempts":1}]
        assert tx.list("evaluation_attempt")[0]["status"] == "pending"


def bound_evaluation_fixture(tmp_path, *, manifest_identity=None, manifest_version='v1', change=None, disk_budget=None):
    """Actual encrypted receipts from a separate backend-journal reader.

    These are synthetic contract cases: even a perfect result stays inconclusive.
    The reader gets evaluation provenance from the backend, not model arguments.
    """
    from dataclasses import replace
    from hashlib import sha256
    from atmem.feedback.verification import Readback
    from test_feedback_verification import verifier_fixture, verify
    f, original, verifier, reader, destination = verifier_fixture(tmp_path)
    manifest = json.loads((Path(__file__).parent/'fixtures/feedback/baseline-manifest.json').read_text())
    task = deepcopy(manifest['tasks'][0])
    task.update(id='single', split='test', episode='episode', paraphrase_group='group',
                input_sha256=sha256(b'Write the ten-day filing deadline.').hexdigest(),
                actions=[{'id':'write','tool':'fixture.write','kind':'write','checks':['fact','destination']}],
                verification={'identity':manifest_identity or f.feedback._principal(reader.credential).principal_id,
                              'method':'independent_readback','evidence':'backend-journal-v1'})
    manifest['tasks'] = [task]
    if disk_budget is not None:
        manifest['budget']['disk_bytes'] = disk_budget
    manifest['versions']['verifier'] = manifest_version
    journal = tmp_path/'simulated-backend-journal.json'
    registered_key = next(iter(verifier._handlers))
    original_readback = verifier._handlers[registered_key]
    def readback(outcome, observation, *, deadline):
        actual = original_readback(outcome, observation, deadline=deadline)
        provenance = json.loads(journal.read_text())
        return Readback(actual.checks, {**actual.evidence,
            'evaluation':provenance.get('evaluation'),
            'evaluation_input':provenance.get('evaluation_input')})
    verifier.register(f.owner['token'], f.scope, principal_id=f.feedback._principal(reader.credential).principal_id, version='v1',
                      tool='fixture.write', schema_version='v1', check_ids=('fact','destination'),
                      readback=readback, binding='effect_receipt')
    qualification = QualificationService(f.feedback)
    frozen = qualification.freeze(f.owner['token'], f.scope, manifest, artifact_sha256='a'*64)
    for arm in ('native','atmem','candidate'):
        outcome = replace(original, outcome_id=f"eval:{frozen['manifest_sha256']}:{arm}:single",
                          required=(original.required[1],),
                          observations=(replace(original.observations[1], arguments={'body':'ten days'}),))
        f.feedback.report_outcome(f.session, outcome, idempotency_key=arm)
        f.simulated_write(outcome, outcome.observations[0])
        independent = json.loads(journal.read_text())
        config = manifest['candidate'] if arm=='candidate' else manifest['baselines'][arm]
        independent['evaluation'] = {'manifest_sha256':frozen['manifest_sha256'], 'task_id':'single', 'arm':arm,
            'input_sha256':task['input_sha256'], 'configuration_sha256':config['configuration_sha256'],
            'memory_sha256':config['memory_sha256'], 'versions':manifest['versions'],
            'environment':manifest['environment'], 'evidence_contract':'backend-journal-v1'}
        independent['evaluation_input'] = 'Write the ten-day filing deadline.'
        if change is not None and arm=='candidate':
            change(independent)
        journal.write_text(json.dumps(independent))
        verify(verifier, reader, outcome, key=arm)
    return f, qualification, frozen, verifier, reader, readback


def test_frozen_independent_reader_and_original_trial_evidence_are_required(tmp_path):
    f, service, frozen, _, _, _ = bound_evaluation_fixture(tmp_path)
    receipt = service.evaluate(f.owner['token'], f.scope,
                              manifest_sha256=frozen['manifest_sha256'], idempotency_key='bound')
    assert receipt['decision'] == 'inconclusive'  # synthetic is not efficacy evidence
    assert receipt['metrics']['unknown_items'] == 0
    assert receipt['metrics']['trial_binding_count'] == 3
    assert all(arm['numerator']==1 for arm in receipt['metrics']['arms'].values())
    with f.feedback.store.transaction(f.scope) as tx:
        trials = list(tx.iter_kind('evaluation_trial'))
        assert len(trials)==3 and all(len(t['receipt_ids'])==1 for t in trials)
        assert all(tx.get('outcome_revision',t['outcome_sha256']) is not None for t in trials)


@pytest.mark.parametrize('change', [
    lambda j:j.update(evaluation_input='A different benchmark question.'),
    lambda j:j['evaluation'].update(arm='atmem'),
    lambda j:j['evaluation'].update(configuration_sha256='f'*64),
    lambda j:j['evaluation'].update(memory_sha256='f'*64),
    lambda j:j['evaluation'].update(environment={'python':'other','os':'other','hardware':'other'}),
    lambda j:j['evaluation'].update(versions={'reader':'new'}),
    lambda j:j.pop('evaluation'),
])
def test_matching_action_success_cannot_substitute_for_trial_provenance(tmp_path, change):
    f, service, frozen, _, _, _ = bound_evaluation_fixture(tmp_path, change=change)
    receipt=service.evaluate(f.owner['token'],f.scope,
                            manifest_sha256=frozen['manifest_sha256'],idempotency_key='mismatch')
    assert receipt['decision']=='inconclusive'
    assert receipt['metrics']['arms']['atmem']['numerator']==1
    assert receipt['metrics']['arms']['candidate']['numerator']==0
    assert receipt['metrics']['unknown_items']==1
    assert receipt['metrics']['rejected_verification_receipts']==1


@pytest.mark.parametrize('option', ['identity','version','revoked','reregistered'])
def test_different_revoked_or_replaced_readers_do_not_qualify_frozen_comparison(tmp_path, option):
    f, service, frozen, verifier, reader, readback=bound_evaluation_fixture(tmp_path,
        manifest_identity='a-different-reader' if option=='identity' else None,
        manifest_version='different-version' if option=='version' else 'v1')
    if option=='revoked':
        verifier.revoke(f.owner['token'],f.scope,principal_id=f.feedback._principal(reader.credential).principal_id,
                        tool='fixture.write',schema_version='v1')
    if option=='reregistered':
        verifier.register(f.owner['token'],f.scope,principal_id=f.feedback._principal(reader.credential).principal_id,version='v1',
                          tool='fixture.write',schema_version='v1',check_ids=('fact','destination'),
                          readback=readback,binding='effect_receipt')
    receipt=service.evaluate(f.owner['token'],f.scope,
                            manifest_sha256=frozen['manifest_sha256'],idempotency_key='reader-change')
    assert receipt['decision']=='inconclusive'
    assert receipt['metrics']['unknown_items']==3
    assert all(arm['numerator']==0 for arm in receipt['metrics']['arms'].values())


def test_disputed_independent_readbacks_cannot_be_hidden_by_a_successful_trial(tmp_path):
    from atmem.contracts.feedback import OutcomeRecord
    from test_feedback_verification import verify
    f, service, frozen, verifier, reader, _=bound_evaluation_fixture(tmp_path)
    key=f"eval:{frozen['manifest_sha256']}:candidate:single"
    outcome=OutcomeRecord.from_dict(f.feedback.outcome(f.session,key)['outcome'])
    (tmp_path/'simulated-destination.txt').write_text('A contradictory later state.')
    verify(verifier,reader,outcome,key='contradictory-readback')
    result=service.evaluate(f.owner['token'],f.scope,
                           manifest_sha256=frozen['manifest_sha256'],idempotency_key='disputed')
    assert result['metrics']['unknown_items']==1
    assert result['metrics']['arms']['candidate']['numerator']==0
    with f.feedback.store.transaction(f.scope) as tx:
        trial=next(t for t in tx.iter_kind('evaluation_trial') if t['outcome_id']==key)
        assert trial['disputed'] and len(trial['receipt_ids'])==2
        assert all(tx.get('verification',receipt) is not None for receipt in trial['receipt_ids'])


def test_trial_bindings_share_the_receipt_disk_ceiling_and_failed_publication_is_atomic(tmp_path):
    from atmem.core.canonical import canonical_json
    measure=tmp_path/'measure'
    measure.mkdir()
    first, service, frozen, _, _, _=bound_evaluation_fixture(measure)
    measured=service.evaluate(first.owner['token'],first.scope,
                              manifest_sha256=frozen['manifest_sha256'],idempotency_key='measure')
    # The receipt itself fits, but its three actual retained trial bindings do
    # not. An implementation charging only report bytes would incorrectly pass.
    assert measured['metrics']['trial_binding_bytes'] > 100
    limit=len(canonical_json(measured).encode())+100
    bounded=tmp_path/'bounded'
    bounded.mkdir()
    f, service, frozen, _, _, _=bound_evaluation_fixture(bounded,disk_budget=limit)
    with pytest.raises(FeedbackError,match='disk_budget_exhausted'):
        service.evaluate(f.owner['token'],f.scope,
                         manifest_sha256=frozen['manifest_sha256'],idempotency_key='disk')
    with f.feedback.store.transaction(f.scope) as tx:
        assert list(tx.iter_kind('qualification'))==[]
        assert list(tx.iter_kind('evaluation_trial'))==[]
        assert list(tx.iter_kind('evaluation_attempt'))[0]['status']=='failed'
