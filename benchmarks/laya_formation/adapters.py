"""Six matched choice adapters for Spec 041.

Remote transports are injected so importing this module never causes egress.
Every adapter receives the same ``ChoiceCase`` and emits the same retained-row
contract. Expected labels are never included in any model payload.
"""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Callable, Mapping, Protocol

from research.laya_formation.jev_protocol import JevIdentityReceipt, verify_response_model

from .contracts import ArmIdentity, ChoiceCase, ChoiceResult, Usage, canonical_bytes, digest


QWEN_MODEL = "Qwen/Qwen3.5-9B"
QWEN_REVISION = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
BASE_LAYA_MODEL = "convaiinnovations/laya"
BASE_LAYA_REVISION = "7b928d828b7b0e022f929d9bd2e44165aa270148"
FINETUNED_LAYA_MODEL = "atmem/atmem-laya-formation-model-v1"
FINETUNED_LAYA_REVISION = "1698278c4b158fac30e4eb2fefd10ef8b8f873b3"


class ChoiceAdapter(Protocol):
    identity: ArmIdentity

    def decide(self, case: ChoiceCase) -> ChoiceResult: ...


Transport = Callable[[Mapping[str, Any], float], Mapping[str, Any]]
LocalDecision = Callable[[ChoiceCase], Mapping[str, Any]]


def _choice_bucket(option_count: int) -> str:
    size = "2" if option_count <= 2 else "3-5" if option_count <= 5 else "6-10" if option_count <= 10 else "11+"
    return f"choice:{size}"


def laya_agent_decision(
    agent: Any, *, abstention_thresholds: Mapping[str, float] | None = None,
) -> LocalDecision:
    """Bind an upstream Laya Agent without exposing scorer-only fields."""

    def decide(case: ChoiceCase) -> Mapping[str, Any]:
        state = canonical_bytes(case.authorized_input).decode()
        raw = agent.system_one(
            state,
            {case.question_id: {
                "type": "choice", "instructions": case.instructions,
                "criteria": {choice: choice.replace("_", " ").lower() for choice in case.options},
            }},
            max_len=512, head_max_len=192,
        )
        answer = raw.get("answers", {}).get(case.question_id)
        if not isinstance(answer, Mapping) or answer.get("type") != "choice":
            raise ValueError("Laya response omitted the requested finite choice")
        selected = answer.get("choice")
        scores = {str(key): float(value) for key, value in dict(answer.get("probabilities") or {}).items()}
        if set(scores) != set(case.options) or selected not in case.options:
            raise ValueError("Laya response differs from the frozen finite choice set")
        confidence = float(answer.get("answer_confidence", scores[selected]))
        abstained = False
        if abstention_thresholds is not None:
            bucket = _choice_bucket(len(case.options))
            if bucket not in abstention_thresholds:
                raise ValueError("no abstention threshold exists for the frozen option bucket")
            abstained = round(confidence, 4) < float(abstention_thresholds[bucket])
        return {
            "selected": None if abstained else selected,
            "scores": scores,
            "abstained": abstained,
            "review_required": abstained,
            "usage": {**dict(raw.get("usage") or {}), "calls": 0},
        }

    return decide


def _usage(value: Mapping[str, Any], *, default_calls: int) -> Usage:
    return Usage(
        calls=int(value.get("calls", default_calls)),
        input_tokens=int(value.get("input_tokens", value.get("prompt_tokens", 0))),
        output_tokens=int(value.get("output_tokens", value.get("completion_tokens", 0))),
        cost_usd=float(value.get("cost_usd", 0.0)),
    )


def _normalize(
    case: ChoiceCase,
    identity: ArmIdentity,
    raw: Mapping[str, Any],
    *,
    latency_ms: float,
    prompt_digest: str,
    escalated: bool = False,
    response_model: str | None = None,
    default_calls: int = 0,
) -> ChoiceResult:
    usage = _usage(raw.get("usage") if isinstance(raw.get("usage"), Mapping) else {}, default_calls=default_calls)
    error = raw.get("error_code")
    selected_value = raw.get("selected", raw.get("selected_choice_ids", ()))
    if isinstance(selected_value, str):
        selected = (selected_value,)
    else:
        selected = tuple(str(value) for value in (selected_value or ()))
    scores_value = raw.get("scores", raw.get("calibrated_scores", {}))
    scores = {str(key): float(value) for key, value in dict(scores_value or {}).items()}
    abstained = bool(raw.get("abstained", not selected))
    if error is None:
        if not set(selected).issubset(case.options) or not set(scores).issubset(case.options):
            raise ValueError("adapter returned a choice outside the frozen option set")
        if not abstained and len(selected) != 1:
            raise ValueError("adapter must select exactly one finite choice")
    return ChoiceResult(
        case_id=case.case_id, identity=identity, matching=case.matching_receipt(),
        selected=selected, scores=scores, abstained=abstained,
        review_required=bool(raw.get("review_required", abstained or error is not None)),
        escalated=escalated, latency_ms=latency_ms, usage=usage,
        prompt_digest=prompt_digest, response_model=response_model,
        error_code=str(error) if error is not None else None,
    )


class LocalChoiceAdapter:
    """Adapter used by deterministic AtMem and either exact Laya checkpoint."""

    def __init__(self, identity: ArmIdentity, decision: LocalDecision) -> None:
        if identity.remote_egress or identity.maximum_calls != 0:
            raise ValueError("local adapter identity cannot authorize remote calls")
        self.identity = identity
        self._decision = decision

    def decide(self, case: ChoiceCase) -> ChoiceResult:
        prompt = canonical_bytes({
            "question_id": case.question_id, "instructions": case.instructions,
            "options": list(case.options), "authorized_input": case.authorized_input,
            "candidate_pool": list(case.candidate_pool),
        })
        started = perf_counter()
        try:
            raw = self._decision(case)
            if not isinstance(raw, Mapping):
                raise TypeError("local decision is not an object")
            return _normalize(
                case, self.identity, raw,
                latency_ms=(perf_counter() - started) * 1000,
                prompt_digest="sha256:" + __import__("hashlib").sha256(prompt).hexdigest(),
            )
        except Exception as exc:
            return _normalize(
                case, self.identity,
                {"error_code": type(exc).__name__, "abstained": True, "review_required": True},
                latency_ms=(perf_counter() - started) * 1000,
                prompt_digest="sha256:" + __import__("hashlib").sha256(prompt).hexdigest(),
            )


def deterministic_atmem(identity: ArmIdentity, decision: LocalDecision) -> LocalChoiceAdapter:
    if identity.arm != "deterministic-atmem" or identity.model != "atmem-deterministic-formation":
        raise ValueError("deterministic AtMem identity mismatch")
    return LocalChoiceAdapter(identity, decision)


def base_laya(identity: ArmIdentity, decision: LocalDecision) -> LocalChoiceAdapter:
    if identity.arm != "base-laya" or (identity.model, identity.revision) != (BASE_LAYA_MODEL, BASE_LAYA_REVISION):
        raise ValueError("base Laya identity mismatch")
    return LocalChoiceAdapter(identity, decision)


def finetuned_laya(identity: ArmIdentity, decision: LocalDecision) -> LocalChoiceAdapter:
    if identity.arm != "finetuned-laya" or (identity.model, identity.revision) != (FINETUNED_LAYA_MODEL, FINETUNED_LAYA_REVISION):
        raise ValueError("fine-tuned Laya identity mismatch")
    return LocalChoiceAdapter(identity, decision)


class QwenChoiceAdapter:
    def __init__(self, identity: ArmIdentity, transport: Transport) -> None:
        if identity.arm != "pinned-current-qwen" or (identity.model, identity.revision) != (QWEN_MODEL, QWEN_REVISION):
            raise ValueError("Qwen must use the frozen current model revision")
        if not identity.remote_egress or identity.maximum_calls != 1 or identity.retries != 0:
            raise ValueError("Qwen arm requires one authorized call and zero retries")
        self.identity = identity
        self._transport = transport

    def decide(self, case: ChoiceCase) -> ChoiceResult:
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["selected"],
            "properties": {"selected": {"type": "string", "enum": list(case.options)}},
        }
        user = canonical_bytes({
            "instructions": case.instructions, "authorized_input": case.authorized_input,
            "candidate_pool": list(case.candidate_pool), "options": list(case.options),
        }).decode()
        payload = {
            "model": self.identity.model,
            "messages": [
                {"role": "system", "content": "Return only the schema-bound finite choice. Do not invent evidence or options."},
                {"role": "user", "content": user},
            ],
            "temperature": 0, "max_tokens": self.identity.maximum_tokens,
            "response_format": {"type": "json_schema", "json_schema": {"name": "formation_choice", "strict": True, "schema": schema}},
        }
        started = perf_counter()
        response_model = None
        try:
            raw = self._transport(payload, self.identity.timeout_seconds)
            response_model = str(raw.get("model", ""))
            if response_model != self.identity.model:
                raise ValueError("Qwen response model differs from the frozen deployment identity")
            choices = raw.get("choices")
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("Qwen response must contain exactly one choice")
            content = choices[0].get("message", {}).get("content")
            parsed = json.loads(content) if isinstance(content, str) else content
            if not isinstance(parsed, Mapping) or set(parsed) != {"selected"}:
                raise ValueError("Qwen response violates the strict choice schema")
            return _normalize(
                case, self.identity,
                {"selected": parsed["selected"], "scores": {}, "usage": raw.get("usage", {"calls": 1})},
                latency_ms=(perf_counter() - started) * 1000,
                prompt_digest=digest(payload), response_model=response_model, default_calls=1,
            )
        except Exception as exc:
            return _normalize(
                case, self.identity,
                {"error_code": type(exc).__name__, "abstained": True, "review_required": True, "usage": {"calls": 1}},
                latency_ms=(perf_counter() - started) * 1000,
                prompt_digest=digest(payload), response_model=response_model, default_calls=1,
            )


class JevChoiceAdapter:
    def __init__(self, identity: ArmIdentity, resolved: JevIdentityReceipt, transport: Transport) -> None:
        if identity.arm != "pinned-jev" or identity.model != resolved.resolved_model:
            raise ValueError("Jev identity is not the authenticated resolved model")
        if not identity.remote_egress or identity.maximum_calls != 1 or identity.retries != 0:
            raise ValueError("Jev arm requires one authorized call and zero retries")
        self.identity, self.resolved, self._transport = identity, resolved, transport

    def decide(self, case: ChoiceCase) -> ChoiceResult:
        payload = {
            "model": self.resolved.resolved_model,
            "state": canonical_bytes(case.authorized_input).decode(),
            "questions": {case.question_id: {
                "type": "choice", "instructions": case.instructions,
                "criteria": {choice: choice.replace("_", " ").lower() for choice in case.options},
            }},
        }
        started = perf_counter()
        response_model = None
        try:
            raw = self._transport(payload, self.identity.timeout_seconds)
            response_model = str(raw.get("model", ""))
            verify_response_model(self.resolved, raw)
            answer = raw["answers"].get(case.question_id)
            if not isinstance(answer, Mapping) or answer.get("type") != "choice":
                raise ValueError("Jev response omitted the requested finite choice")
            selected = answer.get("choice")
            scores = answer.get("probabilities", {})
            return _normalize(
                case, self.identity,
                {"selected": selected, "scores": scores, "usage": raw["usage"]},
                latency_ms=(perf_counter() - started) * 1000,
                prompt_digest=digest(payload), response_model=response_model, default_calls=1,
            )
        except Exception as exc:
            return _normalize(
                case, self.identity,
                {"error_code": type(exc).__name__, "abstained": True, "review_required": True, "usage": {"calls": 1}},
                latency_ms=(perf_counter() - started) * 1000,
                prompt_digest=digest(payload), response_model=response_model, default_calls=1,
            )


class EscalatingChoiceAdapter:
    """Run fine-tuned Laya first and make at most one AtBot escalation call."""

    def __init__(self, identity: ArmIdentity, local: ChoiceAdapter, escalation: Transport) -> None:
        if identity.arm != "finetuned-laya-with-atbot-escalation":
            raise ValueError("escalating adapter arm mismatch")
        if local.identity.arm != "finetuned-laya" or identity.maximum_calls != 1 or identity.retries != 0:
            raise ValueError("escalation requires fine-tuned Laya plus one call and zero retries")
        self.identity, self.local, self._escalation = identity, local, escalation

    def decide(self, case: ChoiceCase) -> ChoiceResult:
        first = self.local.decide(case)
        if first.successful and not first.abstained:
            return ChoiceResult(
                case_id=case.case_id, identity=self.identity, matching=first.matching,
                selected=first.selected, scores=first.scores, abstained=False,
                review_required=False, escalated=False, latency_ms=first.latency_ms,
                usage=Usage(), prompt_digest=first.prompt_digest,
                response_model=first.response_model,
            )
        payload = {
            "question": {"id": case.question_id, "instructions": case.instructions, "options": list(case.options)},
            "authorized_input": case.authorized_input,
            "candidate_ids": list(case.candidate_pool),
        }
        started = perf_counter()
        try:
            raw = self._escalation(payload, self.identity.timeout_seconds)
            return _normalize(
                case, self.identity, raw,
                latency_ms=first.latency_ms + (perf_counter() - started) * 1000,
                prompt_digest=digest(payload), escalated=True,
                response_model=str(raw.get("model", "")) or None, default_calls=1,
            )
        except Exception as exc:
            return _normalize(
                case, self.identity,
                {"error_code": type(exc).__name__, "abstained": True, "review_required": True, "usage": {"calls": 1}},
                latency_ms=first.latency_ms + (perf_counter() - started) * 1000,
                prompt_digest=digest(payload), escalated=True, default_calls=1,
            )
