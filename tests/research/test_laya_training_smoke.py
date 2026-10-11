from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.laya_formation.training.smoke import (
    _load_optimizer_state,
    _save_optimizer_state,
    evaluate_viability,
    load_workload,
    to_laya_rows,
)


def test_fixed_workload_pins_full_training_and_both_objectives() -> None:
    workload = load_workload()
    assert workload["base_model"]["revision"] == "7b928d828b7b0e022f929d9bd2e44165aa270148"
    assert workload["dataset"]["revision"] == "4436089b38cbe3a5374aaaa92c4c77703cdbf668"
    assert workload["training"]["objectives"] == ["soft-ce", "rlcd"]
    assert workload["training"]["freeze_encoder"] is False


def test_viability_requires_every_frozen_gate() -> None:
    limits = load_workload()["viability"]
    evidence = {
        "error": None,
        "nonfinite": False,
        "resume_verified": True,
        "safetensors_reload_verified": True,
        "memory_headroom_fraction": 0.21,
        "free_to_projected_storage_ratio": 3.1,
        "projected_both_objectives_hours": 47.9,
    }
    assert evaluate_viability(evidence, limits) == {"state": "viable", "reason_codes": []}
    evidence["memory_headroom_fraction"] = 0.19
    evidence["projected_both_objectives_hours"] = 48.1
    decision = evaluate_viability(evidence, limits)
    assert decision["state"] == "infeasible"
    assert decision["reason_codes"] == [
        "memory_headroom_below_20_percent", "projected_runtime_over_48_hours"
    ]


def test_dataset_rows_convert_to_finite_laya_choice_questions() -> None:
    row = {
        "question_id": "operation",
        "choice_ids": ["ADD", "REJECT"],
        "expected_choice_ids": ["REJECT"],
        "authorized_input": {"evidence": [{"text": "fictional"}], "initial_state": {}},
    }
    converted = to_laya_rows([row])[0]
    question = converted["questions"]["operation"]
    assert question["type"] == "choice"
    assert list(question["criteria"]) == ["ADD", "REJECT"]
    assert converted["expected"] == {"operation": "REJECT"}


def test_dataset_conversion_rejects_multiselect() -> None:
    row = {
        "question_id": "operation", "choice_ids": ["ADD", "REJECT"],
        "expected_choice_ids": ["ADD", "REJECT"], "authorized_input": {},
    }
    with pytest.raises(ValueError, match="exactly one"):
        to_laya_rows([row])


def test_optimizer_resume_state_uses_safetensors_not_pickle(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    parameter = torch.nn.Parameter(torch.tensor([1.0, 2.0]))
    optimizer = torch.optim.AdamW([parameter], lr=0.01)
    parameter.sum().backward()
    optimizer.step()
    _save_optimizer_state(torch, optimizer, tmp_path, seed=7)
    restored = _load_optimizer_state(tmp_path)
    assert (tmp_path / "optimizer.safetensors").is_file()
    assert (tmp_path / "optimizer.json").is_file()
    assert not list(tmp_path.glob("*.pt"))
    assert restored["param_groups"][0]["lr"] == 0.01
    assert set(restored["state"][0]) == {"step", "exp_avg", "exp_avg_sq"}
