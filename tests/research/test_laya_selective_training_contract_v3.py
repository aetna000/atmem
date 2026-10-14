from __future__ import annotations

from research.laya_formation.training.run import (
    _balance_training_rows,
    _hard_target,
    _semantic_operation_coverage,
)
from research.laya_memory_evidence.training_view import question_definitions


def _row(operation: str, option: str, trajectory: str, option_count: int = 2) -> dict:
    options = [
        {"id": f"option_{index:03d}", "description": f"dynamic {index}"}
        for index in range(option_count)
    ]
    return {
        "trajectory_id": trajectory,
        "expected_operation": operation,
        "request": {"question": {
            "question_id": "formation.joint_transition.v3",
            "type": "choice", "instructions": "Choose one.", "options": options,
        }},
        "expected_response": {"type": "choice", "choice": option},
    }


def test_v3_balancing_uses_semantic_operation_not_opaque_option() -> None:
    rows = [
        _row("STORE_NEW", "option_000", "a"),
        _row("DO_NOT_STORE", "option_000", "b"),
        _row("DO_NOT_STORE", "option_001", "c"),
    ]
    assert [_hard_target(row) for row in rows] == [
        "STORE_NEW", "DO_NOT_STORE", "DO_NOT_STORE",
    ]
    balanced, report = _balance_training_rows(rows, seed=4)
    assert report["formation.joint_transition.v3"]["original"] == {
        "DO_NOT_STORE": 2, "STORE_NEW": 1,
    }
    assert len(balanced) == 4


def test_v3_dynamic_options_have_one_frozen_schema_definition() -> None:
    definitions = question_definitions([
        _row("STORE_NEW", "option_000", "a", 2),
        _row("UPDATE_EXISTING", "option_002", "b", 5),
    ])
    assert definitions["formation.joint_transition.v3"]["options"].startswith(
        "dynamic opaque action-target"
    )


def test_v3_semantic_coverage_is_trajectory_based() -> None:
    rows = [_row("STORE_NEW", "option_000", "same") for _ in range(150)]
    coverage = _semantic_operation_coverage(rows)
    assert coverage["distinct_trajectory_counts"] == {"STORE_NEW": 1}
    assert coverage["sufficient"] is False
