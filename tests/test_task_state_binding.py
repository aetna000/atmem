"""Session-to-task binding: the premises Amendment A rests on.

Spec 007 Amendment A adds an operator-registered session-to-task binding
because no OpenClaw hook supplies a governed task identity, and adds a
host-boundary write path because the adapter boundary has none. Both are claims
about the world as it is today, not permanent truths.

This module holds the Python half of the T058 premise gate. It asserts only
what Python can actually prove. Whether a host populates a field at runtime is
a TypeScript question answered against a pinned dependency by
``integrations/openclaw/test/hook-context-compat.mjs``; asserting it from here
would either read a globally installed OpenClaw, whose version CI cannot
control, or mistake a type declaration for runtime behaviour.

A failure here does not mean something broke. It means a premise moved, and the
amendment should be re-scoped against the new ground rather than patched to keep
the old assertion true.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from atmem.control.server import _tools
from atmem.store.sqlite import _BOOTSTRAP_MIGRATIONS

# Frozen record of the surface Amendment A was written against. The premise
# "the adapter boundary has no task write path" is a claim about *this*, and it
# stays checkable after T069 and T073 add tools -- unlike an assertion against
# the live surface, which would have to be weakened to let the amendment land,
# and would stop being evidence at the moment it mattered.
PRE_AMENDMENT_SURFACE_FIXTURE = (
    Path(__file__).parent / "fixtures" / "task_state" / "pre-amendment-mcp-surface.json"
)

# The two task tools that predate Amendment A. Both are read-and-deliver:
# prepare the authorized context, then confirm it reached the model boundary.
PRE_AMENDMENT_TASK_TOOLS = frozenset(
    {"control_prepare_task_context", "control_task_exposure_shown"}
)

# The only tools Amendment A authorizes at the host boundary, and the task that
# adds each. Anything else appearing on the live surface is unreviewed: the
# allowlist is written ahead of the implementation so T069 and T073 land without
# editing this file, and so a fourth tool cannot arrive unnoticed.
AMENDMENT_A_TOOLS = {
    "control_observe_task_step": "T069",
    "control_propose_task_delta": "T073",
    "control_request_task_lifecycle": "T073",
}

# Inputs that would let a caller move task state rather than read it. A tool
# accepting any of these is a write path regardless of what it is called.
TASK_MUTATING_INPUTS = frozenset(
    {
        "status",
        "item_id",
        "items",
        "delta",
        "deltas",
        "expected_revision",
        "base_revision",
        "lifecycle",
        "phase",
        "constraints",
        "operations",
    }
)

# Inputs that name a governed task. A tool taking one is task-facing whatever
# its name suggests.
TASK_IDENTITY_INPUTS = frozenset({"task_id", "task", "governed_task_id"})

# Spec 007 reserves this bootstrap range; see specs/integration-ownership.md.
SPEC_007_MIGRATION_RANGE = range(70, 80)


def _inventory(*, operator: bool) -> dict[str, set[str]]:
    """Every registered tool mapped to its declared input property names."""
    return {
        tool["name"]: set(tool["inputSchema"].get("properties", {}))
        for tool in _tools(operator=operator)
    }


def _recorded_surface() -> dict[str, dict[str, set[str]]]:
    document = json.loads(PRE_AMENDMENT_SURFACE_FIXTURE.read_text(encoding="utf-8"))
    assert document["format"] == "atmem-pre-amendment-mcp-surface-v1"
    return {
        label: {name: set(properties) for name, properties in tools.items()}
        for label, tools in document["surfaces"].items()
    }


def test_the_recorded_pre_amendment_surface_had_no_task_write_path() -> None:
    """The premise, checked against the frozen record rather than the live one.

    Amendment A's second gap is that the adapter boundary could read governed
    task state and not change it. That is a statement about the surface as it
    was, so it is asserted against the recording -- permanently true, and never
    something a later task has to soften.
    """
    for label, tools in _recorded_surface().items():
        for name, properties in tools.items():
            mutating = properties & TASK_MUTATING_INPUTS
            assert not mutating, (
                f"recorded {label} tool {name} declares task-mutating inputs "
                f"{sorted(mutating)}; the amendment's premise was false when written."
            )
        # Subset, not equality: `control_task_exposure_shown` is keyed by
        # `delivery_id` rather than `task_id`, so it is task-facing by purpose
        # while taking no task identity. Preparation is what names a task;
        # confirmation only acknowledges the delivery preparation authorized.
        task_facing = {n for n, p in tools.items() if p & TASK_IDENTITY_INPUTS}
        assert task_facing <= PRE_AMENDMENT_TASK_TOOLS, (
            f"recorded {label} surface has task-facing tools outside the two known "
            f"ones: {sorted(task_facing - PRE_AMENDMENT_TASK_TOOLS)}"
        )
        assert "control_prepare_task_context" in task_facing, (
            f"recorded {label} surface lost the tool that names a task"
        )


def test_the_live_surface_adds_only_tools_amendment_a_authorizes() -> None:
    """The live surface may grow, but only by tools this amendment named.

    Written before T069 and T073 exist, so it passes now with none of them
    present and keeps passing as each lands -- while still failing on a fourth
    tool nobody reviewed.
    """
    recorded = _recorded_surface()
    for label, operator in (("host", False), ("operator", True)):
        live = set(_inventory(operator=operator))
        removed = set(recorded[label]) - live
        assert not removed, f"{label} surface dropped pre-amendment tools {sorted(removed)}"

        added = live - set(recorded[label])
        unauthorized = added - set(AMENDMENT_A_TOOLS)
        assert not unauthorized, (
            f"{label} surface gained unreviewed tools {sorted(unauthorized)}. "
            "Amendment A authorizes only "
            f"{sorted(AMENDMENT_A_TOOLS)}; add a tool here only with the task that "
            "specifies its authority boundary."
        )


def test_only_authorized_tools_may_take_task_identity_or_mutate() -> None:
    """Task identity and mutation stay confined to the reviewed set.

    This is the assertion that must survive the amendment, so it is written
    against the allowlist rather than against "nothing may mutate" -- which
    T069 and T073 would have made false by design.
    """
    allowed = PRE_AMENDMENT_TASK_TOOLS | set(AMENDMENT_A_TOOLS)
    for operator in (False, True):
        for name, properties in _inventory(operator=operator).items():
            if properties & (TASK_MUTATING_INPUTS | TASK_IDENTITY_INPUTS):
                assert name in allowed, (
                    f"{name} takes task identity or mutating inputs but is not a "
                    f"reviewed task tool; allowed: {sorted(allowed)}"
                )

    # The two pre-amendment tools stay read-and-deliver even as others arrive.
    for operator in (False, True):
        for name, properties in _inventory(operator=operator).items():
            if name not in PRE_AMENDMENT_TASK_TOOLS:
                continue
            mutating = properties & TASK_MUTATING_INPUTS
            assert not mutating, (
                f"{name} gained mutating inputs {sorted(mutating)}; it is one of the "
                "two read-and-deliver tools and must stay that way."
            )


def test_spec_007_spent_its_migration_budget_exactly_as_planned() -> None:
    """`0078` is the binding table; `0079` is the last identifier left.

    T058 recorded that two identifiers remained and that Amendment A budgeted
    one of them. T062 has now spent it. What stays worth asserting is that the
    budget was honoured -- the binding table took `0078` and nothing else in
    the amendment reached for a second -- and that exactly one identifier
    remains, so the next piece of Spec 007 schema work either fits `0079` or
    goes through the Spec 010 registry. Discovering that mid-implementation is
    the failure this prevents.
    """
    applied = {
        int(match.group(1))
        for identifier, _ in _BOOTSTRAP_MIGRATIONS
        if (match := re.match(r"^(\d{4})_", identifier))
        and int(match.group(1)) in SPEC_007_MIGRATION_RANGE
    }
    free = sorted(set(SPEC_007_MIGRATION_RANGE) - applied)

    assert free == [79], (
        f"Spec 007's reserved block 0070-0079 has {len(free)} identifiers free "
        f"({free}). Amendment A budgeted exactly one, for the session-binding "
        "table; a different count means the budget was not honoured."
    )
    binding_steps = [
        identifier
        for identifier, _ in _BOOTSTRAP_MIGRATIONS
        if identifier.startswith("0078")
    ]
    assert binding_steps == ["0078_governed_task_session_bindings"]


def test_bootstrap_migration_identifiers_are_unique_and_ordered() -> None:
    """Append-only means an identifier is never renumbered, reused, or edited."""
    identifiers = [identifier for identifier, _ in _BOOTSTRAP_MIGRATIONS]
    assert len(identifiers) == len(set(identifiers))
    assert identifiers == sorted(identifiers)
