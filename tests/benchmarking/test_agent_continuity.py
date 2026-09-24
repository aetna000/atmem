"""Offline harness gates; no production performance claims or real Home access."""
from __future__ import annotations

import json
import multiprocessing as mp
from pathlib import Path
import secrets

import pytest

from benchmarks.agent_continuity.destination import request, serve
from benchmarks.agent_continuity.faults import BARRIERS, trial
from benchmarks.agent_continuity.manifest import digest, partition
from benchmarks.agent_continuity.oracle import score_context, score_effects
from benchmarks.agent_continuity.report import charge_totals, paired_cluster_interval, summarize


def test_partition_is_clustered_reproducible_and_disjoint():
    tasks = [{"id": str(i), "evaluation_criteria": {"actions": [{
        "name": "cancel_pending_order", "arguments": {"order_id": f"order-{i//2}"}}]}}
             for i in range(20)]
    one = partition(tasks, [str(i) for i in range(20)], 4)
    assert one == partition(tasks, [str(i) for i in range(20)], 4)
    assert set(one["pilot_ids"]).isdisjoint(one["heldout_ids"])
    assert {"0", "1"} <= set(one["pilot_ids"])
    assert one["heldout_digest"] == digest(one["heldout_ids"])
    for i in range(0, 20, 2):
        assert (str(i) in one["pilot_ids"]) == (str(i+1) in one["pilot_ids"])


def test_bad_effects_cannot_be_hidden_by_worker_success():
    expected = {"a": "hash-a", "b": "hash-b"}
    effects = [{"operation_id": "a", "payload_digest": "hash-a"}]*2 + [
        {"operation_id": "rogue", "payload_digest": "hash-x"}]
    scored = score_effects(expected, effects)
    assert scored["duplicate_effects"] == 1
    assert scored["wrong_effects"] == 1
    assert scored["forgotten_operations"] == ["b"]
    assert not scored["valid_completion"]
    assert score_effects(expected, effects, ["b"])["pending_blocked_operations"] == ["b"]


def test_context_truth_is_independent_of_delivery_claim():
    result = score_context([{"id": "a", "revision": 1}, {"id": "missing"}],
                           {"a": {"revision": 2, "eligible": False}})
    assert result == {"delivered": 2, "stale": 1, "unauthorized": 1, "missing_canonical": 1}


def test_cost_duplicates_overlap_unknowns_and_currency_are_explicit():
    charge = {"charge_id": "a", "amount": "0.10", "currency": "USD", "price_source": "fixture",
              "retry": True, "recovery": True}
    result = charge_totals([charge, charge, {"charge_id": "b", "amount": None}])
    assert result["known_subtotals"] == {"USD": "0.10"}
    assert result["unknown_charge_count"] == 1
    assert not result["complete"]
    with pytest.raises(ValueError, match="conflicting"):
        charge_totals([charge, {**charge, "amount": "0.2"}])
    with pytest.raises(ValueError, match="invalid"):
        charge_totals([{**charge, "amount": "NaN"}])


def test_cluster_interval_does_not_invent_uncertainty_from_one_task():
    pairs = [{"pair_id": "1", "cluster_id": "a", "baseline": .3, "candidate": .5}]
    assert paired_cluster_interval(pairs)["interval"] is None
    pairs.append({"pair_id": "2", "cluster_id": "b", "baseline": .3, "candidate": .5})
    assert paired_cluster_interval(pairs)["mean_delta"] == pytest.approx(.2)
    with pytest.raises(ValueError, match="duplicate"):
        paired_cluster_interval(pairs + pairs)


def test_infrastructure_failure_stays_in_report_denominator():
    report = summarize([{"arm": "runtime", "capability": "I", "fault": "after_commit",
                         "negative_control": False, "disposition": "infrastructure_failure",
                         "elapsed_ms": 1, "fault_reached": False}])
    cell = next(iter(report["cells"].values()))
    assert cell["scheduled_trials"] == 1
    assert cell["scored_trials"] == 0
    assert cell["incomplete_denominator"]
    assert not report["production_claims_allowed"]


def test_current_atmem_gates_and_restart(tmp_path):
    from benchmarks.agent_continuity.adapters.atmem import AtMemTaskAdapter
    from atmem.task_state.enablement import ScopeEnablement
    adapter = AtMemTaskAdapter(tmp_path / "fixture.db", "scope", "task-1")
    adapter.setup("operation-1")
    try:
        adapter.set_status("operation-1", "running", "attempt-1")
        with pytest.raises(ValueError, match="receipt"):
            adapter.set_status("operation-1", "completed", "attempt-1")
        receipt = {"outcome": "confirmed_succeeded", "effect_id": "fixture-receipt"}
        adapter.set_status("operation-1", "completed", "attempt-1", receipt)
    finally:
        adapter.close()
    reopened = AtMemTaskAdapter(tmp_path / "fixture.db", "scope", "task-1")
    try:
        assert reopened.status("operation-1") == "completed"
        ScopeEnablement(reopened.store).disable(reopened.scope, actor="operator")
        with pytest.raises(RuntimeError, match="task_state_disabled"):
            reopened.set_status("operation-1", "running", "attempt-2")
    finally:
        reopened.close()


def test_atmem_scope_rejection(tmp_path):
    from benchmarks.agent_continuity.adapters.atmem import AtMemTaskAdapter
    from atmem.contracts import AuthorityScope
    from atmem.task_state.service import TaskStateError
    adapter = AtMemTaskAdapter(tmp_path / "fixture.db", "scope", "task-1")
    try:
        adapter.setup("operation-1")
        with pytest.raises(TaskStateError):
            adapter.service.get(AuthorityScope("other", "fixture-agent", "trial-scope"), "task-1")
    finally:
        adapter.close()


@pytest.mark.parametrize("fault", BARRIERS)
@pytest.mark.parametrize("capability", ["I", "Q", "N"])
def test_actual_worker_crash(tmp_path, fault, capability):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    result = trial(tmp_path / "trial", capability=capability, fault=fault)
    assert result["fault_reached"], result
    assert result["killed_worker_exitcode"] < 0, result
    assert result["disposition"] != "infrastructure_failure", result
    assert result["oracle"]["duplicate_effects"] == 0
    assert result["oracle"]["wrong_effects"] == 0
    blocked = (capability == "N" and fault in {"after_intent", "in_flight", "after_commit", "after_response"}
               or capability == "Q" and fault == "after_intent")
    assert result["disposition"] == ("blocked" if blocked else "completed")
    assert result["restart_to_terminal_ms"] is not None
    runs = [e["run_id"] for e in result["events"] if "resume" in e]
    assert len(runs) == len(set(runs)) == 2


@pytest.mark.parametrize("capability", ["I", "Q", "N"])
def test_atmem_ambiguous_commit(tmp_path, capability):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    result = trial(tmp_path / "trial", capability=capability, atmem=True)
    assert result["disposition"] == ("blocked" if capability == "N" else "completed"), result
    assert result["oracle"]["duplicate_effects"] == 0


def test_negative_control_really_duplicates(tmp_path):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    result = trial(tmp_path / "trial", capability="N", naive=True)
    assert result["worker_outcome"] == "confirmed_succeeded", result
    assert result["oracle"]["duplicate_effects"] == 1
    assert not result["oracle"]["valid_completion"]


@pytest.mark.parametrize("capability,kwargs", [("I", {"retention": 0}), ("Q", {"visibility": 100})])
def test_expired_keys_and_delayed_queries_do_not_authorize_retry(tmp_path, capability, kwargs):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    result = trial(tmp_path / "trial", capability=capability, **kwargs)
    assert result["disposition"] == "blocked", result
    assert result["oracle"]["committed_effects"] == 1


def test_destination_has_no_worker_oracle_route_and_binds_payload():
    ctx = mp.get_context("spawn")
    control, child = ctx.Pipe()
    events, writer = ctx.Pipe(False)
    release = ctx.Event()
    token = secrets.token_urlsafe(24)
    process = ctx.Process(target=serve, args=(child, writer, release, "I", None, token))
    process.start()
    try:
        assert control.poll(15)
        url = control.recv()["url"]
        assert request(url, "wrong", "/effects", {})["error"] == "http_401"
        assert request(url, token, "/ledger", {})["error"] == "http_404"
        assert request(url, token, "/effects", {"operation_id": "a", "payload": 1})["outcome"] == "confirmed_succeeded"
        assert request(url, token, "/effects", {"operation_id": "a", "payload": 2})["error"] == "http_409"
        control.send("snapshot")
        assert control.poll(15)
        assert len(control.recv()) == 1
    finally:
        control.send("stop")
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        for connection in (control, child, events, writer):
            connection.close()


@pytest.mark.parametrize("capability", ["I", "Q", "N"])
def test_fenced_dropped_request_is_not_assumed_successful(tmp_path, capability):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    result = trial(tmp_path / "trial", capability=capability, fault="in_flight", drop_request=True)
    assert result["disposition"] == ("blocked" if capability == "N" else "completed"), result
    if capability == "N":
        assert result["oracle"]["committed_effects"] == 0
        assert result["oracle"]["pending_blocked_operations"] == ["operation-1"]
    else:
        assert result["oracle"]["committed_effects"] == 1


def test_customer_aliases_and_readonly_tasks_bridge_split_clusters():
    database = {"users": {"u": {"email": "u@example.test", "name": {"first_name": "First", "last_name": "Last"},
                               "address": {"zip": "123"}}}, "orders": {"order-u": {"user_id": "u"}}}
    actions = [
        [{"name": "cancel_pending_order", "arguments": {"order_id": "order-u"}}],
        [{"name": "find_user_id_by_email", "arguments": {"email": "u@example.test"}},
         {"name": "modify_user_address", "arguments": {"user_id": "u"}}],
        [{"name": "find_user_id_by_name_zip", "arguments": {"first_name": "First", "last_name": "Last", "zip": "123"}},
         {"name": "modify_user_address", "arguments": {"user_id": "u"}}],
    ]
    tasks = [{"id": str(i), "evaluation_criteria": {"actions": value}} for i, value in enumerate(actions)]
    tasks += [{"id": str(i), "evaluation_criteria": {"actions": [
        {"name": "cancel_pending_order", "arguments": {"order_id": f"other-{i}"}}]}} for i in range(3, 12)]
    split = partition(tasks, [t["id"] for t in tasks], 9, database)
    assert {"0", "1", "2"} <= set(split["pilot_ids"])


def test_runtime_pin_mismatch_fails_before_trial_directory(monkeypatch, tmp_path):
    monkeypatch.setattr('benchmarks.agent_continuity.manifest.importlib.metadata.version', lambda _: '0.0.0')
    with pytest.raises(ValueError, match='protocol lock'):
        trial(tmp_path / 'not-created')
    assert not (tmp_path / 'not-created').exists()


def test_design_exposed_readonly_task_forces_entire_customer_cluster():
    tasks = [{"id": "0", "evaluation_criteria": {"actions": [
        {"name": "get_order_details", "arguments": {"order_id": "shared"}}]}},
        {"id": "1", "evaluation_criteria": {"actions": [
            {"name": "cancel_pending_order", "arguments": {"order_id": "shared"}}]}}]
    tasks += [{"id": str(i), "evaluation_criteria": {"actions": [
        {"name": "cancel_pending_order", "arguments": {"order_id": f"other-{i}"}}]}}
              for i in range(2, 15)]
    split = partition(tasks, [t["id"] for t in tasks], 5)
    assert "0" in split["excluded_zero_write_ids"]
    assert "1" in split["pilot_ids"]
    assert "1" not in split["heldout_ids"]
    with pytest.raises(ValueError, match='design-exposed'):
        partition(tasks[1:], [t["id"] for t in tasks[1:]], 5)


def test_runner_fails_if_negative_control_or_completion_gate_stops_working():
    from benchmarks.agent_continuity.runner import passes_smoke_cell
    row = {"negative_control": True, "capability": "N", "fault": "after_commit",
           "fault_reached": True, "disposition": "completed",
           "oracle": {"duplicate_effects": 0, "wrong_effects": 0}}
    assert not passes_smoke_cell(row)
    row.update(disposition="invalid_effects", oracle={"duplicate_effects": 1, "wrong_effects": 0})
    assert passes_smoke_cell(row)
    row.update(negative_control=False, capability="I", disposition="blocked",
               oracle={"duplicate_effects": 0, "wrong_effects": 0})
    assert not passes_smoke_cell(row)


@pytest.mark.parametrize("atmem", [False, True])
@pytest.mark.parametrize("capability", ["I", "Q", "N"])
def test_clean_control_does_not_kill_or_restart_worker(tmp_path, capability, atmem):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    from benchmarks.agent_continuity.runner import passes_smoke_cell
    result = trial(tmp_path / "clean", capability=capability, atmem=atmem, fault=None)
    assert result["disposition"] == "completed", result
    assert not result["fault_reached"]
    assert "killed_worker_exitcode" not in result
    assert result["restart_to_terminal_ms"] is None
    assert len([e for e in result["events"] if "resume" in e]) == 1
    assert passes_smoke_cell(result)
