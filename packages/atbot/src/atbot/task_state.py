"""Reading an observation for what it says about a task.

AtBot's job here is narrow and its authority is nil. It receives a snapshot
AtMem already authorized plus one observation, and it suggests a bounded delta
against an exact base revision. It cannot invent items, widen scope, unlock a
schema, expire a task, or commit anything.

The prompt and the extraction are independently authored. Observation text is
always treated as data: an instruction found inside it is a reason to refuse,
never a reason to comply.
"""

from __future__ import annotations

import re
from typing import Any

from atbot.domain import TaskStateDelta
from atbot.extraction import refusal_reasons
from atbot.prompts import build_task_observation_prompt
from atbot.providers.base import ModelProvider


# Exactly the operations AtMem accepts. Anything else is dropped before it can
# travel, so a malformed model row never reaches the authority boundary.
ALLOWED_OPERATIONS = frozenset(
    {
        "set_phase",
        "set_item_status",
        "set_item_content",
        "set_item_blocker",
        "satisfy_constraint",
        "mark_source_inspected",
    }
)

ALLOWED_STATUSES = frozenset(
    {"pending", "ready", "running", "blocked", "completed", "skipped", "failed"}
)

MAX_OPERATIONS = 10

DELTA_SCHEMA: dict[str, Any] = {
    "title": "AtBotTaskStateDelta",
    "type": "object",
    "additionalProperties": False,
    "required": ["operations"],
    "properties": {
        "operations": {
            "type": "array",
            "maxItems": MAX_OPERATIONS,
            "items": {
                "type": "object",
                "required": ["kind"],
                "properties": {
                    "kind": {"enum": sorted(ALLOWED_OPERATIONS)},
                    "item_id": {"type": ["string", "null"]},
                    "constraint_id": {"type": ["string", "null"]},
                    "source_id": {"type": ["string", "null"]},
                    "phase": {"type": ["string", "null"]},
                    "status": {"type": ["string", "null"]},
                    "content": {"type": ["object", "null"]},
                    "reason": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string", "maxLength": 500},
    },
}


def propose_task_delta(
    provider: ModelProvider,
    *,
    snapshot: dict[str, Any],
    observation: str,
    task_id: str,
    base_revision: int,
) -> TaskStateDelta | None:
    """Suggest one bounded delta, or nothing at all.

    Returns None when the observation is hostile, empty, or says nothing about
    the task. Returning nothing is a normal outcome: AtMem records `no_change`
    rather than inventing progress.
    """
    text = " ".join(str(observation or "").split())
    if not text or refusal_reasons(text):
        # Hostile or excluded content never becomes a proposal, and the model
        # is not asked about it in the first place.
        return None

    known_items = {
        str(row.get("item_id"))
        for row in snapshot.get("items") or ()
        if row.get("item_id")
    }
    known_constraints = {
        str(row.get("constraint_id"))
        for row in snapshot.get("constraints") or ()
        if row.get("constraint_id")
    }
    known_sources = {str(row) for row in snapshot.get("sources_to_inspect") or ()}
    known_phases = {str(row) for row in snapshot.get("phases") or ()}

    bundle = build_task_observation_prompt(snapshot, text)
    result = provider.complete(
        system=bundle.system, prompt=bundle.prompt, schema=DELTA_SCHEMA
    )
    value = result.structured if isinstance(result.structured, dict) else {}

    operations: list[dict[str, Any]] = []
    affected: list[str] = []
    for row in value.get("operations") or ():
        operation = _clean_operation(
            row,
            known_items=known_items,
            known_constraints=known_constraints,
            known_sources=known_sources,
            known_phases=known_phases,
        )
        if operation is None:
            continue
        operations.append(operation)
        if operation.get("item_id"):
            affected.append(str(operation["item_id"]))
        if len(operations) >= MAX_OPERATIONS:
            break

    if not operations:
        return None

    confidence = _confidence(value.get("confidence"))
    reason = " ".join(str(value.get("reason") or "").split())[:500]
    if refusal_reasons(reason):
        reason = ""
    return TaskStateDelta(
        task_id=str(task_id),
        base_revision=int(base_revision),
        operations=tuple(operations),
        affected_item_ids=tuple(dict.fromkeys(affected)),
        confidence=confidence,
        reason=reason,
        assurance="model_interpreted",
    )


def _clean_operation(
    row: Any,
    *,
    known_items: set[str],
    known_constraints: set[str],
    known_sources: set[str],
    known_phases: set[str],
) -> dict[str, Any] | None:
    """Keep an operation only if it names something the snapshot really has."""
    if not isinstance(row, dict):
        return None
    kind = str(row.get("kind") or "")
    if kind not in ALLOWED_OPERATIONS:
        return None

    operation: dict[str, Any] = {"kind": kind}

    if kind in {"set_item_status", "set_item_content", "set_item_blocker"}:
        item_id = str(row.get("item_id") or "")
        # An item AtBot did not receive is an invented item.
        if item_id not in known_items:
            return None
        operation["item_id"] = item_id

    if kind == "set_item_status":
        status = str(row.get("status") or "")
        if status not in ALLOWED_STATUSES:
            return None
        operation["status"] = status
        if status in {"blocked", "skipped"}:
            reason = " ".join(str(row.get("reason") or "").split())[:500]
            if not reason or refusal_reasons(reason):
                return None
            operation["reason"] = reason

    if kind == "set_item_content":
        content = row.get("content")
        if not isinstance(content, dict):
            return None
        operation["content"] = content

    if kind == "set_item_blocker":
        reason = " ".join(str(row.get("reason") or "").split())[:500]
        if not reason or refusal_reasons(reason):
            return None
        operation["reason"] = reason

    if kind == "set_phase":
        phase = str(row.get("phase") or "")
        if known_phases and phase not in known_phases:
            return None
        if not phase:
            return None
        operation["phase"] = phase

    if kind == "satisfy_constraint":
        constraint_id = str(row.get("constraint_id") or "")
        if constraint_id not in known_constraints:
            return None
        operation["constraint_id"] = constraint_id

    if kind == "mark_source_inspected":
        source_id = str(row.get("source_id") or "")
        if source_id not in known_sources:
            return None
        operation["source_id"] = source_id

    return operation


def _confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    return number if 0.0 <= number <= 1.0 else 0.5
