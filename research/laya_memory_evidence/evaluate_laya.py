"""Frozen base/tuned Laya evaluation over identical sealed typed transitions."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import time
from typing import Any

from atmem.core.canonical import canonical_json
from atmem.laya_formation.contracts_v2 import response_confidence
from atmem.laya_formation.formation_v2 import FormationPlanV2
from atmem.laya_formation.runtime import LayaTypedDecisionEngineV2
from research.laya_memory_evidence.challenge_worker import _post_state_digest


FORMAT = "atmem-laya-sealed-evaluation-v2"


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _answer(response: dict[str, Any]) -> str:
    if response["type"] == "choice":
        return str(response["choice"])
    if response["type"] == "noul":
        return "true" if float(response["noul"]) >= 0.5 else "false"
    probabilities = response["probabilities"]
    return max(probabilities, key=probabilities.get)


def _probabilities(response: dict[str, Any]) -> dict[str, float]:
    if response["type"] == "choice" or response["type"] == "score":
        return {str(key): float(value) for key, value in response["probabilities"].items()}
    probability = float(response["noul"])
    return {"false": 1.0 - probability, "true": probability}


def _macro_f1(expected: list[str], predicted: list[str]) -> float:
    labels = sorted(set(expected) | set(predicted))
    values = []
    for label in labels:
        tp = sum(a == label and b == label for a, b in zip(expected, predicted))
        fp = sum(a != label and b == label for a, b in zip(expected, predicted))
        fn = sum(a == label and b != label for a, b in zip(expected, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return statistics.fmean(values) if values else 0.0


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)]


def _ece(rows: list[dict[str, Any]], bins: int = 15) -> float | None:
    calibrated = [row for row in rows if row.get("confidence") is not None]
    if not calibrated:
        return None
    total = len(calibrated)
    value = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        bucket = [
            row for row in calibrated
            if low <= row["confidence"] <= high and (index == bins - 1 or row["confidence"] < high)
        ]
        if bucket:
            value += len(bucket) / total * abs(
                statistics.fmean(float(row["correct"]) for row in bucket)
                - statistics.fmean(row["confidence"] for row in bucket)
            )
    return value


def _transition_outcomes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["source_transition_id"]].append(row)
    outcomes: list[dict[str, Any]] = []
    target_required = {
        "UPDATE_EXISTING", "SUPERSEDE_EXISTING", "DUPLICATE", "FORGET_EXISTING",
    }
    for transition_id, group in sorted(grouped.items()):
        expected_operations = {row["expected_operation"] for row in group}
        expected_targets = {row.get("expected_target_id") for row in group}
        languages = {row.get("language", "unknown") for row in group}
        post_digests = {row.get("expected_post_state_digest") for row in group}
        canonical_digests = {row.get("canonical_state_digest") for row in group}
        if any(len(values) != 1 for values in (
            expected_operations, expected_targets, post_digests, canonical_digests, languages,
        )):
            raise ValueError(f"transition metadata drift: {transition_id}")
        answers = {
            row["question_id"]: row.get("predicted_answer")
            for row in group if row["status"] == "completed"
        }
        context_answer = answers.get("formation.context_sufficient.v2")
        predicted_operation = group[0].get("ruling_operation") or (
            answers.get("formation.operation.v2") or "REVIEW"
            if context_answer is None else "REVIEW"
        )
        if not group[0].get("ruling_operation") and context_answer == "true":
            if answers.get("formation.is_durable.v2") == "false":
                predicted_operation = "DO_NOT_STORE"
            elif answers.get("formation.is_durable.v2") == "true":
                predicted_operation = answers.get("formation.operation.v2") or "REVIEW"
        canonical_records = group[0].get("canonical_records") or []
        predicted_target = None
        predicted_memory_class = (
            group[0].get("ruling_memory_class")
            or answers.get("formation.memory_class.v2") or "unknown"
        )
        if predicted_operation in target_required:
            predicted_target = (
                group[0].get("ruling_target_id")
                or answers.get("formation.target.v2")
            )
            if predicted_target is None and len(canonical_records) == 1:
                predicted_target = canonical_records[0]["id"]
        predicted_digest = _post_state_digest(
            canonical_records,
            {
                "operation": predicted_operation,
                "target_memory_id": predicted_target,
                "memory_class": predicted_memory_class,
            },
            str(group[0].get("observation_content") or ""),
        )
        expected_operation = next(iter(expected_operations))
        expected_target = next(iter(expected_targets))
        expected_post_digest = next(iter(post_digests))
        typed_correct = all(
            row["status"] == "completed" and row["correct"] for row in group
        )
        post_state_correct = predicted_digest == expected_post_digest
        outcomes.append({
            "source_transition_id": transition_id,
            "language": next(iter(languages)),
            "expected_operation": expected_operation,
            "predicted_operation": predicted_operation,
            "expected_target_id": expected_target,
            "predicted_target_id": predicted_target,
            "operation_correct": predicted_operation == expected_operation,
            "target_correct": (
                predicted_target == expected_target if expected_operation in target_required else True
            ),
            "post_state_correct": post_state_correct,
            "fully_correct": typed_correct and post_state_correct,
        })
    return outcomes


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if row["status"] == "completed"]
    transitions = _transition_outcomes(rows)
    fully = sum(row["fully_correct"] for row in transitions)
    operations = [
        row for row in completed if row["question_id"] == "formation.operation.v2"
    ]
    targets = [row for row in completed if row["question_id"] == "formation.target.v2"]
    brier = []
    labeled_completed = [row for row in completed if row.get("expected_answer") is not None]
    for row in labeled_completed:
        brier.append(sum(
            (probability - float(label == row["expected_answer"])) ** 2
            for label, probability in row["probabilities"].items()
        ))
    mutating = {"STORE_NEW", "UPDATE_EXISTING", "SUPERSEDE_EXISTING", "FORGET_EXISTING"}
    false_store = sum(
        row["predicted_operation"] in mutating
        and row["expected_operation"] in {"DUPLICATE", "DO_NOT_STORE", "REVIEW"}
        for row in transitions
    )
    duplicate_creation = sum(
        row["predicted_operation"] == "STORE_NEW" and row["expected_operation"] == "DUPLICATE"
        for row in transitions
    )
    unsafe = sum(
        row["predicted_operation"] == "FORGET_EXISTING"
        and row["expected_operation"] != "FORGET_EXISTING"
        for row in transitions
    ) + sum(
        row["expected_operation"] in {
            "UPDATE_EXISTING", "SUPERSEDE_EXISTING", "DUPLICATE", "FORGET_EXISTING",
        } and not row["target_correct"] for row in transitions
    )
    latencies = [float(row["latency_ms"]) for row in completed]
    operation_expected = [row["expected_operation"] for row in transitions]
    operation_predicted = [row["predicted_operation"] for row in transitions]
    relational = [
        row for row in transitions if row["expected_operation"] in {
            "UPDATE_EXISTING", "SUPERSEDE_EXISTING", "DUPLICATE", "FORGET_EXISTING",
        }
    ]
    per_language: dict[str, Any] = {}
    for language in sorted({row["language"] for row in transitions}):
        language_transitions = [row for row in transitions if row["language"] == language]
        language_typed = [
            row for row in labeled_completed if row.get("language", "unknown") == language
        ]
        expected = [row["expected_operation"] for row in language_transitions]
        predicted = [row["predicted_operation"] for row in language_transitions]
        critical_false_store = sum(
            row["predicted_operation"] in mutating
            and row["expected_operation"] in {"DUPLICATE", "DO_NOT_STORE", "REVIEW"}
            for row in language_transitions
        )
        per_language[language] = {
            "transitions": len(language_transitions),
            "fully_correct_rate": statistics.fmean(
                float(row["fully_correct"]) for row in language_transitions
            ),
            "operation_macro_f1": _macro_f1(expected, predicted),
            "critical_false_store_count": critical_false_store,
            "critical_false_store_rate": critical_false_store / len(language_transitions),
            "abstention_rate": statistics.fmean(
                float(row["predicted_operation"] == "REVIEW") for row in language_transitions
            ),
            "ece": _ece(language_typed),
        }
    return {
        "typed_examples": len(rows), "completed_examples": len(completed),
        "failure_count": len(rows) - len(completed),
        "transitions": len(transitions), "fully_correct_transitions": fully,
        "fully_correct_rate": fully / len(transitions) if transitions else 0.0,
        "operation_accuracy": (
            statistics.fmean(float(row["operation_correct"]) for row in transitions)
            if transitions else None
        ),
        "operation_macro_f1": _macro_f1(operation_expected, operation_predicted),
        "target_accuracy": (
            statistics.fmean(float(row["target_correct"]) for row in relational)
            if relational else None
        ),
        "exact_post_state_accuracy": (
            statistics.fmean(float(row["post_state_correct"]) for row in transitions)
            if transitions else 0.0
        ),
        "false_store_count": false_store,
        "duplicate_creation_count": duplicate_creation,
        "unsafe_mutation_count": unsafe,
        "abstention_count": sum(bool(row.get("abstained")) for row in rows),
        "brier": statistics.fmean(brier) if brier else None,
        "ece": _ece(labeled_completed),
        "latency_ms": {
            "p50": _percentile(latencies, 0.50), "p95": _percentile(latencies, 0.95),
            "mean": statistics.fmean(latencies) if latencies else None,
        },
        "question_counts": dict(Counter(row["question_id"] for row in rows)),
        "per_language": per_language,
    }


def evaluate(
    *, dataset: Path, output: Path, model: str, revision: str | None,
    device: str, arm: str, tokenizer_revision: str,
    calibration_path: Path | None = None,
) -> dict[str, Any]:
    from laya import Agent

    agent = Agent(model, revision=revision, device=device)
    calibration = None
    choice_threshold = 0.5
    if calibration_path is not None:
        from laya.calibrate import apply_calibration_payload
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        local_weights = Path(model) / "model.safetensors"
        if local_weights.is_file() and _sha_file(local_weights).removeprefix("sha256:") != str(
            calibration["model_digest"]
        ).removeprefix("sha256:"):
            raise ValueError("calibration bundle is not bound to the evaluated model")
        apply_calibration_payload(agent, {
            "temperature": calibration["temperatures"]["by_type"],
            "temperature_by_options": calibration["temperatures"]["by_option_bucket"],
        })
        choice_values = [
            float(value) for key, value in calibration["thresholds"].items()
            if str(key).startswith("choice:")
        ]
        if choice_values:
            choice_threshold = max(choice_values)
    engine = LayaTypedDecisionEngineV2(
        agent, tokenizer_revision=tokenizer_revision,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    examples_by_transition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with dataset.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                example = json.loads(line)
                identity = example["transition_id"].split(":formation.", 1)[0]
                examples_by_transition[identity].append(example)
    plan = FormationPlanV2(choice_confidence_threshold=choice_threshold)
    with output.open("w", encoding="utf-8") as target:
        for transition_id, examples in sorted(examples_by_transition.items()):
            example = examples[0]
            expected_by_question = {
                item["request"]["question"]["question_id"]: item["expected_response"]
                for item in examples
            }
            request = example["request"]
            common = {
                "arm": arm, "source_transition_id": transition_id,
                "trajectory_id": example["trajectory_id"],
                "expected_operation": example["expected_operation"],
                "expected_target_id": example["expected_target_id"],
                "expected_post_state_digest": example["expected_post_state_digest"],
                "canonical_state_digest": example["pre_state"]["canonical_state_digest"],
                "canonical_records": example["pre_state"]["canonical_records"],
                "observation_content": request["observation"]["content"],
                "language": example.get("viewer", {}).get("language", "unknown"),
            }
            tick = time.perf_counter()
            try:
                ruling, receipts = plan.evaluate(
                    engine, scope_id=request["scope_id"],
                    canonical_generation=request["canonical_generation"],
                    observation=request["observation"],
                    retrieved_memories=request["retrieved_memories"],
                )
                latency = (time.perf_counter() - tick) * 1000.0
                for receipt in receipts:
                    response = receipt["response"]
                    question_id = receipt["question_id"]
                    expected = expected_by_question.get(question_id)
                    row = {
                        **common,
                        "example_id": f"{transition_id}:{question_id}",
                        "question_id": question_id,
                        "question_type": receipt["question_type"],
                        "expected_answer": _answer(expected) if expected else None,
                        "status": "completed", "response": response,
                        "predicted_answer": _answer(response),
                        "probabilities": _probabilities(response),
                        "confidence": response_confidence(response),
                        "abstained": ruling.review_required,
                        "ruling_operation": ruling.operation,
                        "ruling_target_id": ruling.target_memory_id,
                        "ruling_memory_class": ruling.memory_class,
                        "latency_ms": latency / max(1, len(receipts)),
                    }
                    row["correct"] = (
                        row["expected_answer"] is not None
                        and row["predicted_answer"] == row["expected_answer"]
                    )
                    target.write(canonical_json(row) + "\n")
                    rows.append(row)
            except Exception as exc:
                row = {
                    **common, "example_id": f"{transition_id}:runtime_failure",
                    "question_id": "runtime_failure", "question_type": "failure",
                    "expected_answer": None, "status": "failed",
                    "error_type": type(exc).__name__, "predicted_answer": None,
                    "probabilities": {}, "confidence": None, "abstained": True,
                    "correct": False, "ruling_operation": "REVIEW",
                    "ruling_target_id": None, "ruling_memory_class": None,
                    "latency_ms": (time.perf_counter() - tick) * 1000.0,
                }
                target.write(canonical_json(row) + "\n")
                rows.append(row)
    report = {
        "format": FORMAT, "arm": arm,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "dataset_path": dataset.name, "dataset_sha256": _sha_file(dataset),
        "model": model, "revision": revision, "device": device,
        "tokenizer_revision": tokenizer_revision,
        "calibration_digest": calibration.get("digest") if calibration else None,
        "choice_confidence_threshold": choice_threshold,
        "elapsed_seconds": time.perf_counter() - started,
        "metrics": summarize(rows),
    }
    report["report_digest"] = "sha256:" + hashlib.sha256(canonical_json(report).encode()).hexdigest()
    report_path = output.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def compare(base_path: Path, tuned_path: Path, output: Path, *, samples: int = 10_000) -> dict[str, Any]:
    def load(path: Path) -> list[dict[str, Any]]:
        with path.open(encoding="utf-8") as stream:
            return [json.loads(line) for line in stream if line.strip()]
    base, tuned = load(base_path), load(tuned_path)
    base_outcomes = {
        row["source_transition_id"]: row for row in _transition_outcomes(base)
    }
    tuned_outcomes = {
        row["source_transition_id"]: row for row in _transition_outcomes(tuned)
    }
    if set(base_outcomes) != set(tuned_outcomes):
        raise ValueError("base and tuned evaluations do not contain identical transitions")
    for transition_id in base_outcomes:
        if any(
            base_outcomes[transition_id][key] != tuned_outcomes[transition_id][key]
            for key in ("expected_operation", "expected_target_id")
        ):
            raise ValueError(f"paired transition truth differs: {transition_id}")
    paired = [
        (transition_id, int(base_outcomes[transition_id]["fully_correct"]),
         int(tuned_outcomes[transition_id]["fully_correct"]))
        for transition_id in sorted(base_outcomes)
    ]
    rng = random.Random(410239)
    deltas = []
    for _ in range(samples):
        draw = [paired[rng.randrange(len(paired))] for _ in paired]
        deltas.append(statistics.fmean(item[2] - item[1] for item in draw))
    ordered = sorted(deltas)
    report = {
        "format": "atmem-laya-paired-comparison-v2",
        "interpretation": "agreement with blinded machine weak supervision; not human ground truth",
        "base": summarize(base), "tuned": summarize(tuned),
        "paired_transition_delta": statistics.fmean(item[2] - item[1] for item in paired),
        "paired_bootstrap_95ci": [
            ordered[int(0.025 * samples)], ordered[min(samples - 1, int(0.975 * samples))],
        ],
        "bootstrap_samples": samples,
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metric_rows = [
        ("Fully correct transition", "fully_correct_rate", True),
        ("Operation accuracy", "operation_accuracy", True),
        ("Operation macro-F1", "operation_macro_f1", True),
        ("Target accuracy", "target_accuracy", True),
        ("Exact post-state accuracy", "exact_post_state_accuracy", True),
        ("False-store count", "false_store_count", False),
        ("Duplicate-creation count", "duplicate_creation_count", False),
        ("Unsafe-mutation count", "unsafe_mutation_count", False),
        ("Brier score", "brier", False),
        ("ECE", "ece", False),
    ]
    def shown(value: Any, rate: bool) -> str:
        if value is None:
            return "n/a"
        return f"{100 * float(value):.2f}%" if rate else f"{float(value):.4f}"
    lines = [
        "# Base vs tuned Laya — sealed stateful comparison",
        "",
        "> Agreement with blinded machine weak supervision; not human ground truth.",
        "",
        "| Metric | Base Laya | Tuned Laya |",
        "| --- | ---: | ---: |",
    ]
    lines.extend(
        f"| {label} | {shown(report['base'].get(key), rate)} | "
        f"{shown(report['tuned'].get(key), rate)} |"
        for label, key, rate in metric_rows
    )
    lines.extend([
        "",
        f"Paired fully-correct delta: {100 * report['paired_transition_delta']:.2f} percentage points ",
        f"(paired bootstrap 95% CI: {100 * report['paired_bootstrap_95ci'][0]:.2f} to "
        f"{100 * report['paired_bootstrap_95ci'][1]:.2f}).",
        "",
    ])
    output.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--dataset", type=Path, required=True)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--model", required=True)
    run_parser.add_argument("--revision")
    run_parser.add_argument("--device", default="cuda")
    run_parser.add_argument("--arm", required=True)
    run_parser.add_argument("--tokenizer-revision", required=True)
    run_parser.add_argument("--calibration", type=Path)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("--base", type=Path, required=True)
    compare_parser.add_argument("--tuned", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "run":
        result = evaluate(
            dataset=args.dataset, output=args.output, model=args.model,
            revision=args.revision, device=args.device, arm=args.arm,
            tokenizer_revision=args.tokenizer_revision,
            calibration_path=args.calibration,
        )
    else:
        result = compare(args.base, args.tuned, args.output)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
