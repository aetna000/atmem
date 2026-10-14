"""Selective, single-call memory-transition classifier contract.

This module contains no storage mutation methods.  It constructs one bounded
Choice request from already-authorized state, retains the opaque option mapping
inside AtMem, validates exactly one model response, and returns a proposal for
the authority layer to revalidate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Sequence

from .contracts_v2 import response_confidence, validate_typed_response
from .formation_v2 import evaluation_request


PLAN_VERSION = "memory-formation-selective-v3"
QUESTION_ID = "formation.joint_transition.v3"
MAX_TARGETS = 32
MAX_OPTIONS = 255

DEFAULT_LEARNED_OPERATIONS = (
    "STORE_NEW",
    "DO_NOT_STORE",
    "UPDATE_EXISTING",
    "SUPERSEDE_EXISTING",
    "DUPLICATE",
)
NON_RELATIONAL = frozenset({"STORE_NEW", "DO_NOT_STORE"})
RELATIONAL = frozenset({
    "UPDATE_EXISTING", "SUPERSEDE_EXISTING", "DUPLICATE", "FORGET_EXISTING",
})
DESCRIPTIONS = {
    "STORE_NEW": "Create a distinct durable memory from the observation.",
    "DO_NOT_STORE": "Do not create persistent memory from the observation.",
    "UPDATE_EXISTING": "Add compatible information to the referenced active memory.",
    "SUPERSEDE_EXISTING": "Replace the referenced active memory because it is no longer current.",
    "DUPLICATE": "The referenced active memory already represents the same meaning.",
    "FORGET_EXISTING": "Honor an authorized request to retire the referenced active memory.",
}


@dataclass(frozen=True, slots=True)
class JointOptionBindingV3:
    option_id: str
    operation: str
    target_alias: str | None
    target_memory_id: str | None


@dataclass(frozen=True, slots=True)
class JointChoiceBundleV3:
    request: dict[str, Any]
    bindings: tuple[JointOptionBindingV3, ...]
    target_aliases: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class JointChoiceResultV3:
    disposition: str
    operation: str
    target_memory_id: str | None
    selected_option_id: str | None
    confidence: float | None
    probabilities: dict[str, float]
    reason_code: str
    model_calls: int
    plan_version: str = PLAN_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {"format": "atmem-selective-formation-result-v3", **asdict(self)}


def _ranked_targets(
    memories: Sequence[Mapping[str, Any]], *, required_target_ids: set[str],
    maximum: int,
) -> list[dict[str, Any]]:
    if maximum <= 0 or maximum > MAX_TARGETS:
        raise ValueError(f"maximum_targets must be within [1,{MAX_TARGETS}]")
    indexed = {str(item["id"]): dict(item) for item in memories}
    if len(indexed) != len(memories):
        raise ValueError("retrieved memory identifiers must be unique")
    missing = required_target_ids - set(indexed)
    if missing:
        raise ValueError("required target is not in the authorized retrieved state")
    if len(required_target_ids) > maximum:
        raise ValueError("required targets exceed the bounded target capacity")
    ranked = sorted(
        indexed.values(),
        key=lambda item: (-float(item.get("retrieval_score", 0.0)), str(item["id"])),
    )
    selected = ranked[:maximum]
    selected_ids = {str(item["id"]) for item in selected}
    for identity in sorted(required_target_ids - selected_ids):
        replaceable = [
            index for index, item in enumerate(selected)
            if str(item["id"]) not in required_target_ids
        ]
        if not replaceable:
            raise ValueError("required targets exceed the bounded target capacity")
        selected[replaceable[-1]] = indexed[identity]
    return sorted(
        selected,
        key=lambda item: (-float(item.get("retrieval_score", 0.0)), str(item["id"])),
    )


def build_joint_choice_v3(
    *, request_id: str, scope_id: str, canonical_generation: int,
    observation: Mapping[str, Any],
    retrieved_memories: Sequence[Mapping[str, Any]],
    allowed_operations: Sequence[str] = DEFAULT_LEARNED_OPERATIONS,
    required_target_ids: set[str] | None = None,
    maximum_targets: int = MAX_TARGETS,
    retriever_revision: str = "atmem-retrieval-v3",
) -> JointChoiceBundleV3:
    """Build one deterministic joint action-target Choice request."""

    operations = tuple(dict.fromkeys(str(value) for value in allowed_operations))
    unknown = set(operations) - set(DESCRIPTIONS)
    if unknown:
        raise ValueError(f"unsupported learned operations: {sorted(unknown)}")
    if not set(operations) & NON_RELATIONAL:
        raise ValueError("at least one non-relational operation is required")
    required = set(required_target_ids or ())
    targets = _ranked_targets(
        retrieved_memories, required_target_ids=required, maximum=maximum_targets,
    ) if retrieved_memories else []
    aliases = {
        str(item["id"]): f"target_{index:02d}"
        for index, item in enumerate(targets)
    }
    sanitized_memories = []
    for item in targets:
        sanitized = dict(item)
        sanitized["id"] = aliases[str(item["id"])]
        sanitized_memories.append(sanitized)

    bindings: list[JointOptionBindingV3] = []
    for operation in operations:
        if operation in NON_RELATIONAL:
            bindings.append(JointOptionBindingV3(
                option_id="", operation=operation,
                target_alias=None, target_memory_id=None,
            ))
        else:
            for item in targets:
                identity = str(item["id"])
                bindings.append(JointOptionBindingV3(
                    option_id="", operation=operation,
                    target_alias=aliases[identity], target_memory_id=identity,
                ))
    if not 2 <= len(bindings) <= MAX_OPTIONS:
        raise ValueError("joint option count must be within [2,255]")
    bindings = [
        JointOptionBindingV3(
            option_id=f"option_{index:03d}", operation=item.operation,
            target_alias=item.target_alias, target_memory_id=item.target_memory_id,
        )
        for index, item in enumerate(bindings)
    ]
    question = {
        "question_id": QUESTION_ID,
        "type": "choice",
        "instructions": (
            "Select the one memory-state transition supported by the authorized "
            "observation and retrieved active memories."
        ),
        "options": [
            {
                "id": item.option_id,
                "description": (
                    DESCRIPTIONS[item.operation]
                    if item.target_alias is None else
                    f"{DESCRIPTIONS[item.operation]} Target: {item.target_alias}."
                ),
            }
            for item in bindings
        ],
    }
    request = evaluation_request(
        request_id=request_id, scope_id=scope_id,
        canonical_generation=canonical_generation,
        observation=observation, retrieved_memories=sanitized_memories,
        question=question, retriever_revision=retriever_revision,
        requested_top_k=max(len(retrieved_memories), len(sanitized_memories)),
    )
    request["formation_plan_version"] = PLAN_VERSION
    return JointChoiceBundleV3(
        request=request, bindings=tuple(bindings),
        target_aliases=tuple(sorted((alias, identity) for identity, alias in aliases.items())),
    )


def evaluate_joint_choice_v3(
    engine: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    bundle: JointChoiceBundleV3, *, confidence_threshold: float = 0.8,
) -> JointChoiceResultV3:
    """Invoke the classifier exactly once and return a non-authoritative result."""

    if not 0.0 <= float(confidence_threshold) <= 1.0:
        raise ValueError("confidence_threshold must be within [0,1]")
    try:
        response = dict(engine(bundle.request))
        validate_typed_response(
            response, bundle.request["question"],
            request_id=str(bundle.request["request_id"]),
        )
    except Exception as exc:
        return JointChoiceResultV3(
            disposition="runtime_failed", operation="REVIEW",
            target_memory_id=None, selected_option_id=None, confidence=None,
            probabilities={}, reason_code=f"invalid_model_output:{type(exc).__name__}",
            model_calls=1,
        )
    confidence = response_confidence(response)
    if confidence < float(confidence_threshold):
        return JointChoiceResultV3(
            disposition="model_abstained", operation="REVIEW",
            target_memory_id=None, selected_option_id=str(response["choice"]),
            confidence=confidence,
            probabilities={key: float(value) for key, value in response["probabilities"].items()},
            reason_code="calibrated_low_confidence", model_calls=1,
        )
    mapping = {item.option_id: item for item in bundle.bindings}
    selected = mapping[str(response["choice"])]
    return JointChoiceResultV3(
        disposition="model_delegated", operation=selected.operation,
        target_memory_id=selected.target_memory_id,
        selected_option_id=selected.option_id, confidence=confidence,
        probabilities={key: float(value) for key, value in response["probabilities"].items()},
        reason_code="validated_joint_choice", model_calls=1,
    )
