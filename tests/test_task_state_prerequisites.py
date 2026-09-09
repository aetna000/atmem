"""The concrete primitives Governed Task State builds on.

Spec 007 declares a hard prerequisite gate: the feature depends only on AtMem
primitives that already exist, and it must fail loudly rather than silently
degrade if one of them is absent or has changed shape. These tests pin the
exact APIs the task-state plane calls, so a future refactor that moves or
narrows one of them breaks here — naming the missing primitive — instead of
surfacing as a confusing failure deep inside task-state code.

Nothing here tests task-state behavior. It tests that the ground is solid.
"""

from __future__ import annotations

import inspect
import sqlite3

import pytest

from atmem.contracts import AuthorityScope, capabilities
from atmem.control.evidence import seal_report, verify_report
from atmem.control.manager import ControlPlaneManager
from atmem.core.canonical import canonical_json, sha256_hex
from atmem.memory import Memory
from atmem.store.sqlite import SQLiteStore


def test_authority_scope_is_a_closed_three_part_identity() -> None:
    scope = AuthorityScope("subject-1", "agent-1", "workspace-1")

    assert scope.to_dict()["format"] == "atmem-authority-scope-v1"
    assert (scope.subject_id, scope.agent_id, scope.workspace_id) == (
        "subject-1",
        "agent-1",
        "workspace-1",
    )
    assert scope.digest().startswith("sha256:")
    for bad in ("", "   ", "has space", "1leading-digit"):
        with pytest.raises(ValueError):
            AuthorityScope(bad, "agent-1", "workspace-1")


def test_canonical_json_is_stable_and_digestible() -> None:
    first = canonical_json({"b": 1, "a": [2, {"d": 4, "c": 3}]})
    second = canonical_json({"a": [2, {"c": 3, "d": 4}], "b": 1})

    assert first == second, "canonical JSON must not depend on key insertion order"
    assert len(sha256_hex(first)) == 64
    assert sha256_hex(first) == sha256_hex(second)


def test_sqlite_store_exposes_nestable_transactions_and_migrations() -> None:
    store = SQLiteStore()
    try:
        assert hasattr(store, "transaction")
        with store.transaction():
            with store.transaction():
                pass
        assert callable(store.applied_migrations)
        # The bootstrap block Spec 007 appends to must already exist and be
        # append-only, so 0070-0079 can be added without renumbering.
        applied = store.applied_migrations()
        assert applied == sorted(applied), "bootstrap identifiers must stay ordered"
    finally:
        store.close()


def test_a_failed_transaction_rolls_back_completely() -> None:
    store = SQLiteStore()
    try:
        subject = "prereq-subject"
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.insert_episode(
                    subject_id=subject,
                    session_id=None,
                    turn_id=None,
                    message="written inside a doomed transaction",
                    source_type="user_message",
                    raw={},
                )
                raise RuntimeError("simulated failure mid-transaction")
        assert store.list_episodes(subject) == []
    finally:
        store.close()


def test_sqlite_supports_the_constraint_features_task_state_needs() -> None:
    """Partial unique indexes and CHECK constraints, used by the task tables."""
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(
            """
            CREATE TABLE probe (
              id TEXT PRIMARY KEY,
              scope TEXT NOT NULL,
              lifecycle TEXT NOT NULL CHECK (
                lifecycle IN ('open', 'paused', 'completed', 'cancelled', 'expired')
              ),
              paused_ms INTEGER NOT NULL DEFAULT 0 CHECK (paused_ms >= 0)
            );
            CREATE UNIQUE INDEX probe_one_open_per_scope
              ON probe(scope) WHERE lifecycle = 'open';
            """
        )
        connection.execute("INSERT INTO probe VALUES ('a', 's', 'open', 0)")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO probe VALUES ('b', 's', 'open', 0)")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO probe VALUES ('c', 't', 'nonsense', 0)")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO probe VALUES ('d', 't', 'open', -1)")
    finally:
        connection.close()


def test_audit_chain_append_and_verification_are_available() -> None:
    memory = Memory(":memory:")
    try:
        subject = "prereq-subject"
        event_id = memory.store.append_audit_event(
            subject_id=subject,
            event_type="prerequisite.probe",
            actor="test",
            session_id=None,
            turn_id=None,
            payload={"probe": True},
        )
        assert event_id
        assert memory.verify(subject)["valid"] is True
    finally:
        memory.close()


def test_evidence_sealing_round_trips() -> None:
    body = {"format": "atmem-probe-v1", "value": 1}
    stable = {"value": 1}
    sealed = seal_report(body, stable_evidence=stable)

    assert verify_report(sealed, stable_evidence=stable)["valid"] is True
    tampered = {**sealed, "value": 2}
    assert verify_report(tampered, stable_evidence=stable)["valid"] is False


def test_control_preparation_and_exposure_confirmation_exist() -> None:
    for name in ("prepare", "confirm_exposure", "record_blackbox_event", "state"):
        assert callable(getattr(ControlPlaneManager, name, None)), (
            f"ControlPlaneManager.{name} is a Spec 007 prerequisite"
        )
    signature = inspect.signature(ControlPlaneManager.prepare)
    for parameter in ("session_id", "host_run_id", "subject_id", "agent_id"):
        assert parameter in signature.parameters, (
            f"ControlPlaneManager.prepare must accept {parameter}"
        )


def test_adapter_identity_and_lifecycle_expose_the_hooks_task_state_maps_to() -> None:
    from atmem.adapters.base import AtMemAdapterIdentity, AtMemTurnLifecycle

    identity = AtMemAdapterIdentity(agent_id="agent-1", workspace_id="workspace-1")
    assert identity.for_run("run-1").run_id == "run-1"
    for name in (
        "begin",
        "context_for_model",
        "model_input",
        "model_output",
        "tool_requested",
        "tool_completed",
        "end",
    ):
        assert callable(getattr(AtMemTurnLifecycle, name, None)), (
            f"AtMemTurnLifecycle.{name} is a Spec 007 prerequisite"
        )


def test_runtime_capabilities_are_a_single_authoritative_response() -> None:
    value = capabilities()

    assert value["format"] == "atmem-capabilities-v1"
    assert isinstance(value["features"], dict)
    # Spec 007 adds governed-task-state flags to this one response; nothing
    # else may become a competing capability authority.
    assert "protocol_versions" in value


def test_atbot_boundary_is_optional_and_isolated() -> None:
    """AtBot must remain optional: importing AtMem cannot require it."""
    from atmem.control.atbot_companion import AtBotCompanionClient

    client = AtBotCompanionClient()
    assert client.endpoint.startswith("http://127.0.0.1")
    with pytest.raises(ValueError):
        AtBotCompanionClient("https://example.com")
    health = client.health()
    # Whether or not a companion is running, the boundary answers honestly.
    assert "available" in health
