from __future__ import annotations

from typing import Any, Mapping

from atmem.core.canonical import canonical_json, sha256_hex

from .models import MEMORY_CLASSES, OPERATIONS, FormationScenarioV1, TypedDecisionExampleV1, digest


QUESTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("operation", OPERATIONS),
    ("memory_class", MEMORY_CLASSES),
    ("evidence_support", ("SUPPORTED", "AMBIGUOUS", "UNSUPPORTED")),
    ("target_selection", ("target:active", "target:none", "REVIEW")),
    ("retrieval_usefulness", ("USEFUL", "NOT_USEFUL", "INSUFFICIENT_EVIDENCE")),
)


def _expected(scenario: FormationScenarioV1, question_id: str) -> str:
    final = scenario.expected_final_state
    if question_id == "operation":
        return str(final["operation"])
    if question_id == "memory_class":
        return str(final["memory_class"])
    if question_id == "evidence_support":
        return str(final["evidence_support"])
    if question_id == "target_selection":
        return str(final["target_selection"])
    if question_id == "retrieval_usefulness":
        return str(final["retrieval_usefulness"])
    raise ValueError("unknown oracle question")


def compile_decisions(scenario: FormationScenarioV1) -> tuple[TypedDecisionExampleV1, ...]:
    evidence = [
        {"event_id": row.event_id, "text": row.text, "actor": row.actor, "scope": row.scope, "timestamp": row.timestamp}
        for row in scenario.evidence_events
    ]
    authorized_input: Mapping[str, Any] = {
        "scope": dict(scenario.scope_fixture),
        "initial_state": dict(scenario.initial_state),
        "evidence": evidence,
    }
    result = []
    for question_id, choices in QUESTIONS:
        expected = _expected(scenario, question_id)
        if expected not in choices:
            raise ValueError(f"oracle produced out-of-set choice for {question_id}")
        payload = {
            "example_id": f"{scenario.scenario_id}:{question_id}",
            "scenario_id": scenario.scenario_id,
            "question_id": question_id,
            "question_type": "choice",
            "authorized_input": dict(authorized_input),
            "choice_ids": list(choices),
            "expected_choice_ids": [expected],
            "allow_abstain": expected in {"AMBIGUOUS", "UNSUPPORTED", "REVIEW", "INSUFFICIENT_EVIDENCE"},
            "oracle_receipt": {
                "format": "atmem-laya-oracle-receipt-v1",
                "scenario_digest": "sha256:" + sha256_hex(canonical_json(scenario.to_dict())),
                "rule": f"state-machine:{question_id}:v1",
            },
            "audit_rationale": f"Executable final state selects {expected} for {question_id}.",
            "split": scenario.split,
        }
        result.append(TypedDecisionExampleV1(**payload, content_digest=digest(payload)))
    return tuple(result)
