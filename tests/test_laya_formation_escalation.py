from __future__ import annotations

from pathlib import Path

from atmem.contracts.models import AuthorityScope
from atmem.laya_formation.artifacts import ArtifactBundle
from atmem.laya_formation.contracts import CalibrationBinding, FormationDecisionRequest, QuestionDefinitionV1
from atmem.laya_formation.escalation import AtBotFormationEscalator, EscalationPolicy
from atmem.laya_formation.packing import AuthorizedRange, pack_authorized_ranges


class Packer:
    revision = "7b928d828b7b0e022f929d9bd2e44165aa270148"
    def head_token_count(self, question, head_max_len): return 40, len(question["crit"])
    def serialize_and_encode_state(self, state):
        import json
        text = json.dumps(state, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return text, list(text.encode())


def request() -> FormationDecisionRequest:
    question = QuestionDefinitionV1(
        "operation", "1.0.0", "choice", "Choose operation.",
        ("ADD", "UPDATE", "NOOP"), True, Packer.revision, 512, 192, 1,
        "whole-authorized-ranges-or-review",
    )
    calibration = CalibrationBinding(
        "f" * 64, "7a3cd0e13d99db02a1e53e51a63fad921e754ac5bbc2376b8a888c1033900f0e",
        "b165d4b7d554cdbda5a889baf7059c3f43ba2774d68754e4fa3aeb63f5f0e067",
        "per-question-temperature-and-abstention-v1", (1.0, 1.0, 1.0),
        {"choice:3-5": 1.0}, {"choice:3-5": 1.0},
    )
    packed = pack_authorized_ranges(
        adapter=Packer(), question=question.to_laya_internal(),
        ranges=[AuthorizedRange("range-1", "source-1", 0, 5, "Alice")],
    )
    return FormationDecisionRequest(
        "request-1", AuthorityScope("subject-1", "agent-1", "private"),
        "generation-1", 3, question, calibration, packed,
        {"range-1": "sha256:" + "a" * 64}, {"candidate-1": "sha256:" + "b" * 64},
    )


class Client:
    def __init__(self, value): self.value, self.calls = value, []
    def propose_formation_decision(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.value, Exception): raise self.value
        return self.value


def provider_value(**changes):
    value = {
        "format": "atbot-formation-decision-proposal-v1",
        "request_id": "request-1", "selected_choice_id": "ADD", "confidence": 0.8,
        "authority_decision": None, "canonical_storage": False,
        "provider": "local-test", "model": "test-v1", "egress_class": "local",
        "usage": {"input_tokens": 100, "output_tokens": 12, "cost_usd": 0.0},
    }
    return {**value, **changes}


def test_allowed_escalation_sends_minimum_authorized_input_and_budgets() -> None:
    client = Client(provider_value())
    policy = EscalationPolicy(enabled=True, max_input_tokens=512, max_output_tokens=64, timeout_seconds=4)
    result = AtBotFormationEscalator(client=client, policy=policy)(request(), "calibrated_low_confidence")
    assert result.used is True
    assert result.response.selected_choice_ids == ("ADD",)
    call = client.calls[0]
    assert call["max_output_tokens"] == 64 and call["timeout_seconds"] == 4
    payload = call["payload"]
    assert set(payload) == {"format", "request_id", "reason", "question", "authorized_input", "candidate_ids"}
    assert payload["authorized_input"]["authorized_ranges"][0]["range_id"] == "range-1"
    assert "scope" not in payload and "digests" not in payload


def test_disabled_unknown_offline_or_malformed_escalation_requires_review() -> None:
    for policy, value, reason in (
        (EscalationPolicy(enabled=False), provider_value(), "calibrated_low_confidence"),
        (EscalationPolicy(enabled=True), provider_value(), "unconfigured_reason"),
        (EscalationPolicy(enabled=True), OSError("offline"), "calibrated_low_confidence"),
        (EscalationPolicy(enabled=True), provider_value(selected_choice_id="INVENTED"), "calibrated_low_confidence"),
    ):
        client = Client(value)
        result = AtBotFormationEscalator(client=client, policy=policy)(request(), reason)
        assert result.used is False
        assert result.response.abstained is True
        assert result.disposition in {"deterministic_fallback", "review_required"}


def test_egress_usage_and_cost_limits_fail_closed() -> None:
    policy = EscalationPolicy(
        enabled=True, remote_egress_allowed=False, max_input_tokens=512,
        max_output_tokens=16, max_cost_usd=0.01,
    )
    for value in (
        provider_value(egress_class="remote"),
        provider_value(usage={"input_tokens": 100, "output_tokens": 17, "cost_usd": 0.0}),
        provider_value(egress_class="remote", usage={"input_tokens": 100, "output_tokens": 10, "cost_usd": 0.02}),
    ):
        result = AtBotFormationEscalator(client=Client(value), policy=policy)(
            request(), "calibrated_low_confidence",
        )
        assert result.response.abstained is True
        assert result.disposition == "review_required"
