"""Real encrypted ledger tests; fixtures are contract evidence, not learning."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json

import pytest

from atmem.feedback.adaptation import AdaptationService, ARMS, FORMAT, Grade, fingerprint, validate_manifest
from atmem.feedback.store import FeedbackError
from rag_fixtures import setup_rag

POLICY={"load":"Inspect relevant original evidence.","offload":"Keep bounded source-linked notes."}
SETTINGS={"model":"fixture","temperature":0}


def setup(tmp_path):
    f=setup_rag(tmp_path)
    cases=[{"id":p,"split":p,"episode":"same-world","input_sha256":fingerprint({"prompt":p}),"target_sha256":fingerprint({"answer":7})} for p in ("train","validation","test")]
    manifest={"format":FORMAT,"corpus":{"id":"fixture","revision":"fixed","sha256":"a"*64,"license":"synthetic","egress":"none","kind":"synthetic_contract"},
              "runtime":{"model":"fixture","endpoint":"none","settings_sha256":fingerprint(SETTINGS),"runner_sha256":"b"*64,"input_usd_per_token":.000001,"output_usd_per_token":.000002},
              "grader":{"id":"strict","sha256":"c"*64},"budget":{"calls":10,"tokens":100000,"usd":1,"seconds":60,"retained_bytes":1000000,"max_output_tokens":64},
              "cases":cases,"hypothesis":"bounded-contract","seed":52}
    def grader(output,target):
        passed=output["answer"]==target["answer"]
        return Grade(passed,1 if passed else 0,{"actual":output["answer"],"expected":target["answer"]})
    service=AdaptationService(f.feedback,grader=grader,grader_id="strict",grader_sha256="c"*64,clock=lambda:1700000000)
    service.create(f.owner["token"],f.scope,"study",manifest,POLICY)
    return f,service,manifest


def trial(f,s,phase,arm="generic",answer=7):
    return s.run_trial(f.owner["token"],f.scope,"study",case_id=phase,arm=arm,public_input={"prompt":phase},target={"answer":7},execute=lambda p,policy,memory:{"answer":answer})


def validation(f,s):
    trial(f,s,"train")
    s.begin_proposal(f.owner["token"],f.scope,"study")
    s.register_revision(f.owner["token"],f.scope,"study",{**POLICY,"load":"Alternative"})
    s.begin_validation(f.owner["token"],f.scope,"study",{**POLICY,"load":"Alternative"},{a:"" if a=="none" else "bounded notes" for a in ARMS})


def test_frozen_selection_separate_hidden_targets_and_no_activation(tmp_path):
    f,s,_=setup(tmp_path)
    validation(f,s)
    trial(f,s,"validation",answer=0)
    trial(f,s,"validation","revised",answer=7)
    assert s.select(f.owner["token"],f.scope,"study")=="revised"
    seen=[]
    for arm in ARMS:
        s.run_trial(f.owner["token"],f.scope,"study",case_id="test",arm=arm,public_input={"prompt":"test"},target={"answer":7},execute=lambda p,policy,memory:(seen.append(p) or {"answer":7}))
    assert seen==[{"prompt":"test"}]*4
    report=s.report(f.owner["token"],f.scope,"study",close=True)
    assert report["arms"]["revised"]["correct"]==1
    assert report["paired_correctness"]["status"]=="inconclusive" # single correlated world
    assert report["activation"]=="not_authorized"
    assert report["production_qualification"]=="inconclusive"
    with pytest.raises(FeedbackError,match="invalid_study_phase"):
        s.begin_validation(f.owner["token"],f.scope,"study",POLICY,{a:"" for a in ARMS})


def test_ties_keep_incumbent_and_final_cannot_select_again(tmp_path):
    f,s,_=setup(tmp_path);validation(f,s)
    for a in ("generic","revised"):trial(f,s,"validation",a)
    assert s.select(f.owner["token"],f.scope,"study")=="generic"
    with pytest.raises(FeedbackError,match="invalid_study_phase"):s.select(f.owner["token"],f.scope,"study")


def test_owner_scope_before_decryption_and_ciphertext_retention(tmp_path):
    f,s,_=setup(tmp_path)
    with pytest.raises(FeedbackError,match="denied"):s.inspect(f.user["token"],f.scope,"study")
    with pytest.raises(FeedbackError,match="denied"):s.inspect(f.owner["token"],replace(f.scope,subject_id="bob"),"study")
    canary="PRIVATE-STUDY-CANARY-XYZ"
    key=s.retain(f.owner["token"],f.scope,"study",{"trace":canary})
    for p in tmp_path.rglob('*'):
        if p.is_file():assert canary.encode() not in p.read_bytes()
    with f.feedback.owner_transaction(f.owner["token"],f.scope) as (tx,_):
        assert tx.get("adaptation_evidence",key)["content"]["trace"]==canary


def test_persisted_pending_attempt_survives_restart_and_cannot_retry(tmp_path):
    f,s,_=setup(tmp_path)
    def crash(*args):raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        s.run_trial(f.owner["token"],f.scope,"study",case_id="train",arm="generic",public_input={"prompt":"train"},target={"answer":7},execute=crash)
    reopened=AdaptationService(f.feedback,grader=s.grader,grader_id="strict",grader_sha256="c"*64,clock=lambda:1700000000)
    with pytest.raises(FeedbackError,match="trial_already_reserved"):trial(f,reopened,"train")
    with pytest.raises(FeedbackError,match="incomplete_phase"):s.begin_proposal(f.owner["token"],f.scope,"study")


def test_changed_inputs_and_early_final_refused_before_execution(tmp_path):
    f,s,_=setup(tmp_path)
    def forbidden(*a):pytest.fail("must not execute")
    for phase,prompt in (("test","test"),("train","modified")):
        with pytest.raises(FeedbackError):s.run_trial(f.owner["token"],f.scope,"study",case_id=phase,arm="generic",public_input={"prompt":prompt},target={"answer":7},execute=forbidden)


def test_closed_manifest_split_and_numeric_validation(tmp_path):
    f,s,m=setup(tmp_path)
    for mutate in (lambda x:x["cases"][1].update(input_sha256=x["cases"][0]["input_sha256"]),
                   lambda x:x["budget"].update(usd=float('nan')),lambda x:x.update(activation=True),
                   lambda x:x["budget"].update(calls=True),lambda x:x["grader"].update(sha256="bad")):
        v=deepcopy(m);mutate(v)
        with pytest.raises(ValueError):validate_manifest(v)


def test_call_reservation_consumes_budget_after_uncertain_failure(tmp_path):
    f,s,m=setup(tmp_path)
    with f.feedback.owner_transaction(f.owner["token"],f.scope) as (tx,_):
        row=s._study(tx,"study");row["manifest"]["budget"]["calls"]=1;s._put(tx,"study",row)
    payload={**SETTINGS,"max_tokens":16,"messages":[{"role":"user","content":"test"}]}
    def bad(payload):raise RuntimeError("secret-upstream-body")
    with pytest.raises(FeedbackError,match="^provider_failed$"):s.call(f.owner["token"],f.scope,"study",payload,bad)
    assert s.inspect(f.owner["token"],f.scope,"study")["calls"]==1
    with pytest.raises(FeedbackError,match="study_call_budget_exhausted"):
        s.call(f.owner["token"],f.scope,"study",payload,lambda p:pytest.fail("must not call"))


def test_successful_call_settles_actual_usage_and_preserves_exact_exchange(tmp_path):
    f,s,_=setup(tmp_path)
    payload={**SETTINGS,"max_tokens":16,"messages":[{"role":"user","content":"exact query"}]}
    result={"response":{"answer":"exact answer"},"prompt_tokens":4,"completion_tokens":3,"usd":.00001}
    assert s.call(f.owner["token"],f.scope,"study",payload,lambda p:result)==result["response"]
    assert s.inspect(f.owner["token"],f.scope,"study")["tokens"]==7
    with f.feedback.owner_transaction(f.owner["token"],f.scope) as (tx,_):
        call=next(tx.iter_kind("adaptation_call"));assert call["request"]==payload and call["result"]==result


def test_runtime_grader_and_budget_changes_fail_closed(tmp_path):
    f,s,_=setup(tmp_path)
    changed=AdaptationService(f.feedback,grader=s.grader,grader_id="different",grader_sha256="d"*64)
    with pytest.raises(FeedbackError,match="grader_changed"):changed.inspect(f.owner["token"],f.scope,"study")
    with pytest.raises(FeedbackError,match="runtime_changed"):
        s.call(f.owner["token"],f.scope,"study",{"model":"other","max_tokens":16},lambda p:pytest.fail("no call"))
    s.clock=lambda:1700000100
    with pytest.raises(FeedbackError,match="study_time_budget_exhausted"):trial(f,s,"train")


def test_forged_model_pass_and_missing_trials_do_not_count_as_verified_success(tmp_path):
    f,s,_=setup(tmp_path);validation(f,s)
    for a in ("generic","revised"):trial(f,s,"validation",a)
    s.select(f.owner["token"],f.scope,"study")
    s.run_trial(f.owner["token"],f.scope,"study",case_id="test",arm="revised",public_input={"prompt":"test"},target={"answer":7},execute=lambda *a:{"answer":0,"correct":True,"reward":1})
    report=s.report(f.owner["token"],f.scope,"study")
    assert report["arms"]["revised"]["correct"]==0
    assert report["arms"]["generic"]["unknown"]==1
    assert report["arms"]["generic"]["scheduled"]==1


def test_one_revision_and_one_call_per_proposal_purpose_survive_restart(tmp_path):
    f,s,_=setup(tmp_path)
    trial(f,s,"train");s.begin_proposal(f.owner["token"],f.scope,"study")
    payload={**SETTINGS,"max_tokens":16,"messages":[{"role":"user","content":"propose"}]}
    response={"response":{"load":"advice","offload":"notes"},"prompt_tokens":4,"completion_tokens":3,"usd":.00001}
    s.call(f.owner["token"],f.scope,"study",payload,lambda p:response,purpose="revision")
    with pytest.raises(FeedbackError,match="proposal_call_already_reserved"):
        s.call(f.owner["token"],f.scope,"study",payload,lambda p:pytest.fail("no second proposal"),purpose="revision")
    s.register_revision(f.owner["token"],f.scope,"study",POLICY)
    with pytest.raises(FeedbackError,match="revision_already_registered_or_closed"):
        s.register_revision(f.owner["token"],f.scope,"study",{**POLICY,"load":"another"})
    summary=s.partial_report(f.owner["token"],f.scope,"study")
    assert summary["phase"]=="proposal" and summary["resources"]["calls"]==1


def test_post_call_deadline_does_not_accept_late_response(tmp_path):
    f,s,_=setup(tmp_path)
    payload={**SETTINGS,"max_tokens":16,"messages":[{"role":"user","content":"test"}]}
    def late(p):
        s.clock=lambda:1700000100
        return {"response":{"answer":7},"prompt_tokens":4,"completion_tokens":3,"usd":.00001}
    with pytest.raises(FeedbackError,match="provider_failed"):s.call(f.owner["token"],f.scope,"study",payload,late)
    summary=s.partial_report(f.owner["token"],f.scope,"study")
    assert summary["unknown_calls"]==1 and summary["resources"]["calls"]==1
