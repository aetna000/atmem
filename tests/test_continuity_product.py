from __future__ import annotations

import json

import pytest

from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from atmem.evidence.service import EvidenceService


def setup(tmp_path, capability="none", ttl=3600):
    from atmem.continuity.service import ContinuityService

    clock = [1000.0]
    vault = EvidenceService(tmp_path / "vault", vault_id="vault")
    owner = EvidencePrincipal("owner", EvidenceRole.EVIDENCE_COLLECTOR, EvidenceScope("local", "student"))
    service = ContinuityService(vault, clock=lambda: clock[0])
    workflow = service.create(owner, "document-workflow", [{
        "name": "upload", "tool": "documents.upload", "arguments": {"text": "PRIVATE_DOCUMENT_9281"},
        "capability": capability, "retention_seconds": ttl, "timeout_seconds": 30,
    }])
    return service, vault, owner, workflow, clock


def begin(service, owner, workflow, attempt="a1", run="r1"):
    return service.begin(owner, workflow["workflow_id"], "upload", run, attempt)


def test_requires_explicit_enablement(tmp_path):
    service, _, owner, workflow, _ = setup(tmp_path)
    assert begin(service, owner, workflow)["action"] == "blocked"
    service.configure(owner, workflow["workflow_id"], enabled=True)
    assert begin(service, owner, workflow)["action"] == "execute"


def test_coordinator_capacity_counts_current_open_work_per_creator(tmp_path):
    service, _, _, _, _ = setup(tmp_path)
    service.MAX_OPEN_COORDINATOR_WORKFLOWS = 1
    actor = EvidencePrincipal("agent-a", EvidenceRole.CONTINUITY_COORDINATOR,
                              EvidenceScope("local", "student", "workspace"))
    other = EvidencePrincipal("agent-b", actor.role, actor.scope)
    definitions = [{"name": "upload", "tool": "upload"}]
    first = service.create(actor, "first", definitions, activate=True)
    with pytest.raises(ValueError, match="open workflow limit"):
        service.create(actor, "second", definitions, activate=True)
    service.create(other, "other", definitions, activate=True)
    decision = begin(service, actor, first)
    service.outcome(actor, first["workflow_id"], "upload", decision["lease_token"], {
        "outcome": "confirmed_succeeded", "operation_id": decision["operation_id"],
        "effect_id": "saved", "result": 1}, run_id="r1", attempt_id="a1")
    service.create(actor, "second", definitions, activate=True)
    assert service.create(actor, "first", definitions, activate=True)["operations"][0]["status"] == "completed"


def test_retained_history_limit_blocks_new_dispatch_but_keeps_reads(tmp_path):
    service, _, _, _, _ = setup(tmp_path)
    actor = EvidencePrincipal("limited-agent", EvidenceRole.CONTINUITY_COORDINATOR,
                              EvidenceScope("local", "student", "workspace"))
    workflow = service.create(actor, "limited", [{"name": "upload", "tool": "upload"}], activate=True)
    service.MAX_COORDINATOR_RETAINED_BYTES = 1
    with pytest.raises(ValueError, match="retained history limit"):
        begin(service, actor, workflow)
    assert service.get(actor, workflow["workflow_id"])["operations"][0]["attempts"] == []
    with pytest.raises(ValueError, match="exactly one"):
        service.create(actor, "batch", [{"name": "a", "tool": "a"}, {"name": "b", "tool": "b"}], activate=True)


def test_late_reports_do_not_copy_completed_workflow_snapshots(tmp_path):
    service, vault, owner, workflow, _ = setup(tmp_path)
    service.configure(owner, workflow["workflow_id"], enabled=True)
    decision = begin(service, owner, workflow)
    receipt = {"outcome": "confirmed_succeeded", "operation_id": decision["operation_id"], "effect_id": "file", "result": "original"}
    service.outcome(owner, workflow["workflow_id"], "upload", decision["lease_token"], receipt, run_id="r1", attempt_id="a1")
    with vault._store() as store:
        before = sum(doc.get("record_type") == "continuity" for doc in store.documents())
    for _ in range(10):
        assert not service.outcome(owner, workflow["workflow_id"], "upload", "old", receipt, run_id="r1", attempt_id="old")["accepted"]
    with pytest.raises(ValueError, match="late receipt limit"):
        service.outcome(owner, workflow["workflow_id"], "upload", "old", receipt, run_id="r1", attempt_id="old")
    with vault._store() as store:
        assert sum(doc.get("record_type") == "continuity" for doc in store.documents()) == before
    assert service.get(owner, workflow["workflow_id"])["operations"][0]["late_receipts"] == 10


def test_revision_limit_applies_to_configuration_too(tmp_path):
    service, _, owner, workflow, _ = setup(tmp_path)
    service.MAX_REVISIONS = 1
    with pytest.raises(ValueError, match="revision limit"):
        service.configure(owner, workflow["workflow_id"], enabled=True)
    assert not service.get(owner, workflow["workflow_id"])["enabled"]


def test_receipt_and_operator_pause_keep_revision_headroom(tmp_path):
    service, _, owner, workflow, _ = setup(tmp_path)
    service.MAX_REVISIONS = 5
    service.configure(owner, workflow["workflow_id"], enabled=True)
    decision = begin(service, owner, workflow)
    service.renew(owner, workflow["workflow_id"], "upload", decision["lease_token"], run_id="r1", attempt_id="a1")
    with pytest.raises(ValueError, match="reserved"):
        service.renew(owner, workflow["workflow_id"], "upload", decision["lease_token"], run_id="r1", attempt_id="a1")
    service.configure(owner, workflow["workflow_id"], enabled=False)
    outcome = service.outcome(owner, workflow["workflow_id"], "upload", decision["lease_token"], {
        "outcome": "confirmed_succeeded", "operation_id": decision["operation_id"], "effect_id": "saved", "result": 1}, run_id="r1", attempt_id="a1")
    assert outcome["status"] == "completed"


def test_coordinator_key_namespace_quota_host_and_deletion(tmp_path):
    service, vault, owner, _, _ = setup(tmp_path)
    scope = EvidenceScope("local", "student", "project")
    coordinator = EvidencePrincipal("agent", EvidenceRole.CONTINUITY_COORDINATOR, scope)
    operator = EvidencePrincipal(owner.principal_id, owner.role, scope)
    definitions = [{"name": "upload", "tool": "upload"}]
    dynamic = service.create(coordinator, "same-key", definitions, activate=True)
    static = service.create(operator, "same-key", definitions)
    assert static["workflow_id"] != dynamic["workflow_id"]
    assert static["enabled"] is False
    host = EvidencePrincipal("host", EvidenceRole.CONTINUITY_HOST, EvidenceScope("local", "student", "project", dynamic["workflow_id"]))
    service.MAX_COORDINATOR_RETAINED_BYTES = 1
    with pytest.raises(ValueError, match="retained history limit"):
        begin(service, host, dynamic)
    service.configure(operator, dynamic["workflow_id"], enabled=False)
    vault.delete_run(owner, dynamic["workflow_id"], confirmation="DELETE " + dynamic["workflow_id"])
    service.MAX_COORDINATOR_RETAINED_BYTES = 16000
    service.create(coordinator, "new-key", definitions, activate=True)
    with pytest.raises(ValueError, match="deleted"):
        service.create(coordinator, "same-key", definitions, activate=True)


def test_byte_headroom_reserves_maximum_receipt_against_other_work(tmp_path):
    service, _, _, _, _ = setup(tmp_path)
    service.MAX_COORDINATOR_RETAINED_BYTES = 200000
    actor = EvidencePrincipal("reserved-agent", EvidenceRole.CONTINUITY_COORDINATOR,
                              EvidenceScope("local", "student", "project"))
    workflow = service.create(actor, "first", [{"name": "upload", "tool": "upload"}], activate=True)
    decision = begin(service, actor, workflow)
    with pytest.raises(ValueError, match="retained history limit"):
        service.create(actor, "competing", [{"name": "upload", "tool": "upload", "arguments": {"text": "x" * 60000}}], activate=True)
    receipt = {"outcome": "confirmed_succeeded", "operation_id": decision["operation_id"],
               "effect_id": "saved", "result": "r" * 64000}
    assert service.outcome(actor, workflow["workflow_id"], "upload", decision["lease_token"], receipt,
                           run_id="r1", attempt_id="a1")["status"] == "completed"
    assert service.get(actor, workflow["workflow_id"])["operations"][0]["receipt"]["result"] == receipt["result"]


def _competing_begin(root, workflow_id, attempt, ready, start, output):
    from atmem.continuity.service import ContinuityService
    vault = EvidenceService(root, vault_id="vault")
    actor = EvidencePrincipal("owner", EvidenceRole.EVIDENCE_COLLECTOR, EvidenceScope("local", "student"))
    ready.put(True)
    start.wait(10)
    output.put(ContinuityService(vault).begin(actor, workflow_id, "upload", "race", attempt)["action"])


def test_two_processes_cannot_both_dispatch(tmp_path):
    import multiprocessing
    service, vault, owner, workflow, _ = setup(tmp_path)
    service.configure(owner, workflow["workflow_id"], enabled=True)
    ctx = multiprocessing.get_context("spawn")
    ready, output, start = ctx.Queue(), ctx.Queue(), ctx.Event()
    workers = [ctx.Process(target=_competing_begin, args=(vault.root, workflow["workflow_id"], f"a{i}", ready, start, output)) for i in range(2)]
    try:
        for worker in workers:
            worker.start()
        for _ in workers:
            ready.get(timeout=15)
        start.set()
        assert sorted(output.get(timeout=15) for _ in workers) == ["blocked", "execute"]
        for worker in workers:
            worker.join(5)
            assert worker.exitcode == 0
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(5)


def test_expired_unsuperseded_receipt_is_still_usable(tmp_path):
    service, _, owner, workflow, clock = setup(tmp_path)
    service.configure(owner, workflow["workflow_id"], enabled=True)
    decision = begin(service, owner, workflow)
    clock[0] += 121
    outcome = service.outcome(owner, workflow["workflow_id"], "upload", decision["lease_token"], {
        "outcome": "confirmed_succeeded", "operation_id": decision["operation_id"],
        "effect_id": "receipt-late", "result": "saved",
    }, run_id="r1", attempt_id="a1")
    assert outcome["status"] == "completed"


def test_receipt_survives_restart_and_skips_repeat(tmp_path):
    from atmem.continuity.service import ContinuityService

    service, _, owner, workflow, clock = setup(tmp_path)
    service.configure(owner, workflow["workflow_id"], enabled=True)
    decision = begin(service, owner, workflow)
    service.outcome(owner, workflow["workflow_id"], "upload", decision["lease_token"], {
        "outcome": "confirmed_succeeded", "operation_id": decision["operation_id"],
        "effect_id": "document-42", "result": {"url": "https://example.invalid/doc/42"},
    }, run_id="r1", attempt_id="a1")
    restarted = ContinuityService(EvidenceService(tmp_path / "vault", vault_id="vault"), clock=lambda: clock[0])
    resumed = begin(restarted, owner, workflow, "a2", "r2")
    assert resumed["action"] == "completed"
    assert resumed["receipt"]["effect_id"] == "document-42"


@pytest.mark.parametrize("capability,action", [("none", "blocked"), ("query", "query"), ("idempotent", "execute")])
def test_crash_uncertainty_uses_declared_capabilities(tmp_path, capability, action):
    service, _, owner, workflow, clock = setup(tmp_path, capability)
    service.configure(owner, workflow["workflow_id"], enabled=True)
    original = begin(service, owner, workflow)
    assert begin(service, owner, workflow, "a2")["reason"] == "attempt_in_progress"
    clock[0] += 121
    recovered = begin(service, owner, workflow, "a3", "r2")
    assert recovered["action"] == action
    if action == "execute":
        assert recovered["idempotency_key"] == original["idempotency_key"]


def test_expired_key_and_clock_rollback_do_not_license_retry(tmp_path):
    service, _, owner, workflow, clock = setup(tmp_path, "idempotent", ttl=180)
    service.configure(owner, workflow["workflow_id"], enabled=True)
    begin(service, owner, workflow)
    clock[0] += 121
    assert begin(service, owner, workflow, "a2")["reason"] == "idempotency_window_expired"
    clock[0] = 500
    with pytest.raises(ValueError, match="clock"):
        begin(service, owner, workflow, "a3")


def test_scope_and_host_role_are_enforced(tmp_path):
    service, _, owner, workflow, _ = setup(tmp_path)
    other = EvidencePrincipal("other", owner.role, EvidenceScope("local", "another-student"))
    with pytest.raises(PermissionError):
        service.get(other, workflow["workflow_id"])
    host = EvidencePrincipal("host", EvidenceRole.CONTINUITY_HOST,
        EvidenceScope("local", "student", run_id=workflow["workflow_id"]))
    service.configure(owner, workflow["workflow_id"], enabled=True)
    assert begin(service, host, workflow)["action"] == "execute"
    with pytest.raises(PermissionError):
        service.configure(host, workflow["workflow_id"], enabled=False)


def test_saved_content_is_encrypted_and_deleted_work_cannot_restart(tmp_path):
    service, vault, owner, workflow, _ = setup(tmp_path)
    assert b"PRIVATE_DOCUMENT_9281" not in vault.vault_path.read_bytes()
    vault.delete_run(owner, workflow["workflow_id"], confirmation="DELETE " + workflow["workflow_id"])
    with pytest.raises(ValueError, match="deleted"):
        service.create(owner, "document-workflow", [{"name": "upload", "tool": "documents.upload", "arguments": {}}])
    with vault._store() as store:
        assert "PRIVATE_DOCUMENT_9281" not in json.dumps(list(store.documents()))


def test_missing_key_blocks_existing_service(tmp_path):
    service, vault, owner, workflow, _ = setup(tmp_path)
    service.configure(owner, workflow["workflow_id"], enabled=True)
    vault.lock(owner, confirmation="LOCK EVIDENCE")
    with pytest.raises(PermissionError):
        begin(service, owner, workflow)


def test_capture_cannot_forge_product_authority(tmp_path):
    service, vault, owner, workflow, _ = setup(tmp_path)
    forged = dict(workflow, enabled=True)
    vault.capture({"record_type": "continuity", "workflow": forged, "run_id": "forged"})
    vault.capture({"workflow": "not an object", "run_id": "malformed"})
    assert begin(service, owner, workflow)["action"] == "blocked"
    assert service.create(owner, "document-workflow", workflow["definitions"])["enabled"] is False


def test_readers_cannot_steal_lease_and_repeated_begin_does_not_dispatch(tmp_path):
    service, _, owner, workflow, _ = setup(tmp_path)
    service.configure(owner, workflow["workflow_id"], enabled=True)
    issued = begin(service, owner, workflow)
    investigator = EvidencePrincipal("reader", EvidenceRole.INVESTIGATOR, owner.scope)
    data = json.dumps(service.get(investigator, workflow["workflow_id"]))
    assert issued["lease_token"] not in data
    assert issued["idempotency_key"] not in data
    assert begin(service, owner, workflow)["reason"] == "attempt_already_issued"
    result = service.outcome(owner, workflow["workflow_id"], "upload", issued["lease_token"], {}, run_id="other", attempt_id="a1")
    assert result["accepted"] is False


def test_blocked_polls_do_not_grow_vault_and_large_receipts_rejected(tmp_path):
    service, vault, owner, workflow, _ = setup(tmp_path)
    with vault._store() as store:
        before = store.count()
    for _ in range(30):
        begin(service, owner, workflow)
    with vault._store() as store:
        assert store.count() == before
    with pytest.raises(ValueError, match="64 KiB"):
        service.outcome(owner, workflow["workflow_id"], "upload", "bad", {"result": "a" * 65536}, run_id="r1", attempt_id="a1")


def test_disabling_stops_dispatch_but_preserves_inflight_receipt(tmp_path):
    service, _, owner, workflow, _ = setup(tmp_path)
    service.configure(owner, workflow["workflow_id"], enabled=True)
    decision = begin(service, owner, workflow)
    service.configure(owner, workflow["workflow_id"], enabled=False)
    result = service.outcome(owner, workflow["workflow_id"], "upload", decision["lease_token"], {
        "outcome": "confirmed_succeeded", "operation_id": decision["operation_id"], "effect_id": "doc1", "result": {}}, run_id="r1", attempt_id="a1")
    assert result["status"] == "completed"


def test_cannot_abandon_live_attempt_or_reduce_capture(tmp_path):
    from atmem.evidence import CaptureMode
    service, vault, owner, workflow, _ = setup(tmp_path)
    service.configure(owner, workflow["workflow_id"], enabled=True)
    begin(service, owner, workflow)
    with pytest.raises(ValueError, match="in progress"):
        service.abandon(owner, workflow["workflow_id"], "upload", "stop")
    with pytest.raises(ValueError, match="resolve or abandon"):
        vault.set_capture_mode(owner, CaptureMode.OFF)
