"""Versioned, dependency-free contracts for optional Laya formation decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Any, Mapping

from atmem.contracts.models import AuthorityScope
from atmem.core.canonical import canonical_json, sha256_hex

from .packing import PackedDecisionInput


CONTRACT_VERSION = "1.0.0"
SUPPORTED_QUESTIONS_DIGEST = "7a3cd0e13d99db02a1e53e51a63fad921e754ac5bbc2376b8a888c1033900f0e"
_HEX = re.compile(r"^[0-9a-f]{64}$")
_BOUND_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def _identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(f"{name} must be a bounded non-empty identifier")


def _hex_digest(name: str, value: str) -> None:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise ValueError(f"{name} must be 64 lowercase hexadecimal characters")


def _bound_digest(name: str, value: str) -> None:
    if not isinstance(value, str) or not _BOUND_DIGEST.fullmatch(value):
        raise ValueError(f"{name} must use sha256:<64 lowercase hex>")


@dataclass(frozen=True, slots=True)
class QuestionDefinitionV1:
    question_id: str
    semantic_version: str
    kind: str
    instructions: str
    choice_ids: tuple[str, ...]
    allow_abstain: bool
    tokenizer_revision: str
    max_len: int
    head_max_len: int
    closing_tokens_reserved: int
    overflow_policy: str

    def validate(self) -> None:
        _identifier("question_id", self.question_id)
        if self.semantic_version != CONTRACT_VERSION or self.kind != "choice":
            raise ValueError("unsupported question definition version or kind")
        if not self.instructions.strip() or len(self.instructions) > 2_000:
            raise ValueError("question instructions must be bounded and non-empty")
        if len(self.choice_ids) < 2 or len(set(self.choice_ids)) != len(self.choice_ids):
            raise ValueError("choice identifiers must be finite, unique, and contain at least two choices")
        if any(not value.strip() or len(value) > 128 for value in self.choice_ids):
            raise ValueError("choice identifiers must be bounded and non-empty")
        if self.max_len != 512 or self.head_max_len != 192 or self.closing_tokens_reserved != 1:
            raise ValueError("question token limits differ from the pinned v1 contract")
        if self.overflow_policy != "whole-authorized-ranges-or-review":
            raise ValueError("unsupported overflow policy")
        _identifier("tokenizer_revision", self.tokenizer_revision)

    def to_laya(self) -> dict[str, Any]:
        self.validate()
        return {
            "type": "choice", "instructions": self.instructions,
            "criteria": {choice: choice.replace("_", " ").lower() for choice in self.choice_ids},
        }

    def to_laya_internal(self) -> dict[str, Any]:
        """Return the normalized shape consumed by Laya's exact head packer."""

        self.validate()
        return {
            "t": "choice", "ins": self.instructions,
            "crit": {choice: choice.replace("_", " ").lower() for choice in self.choice_ids},
        }

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self); value["choice_ids"] = list(self.choice_ids)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "QuestionDefinitionV1":
        result = cls(**{**value, "choice_ids": tuple(value["choice_ids"])})
        result.validate(); return result


@dataclass(frozen=True, slots=True)
class CalibrationBinding:
    model_sha256: str
    questions_digest: str
    calibration_digest: str
    method: str
    temperatures: tuple[float, ...]
    temperature_by_options: Mapping[str, float]
    thresholds: Mapping[str, float]

    def validate(self) -> None:
        for name in ("model_sha256", "questions_digest", "calibration_digest"):
            _hex_digest(name, getattr(self, name))
        if self.questions_digest != SUPPORTED_QUESTIONS_DIGEST:
            raise ValueError("calibration questions digest is incompatible with the v1 runtime")
        if self.method != "per-question-temperature-and-abstention-v1":
            raise ValueError("unsupported calibration method")
        values = [*self.temperatures, *self.temperature_by_options.values(), *self.thresholds.values()]
        if not values or any(not math.isfinite(float(value)) for value in values):
            raise ValueError("calibration values must be finite")
        if any(float(value) <= 0 for value in (*self.temperatures, *self.temperature_by_options.values())):
            raise ValueError("temperatures must be positive")
        if any(not 0 <= float(value) <= 1 for value in self.thresholds.values()):
            raise ValueError("confidence thresholds must be within [0,1]")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self); value["temperatures"] = list(self.temperatures)
        value["temperature_by_options"] = dict(sorted(self.temperature_by_options.items()))
        value["thresholds"] = dict(sorted(self.thresholds.items()))
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CalibrationBinding":
        result = cls(**{
            **value, "temperatures": tuple(value["temperatures"]),
            "temperature_by_options": dict(value["temperature_by_options"]),
            "thresholds": dict(value["thresholds"]),
        })
        result.validate(); return result


@dataclass(frozen=True, slots=True)
class FormationDecisionRequest:
    request_id: str
    scope: AuthorityScope
    generation_id: str
    canonical_generation: int
    question: QuestionDefinitionV1
    calibration: CalibrationBinding
    packed_input: PackedDecisionInput
    authorized_range_digests: Mapping[str, str]
    candidate_digests: Mapping[str, str]
    contract_version: str = CONTRACT_VERSION

    def validate(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("unsupported formation decision contract version")
        _identifier("request_id", self.request_id); _identifier("generation_id", self.generation_id)
        if self.canonical_generation < 0:
            raise ValueError("canonical generation must be non-negative")
        self.question.validate(); self.calibration.validate()
        if self.question.tokenizer_revision != self.packed_input.tokenizer_revision:
            raise ValueError("question and packed input tokenizer revisions differ")
        for mapping_name, mapping in (
            ("authorized range", self.authorized_range_digests), ("candidate", self.candidate_digests)
        ):
            for identity, digest in mapping.items():
                _identifier(f"{mapping_name} identity", identity); _bound_digest(f"{mapping_name} digest", digest)
        known = set(self.authorized_range_digests)
        if set(self.packed_input.included_range_ids) | set(self.packed_input.lost_range_ids) != known:
            raise ValueError("packing receipt membership differs from authorized ranges")

    def assert_model_ready(self) -> None:
        self.validate()
        if self.packed_input.overflow:
            raise ValueError("packed input overflow requires escalation or review")
        if self.packed_input.lost_range_ids:
            raise ValueError("model input cannot omit authorized ranges without an explicit alternate route")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "format": "atmem-formation-decision-request-v1",
            "contract_version": self.contract_version, "request_id": self.request_id,
            "scope": self.scope.to_dict(), "generation_id": self.generation_id,
            "canonical_generation": self.canonical_generation,
            "question": self.question.to_dict(), "calibration": self.calibration.to_dict(),
            "packed_input": self.packed_input.to_dict(),
            "authorized_range_digests": dict(sorted(self.authorized_range_digests.items())),
            "candidate_digests": dict(sorted(self.candidate_digests.items())),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FormationDecisionRequest":
        if value.get("format") != "atmem-formation-decision-request-v1":
            raise ValueError("unsupported request format")
        scope_value = dict(value["scope"]); scope_value.pop("format", None)
        packed = dict(value["packed_input"])
        packed["included_range_ids"] = tuple(packed["included_range_ids"])
        packed["lost_range_ids"] = tuple(packed["lost_range_ids"])
        result = cls(
            request_id=value["request_id"], scope=AuthorityScope(**scope_value),
            generation_id=value["generation_id"], canonical_generation=int(value["canonical_generation"]),
            question=QuestionDefinitionV1.from_dict(value["question"]),
            calibration=CalibrationBinding.from_dict(value["calibration"]),
            packed_input=PackedDecisionInput(**packed),
            authorized_range_digests=dict(value["authorized_range_digests"]),
            candidate_digests=dict(value["candidate_digests"]),
            contract_version=value["contract_version"],
        )
        result.validate(); return result

    def digest(self) -> str:
        return "sha256:" + sha256_hex(canonical_json(self.to_dict()))


@dataclass(frozen=True, slots=True)
class FormationDecisionResponse:
    request_id: str
    selected_choice_ids: tuple[str, ...]
    calibrated_scores: Mapping[str, float]
    confidence: float
    abstained: bool
    reason_code: str
    contract_version: str = CONTRACT_VERSION

    def validate(self, question: QuestionDefinitionV1) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("unsupported response contract version")
        _identifier("request_id", self.request_id); _identifier("reason_code", self.reason_code)
        known = set(question.choice_ids)
        if not self.abstained and len(self.selected_choice_ids) != 1:
            raise ValueError("a non-abstaining response requires exactly one choice")
        if self.abstained and self.selected_choice_ids:
            raise ValueError("an abstaining response cannot select a choice")
        if not set(self.selected_choice_ids).issubset(known) or not set(self.calibrated_scores).issubset(known):
            raise ValueError("response contains an unknown choice")
        values = [self.confidence, *self.calibrated_scores.values()]
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("response scores and confidence must be finite")
        if any(not 0 <= float(value) <= 1 for value in values):
            raise ValueError("response scores and confidence must be within [0,1]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "atmem-formation-decision-response-v1", "contract_version": self.contract_version,
            "request_id": self.request_id, "selected_choice_ids": list(self.selected_choice_ids),
            "calibrated_scores": dict(sorted(self.calibrated_scores.items())),
            "confidence": self.confidence, "abstained": self.abstained, "reason_code": self.reason_code,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FormationDecisionResponse":
        if value.get("format") not in (None, "atmem-formation-decision-response-v1"):
            raise ValueError("unsupported response format")
        return cls(
            request_id=value["request_id"], selected_choice_ids=tuple(value["selected_choice_ids"]),
            calibrated_scores=dict(value["calibrated_scores"]), confidence=float(value["confidence"]),
            abstained=bool(value["abstained"]), reason_code=value["reason_code"],
            contract_version=value.get("contract_version", CONTRACT_VERSION),
        )


@dataclass(frozen=True, slots=True)
class DecisionReceiptV1:
    request_id: str
    request_digest: str
    model_repo: str
    model_revision: str
    model_sha256: str
    questions_digest: str
    calibration_digest: str
    device: str
    proposed_choice_ids: tuple[str, ...]
    calibrated_scores: Mapping[str, float]
    confidence: float
    included_range_ids: tuple[str, ...]
    lost_range_ids: tuple[str, ...]
    canonical_generation: int
    reason_code: str
    latency_ms: float
    final_disposition: str
    authorizes_mutation: bool
    escalation_provider: str | None = None
    escalation_model: str | None = None
    escalation_egress_class: str | None = None
    escalation_input_tokens: int | None = None
    escalation_output_tokens: int | None = None
    escalation_cost_usd: float | None = None

    @classmethod
    def from_decision(
        cls, request: FormationDecisionRequest, response: FormationDecisionResponse, *,
        model_repo: str, model_revision: str, device: str, latency_ms: float,
        final_disposition: str,
        escalation: Mapping[str, Any] | None = None,
    ) -> "DecisionReceiptV1":
        request.validate(); response.validate(request.question)
        extra = dict(escalation or {})
        return cls(
            request_id=request.request_id, request_digest=request.digest(),
            model_repo=model_repo, model_revision=model_revision,
            model_sha256=request.calibration.model_sha256,
            questions_digest=request.calibration.questions_digest,
            calibration_digest=request.calibration.calibration_digest,
            device=device, proposed_choice_ids=response.selected_choice_ids,
            calibrated_scores=dict(response.calibrated_scores), confidence=response.confidence,
            included_range_ids=request.packed_input.included_range_ids,
            lost_range_ids=request.packed_input.lost_range_ids,
            canonical_generation=request.canonical_generation,
            reason_code=response.reason_code, latency_ms=float(latency_ms),
            final_disposition=final_disposition,
            authorizes_mutation=final_disposition == "authorized_mutation_committed",
            escalation_provider=extra.get("provider"), escalation_model=extra.get("model"),
            escalation_egress_class=extra.get("egress_class"),
            escalation_input_tokens=extra.get("input_tokens"),
            escalation_output_tokens=extra.get("output_tokens"),
            escalation_cost_usd=extra.get("cost_usd"),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = "atmem-formation-decision-receipt-v1"
        value["proposed_choice_ids"] = list(self.proposed_choice_ids)
        value["included_range_ids"] = list(self.included_range_ids)
        value["lost_range_ids"] = list(self.lost_range_ids)
        value["audit_digest"] = "sha256:" + sha256_hex(canonical_json(value))
        return value
