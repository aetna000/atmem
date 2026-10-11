"""Strict matched-evaluation contracts for the synthetic formation benchmark."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Any, Mapping


ARMS = frozenset({
    "deterministic-atmem", "pinned-current-qwen", "base-laya",
    "finetuned-laya", "pinned-jev", "finetuned-laya-with-atbot-escalation",
})


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class MatchingReceipt:
    case_id: str
    authorized_input_digest: str
    option_digest: str
    candidate_pool_digest: str
    question_schema_digest: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ChoiceCase:
    case_id: str
    scenario_id: str
    cluster_id: str
    question_id: str
    instructions: str
    authorized_input: Mapping[str, Any]
    options: tuple[str, ...]
    candidate_pool: tuple[str, ...] = ()
    expected: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        identifiers = (self.case_id, self.scenario_id, self.cluster_id, self.question_id)
        if any(not isinstance(value, str) or not value.strip() for value in identifiers):
            raise ValueError("case identifiers must be non-empty")
        if not self.instructions.strip() or len(self.instructions) > 2_000:
            raise ValueError("question instructions must be bounded and non-empty")
        if len(self.options) < 2 or len(set(self.options)) != len(self.options):
            raise ValueError("options must be finite and unique")
        if len(set(self.candidate_pool)) != len(self.candidate_pool):
            raise ValueError("candidate pool must be unique")
        if not set(self.expected).issubset(self.options):
            raise ValueError("expected choices must belong to the option set")

    def matching_receipt(self) -> MatchingReceipt:
        return MatchingReceipt(
            case_id=self.case_id,
            authorized_input_digest=digest(self.authorized_input),
            option_digest=digest(list(self.options)),
            candidate_pool_digest=digest(list(self.candidate_pool)),
            question_schema_digest=digest({
                "question_id": self.question_id,
                "instructions": self.instructions,
                "options": list(self.options),
                "type": "choice",
            }),
        )


@dataclass(frozen=True, slots=True)
class ArmIdentity:
    arm: str
    provider: str
    model: str
    revision: str
    hardware: str
    dtype: str
    batching: str
    maximum_calls: int
    maximum_tokens: int
    timeout_seconds: float
    retries: int
    remote_egress: bool

    def __post_init__(self) -> None:
        if self.arm not in ARMS:
            raise ValueError("unknown evaluation arm")
        if any(not value.strip() for value in (self.provider, self.model, self.revision, self.hardware, self.dtype, self.batching)):
            raise ValueError("arm identity fields must be explicit")
        if self.maximum_calls < 0 or self.maximum_tokens < 0 or self.retries < 0:
            raise ValueError("arm budgets cannot be negative")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("arm timeout must be finite and positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if min(self.calls, self.input_tokens, self.output_tokens) < 0:
            raise ValueError("usage counts cannot be negative")
        if not math.isfinite(self.cost_usd) or self.cost_usd < 0:
            raise ValueError("cost must be finite and non-negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ChoiceResult:
    case_id: str
    identity: ArmIdentity
    matching: MatchingReceipt
    selected: tuple[str, ...]
    scores: Mapping[str, float]
    abstained: bool
    review_required: bool
    escalated: bool
    latency_ms: float
    usage: Usage
    prompt_digest: str
    response_model: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.case_id != self.matching.case_id:
            raise ValueError("result case differs from matching receipt")
        if not math.isfinite(self.latency_ms) or self.latency_ms < 0:
            raise ValueError("latency must be finite and non-negative")
        if self.error_code is None and self.abstained == bool(self.selected):
            raise ValueError("successful result must select exactly when not abstaining")
        if any(not math.isfinite(float(value)) or not 0 <= float(value) <= 1 for value in self.scores.values()):
            raise ValueError("scores must be finite probabilities")
        if self.usage.calls > self.identity.maximum_calls:
            raise ValueError("result exceeded call budget")
        if self.usage.input_tokens + self.usage.output_tokens > self.identity.maximum_tokens:
            raise ValueError("result exceeded token budget")

    @property
    def successful(self) -> bool:
        return self.error_code is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "atmem-laya-evaluation-case-result-v1",
            "case_id": self.case_id,
            "identity": self.identity.to_dict(),
            "matching": self.matching.to_dict(),
            "selected": list(self.selected),
            "scores": dict(sorted(self.scores.items())),
            "abstained": self.abstained,
            "review_required": self.review_required,
            "escalated": self.escalated,
            "latency_ms": self.latency_ms,
            "usage": self.usage.to_dict(),
            "prompt_digest": self.prompt_digest,
            "response_model": self.response_model,
            "error_code": self.error_code,
        }
