"""Host-boundary contracts: session identity, bindings, and typed requests.

Spec 007 Amendment A, T059 and T060. These contracts are the boundary between
what a host adapter may *say* and what AtMem will place. Two properties matter
more than the rest:

* A host states which conversation it is, and AtMem decides what that
  conversation may do. Session identity is an addressing claim, which is why it
  is allowed to arrive from the caller where an actor-role or capability field
  is not.
* A partial identity is malformed, never resolved on whatever survived. Hosts
  declare these fields as optional, so absence is common and must fail closed.
"""

from __future__ import annotations

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    BindingResolution,
    EvidenceRef,
    HostSessionIdentity,
    HostTaskLifecycleRequest,
    HostTaskObservationRequest,
    HostTaskProposalRequest,
    ItemStatus,
    OperationKind,
    SessionBinding,
    TaskOperation,
    TaskProfile,
)
from atmem.task_state.profiles import GENERAL_V1

from jsonschema_mini import as_json_document, load, validate


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
IDENTITY = {"host_type": "openclaw", "session_key": "session-1", "session_epoch": "epoch-1"}
OPERATION = {"kind": "set_item_status", "item_id": "schema", "status": "completed"}

HOST_SCHEMAS = {
    "host-task-observation-request.json": "atmem-host-task-observation-request-v1",
    "host-task-proposal-request.json": "atmem-host-task-proposal-request-v1",
    "host-task-lifecycle-request.json": "atmem-host-task-lifecycle-request-v1",
}


def _observation(**overrides) -> dict:
    return {
        "identity": IDENTITY,
        "task_id": "migrate",
        "idempotency_key": "run-1:tool-3",
        "observation": "the migration script exited zero",
        "adapter": "openclaw",
        **overrides,
    }


def _proposal(**overrides) -> dict:
    return {
        "identity": IDENTITY,
        "task_id": "migrate",
        "base_revision": 2,
        "idempotency_key": "run-1:tool-3",
        "operations": [OPERATION],
        "adapter": "openclaw",
        **overrides,
    }


def _lifecycle(**overrides) -> dict:
    return {
        "identity": IDENTITY,
        "task_id": "migrate",
        "action": "complete",
        "expected_revision": 3,
        "idempotency_key": "run-1:end",
        "adapter": "openclaw",
        **overrides,
    }


REQUESTS = (
    (HostTaskObservationRequest, _observation),
    (HostTaskProposalRequest, _proposal),
    (HostTaskLifecycleRequest, _lifecycle),
)


# --- session identity -------------------------------------------------------


def test_a_complete_identity_round_trips() -> None:
    identity = HostSessionIdentity.from_dict(IDENTITY)
    assert identity.to_dict()["format"] == "atmem-host-session-identity-v1"
    assert HostSessionIdentity.from_dict(identity.to_dict()) == identity


@pytest.mark.parametrize("field", ["host_type", "session_key", "session_epoch"])
@pytest.mark.parametrize("bad", [None, "", "   "])
def test_a_partial_identity_is_malformed_not_resolved(field: str, bad) -> None:
    """Every absent, empty, and blank case for every part, in both directions.

    This is the negative set that matters: the host may legally pass nothing,
    so each of these arrives in practice.
    """
    payload = {**IDENTITY, field: bad}
    if bad is None:
        payload.pop(field)
    with pytest.raises(ValueError, match="incomplete host session identity"):
        HostSessionIdentity.from_dict(payload)


def test_identity_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="unknown fields"):
        HostSessionIdentity.from_dict({**IDENTITY, "tenant": "acme"})


# --- host request contracts -------------------------------------------------


@pytest.mark.parametrize("contract,build", REQUESTS)
def test_requests_round_trip_and_match_their_published_schema(contract, build) -> None:
    request = contract.from_dict(build())
    assert contract.from_dict(request.to_dict()) == request
    schema_name = next(
        name for name, fmt in HOST_SCHEMAS.items() if fmt == contract.format
    )
    validate(as_json_document(request.to_dict()), load(schema_name))


@pytest.mark.parametrize("contract,build", REQUESTS)
@pytest.mark.parametrize(
    "smuggled",
    ["actor_role", "role", "capability", "capabilities", "authority", "permissions"],
)
def test_requests_reject_caller_supplied_authority(contract, build, smuggled) -> None:
    """Malformed, not honoured and not silently ignored.

    Ignoring the field would leave the caller believing it was accepted, which
    is the failure mode worth avoiding: a host that thinks it asked for
    operator authority and got a success is a host that will ask again.
    """
    with pytest.raises(ValueError, match="caller-supplied authority fields"):
        contract.from_dict(build(**{smuggled: "operator"}))


@pytest.mark.parametrize("contract,build", REQUESTS)
@pytest.mark.parametrize("field", ["host_type", "session_key", "session_epoch"])
def test_requests_reject_incomplete_session_identity(contract, build, field) -> None:
    identity = {k: v for k, v in IDENTITY.items() if k != field}
    with pytest.raises(ValueError, match="incomplete host session identity"):
        contract.from_dict(build(identity=identity))


@pytest.mark.parametrize("contract,build", REQUESTS)
def test_requests_require_session_identity_at_all(contract, build) -> None:
    payload = build()
    payload.pop("identity")
    with pytest.raises(ValueError, match="incomplete host session identity"):
        contract.from_dict(payload)


@pytest.mark.parametrize("contract,build", REQUESTS)
def test_requests_reject_unknown_fields(contract, build) -> None:
    with pytest.raises(ValueError, match="unknown fields"):
        contract.from_dict(build(priority="high"))


def test_a_host_may_not_request_cancellation() -> None:
    """Cancellation is operator-only under the Governance Matrix (FR-045).

    Absent from the permitted set rather than checked later, so there is no
    code path where a host cancel could be evaluated at all.
    """
    with pytest.raises(ValueError, match="host lifecycle action must be one of"):
        HostTaskLifecycleRequest.from_dict(_lifecycle(action="cancel"))
    assert "cancel" not in HostTaskLifecycleRequest.PERMITTED_ACTIONS


def test_a_proposal_must_carry_at_least_one_operation() -> None:
    with pytest.raises(ValueError, match="at least one operation"):
        HostTaskProposalRequest.from_dict(_proposal(operations=[]))


def test_a_proposal_base_revision_starts_at_one() -> None:
    with pytest.raises(ValueError, match="base_revision starts at 1"):
        HostTaskProposalRequest.from_dict(_proposal(base_revision=0))


# --- operation parsing ------------------------------------------------------


def test_operation_parsing_is_closed_and_honours_an_assurance_ceiling() -> None:
    operation = TaskOperation.from_dict(OPERATION)
    assert operation.kind is OperationKind.SET_ITEM_STATUS
    assert operation.status is ItemStatus.COMPLETED

    with pytest.raises(ValueError, match="unknown fields"):
        TaskOperation.from_dict({**OPERATION, "confidence": 0.9})

    # A channel that knows its own ceiling imposes it rather than trusting the
    # payload: a model interpretation cannot assert a verified outcome.
    from atmem.contracts.task_state import Assurance

    claimed = TaskOperation.from_dict(
        {**OPERATION, "assurance": "independently_verified"},
        assurance=Assurance.MODEL_INTERPRETED,
    )
    assert claimed.assurance is Assurance.MODEL_INTERPRETED


# --- session binding --------------------------------------------------------


def _binding(**overrides) -> SessionBinding:
    fields = {
        "binding_id": "binding-1",
        "scope": SCOPE,
        "identity": HostSessionIdentity.from_dict(IDENTITY),
        "task_id": "migrate",
        **overrides,
    }
    return SessionBinding(
        **fields,
        actor="you@example.com",
        reason="drive the migration from this conversation",
        registered_at_utc="2026-09-05T09:00:00+00:00",
        evidence=(EvidenceRef("operator_request", "req-1"),),
    )


def test_a_binding_round_trips_and_matches_its_schema() -> None:
    binding = _binding()
    assert SessionBinding.from_dict(binding.to_dict()) == binding
    validate(as_json_document(binding.to_dict()), load("task-session-binding.json"))


def test_task_id_is_the_target_and_not_part_of_the_uniqueness_key() -> None:
    """What makes bindings many-to-one, and retargeting inexpressible as an update.

    Two bindings differing only by target collide on the key, so repointing a
    session cannot be written as an upsert -- it has to be a revoke and a
    register, each carrying its own authority and evidence.
    """
    assert _binding().key() == _binding(task_id="docs-audit").key()
    assert _binding().key() == (
        "subject-1", "agent-1", "workspace-1", "openclaw", "session-1", "epoch-1",
    )


def test_the_session_generation_is_part_of_the_key() -> None:
    """A new conversation incarnation simply does not match an active row.

    Exact scope alone does not separate conversations: a recycled key in the
    same subject/agent/workspace would otherwise inherit the earlier binding.
    """
    other = SessionBinding.from_dict(
        {**_binding().to_dict(), "identity": {**IDENTITY, "session_epoch": "epoch-2"}}
    )
    assert other.key() != _binding().key()


def test_revocation_is_recorded_rather_than_deleted() -> None:
    binding = _binding(
        revoked_at_utc="2026-09-05T10:00:00+00:00",
        revoked_by="you@example.com",
        revoked_reason="conversation finished",
    )
    assert not binding.active
    assert _binding().active


def test_only_explicit_and_bound_resolutions_deliver() -> None:
    """There is deliberately no resolution value meaning "chose one"."""
    delivering = {r for r in BindingResolution if r.delivers}
    assert delivering == {BindingResolution.EXPLICIT, BindingResolution.BOUND}


# --- profile binding lifetime (T060) ---------------------------------------


def test_general_v1_declares_a_supplemental_binding_lifetime() -> None:
    assert GENERAL_V1.binding_lifetime_ms == 12 * 60 * 60 * 1000


def test_a_profile_persisted_before_the_amendment_still_loads() -> None:
    """Absent is the correct default: no supplemental expiry, and no migration."""
    legacy = {
        "format": "atmem-task-profile-v1",
        "profile_id": "legacy",
        "version": "legacy-v1",
        "phases": ["plan", "complete"],
        "phase_transitions": [["plan", "complete"]],
        "required_item_kinds": [],
        "optional_context_fields": [],
        "permitted_operations": ["set_item_status"],
        "no_progress_action_threshold": 3,
        "expiry": {"max_absolute_age_ms": None, "max_no_progress_age_ms": None},
        "allow_schema_extension_phases": [],
        "description": "",
    }
    profile = TaskProfile.from_dict(legacy)
    assert profile.binding_lifetime_ms is None
    validate(as_json_document(profile.to_dict()), load("task-profile.json"))


def test_the_published_profile_schema_accepts_both_shapes() -> None:
    schema = load("task-profile.json")
    validate(as_json_document(GENERAL_V1.to_dict()), schema)
    without = {k: v for k, v in GENERAL_V1.to_dict().items() if k != "binding_lifetime_ms"}
    validate(as_json_document(without), schema)


def test_a_binding_lifetime_must_be_positive_when_present() -> None:
    with pytest.raises(ValueError, match="binding_lifetime_ms must be a positive"):
        TaskProfile.from_dict({**GENERAL_V1.to_dict(), "binding_lifetime_ms": 0})


def test_the_published_schema_says_the_lifetime_is_not_a_substitute() -> None:
    """The distinction is load-bearing, so the published contract carries it.

    A lifetime cannot detect a reset that happens inside it. An integrator
    reading only the schema could otherwise conclude a TTL is sufficient on its
    own, which is exactly the unsafe design FR-052 rules out -- so the warning
    belongs in the artefact they read, not only in our source comments.
    """
    description = load("task-profile.json")["properties"]["binding_lifetime_ms"][
        "description"
    ]
    assert "Never a substitute for a host reset signal" in description
    assert "cannot detect a reset occurring inside it" in description
