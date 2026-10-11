from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
from typing import Any, Iterable, Mapping, Sequence

from research.laya_formation.dataset.audit import validate_audit_result
from research.laya_formation.training.contracts import canonical_digest, collapse_report
from research.laya_formation.training.smoke import QUESTION_INSTRUCTIONS, sha256_file, to_laya_rows


FORMAT_FREEZE = "atmem-laya-sealed-freeze-v1"
FORMAT_PACKET = "atmem-laya-blinded-audit-packet-v1"
FORMAT_ANSWER_KEY = "atmem-laya-audit-answer-key-v1"
FORMAT_REPORT = "atmem-laya-sealed-evaluation-v1"
SEED = 410241


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain an object")
            rows.append(value)
    return rows


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _dataset_file(manifest: Mapping[str, Any], relative: str) -> dict[str, Any]:
    matches = [row for row in manifest.get("files", []) if row.get("path") == relative]
    if len(matches) != 1:
        raise ValueError(f"dataset manifest must inventory {relative} exactly once")
    return matches[0]


def freeze(
    *,
    selection_path: Path,
    run_root: Path,
    dataset_manifest_path: Path,
    sealed_inputs_path: Path,
    sealed_labels_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Freeze identities without parsing either sealed JSONL file."""
    selection = _read_object(selection_path)
    selected_run = selection["selected_run_id"]
    if run_root.name != selected_run:
        raise ValueError("selected run path does not match the frozen selection")
    training_manifest_path = run_root / "training-manifest.json"
    calibration_path = run_root / "calibration-bundle.json"
    model_path = run_root / "model" / "model.safetensors"
    training_manifest = _read_object(training_manifest_path)
    calibration = _read_object(calibration_path)
    dataset_manifest = _read_object(dataset_manifest_path)
    expected_inputs = _dataset_file(dataset_manifest, "sealed/test-inputs.jsonl")
    expected_labels = _dataset_file(dataset_manifest, "sealed/test-labels.jsonl")
    for path, expected in ((sealed_inputs_path, expected_inputs), (sealed_labels_path, expected_labels)):
        if path.stat().st_size != expected["size"]:
            raise ValueError(f"sealed file size mismatch without opening content: {path}")
    if sha256_file(model_path) != calibration["model_digest"]:
        raise ValueError("selected model and calibration bundle disagree")
    if training_manifest["questions_digest"] != calibration["questions_digest"]:
        raise ValueError("selected manifest and calibration question digests disagree")
    analysis_path = Path(__file__).resolve()
    receipt = {
        "format": FORMAT_FREEZE,
        "frozen_at": _utc_now(),
        "selection": {
            "path": str(selection_path),
            "sha256": sha256_file(selection_path),
            "policy_digest": selection["policy_digest"],
            "selected_objective": selection["selected_objective"],
            "selected_run_id": selected_run,
        },
        "model": {"path": str(model_path), "sha256": sha256_file(model_path)},
        "training_manifest": {
            "path": str(training_manifest_path),
            "sha256": sha256_file(training_manifest_path),
            "questions_digest": training_manifest["questions_digest"],
        },
        "calibration": {
            "path": str(calibration_path),
            "sha256": sha256_file(calibration_path),
            "bundle_digest": calibration["digest"],
        },
        "sealed_files": {
            "inputs": {
                "path": str(sealed_inputs_path), "inventory_path": expected_inputs["path"],
                "size": expected_inputs["size"], "sha256": expected_inputs["sha256"],
            },
            "labels": {
                "path": str(sealed_labels_path), "inventory_path": expected_labels["path"],
                "size": expected_labels["size"], "sha256": expected_labels["sha256"],
            },
        },
        "analysis": {"path": str(analysis_path), "sha256": sha256_file(analysis_path)},
        "constraints": {
            "selection_or_tuning_from_sealed_results": False,
            "audit_sample_size": 400,
            "evaluation_attempts": 1,
        },
    }
    receipt["digest"] = canonical_digest(receipt)
    _write_exclusive(output_path, receipt)
    return receipt


def _assert_frozen(freeze_path: Path, *, verify_sealed: bool = True) -> dict[str, Any]:
    frozen = _read_object(freeze_path)
    if frozen.get("format") != FORMAT_FREEZE:
        raise ValueError("unsupported freeze receipt")
    if frozen.get("digest") != canonical_digest({key: value for key, value in frozen.items() if key != "digest"}):
        raise ValueError("freeze receipt digest mismatch")
    if sha256_file(Path(frozen["analysis"]["path"])) != frozen["analysis"]["sha256"]:
        raise ValueError("sealed analysis code changed after freeze")
    for name in ("model", "training_manifest", "calibration"):
        if sha256_file(Path(frozen[name]["path"])) != frozen[name]["sha256"]:
            raise ValueError(f"frozen {name} digest mismatch")
    if verify_sealed:
        for name in ("inputs", "labels"):
            item = frozen["sealed_files"][name]
            path = Path(item["path"])
            if path.stat().st_size != item["size"] or sha256_file(path) != item["sha256"]:
                raise ValueError(f"frozen sealed {name} digest mismatch")
    return frozen


def prepare_audit(
    *, freeze_path: Path, packet_path: Path, answer_key_path: Path, marker_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    frozen = _assert_frozen(freeze_path, verify_sealed=False)
    _write_exclusive(marker_path, {
        "format": "atmem-laya-sealed-audit-open-v1",
        "freeze_digest": frozen["digest"],
        "opened_at": _utc_now(),
        "state": "started",
    })
    _assert_frozen(freeze_path)
    inputs = _read_jsonl(Path(frozen["sealed_files"]["inputs"]["path"]))
    labels = _read_jsonl(Path(frozen["sealed_files"]["labels"]["path"]))
    labels_by_id = {row["example_id"]: row for row in labels}
    if len(labels_by_id) != len(labels) or {row["example_id"] for row in inputs} != set(labels_by_id):
        raise ValueError("sealed input/label membership mismatch")
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in inputs:
        buckets[row["question_id"]].append(row)
    if set(buckets) != set(QUESTION_INSTRUCTIONS):
        raise ValueError("sealed question coverage differs from the frozen five-question contract")
    rng = random.Random(SEED)
    selected = []
    per_question = 400 // len(QUESTION_INSTRUCTIONS)
    for question_id in QUESTION_INSTRUCTIONS:
        candidates = sorted(buckets[question_id], key=lambda row: row["example_id"])
        rng.shuffle(candidates)
        if len(candidates) < per_question:
            raise ValueError(f"sealed audit is underpowered for {question_id}")
        selected.extend(candidates[:per_question])
    selected.sort(key=lambda row: row["example_id"])
    packet = {
        "format": FORMAT_PACKET,
        "freeze_digest": frozen["digest"],
        "seed": SEED,
        "sealed_rows": len(selected),
        "sample_size": len(selected),
        "question_counts": dict(sorted(Counter(row["question_id"] for row in selected).items())),
        "rows": [{
            "example_id": row["example_id"],
            "question_id": row["question_id"],
            "authorized_input": row["authorized_input"],
            "choice_ids": row["choice_ids"],
            "safety_tags": [],
        } for row in selected],
    }
    answer_key = {
        "format": FORMAT_ANSWER_KEY,
        "freeze_digest": frozen["digest"],
        "independent_reviewer_required": True,
        "rows": [{
            "example_id": row["example_id"],
            "expected_choice_ids": labels_by_id[row["example_id"]]["expected_choice_ids"],
            "oracle_receipt": labels_by_id[row["example_id"]]["oracle_receipt"],
            "audit_rationale": "sealed synthetic oracle; reviewer receives no answer-key fields",
        } for row in selected],
    }
    _write_exclusive(packet_path, packet)
    _write_exclusive(answer_key_path, answer_key)
    return packet, answer_key


def _softmax(values: Sequence[float], temperature: float) -> list[float]:
    shifted = [(float(value) / temperature) for value in values]
    peak = max(shifted)
    exp = [math.exp(value - peak) for value in shifted]
    total = sum(exp)
    return [value / total for value in exp]


def _macro_f1(expected: Sequence[str], predicted: Sequence[str]) -> float:
    scores = []
    for label in sorted(set(expected) | set(predicted)):
        tp = sum(e == label and p == label for e, p in zip(expected, predicted))
        fp = sum(e != label and p == label for e, p in zip(expected, predicted))
        fn = sum(e == label and p != label for e, p in zip(expected, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def _ece(confidences: Sequence[float], correct: Sequence[bool], bins: int = 15) -> float:
    total = len(confidences)
    result = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        members = [i for i, value in enumerate(confidences) if low <= value <= high if index == bins - 1 or value < high]
        if members:
            accuracy = sum(correct[i] for i in members) / len(members)
            confidence = sum(confidences[i] for i in members) / len(members)
            result += len(members) / total * abs(accuracy - confidence)
    return result


def evaluate(
    *, freeze_path: Path, audit_packet_path: Path, audit_result_path: Path, output_path: Path,
    attempt_path: Path, device_name: str, batch_size: int,
) -> dict[str, Any]:
    frozen = _assert_frozen(freeze_path, verify_sealed=False)
    audit_result = _read_object(audit_result_path)
    audit_packet = _read_object(audit_packet_path)
    validate_audit_result(audit_result)
    if audit_packet.get("format") != FORMAT_PACKET or audit_packet.get("freeze_digest") != frozen["digest"]:
        raise ValueError("sealed audit packet is not bound to the frozen evaluation")
    packet_digest = "sha256:" + hashlib.sha256(
        json.dumps(audit_packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    if audit_result.get("packet_sha256") != packet_digest:
        raise ValueError("sealed audit result is not bound to the supplied packet")
    reviewer = str(audit_result.get("reviewer", ""))
    if "gpt-4.1:independent-audit-v1" in reviewer:
        raise ValueError("sealed audit must use a different reviewer from the nonsealed gpt-4.1 audit")
    _write_exclusive(attempt_path, {
        "format": "atmem-laya-sealed-evaluation-attempt-v1",
        "freeze_digest": frozen["digest"], "started_at": _utc_now(), "state": "started",
    })
    _assert_frozen(freeze_path)

    import numpy as np
    import torch
    import laya.train as train
    from laya.common import temp_bucket

    inputs = _read_jsonl(Path(frozen["sealed_files"]["inputs"]["path"]))
    labels = _read_jsonl(Path(frozen["sealed_files"]["labels"]["path"]))
    labels_by_id = {row["example_id"]: row for row in labels}
    rows = [{**row, "expected_choice_ids": labels_by_id[row["example_id"]]["expected_choice_ids"]} for row in inputs]
    calibration = _read_object(Path(frozen["calibration"]["path"]))
    model, tokenizer, _config = train.load_checkpoint(str(Path(frozen["model"]["path"]).parent))
    device = train.resolve_device(device_name)
    model.to(device)
    items, skipped = train.items_from_rows(tokenizer, to_laya_rows(rows), 512, 192)
    if skipped or len(items) != len(rows):
        raise RuntimeError(f"sealed preprocessing skipped rows: {skipped}")
    truncation = []
    for row, item in zip(rows, items):
        _ids, _markers, stats = train.build_sequence(
            tokenizer, None, item["q"], 512, 192,
            state_ids=item["state_ids"], return_truncation_stats=True,
        )
        if stats.get("truncated"):
            truncation.append(row["example_id"])
    records = train.calibration_records(model, tokenizer, items, device, 512, 192, batch_size=batch_size)
    expected, predicted, confidences, correctness = [], [], [], []
    nll_total = brier_total = 0.0
    failures = []
    by_question: dict[str, dict[str, int]] = defaultdict(lambda: {"items": 0, "correct": 0})
    temperatures = calibration["temperatures"]
    accepted = 0
    accepted_correct = 0
    for row, (qtype, logits, target, count) in zip(rows, records):
        qid = row["question_id"]
        choices = row["choice_ids"]
        bucket = temp_bucket(int(qtype), int(count))
        by_type = temperatures["by_type"]
        by_bucket = temperatures["by_option_bucket"]
        temperature = float(by_bucket.get(bucket, by_type[int(qtype)]))
        probabilities = _softmax(np.asarray(logits[:count], dtype=float).tolist(), temperature)
        gold_index = int(np.asarray(target[:count]).argmax())
        predicted_index = max(range(count), key=probabilities.__getitem__)
        gold, choice = f"{qid}:{choices[gold_index]}", f"{qid}:{choices[predicted_index]}"
        is_correct = gold_index == predicted_index
        expected.append(gold); predicted.append(choice)
        confidences.append(probabilities[predicted_index]); correctness.append(is_correct)
        nll_total += -math.log(max(probabilities[gold_index], 1e-15))
        brier_total += sum((probability - (index == gold_index)) ** 2 for index, probability in enumerate(probabilities))
        by_question[qid]["items"] += 1
        by_question[qid]["correct"] += int(is_correct)
        threshold = float(calibration["thresholds"].get(bucket, 0.0))
        is_accepted = round(probabilities[predicted_index], 4) >= threshold
        accepted += int(is_accepted)
        accepted_correct += int(is_accepted and is_correct)
        if not is_correct:
            failures.append({
                "example_id": row["example_id"], "question_id": qid,
                "expected": choices[gold_index], "predicted": choices[predicted_index],
                "confidence": probabilities[predicted_index],
            })
    count = len(rows)
    report = {
        "format": FORMAT_REPORT,
        "created_at": _utc_now(),
        "freeze_digest": frozen["digest"],
        "audit_result_sha256": sha256_file(audit_result_path),
        "device": str(device),
        "items": count,
        "metrics": {
            "accuracy": sum(correctness) / count,
            "macro_f1": _macro_f1(expected, predicted),
            "nll": nll_total / count,
            "brier": brier_total / count,
            "ece": _ece(confidences, correctness),
            "abstention": {
                "accepted": accepted,
                "coverage": accepted / count,
                "accepted_accuracy": accepted_correct / accepted if accepted else None,
            },
            "by_question": {name: {**value, "accuracy": value["correct"] / value["items"]} for name, value in sorted(by_question.items())},
        },
        "truncation": {"count": len(truncation), "example_ids": truncation},
        "collapse": collapse_report(expected, predicted),
        "failure_count": len(failures),
        "failures": sorted(failures, key=lambda row: (-row["confidence"], row["example_id"])),
        "sealed_results_used_for_selection_or_tuning": False,
    }
    report["digest"] = canonical_digest(report)
    _write_exclusive(output_path, report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze and execute the one-shot Spec 041 sealed evaluation")
    commands = parser.add_subparsers(dest="command", required=True)
    freeze_parser = commands.add_parser("freeze")
    freeze_parser.add_argument("--selection", type=Path, required=True)
    freeze_parser.add_argument("--run-root", type=Path, required=True)
    freeze_parser.add_argument("--dataset-manifest", type=Path, required=True)
    freeze_parser.add_argument("--sealed-inputs", type=Path, required=True)
    freeze_parser.add_argument("--sealed-labels", type=Path, required=True)
    freeze_parser.add_argument("--output", type=Path, required=True)
    audit_parser = commands.add_parser("prepare-audit")
    audit_parser.add_argument("--freeze", type=Path, required=True)
    audit_parser.add_argument("--packet", type=Path, required=True)
    audit_parser.add_argument("--answer-key", type=Path, required=True)
    audit_parser.add_argument("--marker", type=Path, required=True)
    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("--freeze", type=Path, required=True)
    evaluate_parser.add_argument("--audit-packet", type=Path, required=True)
    evaluate_parser.add_argument("--audit-result", type=Path, required=True)
    evaluate_parser.add_argument("--output", type=Path, required=True)
    evaluate_parser.add_argument("--attempt", type=Path, required=True)
    evaluate_parser.add_argument("--device", default="mps")
    evaluate_parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        result = freeze(
            selection_path=args.selection, run_root=args.run_root,
            dataset_manifest_path=args.dataset_manifest, sealed_inputs_path=args.sealed_inputs,
            sealed_labels_path=args.sealed_labels, output_path=args.output,
        )
    elif args.command == "prepare-audit":
        packet, answer_key = prepare_audit(
            freeze_path=args.freeze, packet_path=args.packet,
            answer_key_path=args.answer_key, marker_path=args.marker,
        )
        result = {"packet_digest": canonical_digest(packet), "answer_key_digest": canonical_digest(answer_key)}
    else:
        result = evaluate(
            freeze_path=args.freeze, audit_packet_path=args.audit_packet,
            audit_result_path=args.audit_result,
            output_path=args.output, attempt_path=args.attempt,
            device_name=args.device, batch_size=args.batch_size,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
