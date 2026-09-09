"""The published task-state schemas, checked against real documents.

Every contract AtMem emits must satisfy the schema AtMem publishes, and every
document a schema accepts must be one the Python contract also accepts. A gap
in either direction means an integrator building to the schema would produce
something AtMem rejects, or vice versa.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    ContextDisposition,
    EvidenceRef,
    GuardSignal,
    GuardType,
    ItemStatus,
    OperationKind,
    StepOutcome,
    TaskConstraint,
    TaskContextPackage,
    TaskItem,
    TaskLifecycle,
    TaskOperation,
    TaskProfile,
    TaskStartRequest,
    TaskState,
    TaskStateProposal,
    TransitionDecision,
)
from atmem.task_state import GENERAL_V1

from jsonschema_mini import SchemaError, as_json_document, is_valid, load, validate


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
SCHEMA_NAMES = (
    "task-profile.json",
    "task-start-request.json",
    "task-state.json",
    "task-state-proposal.json",
    "task-transition-decision.json",
    "task-context-package.json",
)


def _doc(contract) -> dict:
    return as_json_document(contract.to_dict())


# --- the schema files themselves -------------------------------------------


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_every_schema_parses_and_is_self_describing(name: str) -> None:
    schema = load(name)

    assert schema["$schema"].startswith("https://json-schema.org/draft/")
    assert schema["$id"] == f"https://atmem.dev/schemas/v1/{name}"
    assert schema["title"].startswith("AtMem"), "schemas must name their owner"
    assert schema["description"], "a published contract explains itself"
    assert schema["additionalProperties"] is False, (
        "task-state schemas are closed: an unknown field is an error"
    )


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_schemas_are_independently_authored(name: str) -> None:
    """FR-028: no third-party research names or branded components."""
    text = (Path("atmem/schemas/v1") / name).read_text().lower()
    for forbidden in ("androidworld", "webarena", "osworld", "mind2web", "gaia"):
        assert forbidden not in text


# --- valid vectors: what AtMem emits satisfies what AtMem publishes --------


def test_the_built_in_profile_satisfies_the_profile_schema() -> None:
    validate(_doc(GENERAL_V1), load("task-profile.json"))


def test_a_start_request_satisfies_its_schema() -> None:
    request = TaskStartRequest(
        task_id="task-1",
        scope=SCOPE,
        profile_id="general",
        profile_version="general-v1",
        goal="Migrate the billing service",
        actor="operator@example.com",
        actor_role=ActorRole.OPERATOR,
        idempotency_key="start-1",
        constraints=("Do not touch production data",),
        sources_to_inspect=("runbook",),
        evidence=(EvidenceRef(kind="operator_request", reference_id="request-1"),),
    )
    validate(_doc(request), load("task-start-request.json"))


def test_a_full_task_state_satisfies_its_schema() -> None:
    state = TaskState(
        task_id="task-1",
        scope=SCOPE,
        revision=3,
        lifecycle=TaskLifecycle.OPEN,
        phase="execute",
        goal="Migrate the billing service",
        profile_id="general",
        profile_version="general-v1",
        items=(
            TaskItem(item_id="item-1", kind="step", title="Snapshot the database",
                     status=ItemStatus.COMPLETED, assurance=Assurance.HOST_REPORTED,
                     evidence=(EvidenceRef(kind="tool_call", reference_id="call-1"),),
                     required=True),
            TaskItem(item_id="item-2", kind="step", title="Run the migration",
                     status=ItemStatus.BLOCKED, blocker_reason="Waiting on approval",
                     depends_on=("item-1",)),
        ),
        constraints=(TaskConstraint(constraint_id="c-1", text="Stay under one hour"),),
        sources_to_inspect=("runbook",),
        completed_sources=("runbook",),
        created_at="2026-09-05T10:00:00+00:00",
        updated_at="2026-09-05T10:30:00+00:00",
        last_progress_at="2026-09-05T10:30:00+00:00",
        parent_revision=2,
    )
    validate(_doc(state), load("task-state.json"))


def test_a_proposal_satisfies_its_schema() -> None:
    proposal = TaskStateProposal(
        proposal_id="proposal-1",
        task_id="task-1",
        scope=SCOPE,
        base_revision=3,
        idempotency_key="delta-1",
        actor="atbot",
        actor_role=ActorRole.ATBOT_INTELLIGENCE,
        operations=(
            TaskOperation(kind=OperationKind.SET_ITEM_STATUS, item_id="item-2",
                          status=ItemStatus.COMPLETED, assurance=Assurance.HOST_REPORTED),
            TaskOperation(kind=OperationKind.SET_PHASE, phase="verify"),
        ),
        evidence=(EvidenceRef(kind="tool_call", reference_id="call-2"),),
        interpreter="atbot-task-v1",
        assurance=Assurance.MODEL_INTERPRETED,
    )
    validate(_doc(proposal), load("task-state-proposal.json"))


@pytest.mark.parametrize(
    ("outcome", "reason", "resulting"),
    [
        (StepOutcome.ACCEPTED, "transition_accepted", 4),
        (StepOutcome.REJECTED, "illegal_status_transition", None),
        (StepOutcome.CONFLICT, "stale_base_revision", None),
        (StepOutcome.NO_CHANGE, "state_already_matches", 3),
    ],
)
def test_every_decision_outcome_satisfies_its_schema(outcome, reason, resulting) -> None:
    decision = TransitionDecision(
        decision_id="decision-1", proposal_id="proposal-1", task_id="task-1",
        scope=SCOPE, outcome=outcome, reason_codes=(reason,), base_revision=3,
        resulting_revision=resulting, decided_at="2026-09-05T10:31:00+00:00",
        guards=(
            GuardSignal(
                guard_type=GuardType.NO_PROGRESS, task_id="task-1", revision=3,
                message="Three equivalent actions produced no accepted progress.",
                repeated_action_count=3,
            ),
        ),
    )
    validate(_doc(decision), load("task-transition-decision.json"))


@pytest.mark.parametrize(
    ("disposition", "context", "reasons"),
    [
        (ContextDisposition.INJECTED, "task body", ()),
        (ContextDisposition.WITHHELD, "", ("task_context_selection_required",)),
        (ContextDisposition.WITHHELD, "", ("task_context_not_eligible",)),
        (ContextDisposition.WITHHELD, "", ("task_context_budget_exceeded",)),
    ],
)
def test_every_context_disposition_satisfies_its_schema(
    disposition, context, reasons
) -> None:
    package = TaskContextPackage(
        context_id="context-1", task_id="task-1", scope=SCOPE, revision=3,
        disposition=disposition, context=context, reason_codes=reasons,
        profile_version="general-v1",
    )
    validate(_doc(package), load("task-context-package.json"))


# --- invalid vectors: what the schema must refuse --------------------------


@pytest.mark.parametrize(
    ("name", "document"),
    [
        # unknown fields are errors, not extensions
        (
            "task-state.json",
            {**_doc(TaskState(task_id="t", scope=SCOPE, revision=1,
                              lifecycle=TaskLifecycle.OPEN, phase="plan", goal="G",
                              profile_id="general", profile_version="general-v1")),
             "surprise": 1},
        ),
        # revision zero
        (
            "task-state.json",
            {**_doc(TaskState(task_id="t", scope=SCOPE, revision=1,
                              lifecycle=TaskLifecycle.OPEN, phase="plan", goal="G",
                              profile_id="general", profile_version="general-v1")),
             "revision": 0},
        ),
        # a lifecycle value outside the closed set of five
        (
            "task-state.json",
            {**_doc(TaskState(task_id="t", scope=SCOPE, revision=1,
                              lifecycle=TaskLifecycle.OPEN, phase="plan", goal="G",
                              profile_id="general", profile_version="general-v1")),
             "lifecycle": "archived"},
        ),
        # an item status outside the closed set of seven
        (
            "task-state.json",
            {**_doc(TaskState(task_id="t", scope=SCOPE, revision=1,
                              lifecycle=TaskLifecycle.OPEN, phase="plan", goal="G",
                              profile_id="general", profile_version="general-v1")),
             "items": [{"item_id": "i", "kind": "k", "title": "T", "status": "vibing"}]},
        ),
        # an empty goal
        (
            "task-state.json",
            {**_doc(TaskState(task_id="t", scope=SCOPE, revision=1,
                              lifecycle=TaskLifecycle.OPEN, phase="plan", goal="G",
                              profile_id="general", profile_version="general-v1")),
             "goal": ""},
        ),
    ],
)
def test_invalid_state_documents_are_refused(name: str, document: dict) -> None:
    assert not is_valid(document, load(name))


def test_a_proposal_with_no_operations_is_refused() -> None:
    document = _doc(
        TaskStateProposal(
            proposal_id="p", task_id="t", scope=SCOPE, base_revision=1,
            idempotency_key="k", actor="a", actor_role=ActorRole.HOST_AGENT,
            operations=(TaskOperation(kind=OperationKind.LOCK_SCHEMA),),
        )
    )
    document["operations"] = []
    assert not is_valid(document, load("task-state-proposal.json"))


def test_a_proposal_cannot_smuggle_a_full_replacement_operation() -> None:
    document = _doc(
        TaskStateProposal(
            proposal_id="p", task_id="t", scope=SCOPE, base_revision=1,
            idempotency_key="k", actor="a", actor_role=ActorRole.ATBOT_INTELLIGENCE,
            operations=(TaskOperation(kind=OperationKind.LOCK_SCHEMA),),
        )
    )
    document["operations"] = [{"kind": "replace_state", "content": {"items": []}}]
    assert not is_valid(document, load("task-state-proposal.json"))


def test_an_accepted_decision_without_a_resulting_revision_is_refused() -> None:
    document = _doc(
        TransitionDecision(
            decision_id="d", proposal_id="p", task_id="t", scope=SCOPE,
            outcome=StepOutcome.ACCEPTED, reason_codes=("transition_accepted",),
            base_revision=1, resulting_revision=2,
        )
    )
    document.pop("resulting_revision")
    assert not is_valid(document, load("task-transition-decision.json"))


def test_a_withheld_package_carrying_bytes_is_refused_by_the_schema() -> None:
    document = _doc(
        TaskContextPackage(
            context_id="c", task_id="t", scope=SCOPE, revision=1,
            disposition=ContextDisposition.WITHHELD,
            reason_codes=("task_context_not_eligible",),
        )
    )
    document["context"] = "smuggled task state"
    assert not is_valid(document, load("task-context-package.json"))


def test_a_profile_with_a_zero_expiry_threshold_is_refused() -> None:
    document = _doc(GENERAL_V1)
    document["expiry"] = {"max_absolute_age_ms": 0, "max_no_progress_age_ms": None}
    assert not is_valid(document, load("task-profile.json"))


def test_a_profile_with_a_zero_progress_threshold_is_refused() -> None:
    document = _doc(GENERAL_V1)
    document["no_progress_action_threshold"] = 0
    assert not is_valid(document, load("task-profile.json"))


# --- the two directions agree ----------------------------------------------


def test_schema_and_python_contract_refuse_the_same_bad_documents() -> None:
    """A document one layer rejects must not be accepted by the other."""
    profile_schema = load("task-profile.json")
    bad = _doc(GENERAL_V1)
    bad["phases"] = []

    assert not is_valid(bad, profile_schema)
    with pytest.raises(ValueError):
        TaskProfile.from_dict({**GENERAL_V1.to_dict(), "phases": ()})


def test_the_checker_refuses_a_schema_it_cannot_fully_enforce() -> None:
    """Guards the guard: an unimplemented keyword must fail loudly."""
    with pytest.raises(SchemaError, match="does not implement"):
        validate({}, {"type": "object", "dependentRequired": {"a": ["b"]}})
