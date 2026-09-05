"""The Governance Matrix, as executable code rather than a table in a doc.

Every capability here is derived from a role, not read from a string an actor
supplied. That distinction is the whole point: a caller claiming to be an
administrator gets exactly the capabilities the administrator row grants, and a
caller claiming a role that does not exist gets nothing.

AtMem is the only row that commits. The scoped policy evaluator exists to own
exactly one action — expiry — so that ageing out a task can never be spelled as
an agent cancellation or an operator override.
"""

from __future__ import annotations

from atmem.contracts.task_state import ActorRole, GovernanceCapability


GOVERNANCE_MATRIX: dict[ActorRole, GovernanceCapability] = {
    ActorRole.ATMEM_AUTHORITY: GovernanceCapability(
        actor_role=ActorRole.ATMEM_AUTHORITY,
        read_state=True,
        propose_delta=True,
        commit_state=True,
        correct_state=True,
        register_profile=True,
        change_lifecycle=True,
        deliver_context=True,
        delete_state=True,
    ),
    # Owns expiry and nothing else. It cannot read content, propose, or commit
    # anything other than the terminal transition its rule requires.
    ActorRole.POLICY_EVALUATOR: GovernanceCapability(
        actor_role=ActorRole.POLICY_EVALUATOR,
        expire_task=True,
    ),
    # May propose. May never write, complete, cancel, expire, inject, or delete.
    ActorRole.ATBOT_INTELLIGENCE: GovernanceCapability(
        actor_role=ActorRole.ATBOT_INTELLIGENCE,
        read_state=True,
        propose_delta=True,
    ),
    ActorRole.HOST_AGENT: GovernanceCapability(
        actor_role=ActorRole.HOST_AGENT,
        read_state=True,
        propose_delta=True,
    ),
    ActorRole.OPERATOR: GovernanceCapability(
        actor_role=ActorRole.OPERATOR,
        read_state=True,
        propose_delta=True,
        correct_state=True,
        change_lifecycle=True,
    ),
    # Administrative permission is distinct from ordinary operator access.
    ActorRole.ADMINISTRATOR: GovernanceCapability(
        actor_role=ActorRole.ADMINISTRATOR,
        read_state=True,
        propose_delta=True,
        correct_state=True,
        register_profile=True,
        change_lifecycle=True,
        delete_state=True,
    ),
    # Supplies stronger evidence for a bounded claim; owns no state.
    ActorRole.VERIFIER: GovernanceCapability(
        actor_role=ActorRole.VERIFIER,
        read_state=True,
        propose_delta=True,
    ),
    ActorRole.AUDITOR: GovernanceCapability(
        actor_role=ActorRole.AUDITOR,
        read_state=True,
    ),
    # No task access by default: a delegated context provider governs memory
    # retrieval, not execution state.
    ActorRole.DELEGATED_PROVIDER: GovernanceCapability(
        actor_role=ActorRole.DELEGATED_PROVIDER,
    ),
}

GOVERNANCE_ACTIONS = (
    "read_state",
    "propose_delta",
    "commit_state",
    "correct_state",
    "register_profile",
    "change_lifecycle",
    "expire_task",
    "deliver_context",
    "delete_state",
)


class CapabilityDenied(PermissionError):
    """A governance action was requested by a role that does not hold it."""

    reason_code = "capability_denied"

    def __init__(self, actor_role: ActorRole, action: str) -> None:
        super().__init__(
            f"{actor_role.value} may not {action.replace('_', ' ')}"
        )
        self.actor_role = actor_role
        self.action = action


def capability_for(actor_role: ActorRole) -> GovernanceCapability:
    """The capabilities of one role. An unknown role holds nothing."""
    return GOVERNANCE_MATRIX.get(
        actor_role, GovernanceCapability(actor_role=actor_role)
    )


def permits(actor_role: ActorRole, action: str) -> bool:
    if action not in GOVERNANCE_ACTIONS:
        raise ValueError(f"unknown governance action: {action!r}")
    return capability_for(actor_role).permits(action)


def require(actor_role: ActorRole, action: str) -> None:
    """Raise unless this role holds this capability."""
    if not permits(actor_role, action):
        raise CapabilityDenied(actor_role, action)


def matrix_rows() -> list[dict[str, object]]:
    """The whole matrix, for documentation and conformance fixtures."""
    return [
        {
            "actor_role": role.value,
            **{action: capability_for(role).permits(action) for action in GOVERNANCE_ACTIONS},
        }
        for role in ActorRole
    ]
