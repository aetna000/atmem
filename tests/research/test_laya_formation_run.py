from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.laya_formation.adapters import LocalChoiceAdapter
from benchmarks.laya_formation.contracts import ArmIdentity, ChoiceCase
from benchmarks.laya_formation.formation_run import run_arm, score_arm


def _identity() -> ArmIdentity:
    return ArmIdentity(
        arm="deterministic-atmem", provider="atmem", model="atmem-deterministic-formation",
        revision="2.3.9b1", hardware="test-cpu", dtype="rules", batching="one",
        maximum_calls=0, maximum_tokens=0, timeout_seconds=10, retries=0,
        remote_egress=False,
    )


def _case(question_id: str, expected: str) -> ChoiceCase:
    options = {
        "operation": ("ADD", "NOOP", "REJECT"),
        "memory_class": ("preference", "non_memory"),
        "evidence_support": ("SUPPORTED", "UNSUPPORTED"),
        "target_selection": ("target:none", "target:active"),
        "retrieval_usefulness": ("USEFUL", "NOT_USEFUL"),
    }[question_id]
    return ChoiceCase(
        case_id=f"scenario-000000:{question_id}", scenario_id="scenario-000000",
        cluster_id="cluster-000000", question_id=question_id,
        instructions="Choose one.", authorized_input={"safe": True},
        options=options, candidate_pool=(), expected=(expected,),
    )


def test_run_arm_blinds_expected_labels_and_refuses_overwrite(tmp_path: Path) -> None:
    seen = []

    def decide(case: ChoiceCase):
        seen.append(case.expected)
        return {"selected": case.options[0], "scores": {case.options[0]: 1.0}}

    output = tmp_path / "arm.jsonl"
    run_arm([_case("operation", "ADD")], LocalChoiceAdapter(_identity(), decide), output)
    assert seen == [()]
    with pytest.raises(FileExistsError):
        run_arm([_case("operation", "ADD")], LocalChoiceAdapter(_identity(), decide), output)


def test_score_requires_one_result_for_every_frozen_case(tmp_path: Path) -> None:
    cases = [_case("operation", "ADD"), _case("memory_class", "preference")]
    results = tmp_path / "incomplete.jsonl"
    arm = LocalChoiceAdapter(_identity(), lambda case: {"selected": case.options[0], "scores": {case.options[0]: 1.0}})
    run_arm(cases[:1], arm, results)
    with pytest.raises(ValueError, match="incomplete"):
        score_arm(cases, results, tmp_path / "post.jsonl")
