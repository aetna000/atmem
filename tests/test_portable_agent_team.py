import concurrent.futures
import json
import os

import pytest

from atmem.agent_team.client import TeamClient
from atmem.agent_team.outcomes import outcome
from atmem.control.agent_team import execute, history
from atmem.evidence import CaptureMode, EvidenceRole, EvidenceScope, EvidencePrincipal
from tools.team_qualification.workspace import Project, QUESTION


@pytest.fixture
def project(tmp_path, monkeypatch):
    pytest.importorskip("sqlcipher3")
    monkeypatch.setenv("ATMEM_HOME", str(tmp_path / "home"))
    p = Project(tmp_path)
    p.serve()
    try:
        for host in ("openclaw", "hermes", "mcp"):
            p.bind(host)
        yield p
    finally:
        p.close()


def client(p, host):
    return TeamClient.from_file(p.paths[host], host)


def offer(p, key="test", **extra):
    return client(p, "openclaw").call(
        "offer", {"question": QUESTION, "recipient": "team:hermes:reviewer", "request_id": key, **extra}
    )


def get(p, key):
    return history(p.manager, lambda: p.session, {"action": "get", "run_id": key})


def test_receipt_scope_replay_concurrency_and_delete(project):
    p = project
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        offers = list(pool.map(lambda _: offer(p), range(2)))
    assert offers[0] == offers[1] and offers[0]["outcome"] == "offered"
    args = {"run_id": offers[0]["run_id"]}
    with pytest.raises(ValueError):
        offer(p, question="Who?")
    with pytest.raises(PermissionError):
        client(p, "mcp").call("receive", args)
    p.restart()
    receiver = client(p, "hermes")
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        deliveries = list(pool.map(lambda _: receiver.call("receive", args), range(2)))
    assert deliveries[0] == deliveries[1] and "AX-100" in deliveries[0]["passages"][0]["text"]
    body = {**args, "delivery_id": deliveries[0]["delivery_id"], "quote": "AX-100"}
    with pytest.raises(PermissionError):
        receiver.call("complete", {**body, "delivery_id": "wrong"})
    with pytest.raises(ValueError):
        receiver.call("complete", {**body, "quote": "outside evidence"})
    assert receiver.call("complete", body) == receiver.call("complete", body)
    with pytest.raises(ValueError):
        receiver.call("complete", {**body, "quote": "AX"})
    run = get(p, args["run_id"])
    assert [s["role"] for s in run["steps"]] == ["offer", "receive", "complete"]
    assert run["steps"][2]["parent_step_id"] == run["steps"][1]["step_id"]
    assert run["input_tokens"] is None and run["steps"][2]["provenance"][0]["source_id"] == "routing-v1"
    outsider = EvidencePrincipal(
        "wrong", EvidenceRole.ADMINISTRATOR, EvidenceScope("local", p.access.subject_id, "other")
    )
    with pytest.raises(PermissionError):
        p.manager.evidence_service().delete_run(
            outsider, args["run_id"], confirmation="DELETE " + args["run_id"]
        )
    p.manager.evidence_service().delete_run(
        p.owner, args["run_id"], confirmation="DELETE " + args["run_id"]
    )
    assert history(p.manager, lambda: p.session, {"action": "list"})["runs"] == []
    with pytest.raises(ValueError, match="deleted"):
        offer(p)


def test_correction_between_offer_delivery_and_completion(project):
    p = project
    args = {"run_id": offer(p)["run_id"]}
    waiting = {"run_id": offer(p, "waiting")["run_id"]}
    recipient = client(p, "hermes")
    first = recipient.call("receive", args)
    p.remember("routing-v2", "My Atlas routing code is AX-745.")
    withheld = recipient.call("complete", {**args, "delivery_id": first["delivery_id"], "quote": "AX-100"})
    assert withheld["outcome"] == "withheld" and "passages" not in withheld
    assert recipient.call("receive", waiting)["outcome"] == "withheld"
    assert recipient.call("receive", args)["outcome"] == "withheld"
    fresh = offer(p, "fresh", rerun_of=args["run_id"])
    assert "AX-745" in recipient.call("receive", {"run_id": fresh["run_id"]})["passages"][0]["text"]
    with pytest.raises(ValueError):
        offer(p, "changed-question", question="What is my color?", rerun_of=args["run_id"])


def test_revoked_wrong_host_scope_and_disabled_capture(project):
    p = project
    args = {"run_id": offer(p)["run_id"]}
    from atmem.agent_team.portable import dispatch

    raw = json.loads(p.paths["hermes"].read_text())
    with pytest.raises(PermissionError):
        dispatch(p.manager, raw["token"], "receive", args, expected_host="openclaw")
    with pytest.raises(PermissionError):
        TeamClient.from_file(p.paths["hermes"], "langgraph")
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError

    with pytest.raises(HTTPError) as err:
        urlopen(
            Request(
                p.endpoint + "/v1/memories", data=b"{}", headers={"Authorization": "Bearer " + raw["token"]}
            )
        )
    assert err.value.code == 403
    service = p.manager.evidence_service()
    outsider = service.grant(
        p.owner, principal_id="team:hermes:outsider", role=EvidenceRole.TEAM_HOST, scope=p.access
    )
    with pytest.raises(PermissionError):
        dispatch(p.manager, outsider["token"], "inbox", {})
    service.revoke(p.owner, principal_id="team:hermes:reviewer")
    with pytest.raises(PermissionError):
        client(p, "hermes").call("receive", args)
    service.set_capture_mode(p.owner, CaptureMode.METADATA)
    with pytest.raises(PermissionError):
        offer(p, "disabled")
    os.chmod(p.paths["openclaw"], 0o644)
    if os.name == "posix":
        with pytest.raises(PermissionError):
            client(p, "openclaw")


def test_outcome_provenance_junit_and_cross_workspace(project):
    p = project
    run = get(p, offer(p)["run_id"])
    xml = '<testsuite><testcase classname="routing" name="correct"><failure/></testcase></testsuite>'
    data = {
        "kind": "test",
        "reference": "CI-12",
        "classname": "routing",
        "test_name": "correct",
        "junit": xml,
        "step_id": run["steps"][0]["step_id"],
        "status": "passed",
    }
    arg = {"action": "attach", "run_id": run["run_id"], "outcome": data}
    for _ in range(2):
        attached = history(p.manager, lambda: p.session, arg)
        assert len(attached["outcomes"]) == 1 and attached["outcomes"][0]["status"] == "failed"
        assert "junit" not in attached["outcomes"][0]
    assert (
        history(p.manager, lambda: p.session, {"action": "list", "outcome_ref": "ci-12"})["runs"][0][
            "run_id"
        ]
        == run["run_id"]
    )
    for changes in (
        {"junit": "<!DOCTYPE foo>" + xml},
        {"junit": "<broken"},
        {"test_name": "absent"},
        {"step_id": "foreign"},
        {"url": "javascript:alert(1)"},
        {"url": "https://name:pwd@example.org"},
    ):
        with pytest.raises(ValueError):
            outcome({**data, **changes}, run, "owner")
    for kind, state in (("ticket", "closed"), ("pull_request", "merged"), ("incident", "resolved")):
        report = {"kind": kind, "status": state, "reference": "REF-1", "step_id": data["step_id"]}
        item = history(p.manager, lambda: p.session, {**arg, "outcome": report})["outcomes"][-1]
        assert item["verification"] == "human_reported" and item["status"] == state
    account = dict(p.session["account"], role="investigator")
    with pytest.raises(PermissionError):
        history(p.manager, lambda: {"account": account}, arg)
    account["scope"] = {**p.access.to_dict(), "workspace_id": "other"}
    with pytest.raises(PermissionError):
        history(p.manager, lambda: {"account": account}, {"action": "get", "run_id": run["run_id"]})


def test_dashboard_rerun_uses_new_revision_without_rewriting_original(project, monkeypatch):
    from atmem.agent_team.local import LocalAgents, AgentReply

    monkeypatch.setattr(LocalAgents, "ensure_available", lambda self: None)

    monkeypatch.setattr(
        LocalAgents,
        "invoke",
        lambda self, role, q, e: AgentReply("AX-745" if "AX-745" in e else "AX-100", 31, 4),
    )
    first = execute(project.manager, lambda: project.session, {"question": QUESTION})
    assert first["archived"] and first["policy"] == "single" and first["answer"] == "AX-100"
    project.remember("routing-v2", "My Atlas routing code is AX-745.")
    second = execute(project.manager, lambda: project.session, {"rerun_of": first["run_id"]})
    assert second["answer"] == "AX-745" and second["source_ids"] == ["routing-v2"]
    assert get(project, first["run_id"])["answer"] == "AX-100"
    comparisons = {r["metric"]: r for r in get(project, second["run_id"])["comparison"]}
    assert comparisons["answer"]["before"] == "AX-100" and comparisons["cost_microusd"]["before"] is None
    project.manager.evidence_service().set_capture_mode(project.owner, CaptureMode.OFF)
    ephemeral = execute(project.manager, lambda: project.session, {"question": QUESTION})
    assert ephemeral["answer"] == "AX-745" and not ephemeral["archived"]


def test_source_bound_reviewer_and_observed_reader_cost(project):
    p = project
    sender, reader = client(p, "openclaw"), client(p, "hermes")
    prepared = sender.call("review", {"question": QUESTION})
    review = {k: prepared[k] for k in ("evidence_sha256", "generation")}
    review.update(
        quote="AX-100",
        usage={"input_tokens": 20, "output_tokens": 3, "cost_microusd": 17, "model_calls": 1},
    )
    prices = {"input_usd_per_million": "1.25", "output_usd_per_million": "5"}
    with pytest.raises(ValueError):
        offer(p, review={**review, "evidence_sha256": "fake"})
    with pytest.raises(ValueError):
        offer(p, review={**review, "quote": "AX-700"})
    args = {
        "run_id": offer(p, review=review, reader_model="fixture-reader", reader_pricing=prices)["run_id"]
    }
    delivery = reader.call("receive", args)
    assert delivery["reviewer_quote"] == "AX-100" and delivery["reader_pricing"] == prices
    usage = {
        "input_tokens": 80,
        "output_tokens": 10,
        "cost_microusd": 148,
        "model": "fixture-reader",
        "model_calls": 1,
    }
    body = {**args, "delivery_id": delivery["delivery_id"], "quote": "AX-100", "usage": usage}
    with pytest.raises(ValueError):
        reader.call("complete", {**body, "quote": "routing code"})
    with pytest.raises(ValueError):
        reader.call("complete", {**body, "usage": {**usage, "model": "other"}})
    reader.call("complete", body)
    run = get(p, args["run_id"])
    assert (run["input_tokens"], run["output_tokens"], run["model_calls"], run["cost_microusd"]) == (
        100,
        13,
        2,
        165,
    )
    assert (
        run["estimated_reader_cost_microusd"],
        run["reported_reader_cost_microusd"],
        run["reader_cost_delta_microusd"],
    ) == (150, 148, -2)


def test_capture_consent_change_during_model_call_leaves_no_archive(project, monkeypatch):
    from atmem.agent_team.local import LocalAgents, AgentReply

    monkeypatch.setattr(LocalAgents, "ensure_available", lambda self: None)

    def change_capture(*args):
        service = project.manager.evidence_service()
        service.set_capture_mode(project.owner, CaptureMode.OFF)
        service.set_capture_mode(project.owner, CaptureMode.FULL)
        return AgentReply("AX-100", 20, 2)

    monkeypatch.setattr(LocalAgents, "invoke", change_capture)
    result = execute(project.manager, lambda: project.session, {"question": QUESTION})
    assert result["answer"] == "AX-100" and result["archived"] is False
    assert not history(project.manager, lambda: project.session, {"action": "list"})["runs"]


def test_grant_cli_creates_a_host_bound_owner_only_file(project, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from atmem.agent_team import __main__ as provision

    identity = project.manager.identity_service()
    first = identity.bootstrap()
    initial = identity.login("administrator", first["password"])
    password = "TemporaryLocal!Passphrase298"
    identity.change_password(initial["session_token"], first["password"], password)
    monkeypatch.setattr(provision, "getpass", lambda _: password)
    path = tmp_path / "bound-graph.json"
    args = SimpleNamespace(
        state=project.state_path,
        endpoint=project.endpoint,
        agent="graph",
        host="langgraph",
        username="administrator",
        workspace=project.access.workspace_id,
        binding=path,
        account=None,
    )
    provision.grant(args)
    assert TeamClient.from_file(path, "langgraph").call("inbox", {}) == {"runs": []}
    with pytest.raises(FileExistsError):
        provision.grant(args)
    assert TeamClient.from_file(path, "langgraph").call("inbox", {}) == {"runs": []}


def test_original_excerpt_uses_unicode_offsets_and_only_recorded_references(project):
    p = project
    sentence = "My Astral reviewer is Zoë."
    p.remember("astral-source", sentence)
    run = get(p, offer(p, "unicode", question="What is my Astral reviewer?")["run_id"])
    args = {
        "action": "source",
        "run_id": run["run_id"],
        "step_id": run["steps"][0]["step_id"],
        "source_index": 0,
    }
    ref = history(p.manager, lambda: p.session, args)
    assert ref["status"] == "verified" and ref["excerpt"] == sentence
    assert ref["end_offset"] == len(sentence) < len(sentence.encode())
    with pytest.raises(ValueError):
        history(p.manager, lambda: p.session, {**args, "source_index": -1})
    with pytest.raises(ValueError):
        history(p.manager, lambda: p.session, {**args, "source_id": "other-source"})
    p.manager.transition("shadow", actor="synthetic operator")
    with pytest.raises(PermissionError):
        history(p.manager, lambda: p.session, args)
    assert get(p, run["run_id"])["steps"][0]["provenance"][0]["excerpt_sha256"] == ref["excerpt_sha256"]


def test_key_rotation_and_time_limited_delivery(project, monkeypatch):
    from dataclasses import replace
    from datetime import datetime, timezone, timedelta
    from atmem import Memory
    from atmem.contracts import SourceCaptureRequest
    from atmem.extract.formation import form_typed_proposals
    import atmem.agent_team.portable as portable

    p = project
    source, statement = "time-limited", "My overnight reviewer is Ana."
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    memory = Memory(p.db, auto_vectors=False)
    try:
        memory.capture_source(SourceCaptureRequest(source, source, p.scope, statement))
        proposal = form_typed_proposals(statement, scope=p.scope, source_id=source, formation_id=source)[0]
        formed = replace(proposal, unit=replace(proposal.unit, valid_until=expires))
        assert (
            memory.submit_extraction_proposal(formed, source_text=statement)["review_state"] == "committed"
        )
    finally:
        memory.close()
    pending = offer(p, "expiry", question="What is my overnight reviewer?")
    assert pending["outcome"] == "offered"
    p.manager.evidence_service().rotate_key(p.owner, confirmation="ROTATE EVIDENCE KEY")
    p.restart()
    args = {"run_id": pending["run_id"]}
    before = client(p, "hermes").call("receive", args)
    assert before["outcome"] == "delivered"
    real_expired = portable._expired
    monkeypatch.setattr(portable, "_expired", lambda stamp: stamp == expires or real_expired(stamp))
    after = client(p, "hermes").call("receive", args)
    assert after["outcome"] == "withheld" and "passages" not in after
