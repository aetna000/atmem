from __future__ import annotations

import pytest

from benchmarks.laya_formation.adapters import (
    BASE_LAYA_MODEL, BASE_LAYA_REVISION, FINETUNED_LAYA_MODEL,
    FINETUNED_LAYA_REVISION, QWEN_MODEL, QWEN_REVISION,
    EscalatingChoiceAdapter, JevChoiceAdapter, QwenChoiceAdapter,
    base_laya, deterministic_atmem, finetuned_laya, laya_agent_decision,
)
from benchmarks.laya_formation.contracts import ArmIdentity, ChoiceCase
from research.laya_formation.jev_protocol import resolve_model_identity


def case() -> ChoiceCase:
    return ChoiceCase(
        case_id="scenario-1:operation", scenario_id="scenario-1", cluster_id="cluster-1",
        question_id="operation", instructions="Choose the operation.",
        authorized_input={"evidence": [{"text": "fictional"}], "initial_state": {}},
        options=("ADD", "NOOP", "REJECT"), candidate_pool=("target:none",),
        expected=("ADD",),
    )


def identity(arm: str, model: str, revision: str, *, remote: bool = False) -> ArmIdentity:
    return ArmIdentity(
        arm=arm, provider="test", model=model, revision=revision, hardware="cpu",
        dtype="float32", batching="one", maximum_calls=int(remote),
        maximum_tokens=128 if remote else 0, timeout_seconds=10, retries=0,
        remote_egress=remote,
    )


def test_all_local_arms_share_exact_matching_receipt_and_hide_expected() -> None:
    seen = []
    def decide(value):
        seen.append(value)
        return {"selected": "ADD", "scores": {"ADD": 1.0}}
    arms = [
        deterministic_atmem(identity("deterministic-atmem", "atmem-deterministic-formation", "2.3.9b1"), decide),
        base_laya(identity("base-laya", BASE_LAYA_MODEL, BASE_LAYA_REVISION), decide),
        finetuned_laya(identity("finetuned-laya", FINETUNED_LAYA_MODEL, FINETUNED_LAYA_REVISION), decide),
    ]
    results = [arm.decide(case()) for arm in arms]
    assert len({result.matching.authorized_input_digest for result in results}) == 1
    assert all(result.selected == ("ADD",) for result in results)
    assert all(value.expected == ("ADD",) for value in seen)  # scorer-only field remains on case
    assert all("expected" not in result.prompt_digest for result in results)


def test_qwen_enforces_frozen_identity_and_strict_schema() -> None:
    arm = QwenChoiceAdapter(
        identity("pinned-current-qwen", QWEN_MODEL, QWEN_REVISION, remote=True),
        lambda payload, timeout: {
            "model": QWEN_MODEL, "choices": [{"message": {"content": '{"selected":"ADD"}'}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 4, "cost_usd": 0.01, "calls": 1},
        },
    )
    result = arm.decide(case())
    assert result.selected == ("ADD",) and result.usage.calls == 1
    mismatch = QwenChoiceAdapter(
        arm.identity,
        lambda payload, timeout: {"model": "moving-alias", "choices": []},
    ).decide(case())
    assert mismatch.error_code == "ValueError" and mismatch.response_model == "moving-alias"


def test_jev_uses_authenticated_concrete_identity() -> None:
    receipt = resolve_model_identity(
        {"models": [{"name": "jev-1.13.0", "release_date": "2026-09-15"}]},
        requested_model="jev-1.13.0",
    )
    arm = JevChoiceAdapter(
        identity("pinned-jev", "jev-1.13.0", "2026-09-15", remote=True), receipt,
        lambda payload, timeout: {
            "model": "jev-1.13.0",
            "answers": {"operation": {"type": "choice", "choice": "ADD", "probabilities": {"ADD": 1.0}}},
            "usage": {"calls": 1, "input_tokens": 20, "output_tokens": 1, "cost_usd": 0.0},
        },
    )
    assert arm.decide(case()).response_model == "jev-1.13.0"


def test_escalation_calls_once_only_after_local_abstention_and_retains_error() -> None:
    local = finetuned_laya(
        identity("finetuned-laya", FINETUNED_LAYA_MODEL, FINETUNED_LAYA_REVISION),
        lambda value: {"abstained": True, "review_required": True},
    )
    calls = []
    remote_identity = identity(
        "finetuned-laya-with-atbot-escalation", "bounded-atbot-provider", "frozen", remote=True,
    )
    arm = EscalatingChoiceAdapter(
        remote_identity, local,
        lambda payload, timeout: calls.append(payload) or {
            "selected": "ADD", "scores": {"ADD": 1.0},
            "usage": {"calls": 1, "input_tokens": 20, "output_tokens": 1, "cost_usd": 0.001},
            "model": "provider-snapshot",
        },
    )
    result = arm.decide(case())
    assert result.escalated and result.selected == ("ADD",) and len(calls) == 1

    failed = EscalatingChoiceAdapter(
        remote_identity, local,
        lambda payload, timeout: (_ for _ in ()).throw(TimeoutError()),
    ).decide(case())
    assert failed.error_code == "TimeoutError" and failed.review_required


def test_laya_decision_applies_frozen_bucket_threshold() -> None:
    class Agent:
        def system_one(self, state, questions, **kwargs):
            return {
                "answers": {"operation": {
                    "type": "choice", "choice": "ADD", "answer_confidence": .9,
                    "probabilities": {"ADD": .9, "NOOP": .05, "REJECT": .05},
                }},
                "usage": {"input_tokens": 10, "output_tokens": 1},
            }

    decision = laya_agent_decision(Agent(), abstention_thresholds={"choice:3-5": 1.0})
    result = decision(case())
    assert result["abstained"] is True
    assert result["selected"] is None
    assert result["review_required"] is True
