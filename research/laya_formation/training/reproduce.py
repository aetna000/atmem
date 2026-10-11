from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
from typing import Any, Sequence

from research.laya_formation.dataset.training_view import iter_training_rows
from research.laya_formation.training.contracts import CROSS_BACKEND_TOLERANCE, SAME_BACKEND_TOLERANCE
from research.laya_formation.training.smoke import to_laya_rows


def _rows(path: Path, per_question: int = 20) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in iter_training_rows([path]):
        if len(buckets[row["question_id"]]) < per_question:
            buckets[row["question_id"]].append(row)
    if len(buckets) != 5 or any(len(rows) != per_question for rows in buckets.values()):
        raise ValueError("reproduction sample is underpowered")
    return [row for name in sorted(buckets) for row in buckets[name]]


def probe(*, model_root: Path, rows_path: Path, device_name: str, output: Path) -> dict[str, Any]:
    import numpy as np
    import laya.train as train

    rows = _rows(rows_path)
    model, tokenizer, _config = train.load_checkpoint(str(model_root))
    device = train.resolve_device(device_name)
    model.to(device)
    items, skipped = train.items_from_rows(tokenizer, to_laya_rows(rows), 512, 192)
    if skipped or len(items) != len(rows):
        raise RuntimeError(f"reproduction preprocessing skipped rows: {skipped}")
    records = train.calibration_records(model, tokenizer, items, device, 512, 192, batch_size=20)
    predictions = []
    for row, (_qtype, logits, target, count) in zip(rows, records):
        values = np.asarray(logits[:count], dtype=float)
        values -= values.max()
        probability = np.exp(values); probability /= probability.sum()
        gold = int(np.asarray(target[:count]).argmax())
        selected = int(probability.argmax())
        predictions.append({
            "example_id": row["example_id"], "question_id": row["question_id"],
            "choice_ids": row["choice_ids"], "expected_index": gold,
            "selected_index": selected, "normalized_scores": probability.tolist(),
        })
    result = {
        "format": "atmem-laya-reproduction-probe-v1", "device": str(device),
        "items": len(predictions), "accuracy": sum(row["expected_index"] == row["selected_index"] for row in predictions) / len(predictions),
        "predictions": predictions,
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def compare(*, first_cpu: Path, second_cpu: Path, accelerator: Path, output: Path) -> dict[str, Any]:
    a, b, c = (json.loads(path.read_text(encoding="utf-8")) for path in (first_cpu, second_cpu, accelerator))
    for value in (a, b, c):
        if value.get("format") != "atmem-laya-reproduction-probe-v1":
            raise ValueError("unsupported reproduction probe")
    def pair(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
        if [row["example_id"] for row in left["predictions"]] != [row["example_id"] for row in right["predictions"]]:
            raise ValueError("reproduction membership mismatch")
        agreement = sum(x["selected_index"] == y["selected_index"] for x, y in zip(left["predictions"], right["predictions"])) / left["items"]
        delta = max(abs(x - y) for left_row, right_row in zip(left["predictions"], right["predictions"]) for x, y in zip(left_row["normalized_scores"], right_row["normalized_scores"]))
        return {"choice_agreement": agreement, "maximum_normalized_score_delta": delta}
    same = pair(a, b)
    cross = pair(a, c)
    aggregate_delta_points = abs(a["accuracy"] - c["accuracy"]) * 100
    same_passed = (
        same["choice_agreement"] >= SAME_BACKEND_TOLERANCE["minimum_choice_agreement"]
        and same["maximum_normalized_score_delta"] <= SAME_BACKEND_TOLERANCE["maximum_normalized_score_delta"]
    )
    cross_passed = (
        cross["choice_agreement"] >= CROSS_BACKEND_TOLERANCE["minimum_choice_agreement"]
        and aggregate_delta_points <= CROSS_BACKEND_TOLERANCE["maximum_primary_aggregate_delta_points"]
    )
    result = {
        "format": "atmem-laya-reproduction-report-v1",
        "same_backend": {**same, "tolerance": SAME_BACKEND_TOLERANCE, "passed": same_passed},
        "cross_backend": {
            **cross, "primary_aggregate_delta_points": aggregate_delta_points,
            "tolerance": CROSS_BACKEND_TOLERANCE, "passed": cross_passed,
        },
        "passed": same_passed and cross_passed,
    }
    if not all(math.isfinite(float(value)) for section in (same, cross) for value in section.values()):
        raise ValueError("nonfinite reproduction comparison")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe clean selected-model reloads and enforce FR-019 tolerances")
    commands = parser.add_subparsers(dest="command", required=True)
    probe_parser = commands.add_parser("probe")
    probe_parser.add_argument("--model-root", type=Path, required=True)
    probe_parser.add_argument("--rows", type=Path, required=True)
    probe_parser.add_argument("--device", required=True)
    probe_parser.add_argument("--output", type=Path, required=True)
    compare_parser = commands.add_parser("compare")
    compare_parser.add_argument("--first-cpu", type=Path, required=True)
    compare_parser.add_argument("--second-cpu", type=Path, required=True)
    compare_parser.add_argument("--accelerator", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "probe":
        result = probe(model_root=args.model_root, rows_path=args.rows, device_name=args.device, output=args.output)
    else:
        result = compare(first_cpu=args.first_cpu, second_cpu=args.second_cpu, accelerator=args.accelerator, output=args.output)
    print(json.dumps({key: value for key, value in result.items() if key != "predictions"}, sort_keys=True))
    return 0 if result.get("passed", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
