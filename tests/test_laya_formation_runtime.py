from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from atmem.contracts.models import AuthorityScope
from atmem.laya_formation.artifacts import ArtifactBundle
from atmem.laya_formation.contracts import (
    CalibrationBinding,
    FormationDecisionRequest,
    QuestionDefinitionV1,
)
from atmem.laya_formation.packing import AuthorizedRange, pack_authorized_ranges
from atmem.laya_formation.runtime import LayaDecisionEngine, select_device


class ExactTestPacker:
    revision = "7b928d828b7b0e022f929d9bd2e44165aa270148"

    def head_token_count(self, question, head_max_len):
        return 40, len(question["crit"])

    def serialize_and_encode_state(self, state):
        import json
        value = json.dumps(state, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return value, list(value.encode("utf-8"))


class FakeAgent:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def system_one(self, state, questions, **kwargs):
        self.calls.append((state, questions, kwargs))
        return {
            "answers": {"operation": self.answer},
            "usage": {
                "truncated": False,
                "state_tokens_dropped": 0,
                "input_tokens": 100,
                "output_tokens": 0,
            },
        }


def _question() -> QuestionDefinitionV1:
    return QuestionDefinitionV1(
        question_id="operation", semantic_version="1.0.0", kind="choice",
        instructions="Choose the only permitted memory formation operation.",
        choice_ids=("ADD", "UPDATE", "SUPERSEDE", "NOOP", "REJECT"),
        allow_abstain=True, tokenizer_revision=ExactTestPacker.revision,
        max_len=512, head_max_len=192, closing_tokens_reserved=1,
        overflow_policy="whole-authorized-ranges-or-review",
    )


def _calibration() -> CalibrationBinding:
    return CalibrationBinding(
        model_sha256="f2ba3dd7679da45aabab4cac30e9a079baeb2dc98229ff3b1618e6a06fc6d683",
        questions_digest="7a3cd0e13d99db02a1e53e51a63fad921e754ac5bbc2376b8a888c1033900f0e",
        calibration_digest="b165d4b7d554cdbda5a889baf7059c3f43ba2774d68754e4fa3aeb63f5f0e067",
        method="per-question-temperature-and-abstention-v1",
        temperatures=(1.0, 1.0, 1.0),
        temperature_by_options={"choice:3-5": 1.0}, thresholds={"choice:3-5": 1.0},
    )


def _bundle() -> ArtifactBundle:
    return ArtifactBundle(
        root=Path("/verified/model"), repo_id="atmem/atmem-laya-formation-model-v1",
        revision="1698278c4b158fac30e4eb2fefd10ef8b8f873b3",
        model_sha256=_calibration().model_sha256,
        questions_digest=_calibration().questions_digest,
        calibration_digest=_calibration().calibration_digest,
        export_digest="6f7d53c18431c27baa617ab95ebcc4cad669917a6508145fa001eb7c8e799900",
        calibration=_calibration(),
        questions={
            "operation": {
                "instructions": _question().instructions,
                "choice_ids": list(_question().choice_ids),
            }
        },
    )


def _request() -> FormationDecisionRequest:
    packed = pack_authorized_ranges(
        adapter=ExactTestPacker(), question=_question().to_laya_internal(),
        ranges=[AuthorizedRange("range-1", "source-1", 0, 5, "Alice")],
    )
    return FormationDecisionRequest(
        request_id="request-1",
        scope=AuthorityScope(subject_id="user-1", agent_id="agent-1", workspace_id="private"),
        generation_id="generation-1", canonical_generation=4,
        question=_question(), calibration=_calibration(), packed_input=packed,
        authorized_range_digests={"range-1": "sha256:" + "a" * 64},
        candidate_digests={},
    )


def _answer(scores, confidence):
    return {
        "type": "choice", "choice": max(scores, key=scores.get),
        "probabilities": scores, "answer_confidence": confidence,
        "confidence": confidence, "action": {"act_probability": 1.0},
    }


def test_explicit_cpu_device_is_stable_and_auto_is_resolved() -> None:
    assert select_device("cpu") == "cpu"
    assert select_device("auto").split(":")[0] in {"cpu", "cuda", "mps"}
    with pytest.raises(ValueError, match="device"):
        select_device("tpu")


def test_bounded_inference_accepts_only_full_calibrated_choice_vector() -> None:
    scores = {choice: float(choice == "ADD") for choice in _question().choice_ids}
    agent = FakeAgent(_answer(scores, 1.0))
    engine = LayaDecisionEngine(_bundle(), device="cpu", agent=agent, packing_adapter=ExactTestPacker())
    response = engine(_request())
    assert response.selected_choice_ids == ("ADD",)
    assert response.abstained is False
    assert agent.calls[0][2] == {"max_len": 512, "head_max_len": 192}
    assert engine.diagnostics()["input_digest"] == _request().packed_input.state_digest
    assert "Alice" not in repr(engine.diagnostics())


def test_low_calibrated_confidence_abstains_deterministically() -> None:
    scores = {"ADD": .9999, "UPDATE": .0001, "SUPERSEDE": 0.0, "NOOP": 0.0, "REJECT": 0.0}
    engine = LayaDecisionEngine(
        _bundle(), device="cpu", agent=FakeAgent(_answer(scores, .9999)),
        packing_adapter=ExactTestPacker(),
    )
    response = engine(_request())
    assert response.abstained is True
    assert response.selected_choice_ids == ()
    assert response.reason_code == "calibrated_low_confidence"


@pytest.mark.parametrize("answer", [
    _answer({"ADD": 1.0}, 1.0),
    _answer({"ADD": float("nan"), "UPDATE": 0.0, "SUPERSEDE": 0.0, "NOOP": 0.0, "REJECT": 0.0}, 1.0),
    _answer({"ADD": .8, "UPDATE": .8, "SUPERSEDE": 0.0, "NOOP": 0.0, "REJECT": 0.0}, .8),
])
def test_malformed_scores_fail_closed(answer) -> None:
    engine = LayaDecisionEngine(
        _bundle(), device="cpu", agent=FakeAgent(answer), packing_adapter=ExactTestPacker(),
    )
    with pytest.raises(ValueError, match="score|probability|choice"):
        engine(_request())


def test_runtime_refuses_calibration_or_question_drift() -> None:
    scores = {choice: float(choice == "ADD") for choice in _question().choice_ids}
    engine = LayaDecisionEngine(
        _bundle(), device="cpu", agent=FakeAgent(_answer(scores, 1.0)),
        packing_adapter=ExactTestPacker(),
    )
    request = _request()
    bad = FormationDecisionRequest(
        request_id=request.request_id, scope=request.scope, generation_id=request.generation_id,
        canonical_generation=request.canonical_generation,
        question=QuestionDefinitionV1(**{**request.question.to_dict(), "instructions": "Changed"}),
        calibration=request.calibration, packed_input=request.packed_input,
        authorized_range_digests=request.authorized_range_digests,
        candidate_digests=request.candidate_digests,
    )
    with pytest.raises(ValueError, match="question"):
        engine(bad)
