from __future__ import annotations

from dataclasses import replace

import pytest

from atmem.contracts.models import AuthorityScope
from atmem.laya_formation.contracts import CalibrationBinding, QuestionDefinitionV1
from atmem.laya_formation.governance import (
    AuthoritySnapshot,
    CandidateSnapshot,
    FormationDecisionIntent,
    FormationGovernanceAdapter,
    SourceRangeSnapshot,
)
from atmem.laya_formation.escalation import EscalationResult

SCOPE = AuthorityScope(subject_id="user-1", agent_id="agent-1", workspace_id="private")


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
        model_sha256="f2ba3dd7679da45aabab4cac30e9a079baeb2dc98229ff3b1618e6a06fc6d683",
        questions_digest="7a3cd0e13d99db02a1e53e51a63fad921e754ac5bbc2376b8a888c1033900f0e",
        calibration_digest="b165d4b7d554cdbda5a889baf7059c3f43ba2774d68754e4fa3aeb63f5f0e067",
        method="per-question-temperature-and-abstention-v1", temperatures=(1.0, 1.0, 1.0),
        temperature_by_options={"choice:3-5": 1.0}, thresholds={"choice:3-5": 1.0},
    )


class Gateway:
    def __init__(self, snapshots: list[AuthoritySnapshot]) -> None:
        self.snapshots = snapshots
        self.calls = 0

    def load(self, intent: FormationDecisionIntent) -> AuthoritySnapshot:
        value = self.snapshots[min(self.calls, len(self.snapshots) - 1)]
        self.calls += 1
        return value


def snapshot(**changes) -> AuthoritySnapshot:
    value = AuthoritySnapshot(
        scope=SCOPE, generation_id="gen-1", canonical_generation=7,
        source_ranges={"range-1": SourceRangeSnapshot(
            range_id="range-1", source_id="source-1", start=0, end=5,
            text="Alice", digest="sha256:" + "a" * 64,
        )},
        candidates={"unit-1": CandidateSnapshot(
            candidate_id="unit-1", generation_id="gen-1", lifecycle="active",
            digest="sha256:" + "b" * 64,
        )},
        policy_allowed=True,
    )
    return replace(value, **changes)


def intent(**changes) -> FormationDecisionIntent:
    value = FormationDecisionIntent(
        request_id="request-1", scope=SCOPE, generation_id="gen-1",
        canonical_generation=7, question=question(), calibration=calibration(),
        requested_range_ids=("range-1",), requested_candidate_ids=("unit-1",),
    )
    return replace(value, **changes)


def adapter(snapshots: list[AuthoritySnapshot]) -> FormationGovernanceAdapter:
    return FormationGovernanceAdapter(Gateway(snapshots), tokenizer_revision="7b928d828b7b0e022f929d9bd2e44165aa270148")


@pytest.mark.parametrize("bad", [
    intent(scope=AuthorityScope(subject_id="attacker", agent_id="agent-1", workspace_id="private")),
    intent(canonical_generation=6),
    intent(requested_range_ids=("invented",)),
    intent(requested_candidate_ids=("invented",)),
])
def test_forged_stale_cross_scope_or_invented_input_fails_before_model(bad) -> None:
    called = False
    def engine(_request):
        nonlocal called
        called = True
        raise AssertionError
    result = adapter([snapshot()]).decide(bad, engine=engine)
    assert result.receipt.authorizes_mutation is False
    assert result.receipt.final_disposition in {"authority_rejected", "deterministic_fallback"}
    assert called is False


def test_policy_denial_never_calls_model() -> None:
    result = adapter([snapshot(policy_allowed=False)]).decide(intent(), engine=lambda _: pytest.fail("model called"))
    assert result.receipt.final_disposition == "policy_denied"
    assert result.receipt.authorizes_mutation is False


def test_deletion_race_is_reloaded_after_model_and_fails_closed() -> None:
    result = adapter([snapshot(), snapshot(source_ranges={})]).decide(intent(), engine=lambda request: {
        "request_id": request.request_id,
        "selected_choice_ids": ["ADD"],
        "calibrated_scores": {choice: float(choice == "ADD") for choice in question().choice_ids},
        "confidence": 1.0, "abstained": False, "reason_code": "model_choice",
    })
    assert result.receipt.final_disposition == "authority_changed"
    assert result.receipt.authorizes_mutation is False


def test_provider_cannot_add_unauthorized_input_or_target() -> None:
    result = adapter([snapshot(), snapshot()]).decide(intent(), engine=lambda request: {
        "request_id": request.request_id,
        "selected_choice_ids": ["target:invented"],
        "calibrated_scores": {"target:invented": 1.0},
        "confidence": 1.0, "abstained": False, "reason_code": "provider_choice",
    })
    assert result.receipt.final_disposition == "invalid_model_output"
    assert result.receipt.authorizes_mutation is False


def test_timeout_or_authority_reload_failure_uses_non_authoritative_fallback() -> None:
    timed_out = adapter([snapshot()]).decide(
        intent(), engine=lambda _request: (_ for _ in ()).throw(TimeoutError("deadline")),
    )
    assert timed_out.receipt.final_disposition == "invalid_model_output"
    assert timed_out.receipt.authorizes_mutation is False

    class DeletedGateway(Gateway):
        def load(self, value):
            if self.calls:
                raise ValueError("deleted")
            return super().load(value)

    result = FormationGovernanceAdapter(
        DeletedGateway([snapshot()]), tokenizer_revision=question().tokenizer_revision,
    ).decide(intent(), engine=lambda request: {
        "request_id": request.request_id,
        "selected_choice_ids": ["ADD"],
        "calibrated_scores": {choice: float(choice == "ADD") for choice in question().choice_ids},
        "confidence": 1.0, "abstained": False, "reason_code": "model_choice",
    })
    assert result.receipt.final_disposition == "authority_changed"
    assert result.receipt.authorizes_mutation is False


def test_low_confidence_escalation_is_revalidated_and_remains_a_proposal() -> None:
    def escalation(request, reason):
        assert reason == "calibrated_low_confidence"
        response = {
            "request_id": request.request_id, "selected_choice_ids": ["UPDATE"],
            "calibrated_scores": {choice: float(choice == "UPDATE") for choice in question().choice_ids},
            "confidence": 0.8, "abstained": False, "reason_code": "atbot_bounded_escalation",
        }
        from atmem.laya_formation.contracts import FormationDecisionResponse
        return EscalationResult(
            response=FormationDecisionResponse.from_dict(response), used=True,
            disposition="escalated_proposal", provider="local-test", model="test-v1",
            egress_class="local", input_tokens=100, output_tokens=8, cost_usd=0.0,
        )

    result = adapter([snapshot(), snapshot()]).decide(
        intent(),
        engine=lambda request: {
            "request_id": request.request_id, "selected_choice_ids": [],
            "calibrated_scores": {}, "confidence": 0.0, "abstained": True,
            "reason_code": "calibrated_low_confidence",
        },
        escalator=escalation,
    )
    assert result.response.selected_choice_ids == ("UPDATE",)
    assert result.receipt.final_disposition == "escalated_proposal"
    assert result.receipt.escalation_provider == "local-test"
    assert result.receipt.authorizes_mutation is False
