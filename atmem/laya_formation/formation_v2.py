"""Deterministic V2 formation plan and typed-response receptor.

Laya answers one bounded question at a time.  This module owns the sequence and
combines validated answers into a proposal; it has no storage mutation methods.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping, Sequence

from atmem.core.canonical import canonical_json, sha256_hex

from .contracts_v2 import (
    REQUEST_FORMAT, SCHEMA_VERSION, response_confidence,
    validate_evaluation_request, validate_typed_response,
)


PLAN_VERSION = "memory-formation-plan-v2"
OPERATIONS = (
    "STORE_NEW",
    "UPDATE_EXISTING",
    "SUPERSEDE_EXISTING",
    "DUPLICATE",
    "DO_NOT_STORE",
    "FORGET_EXISTING",
)
MEMORY_CLASSES = (
    "preference", "durable_fact", "procedure", "commitment", "relationship",
    "episode", "temporary_state", "sensitive", "non_memory",
)
TARGET_REQUIRED = frozenset({
    "UPDATE_EXISTING", "SUPERSEDE_EXISTING", "DUPLICATE", "FORGET_EXISTING",
})
MUTATING_OPERATIONS = frozenset({
    "STORE_NEW", "UPDATE_EXISTING", "SUPERSEDE_EXISTING", "FORGET_EXISTING",
})


def evaluation_request(
    *, request_id: str, scope_id: str, canonical_generation: int,
    observation: Mapping[str, Any], retrieved_memories: Sequence[Mapping[str, Any]],
    question: Mapping[str, Any], retriever_revision: str = "atmem-retrieval-v2",
    requested_top_k: int | None = None,
) -> dict[str, Any]:
    """Build and validate one portable typed evaluation request."""

    memories = [dict(item) for item in retrieved_memories]
    requested = len(memories) if requested_top_k is None else int(requested_top_k)
    if requested < len(memories):
        raise ValueError("requested_top_k cannot be smaller than returned memories")
    result_digest = "sha256:" + sha256_hex(canonical_json(memories))
    request = {
        "format": REQUEST_FORMAT, "schema_version": SCHEMA_VERSION,
        "request_id": request_id, "formation_plan_version": PLAN_VERSION,
        "scope_id": scope_id, "canonical_generation": canonical_generation,
        "observation": dict(observation), "retrieved_memories": memories,
        "retrieval_receipt": {
            "retriever_revision": retriever_revision,
            "requested_top_k": requested, "returned_count": len(memories),
            "complete": True, "truncated": False,
            "result_digest": result_digest,
        },
        "question": dict(question),
    }
    validate_evaluation_request(request)
    return request


def context_sufficient_question() -> dict[str, Any]:
    return {
        "question_id": "formation.context_sufficient.v2",
        "type": "noul",
        "instructions": "Do the supplied authorized observation and retrieved memories contain enough relevant context to make a safe memory decision?",
    }


def durable_question() -> dict[str, Any]:
    return {
        "question_id": "formation.is_durable.v2",
        "type": "noul",
        "instructions": "Does the authorized observation express information likely to remain useful in future interactions?",
    }


def operation_question() -> dict[str, Any]:
    descriptions = {
        "STORE_NEW": "Create distinct durable memory not represented by current state.",
        "UPDATE_EXISTING": "Add compatible detail to one active memory.",
        "SUPERSEDE_EXISTING": "Replace one active memory that is no longer current.",
        "DUPLICATE": "The same meaning is already represented by one active memory.",
        "DO_NOT_STORE": "Do not create persistent memory from this observation.",
        "FORGET_EXISTING": "Honor an explicit authorized request to retire one memory.",
    }
    return {
        "question_id": "formation.operation.v2",
        "type": "choice",
        "instructions": "Select the one memory-state operation supported by the authorized evidence.",
        "options": [
            {"id": identity, "description": descriptions[identity]}
            for identity in OPERATIONS
        ],
    }


def memory_class_question() -> dict[str, Any]:
    descriptions = {
        "preference": "Standing user choice or desired assistant behavior.",
        "durable_fact": "Stable fact likely useful in future interactions.",
        "procedure": "Repeatable workflow, instruction, or constraint.",
        "commitment": "Future obligation or promise with continuing relevance.",
        "relationship": "Durable interpersonal relationship information.",
        "episode": "Past event worth retaining as an episode.",
        "temporary_state": "Time-bounded state with short-lived usefulness.",
        "sensitive": "Potentially durable information requiring stricter review.",
        "non_memory": "Content that should not become memory.",
    }
    return {
        "question_id": "formation.memory_class.v2", "type": "choice",
        "instructions": "Classify the observation's supported memory type.",
        "options": [
            {"id": identity, "description": descriptions[identity]}
            for identity in MEMORY_CLASSES
        ],
    }


def target_question(targets: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    options: list[dict[str, str]] = []
    for target in targets:
        identity = str(target["id"])
        description = str(target.get("description") or target.get("content") or identity)
        options.append({"id": identity, "description": description[:1_000]})
    if len(options) < 2:
        # Laya Choice requires at least two options. A single authorized target is
        # selected deterministically by AtMem and never sent as a fake choice.
        raise ValueError("target choice requires at least two authorized targets")
    return {
        "question_id": "formation.target.v2", "type": "choice",
        "instructions": "Select the active memory targeted by the proposed operation.",
        "options": options,
    }


def future_utility_question() -> dict[str, Any]:
    return {
        "question_id": "formation.future_utility.v2", "type": "score",
        "instructions": "Rate the likely future usefulness of retaining the proposed state.",
        "criteria": [
            "No expected future usefulness",
            "Limited future usefulness",
            "Moderate future usefulness",
            "High future usefulness",
            "Very high recurring usefulness",
        ],
    }


@dataclass(frozen=True, slots=True)
class FormationRulingV2:
    operation: str
    memory_class: str | None
    target_memory_id: str | None
    operation_probability: float | None
    target_probability: float | None
    context_sufficient_probability: float
    durable_probability: float
    future_utility_score: float | None
    review_required: bool
    review_reason: str | None
    plan_version: str = PLAN_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {"format": "atmem-formation-ruling-v2", **asdict(self)}


@dataclass(frozen=True, slots=True)
class FormationDecisionReceiptV2:
    request_id: str
    classifier: str
    proposal: Mapping[str, Any]
    authority_result: str
    authority_reason: str
    expected_generation: int
    observed_generation: int
    resulting_generation: int | None = None
    resulting_memory_id: str | None = None
    superseded_memory_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"format": "atmem-formation-decision-receipt-v2", **asdict(self)}


def apply_ruling_to_proposals(
    ruling: FormationRulingV2, proposals: Sequence[Any], *,
    authorized_targets: Sequence[Mapping[str, Any]],
) -> tuple[Any, ...]:
    """Apply one authorized semantic ruling to source-grounded structures.

    The deterministic extractor is allowed to construct evidence-bound memory
    units, but its default ``ADD`` action is not authoritative in Laya mode.
    This receptor replaces that action exactly once and never invents content.
    """

    from atmem.core.canonical import sha256_hex
    from atmem.extract.models import MemoryClass, ProposalAction, ProposalPrecondition

    if ruling.review_required or ruling.operation == "REVIEW":
        return tuple(
            replace(
                proposal, review_required=True,
                reason_codes=tuple(dict.fromkeys(
                    proposal.reason_codes
                    + ("laya_v2_review", ruling.review_reason or "classifier_review")
                )),
            )
            for proposal in proposals
        )
    targets = {str(row["id"]): row for row in authorized_targets}
    target = targets.get(str(ruling.target_memory_id)) if ruling.target_memory_id else None
    if ruling.operation in TARGET_REQUIRED and target is None:
        raise ValueError("Laya ruling target is not in the authorized target set")
    if ruling.operation in {"UPDATE_EXISTING", "SUPERSEDE_EXISTING"} and len(proposals) != 1:
        raise ValueError("a relational Laya ruling requires exactly one structured proposal")

    action = {
        "STORE_NEW": ProposalAction.ADD,
        "UPDATE_EXISTING": ProposalAction.UPDATE,
        "SUPERSEDE_EXISTING": ProposalAction.SUPERSEDE,
        "DUPLICATE": ProposalAction.NOOP,
        "DO_NOT_STORE": ProposalAction.NOOP,
    }.get(ruling.operation)
    if action is None:
        # Forgetting requires a separately authorized deletion workflow.  It is
        # never disguised as an extraction proposal.
        raise ValueError("FORGET_EXISTING requires governed deletion review")
    memory_class = {
        "preference": MemoryClass.DURABLE_FACT,
        "durable_fact": MemoryClass.DURABLE_FACT,
        "procedure": MemoryClass.PROCEDURE,
        "commitment": MemoryClass.DURABLE_FACT,
        "relationship": MemoryClass.DURABLE_FACT,
        "episode": MemoryClass.EPISODE,
        "temporary_state": MemoryClass.TEMPORARY_STATE,
        "sensitive": MemoryClass.DURABLE_FACT,
        "non_memory": MemoryClass.NON_MEMORY,
    }.get(str(ruling.memory_class))
    if memory_class is None:
        raise ValueError("Laya ruling has no supported memory class")

    preconditions: tuple[ProposalPrecondition, ...] = ()
    affected: tuple[str, ...] = ()
    if target is not None:
        target_id = str(target["id"])
        affected = (target_id,)
        preconditions = (
            ProposalPrecondition(
                record_id=target_id,
                generation=int(target.get("generation") or 0),
                status=str(target.get("status") or "active"),
                content_sha256=f"sha256:{sha256_hex(str(target.get('content') or ''))}",
            ),
        )
    return tuple(
        replace(
            proposal, action=action, memory_class=memory_class,
            unit=(proposal.unit if proposal.memory_class is memory_class else None),
            fact_key=(proposal.fact_key if proposal.memory_class is memory_class else None),
            affected_record_ids=affected, preconditions=preconditions,
            reason_codes=tuple(dict.fromkeys(
                proposal.reason_codes
                + (
                    "laya_v2_semantic_ruling",
                    "laya_memory_class_receptor",
                    f"laya_{ruling.operation.lower()}",
                )
            )),
        )
        for proposal in proposals
    )


def revalidate_ruling(
    ruling: FormationRulingV2, *, request_id: str, classifier: str,
    expected_generation: int, observed_generation: int,
    allowed_target_ids: Sequence[str], policy_allowed: bool,
    allow_forget: bool = False,
) -> FormationDecisionReceiptV2:
    """Recheck authority without repeating Laya's semantic classification."""

    if ruling.review_required or ruling.operation == "REVIEW":
        result, reason = "REVIEW", ruling.review_reason or "classifier_review"
    elif observed_generation != expected_generation:
        result, reason = "STALE_STATE", "canonical_generation_changed"
    elif not policy_allowed:
        result, reason = "AUTHORITY_REJECTED", "policy_denied"
    elif ruling.operation == "FORGET_EXISTING" and not allow_forget:
        result, reason = "REVIEW", "forget_requires_explicit_deletion_authority"
    elif ruling.operation in TARGET_REQUIRED and ruling.target_memory_id not in set(allowed_target_ids):
        result, reason = "AUTHORITY_REJECTED", "target_not_authorized"
    elif ruling.operation not in (*OPERATIONS, "REVIEW"):
        result, reason = "AUTHORITY_REJECTED", "unknown_operation"
    else:
        result, reason = "AUTHORIZED_PROPOSAL", "governance_revalidation_passed"
    return FormationDecisionReceiptV2(
        request_id=request_id, classifier=classifier,
        proposal=ruling.to_dict(), authority_result=result,
        authority_reason=reason, expected_generation=expected_generation,
        observed_generation=observed_generation,
    )


class FormationPlanV2:
    """Validate typed answers and produce one non-authoritative ruling."""

    def __init__(
        self, *, context_threshold: float = 0.5,
        durability_threshold: float = 0.5, choice_confidence_threshold: float = 0.5,
    ) -> None:
        for name, value in (
            ("context_threshold", context_threshold),
            ("durability_threshold", durability_threshold),
            ("choice_confidence_threshold", choice_confidence_threshold),
        ):
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be within [0,1]")
        self.context_threshold = float(context_threshold)
        self.durability_threshold = float(durability_threshold)
        self.choice_confidence_threshold = float(choice_confidence_threshold)

    def evaluate(
        self, engine: Any, *, scope_id: str, canonical_generation: int,
        observation: Mapping[str, Any],
        retrieved_memories: Sequence[Mapping[str, Any]],
    ) -> tuple[FormationRulingV2, tuple[dict[str, Any], ...]]:
        """Execute the conditional plan with one bounded call per question."""

        responses: dict[str, Mapping[str, Any]] = {}
        request_ids: dict[str, str] = {}
        receipts: list[dict[str, Any]] = []

        def ask(question: Mapping[str, Any]) -> Mapping[str, Any]:
            question_id = str(question["question_id"])
            request_id = "laya_" + sha256_hex(canonical_json([
                PLAN_VERSION, scope_id, canonical_generation,
                observation["id"], question_id,
            ]))[:32]
            request = evaluation_request(
                request_id=request_id, scope_id=scope_id,
                canonical_generation=canonical_generation,
                observation=observation, retrieved_memories=retrieved_memories,
                question=question,
            )
            response = engine(request)
            validate_typed_response(response, question, request_id=request_id)
            responses[question_id] = response
            request_ids[question_id] = request_id
            receipts.append({
                "request_id": request_id, "question_id": question_id,
                "question_type": question["type"], "response": dict(response),
            })
            return response

        if float(ask(context_sufficient_question())["noul"]) >= self.context_threshold:
            if float(ask(durable_question())["noul"]) >= self.durability_threshold:
                ask(memory_class_question())
                operation = str(ask(operation_question())["choice"])
                if operation in TARGET_REQUIRED and len(retrieved_memories) > 1:
                    ask(target_question([
                        {"id": row["id"], "content": row["content"]}
                        for row in retrieved_memories
                    ]))
                if operation in MUTATING_OPERATIONS - {"FORGET_EXISTING"}:
                    ask(future_utility_question())
        ruling = self.build_ruling(
            responses=responses, request_ids=request_ids,
            authorized_targets=retrieved_memories,
        )
        return ruling, tuple(receipts)

    @staticmethod
    def _validate(
        response: Mapping[str, Any], question: Mapping[str, Any], request_id: str,
    ) -> Mapping[str, Any]:
        validate_typed_response(response, question, request_id=request_id)
        return response

    def build_ruling(
        self, *, responses: Mapping[str, Mapping[str, Any]],
        request_ids: Mapping[str, str], authorized_targets: Sequence[Mapping[str, Any]],
    ) -> FormationRulingV2:
        context_q = context_sufficient_question()
        context = self._validate(
            responses[context_q["question_id"]], context_q,
            request_ids[context_q["question_id"]],
        )
        context_probability = float(context["noul"])
        if context_probability < self.context_threshold:
            return FormationRulingV2(
                operation="REVIEW", memory_class=None, target_memory_id=None,
                operation_probability=None, target_probability=None,
                context_sufficient_probability=context_probability,
                durable_probability=0.0, future_utility_score=None,
                review_required=True, review_reason="insufficient_context",
            )

        durable_q = durable_question()
        durable = self._validate(
            responses[durable_q["question_id"]], durable_q,
            request_ids[durable_q["question_id"]],
        )
        durable_probability = float(durable["noul"])
        if durable_probability < self.durability_threshold:
            return FormationRulingV2(
                operation="DO_NOT_STORE", memory_class="non_memory", target_memory_id=None,
                operation_probability=None, target_probability=None,
                context_sufficient_probability=context_probability,
                durable_probability=durable_probability, future_utility_score=None,
                review_required=False, review_reason=None,
            )

        memory_class_q = memory_class_question()
        memory_class_response = self._validate(
            responses[memory_class_q["question_id"]], memory_class_q,
            request_ids[memory_class_q["question_id"]],
        )
        memory_class = str(memory_class_response["choice"])
        memory_class_confidence = response_confidence(memory_class_response)
        if (
            memory_class_confidence is None
            or memory_class_confidence < self.choice_confidence_threshold
        ):
            return FormationRulingV2(
                operation="REVIEW", memory_class=memory_class,
                target_memory_id=None, operation_probability=None,
                target_probability=None,
                context_sufficient_probability=context_probability,
                durable_probability=durable_probability,
                future_utility_score=None, review_required=True,
                review_reason="memory_class_low_confidence",
            )

        operation_q = operation_question()
        operation_response = self._validate(
            responses[operation_q["question_id"]], operation_q,
            request_ids[operation_q["question_id"]],
        )
        operation = str(operation_response["choice"])
        operation_probability = float(operation_response["probabilities"][operation])
        confidence = response_confidence(operation_response)
        if confidence is None or confidence < self.choice_confidence_threshold:
            return FormationRulingV2(
                operation="REVIEW", memory_class=memory_class, target_memory_id=None,
                operation_probability=operation_probability, target_probability=None,
                context_sufficient_probability=context_probability,
                durable_probability=durable_probability, future_utility_score=None,
                review_required=True, review_reason="operation_low_confidence",
            )

        target_id: str | None = None
        target_probability: float | None = None
        if operation in TARGET_REQUIRED:
            if not authorized_targets:
                return FormationRulingV2(
                    operation="REVIEW", memory_class=memory_class, target_memory_id=None,
                    operation_probability=operation_probability, target_probability=None,
                    context_sufficient_probability=context_probability,
                    durable_probability=durable_probability, future_utility_score=None,
                    review_required=True, review_reason="missing_authorized_target",
                )
            if len(authorized_targets) == 1:
                target_id = str(authorized_targets[0]["id"])
                target_probability = 1.0
            else:
                target_q = target_question(authorized_targets)
                target_response = self._validate(
                    responses[target_q["question_id"]], target_q,
                    request_ids[target_q["question_id"]],
                )
                target_id = str(target_response["choice"])
                target_probability = float(target_response["probabilities"][target_id])
                target_confidence = response_confidence(target_response)
                if target_confidence is None or target_confidence < self.choice_confidence_threshold:
                    return FormationRulingV2(
                        operation="REVIEW", memory_class=memory_class,
                        target_memory_id=target_id,
                        operation_probability=operation_probability,
                        target_probability=target_probability,
                        context_sufficient_probability=context_probability,
                        durable_probability=durable_probability,
                        future_utility_score=None, review_required=True,
                        review_reason="target_low_confidence",
                    )

        future_score: float | None = None
        if operation in MUTATING_OPERATIONS - {"FORGET_EXISTING"}:
            future_q = future_utility_question()
            future = self._validate(
                responses[future_q["question_id"]], future_q,
                request_ids[future_q["question_id"]],
            )
            future_score = float(future["score"])

        return FormationRulingV2(
            operation=operation, memory_class=memory_class,
            target_memory_id=target_id,
            operation_probability=operation_probability,
            target_probability=target_probability,
            context_sufficient_probability=context_probability,
            durable_probability=durable_probability,
            future_utility_score=future_score,
            review_required=False, review_reason=None,
        )

