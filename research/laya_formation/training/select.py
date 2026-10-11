from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from research.laya_formation.training.contracts import canonical_digest, write_json


SELECTION_POLICY = {
    "format": "atmem-laya-objective-selection-policy-v1",
    "eligible_objectives": ["soft-ce", "rlcd"],
    "sealed_test_available": False,
    "vetoes": {
        "nonfinite": True,
        "any_truncation": True,
        "prediction_collapse": True,
        "missing_expected_class": True,
        "calibration_underpowered": True,
        "validation_accuracy_drop_from_base_over": 0.002,
    },
    "ranking": [
        "maximize_min_validation_calibration_accuracy",
        "maximize_mean_validation_calibration_macro_f1",
        "minimize_mean_validation_calibration_nll",
        "minimize_calibration_ece",
        "minimize_calibration_brier",
        "objective_name_ascending_stable_tiebreak",
    ],
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def assess(run: Path) -> dict[str, Any]:
    manifest = _read(run / "training-manifest.json")
    base = _read(run / manifest["metrics"]["base_validation"])
    validation = _read(run / manifest["metrics"]["validation"])
    calibration = _read(run / manifest["metrics"]["calibration"])
    bundle = _read(run / manifest["calibration"]["path"])
    vetoes = []
    for name, report in (("validation", validation), ("calibration", calibration)):
        if report["nonfinite"]:
            vetoes.append(f"{name}_nonfinite")
        if report["truncation"]["truncated_items"]:
            vetoes.append(f"{name}_truncation")
        if report["collapse"]["collapsed"] or report["collapse"]["laya_warning"]:
            vetoes.append(f"{name}_collapse")
        if report["collapse"]["missing_expected_classes"]:
            vetoes.append(f"{name}_missing_expected_class")
    if not bundle["sample_counts"]["sufficient"]:
        vetoes.append("calibration_underpowered")
    if validation["accuracy"] + 0.002 < base["accuracy"]:
        vetoes.append("validation_accuracy_regression")
    values = [
        validation["accuracy"], calibration["accuracy"], validation["macro_f1"],
        calibration["macro_f1"], validation["nll"], calibration["nll"],
        calibration["ece"], calibration["brier"],
    ]
    if any(not math.isfinite(float(value)) for value in values):
        vetoes.append("nonfinite_selection_metric")
    rank = [
        min(validation["accuracy"], calibration["accuracy"]),
        (validation["macro_f1"] + calibration["macro_f1"]) / 2,
        -((validation["nll"] + calibration["nll"]) / 2),
        -calibration["ece"],
        -calibration["brier"],
    ]
    return {
        "run_id": manifest["run_id"], "objective": manifest["objective"],
        "eligible": not vetoes, "vetoes": vetoes, "rank": rank,
        "metrics": {"base_validation": base, "validation": validation, "calibration": calibration},
        "manifest_digest": canonical_digest(manifest),
        "calibration_digest": bundle["digest"],
    }


def select(runs: Sequence[Path]) -> dict[str, Any]:
    if len(runs) != 2:
        raise ValueError("selection requires exactly the soft-ce and rlcd runs")
    assessments = [assess(path) for path in runs]
    if sorted(item["objective"] for item in assessments) != ["rlcd", "soft-ce"]:
        raise ValueError("selection requires one soft-ce and one rlcd run")
    eligible = [item for item in assessments if item["eligible"]]
    # Stable objective-name ordering resolves an otherwise exact tie before the
    # descending metric sort; results cannot depend on filesystem order.
    eligible.sort(key=lambda item: item["objective"])
    eligible.sort(key=lambda item: tuple(item["rank"]), reverse=True)
    selected = eligible[0] if eligible else None
    result = {
        "format": "atmem-laya-objective-selection-v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "policy": SELECTION_POLICY,
        "policy_digest": canonical_digest(SELECTION_POLICY),
        "sealed_test_opened": False,
        "assessments": assessments,
        "selected_objective": selected["objective"] if selected else None,
        "selected_run_id": selected["run_id"] if selected else None,
        "state": "selected" if selected else "blocked",
    }
    result["digest"] = canonical_digest(result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select the frozen AtMem Laya training objective")
    parser.add_argument("runs", nargs=2, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = select([path.resolve() for path in args.runs])
    write_json(args.output.resolve(), result)
    print(json.dumps({"state": result["state"], "selected_objective": result["selected_objective"]}))
    return 0 if result["state"] == "selected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
