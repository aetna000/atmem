"""Bounded generative escalation through the existing AtBot companion."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any, Callable, Mapping

from .contracts import FormationDecisionRequest, FormationDecisionResponse


ALLOWED_ESCALATION_REASONS = frozenset({
    "ambiguity",
    "coupled_mutations",
    "unsupported_normalized_value",
    "input_overflow",
    "calibrated_low_confidence",
})


@dataclass(frozen=True, slots=True)
class EscalationPolicy:
    enabled: bool = False
    allowed_reasons: frozenset[str] = ALLOWED_ESCALATION_REASONS
    max_calls: int = 1
    max_input_tokens: int = 2_048
    max_output_tokens: int = 128
    timeout_seconds: float = 15.0
    retries: int = 0
    remote_egress_allowed: bool = False
    max_cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if not set(self.allowed_reasons).issubset(ALLOWED_ESCALATION_REASONS):
            raise ValueError("escalation policy contains an unsupported reason")
        if self.max_calls not in (0, 1):
            raise ValueError("formation escalation supports at most one provider call")
        if self.retries != 0:
            raise ValueError("formation escalation retries must remain zero")
        if not 128 <= self.max_input_tokens <= 8_192:
            raise ValueError("max_input_tokens must be within [128,8192]")
        if not 1 <= self.max_output_tokens <= 512:
            raise ValueError("max_output_tokens must be within [1,512]")
        if not math.isfinite(float(self.timeout_seconds)) or not 0 < self.timeout_seconds <= 90:
            raise ValueError("timeout_seconds must be finite and within (0,90]")
        if not math.isfinite(float(self.max_cost_usd)) or self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class EscalationResult:
    response: FormationDecisionResponse
    used: bool
    disposition: str
    provider: str | None = None
    model: str | None = None
    egress_class: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


def _abstain(request: FormationDecisionRequest, reason: str, disposition: str) -> EscalationResult:
    response = FormationDecisionResponse(
        request_id=request.request_id, selected_choice_ids=(), calibrated_scores={},
        confidence=0.0, abstained=True, reason_code=reason,
    )
    response.validate(request.question)
    return EscalationResult(response=response, used=False, disposition=disposition)


class AtBotFormationEscalator:
    def __init__(self, *, client: Any | None = None, policy: EscalationPolicy | None = None) -> None:
        if client is None:
            from atmem.control.atbot_companion import AtBotCompanionClient
            client = AtBotCompanionClient()
        self.client = client
        self.policy = policy or EscalationPolicy()

    def _payload(self, request: FormationDecisionRequest, reason: str) -> dict[str, Any]:
        try:
            state = json.loads(request.packed_input.state)
        except (TypeError, json.JSONDecodeError):
            raise ValueError("packed escalation input is not JSON") from None
        rows = state.get("authorized_ranges") if isinstance(state, dict) else None
        if not isinstance(rows, list):
            raise ValueError("packed escalation input has no authorized ranges")
        included = set(request.packed_input.included_range_ids)
        if any(not isinstance(row, dict) or str(row.get("range_id")) not in included for row in rows):
            raise ValueError("packed escalation input exceeds authorized range membership")
        return {
            "format": "atmem-formation-escalation-request-v1",
            "request_id": request.request_id,
            "reason": reason,
            "question": {
                "question_id": request.question.question_id,
                "instructions": request.question.instructions,
                "choice_ids": list(request.question.choice_ids),
            },
            "authorized_input": {"authorized_ranges": rows},
            "candidate_ids": sorted(request.candidate_digests),
        }

    def __call__(self, request: FormationDecisionRequest, reason: str) -> EscalationResult:
        request.validate()
        policy = self.policy
        if not policy.enabled or policy.max_calls == 0:
            return _abstain(request, "escalation_disabled", "deterministic_fallback")
        if reason not in policy.allowed_reasons:
            return _abstain(request, "escalation_reason_not_allowed", "deterministic_fallback")
        if request.packed_input.total_tokens > policy.max_input_tokens:
            return _abstain(request, "escalation_input_budget_exceeded", "review_required")
        try:
            value = self.client.propose_formation_decision(
                payload=self._payload(request, reason),
                max_input_tokens=policy.max_input_tokens,
                max_output_tokens=policy.max_output_tokens,
                timeout_seconds=policy.timeout_seconds,
                remote_egress_allowed=policy.remote_egress_allowed,
                max_cost_usd=policy.max_cost_usd,
            )
            if not isinstance(value, Mapping) or value.get("format") != "atbot-formation-decision-proposal-v1":
                raise ValueError("AtBot returned an incompatible escalation result")
            if value.get("authority_decision") is not None or value.get("canonical_storage") is not False:
                raise ValueError("AtBot crossed the non-authoritative proposal boundary")
            if str(value.get("request_id")) != request.request_id:
                raise ValueError("AtBot changed the escalation request identity")
            selected = str(value.get("selected_choice_id") or "")
            if selected not in request.question.choice_ids:
                raise ValueError("AtBot selected a choice outside the finite schema")
            confidence = float(value.get("confidence"))
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("AtBot returned invalid confidence")
            egress = str(value.get("egress_class") or "")
            if egress not in {"local", "remote"}:
                raise ValueError("AtBot omitted a valid egress class")
            if egress == "remote" and not policy.remote_egress_allowed:
                raise ValueError("remote escalation egress is denied")
            usage = value.get("usage")
            if not isinstance(usage, Mapping):
                raise ValueError("AtBot omitted escalation usage")
            input_tokens = int(usage.get("input_tokens"))
            output_tokens = int(usage.get("output_tokens"))
            if input_tokens < 0 or input_tokens > policy.max_input_tokens:
                raise ValueError("AtBot exceeded the escalation input budget")
            if output_tokens < 0 or output_tokens > policy.max_output_tokens:
                raise ValueError("AtBot exceeded the escalation output budget")
            raw_cost = usage.get("cost_usd")
            if raw_cost is None and egress == "remote":
                raise ValueError("remote escalation omitted its cost receipt")
            cost = 0.0 if raw_cost is None else float(raw_cost)
            if not math.isfinite(cost) or cost < 0 or cost > policy.max_cost_usd:
                raise ValueError("AtBot exceeded the escalation cost budget")
            scores = {choice: confidence if choice == selected else 0.0 for choice in request.question.choice_ids}
            response = FormationDecisionResponse(
                request_id=request.request_id, selected_choice_ids=(selected,),
                calibrated_scores=scores, confidence=confidence, abstained=False,
                reason_code="atbot_bounded_escalation",
            )
            response.validate(request.question)
            return EscalationResult(
                response=response, used=True, disposition="escalated_proposal",
                provider=str(value.get("provider") or ""), model=str(value.get("model") or ""),
                egress_class=egress, input_tokens=input_tokens, output_tokens=output_tokens,
                cost_usd=cost,
            )
        except (KeyError, TypeError, ValueError, RuntimeError, OSError, TimeoutError):
            return _abstain(request, "escalation_provider_unavailable_or_invalid", "review_required")
