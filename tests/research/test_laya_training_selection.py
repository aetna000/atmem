from __future__ import annotations

import json

from research.laya_formation.training.select import SELECTION_POLICY, select


def _run(tmp_path, objective: str, *, accuracy: float, collapsed: bool = False):
    run = tmp_path / objective
    run.mkdir()
    metric = {
        "format": "atmem-laya-metric-report-v1", "run_id": objective,
        "objective": objective, "split": "validation", "loss_history": [0.1],
        "accuracy": accuracy, "macro_f1": accuracy, "nll": 1 - accuracy,
        "brier": 1 - accuracy, "ece": 1 - accuracy,
        "class_distribution": {"a": 0.5, "b": 0.5},
        "collapse": {"collapsed": collapsed, "laya_warning": None,
                     "missing_expected_classes": []},
        "truncation": {"truncated_items": 0}, "nonfinite": False,
    }
    base = {**metric, "accuracy": 0.5}
    calibration = {**metric, "split": "calibration"}
    bundle = {"sample_counts": {"sufficient": True}, "digest": "d" * 64}
    manifest = {
        "run_id": objective, "objective": objective,
        "metrics": {"base_validation": "base.json", "validation": "validation.json", "calibration": "calibration.json"},
        "calibration": {"path": "bundle.json"},
    }
    for name, value in (("base.json", base), ("validation.json", metric),
                        ("calibration.json", calibration), ("bundle.json", bundle),
                        ("training-manifest.json", manifest)):
        (run / name).write_text(json.dumps(value), encoding="utf-8")
    return run


def test_selection_policy_is_predeclared_and_never_uses_sealed_test(tmp_path) -> None:
    soft = _run(tmp_path, "soft-ce", accuracy=0.8)
    rlcd = _run(tmp_path, "rlcd", accuracy=0.9)
    result = select([soft, rlcd])
    assert SELECTION_POLICY["sealed_test_available"] is False
    assert result["sealed_test_opened"] is False
    assert result["selected_objective"] == "rlcd"


def test_collapse_is_a_veto_even_when_accuracy_would_win(tmp_path) -> None:
    soft = _run(tmp_path, "soft-ce", accuracy=0.8)
    rlcd = _run(tmp_path, "rlcd", accuracy=0.99, collapsed=True)
    result = select([soft, rlcd])
    assert result["selected_objective"] == "soft-ce"
    failed = next(item for item in result["assessments"] if item["objective"] == "rlcd")
    assert "validation_collapse" in failed["vetoes"]
