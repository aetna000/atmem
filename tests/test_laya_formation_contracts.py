from __future__ import annotations

from dataclasses import replace

import pytest

from atmem.contracts.models import AuthorityScope
from atmem.laya_formation.contracts import (
    CalibrationBinding,
    DecisionReceiptV1,
    FormationDecisionRequest,
    FormationDecisionResponse,
    QuestionDefinitionV1,
)
from atmem.laya_formation.packing import AuthorizedRange, PackedDecisionInput


MODEL_SHA = "f2ba3dd7679da45aabab4cac30e9a079baeb2dc98229ff3b1618e6a06fc6d683"
QUESTION_SHA = "7a3cd0e13d99db02a1e53e51a63fad921e754ac5bbc2376b8a888c1033900f0e"
CALIBRATION_SHA = "b165d4b7d554cdbda5a889baf7059c3f43ba2774d68754e4fa3aeb63f5f0e067"


def question() -> QuestionDefinitionV1:
    return QuestionDefinitionV1(
        question_id="operation", semantic_version="1.0.0", kind="choice",
        instructions="Choose the only permitted memory formation operation.",
        choice_ids=("ADD", "UPDATE", "SUPERSEDE", "NOOP", "REJECT"),
        allow_abstain=True, tokenizer_revision="7b928d828b7b0e022f929d9bd2e44165aa270148",
        max_len=512, head_max_len=192, closing_tokens_reserved=1,
        overflow_policy="whole-authorized-ranges-or-review",
    )


def calibration() -> CalibrationBinding:
    return CalibrationBinding(
        model_sha256=MODEL_SHA, questions_digest=QUESTION_SHA,
        calibration_digest=CALIBRATION_SHA, method="per-question-temperature-and-abstention-v1",
        temperatures=(1.0, 1.0, 1.0), temperature_by_options={"choice:3-5": 1.0},
        thresholds={"choice:3-5": 1.0},
    )


def packing(*, overflow: bool = False) -> PackedDecisionInput:
    return PackedDecisionInput(
        format="atmem-laya-packed-decision-input-v1", packer_version="1.0.0",
        tokenizer_revision="7b928d828b7b0e022f929d9bd2e44165aa270148",
        state='{"authorized_ranges":[]}', state_digest="sha256:" + "a" * 64,
        included_range_ids=() if overflow else ("range-1",),
        lost_range_ids=("range-1",) if overflow else (), head_tokens=51,
        state_tokens=10, max_len=512, head_max_len=192,
        closing_tokens_reserved=1, total_tokens=62, overflow=overflow,
    )


def request(*, overflow: bool = False) -> FormationDecisionRequest:
    return FormationDecisionRequest(
        request_id="request-1",
        scope=AuthorityScope(subject_id="user-1", agent_id="agent-1", workspace_id="private"),
        generation_id="gen-1", canonical_generation=7,
        question=question(), calibration=calibration(), packed_input=packing(overflow=overflow),
        authorized_range_digests={"range-1": "sha256:" + "b" * 64},
        candidate_digests={"unit-1": "sha256:" + "c" * 64},
    )


def test_contract_golden_round_trip_is_stable_and_content_bounded() -> None:
    value = request()
    encoded = value.to_dict()
    assert FormationDecisionRequest.from_dict(encoded) == value
    assert encoded["question"]["choice_ids"] == ["ADD", "UPDATE", "SUPERSEDE", "NOOP", "REJECT"]
    assert "password" not in str(encoded).casefold()


@pytest.mark.parametrize("mutation", [
    lambda value: replace(value, contract_version="2.0.0"),
    lambda value: replace(value, question=replace(value.question, choice_ids=("ADD", "ADD"))),
    lambda value: replace(value, calibration=replace(value.calibration, questions_digest="0" * 64)),
])
def test_malformed_or_incompatible_contracts_fail_closed(mutation) -> None:
    with pytest.raises(ValueError):
        mutation(request()).validate()


def test_overflow_is_explicit_and_cannot_be_sent_to_laya() -> None:
    value = request(overflow=True)
    assert value.packed_input.overflow is True
    assert value.packed_input.lost_range_ids == ("range-1",)
    with pytest.raises(ValueError, match="overflow"):
        value.assert_model_ready()


def test_response_preserves_finite_choices_and_rejects_nonfinite_scores() -> None:
    value = FormationDecisionResponse(
        request_id="request-1", selected_choice_ids=("ADD",),
        calibrated_scores={"ADD": 1.0, "UPDATE": 0.0, "SUPERSEDE": 0.0, "NOOP": 0.0, "REJECT": 0.0},
        confidence=1.0, abstained=False, reason_code="model_choice",
    )
    value.validate(question())
    with pytest.raises(ValueError, match="finite"):
        replace(value, calibrated_scores={**value.calibrated_scores, "ADD": float("nan")}).validate(question())
    with pytest.raises(ValueError, match="unknown"):
        replace(value, selected_choice_ids=("INVENTED",)).validate(question())


def test_receipt_separates_proposal_from_authoritative_disposition() -> None:
    receipt = DecisionReceiptV1.from_decision(
        request(), FormationDecisionResponse(
            request_id="request-1", selected_choice_ids=("ADD",),
            calibrated_scores={choice: float(choice == "ADD") for choice in question().choice_ids},
            confidence=1.0, abstained=False, reason_code="model_choice",
        ),
        model_repo="atmem/atmem-laya-formation-model-v1",
        model_revision="1698278c4b158fac30e4eb2fefd10ef8b8f873b3",
        device="cpu", latency_ms=12.5, final_disposition="policy_denied",
    )
    assert receipt.proposed_choice_ids == ("ADD",)
    assert receipt.final_disposition == "policy_denied"
    assert receipt.authorizes_mutation is False
