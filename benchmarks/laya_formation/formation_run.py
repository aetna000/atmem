"""Execute and score the frozen synthetic formation/store comparison."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
import json
from pathlib import Path
from statistics import median
from typing import Any, Mapping

from atmem.contracts.models import AuthorityScope
from atmem.extract.formation import form_typed_proposals

from research.laya_formation.dataset.generator import build_scenario

from .adapters import ChoiceAdapter
from .contracts import ChoiceCase, ChoiceResult


MUTATIONS = frozenset({"ADD", "UPDATE", "SUPERSEDE"})


def load_frozen_cases(packet_path: Path, answer_key_path: Path) -> list[ChoiceCase]:
    packet, key = json.loads(packet_path.read_text()), json.loads(answer_key_path.read_text())
    if packet.get("format") != "atmem-laya-matched-evaluation-packet-v1" or key.get("format") != "atmem-laya-matched-evaluation-answer-key-v1":
        raise ValueError("unsupported evaluation packet")
    labels = {row["case_id"]: tuple(row["expected"]) for row in key["labels"]}
    if len(labels) != key.get("case_count") or set(labels) != {row["case_id"] for row in packet["cases"]}:
        raise ValueError("evaluation packet and answer key differ")
    result = []
    for row in packet["cases"]:
        case = ChoiceCase(
            case_id=row["case_id"], scenario_id=row["scenario_id"],
            cluster_id=row["cluster_id"], question_id=row["question_id"],
            instructions=row["instructions"], authorized_input=row["authorized_input"],
            options=tuple(row["options"]), candidate_pool=tuple(row["candidate_pool"]),
            expected=labels[row["case_id"]],
        )
        if case.matching_receipt().to_dict() != row["matching"]:
            raise ValueError("frozen matching receipt changed")
        result.append(case)
    return result


def deterministic_decision(case: ChoiceCase) -> Mapping[str, Any]:
    """Use product formation primitives, never generator labels, as baseline."""

    value = case.authorized_input
    scope_value = value["scope"]
    scope = AuthorityScope(
        subject_id=scope_value["subject_id"], agent_id=scope_value["agent_id"],
        workspace_id=scope_value["workspace_id"],
    )
    text = "\n".join(str(row["text"]) for row in value.get("evidence", ()))
    proposals = form_typed_proposals(
        text, scope=scope, source_id="source-evaluation",
        formation_id="formation-evaluation", confidence=1.0,
    )
    classes = {proposal.memory_class.value for proposal in proposals}
    initial = value.get("initial_state") or {}
    facts = {str(proposal.fact) for proposal in proposals if proposal.fact}
    ambiguous = len(value.get("evidence", ())) > 1 and len(facts) > 1
    if ambiguous:
        operation, support, target, usefulness = "REJECT", "AMBIGUOUS", "REVIEW", "INSUFFICIENT_EVIDENCE"
    elif not proposals:
        operation, support, target, usefulness = "REJECT", "UNSUPPORTED", "target:none", "INSUFFICIENT_EVIDENCE"
    elif not initial:
        operation, support, target, usefulness = "ADD", "SUPPORTED", "target:none", "USEFUL"
    else:
        initial_values = {str(row.get("value")) for row in initial.values() if isinstance(row, Mapping)}
        operation = "NOOP" if any(value in text for value in initial_values) and len(initial_values) == 1 else "SUPERSEDE"
        support, target = "SUPPORTED", "target:active"
        usefulness = "NOT_USEFUL" if operation == "NOOP" else "USEFUL"
    memory_class = next(iter(classes)) if len(classes) == 1 else "non_memory" if not classes else None
    selected = {
        "operation": operation, "memory_class": memory_class,
        "evidence_support": support, "target_selection": target,
        "retrieval_usefulness": usefulness,
    }[case.question_id]
    if selected is None or selected not in case.options:
        return {"abstained": True, "review_required": True}
    return {"selected": selected, "scores": {selected: 1.0}, "abstained": False}


def run_arm(cases: list[ChoiceCase], adapter: ChoiceAdapter, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite arm results: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    counts = defaultdict(int)
    with temporary.open("x", encoding="utf-8") as stream:
        for case in cases:
            # The answer key remains scorer-only even in process.  Matching digests do
            # not include ``expected``, so the blinded view is byte-identical for every
            # field an arm is authorized to receive.
            result = adapter.decide(replace(case, expected=()))
            row = result.to_dict()
            row["scenario_id"] = case.scenario_id
            row["cluster_id"] = case.cluster_id
            row["question_id"] = case.question_id
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            counts["rows"] += 1
            counts["errors"] += int(result.error_code is not None)
            counts["abstained"] += int(result.abstained)
            counts["escalated"] += int(result.escalated)
    temporary.replace(output_path)
    return dict(counts)


def blocked_arm(cases: list[ChoiceCase], adapter_identity: Any, code: str, output_path: Path) -> dict[str, Any]:
    class Blocked:
        identity = adapter_identity
        def decide(self, case: ChoiceCase) -> ChoiceResult:
            from .contracts import Usage, digest
            return ChoiceResult(
                case_id=case.case_id, identity=self.identity, matching=case.matching_receipt(),
                selected=(), scores={}, abstained=True, review_required=True,
                escalated=False, latency_ms=0.0, usage=Usage(),
                prompt_digest=digest({"blocked": code}), error_code=code,
            )
    return run_arm(cases, Blocked(), output_path)


def _scenario_index(scenario_id: str) -> int:
    prefix = "scenario-"
    if not scenario_id.startswith(prefix):
        raise ValueError("unexpected scenario identity")
    return int(scenario_id[len(prefix):])


def _predicted_state(scenario: Any, decisions: Mapping[str, str]) -> tuple[Mapping[str, Any], bool]:
    operation = decisions.get("operation")
    support = decisions.get("evidence_support")
    target = decisions.get("target_selection")
    initial = dict(scenario.initial_state)
    expected_canonical = dict(scenario.expected_final_state["canonical_state"])
    if operation in {"NOOP", "REJECT"}:
        return initial, True
    if support != "SUPPORTED":
        return initial, False
    if operation == "ADD" and target == "target:none" and "target:new" in expected_canonical:
        return {"target:new": expected_canonical["target:new"]}, True
    if operation in {"UPDATE", "SUPERSEDE"} and target == "target:active" and "target:active" in expected_canonical:
        return {"target:active": expected_canonical["target:active"]}, True
    return initial, False


def score_arm(cases: list[ChoiceCase], results_path: Path, post_state_path: Path) -> dict[str, Any]:
    expected = {case.case_id: case for case in cases}
    rows = [json.loads(line) for line in results_path.read_text().splitlines() if line]
    if len(rows) != len(cases) or {row["case_id"] for row in rows} != set(expected):
        raise ValueError("arm result rows are incomplete")
    by_scenario: dict[str, dict[str, str]] = defaultdict(dict)
    correctness = CounterLike()
    latencies, costs = [], []
    for row in rows:
        case = expected[row["case_id"]]
        selected = tuple(row.get("selected") or ())
        is_correct = row.get("error_code") is None and selected == case.expected
        correctness.add(case.question_id, is_correct)
        if row.get("error_code") is None and len(selected) == 1:
            by_scenario[case.scenario_id][case.question_id] = selected[0]
        latencies.append(float(row["latency_ms"]))
        costs.append(float((row.get("usage") or {}).get("cost_usd", 0.0)))
    exact = safe = 0
    post_rows = []
    for scenario_id in sorted({case.scenario_id for case in cases}):
        scenario = build_scenario(_scenario_index(scenario_id))
        decisions = by_scenario.get(scenario_id, {})
        state, disposition_valid = _predicted_state(scenario, decisions)
        success = disposition_valid and state == scenario.expected_final_state["canonical_state"]
        expected_operation = scenario.expected_final_state["operation"]
        predicted_operation = decisions.get("operation")
        safety_violation = expected_operation == "REJECT" and predicted_operation in MUTATIONS
        exact += int(success)
        safe += int(safety_violation)
        post_rows.append({
            "scenario_id": scenario_id, "predicted_decisions": decisions,
            "predicted_canonical_state": state,
            "expected_canonical_state": scenario.expected_final_state["canonical_state"],
            "exact": success, "disposition_valid": disposition_valid,
            "safety_violation": safety_violation,
        })
    if post_state_path.exists():
        raise FileExistsError(f"refusing to overwrite post-state results: {post_state_path}")
    post_state_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in post_rows))
    total_scenarios = len(post_rows)
    errors = sum(row.get("error_code") is not None for row in rows)
    reviews = sum(bool(row.get("review_required")) for row in rows)
    escalations = sum(bool(row.get("escalated")) for row in rows)
    return {
        "format": "atmem-laya-formation-arm-summary-v1",
        "arm": rows[0]["identity"]["arm"], "cases": len(rows),
        "scenarios": total_scenarios,
        "exact_canonical_state_success": exact / total_scenarios,
        "component_accuracy": correctness.rates(),
        "safety_violations": safe, "review_rate": reviews / len(rows),
        "escalation_rate": escalations / len(rows), "error_rate": errors / len(rows),
        "latency_ms": {"median": median(latencies), "sum": sum(latencies)},
        "cost_usd": sum(costs),
    }


class CounterLike:
    def __init__(self) -> None:
        self.values: dict[str, list[int]] = defaultdict(list)

    def add(self, name: str, correct: bool) -> None:
        self.values[name].append(int(correct))

    def rates(self) -> dict[str, float]:
        return {name: sum(values) / len(values) for name, values in sorted(self.values.items())}
