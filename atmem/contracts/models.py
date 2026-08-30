"""Dependency-free typed contracts shared by Python, JSON, CLI, and MCP."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, ClassVar, Literal

from atmem.core.canonical import canonical_json, sha256_hex


_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def _required_id(name: str, value: str) -> str:
    text = str(value or "").strip()
    if not _ID.fullmatch(text):
        raise ValueError(f"{name} must be a non-empty protocol identifier")
    return text


def _digest(name: str, value: str) -> str:
    text = str(value or "").strip()
    if not _DIGEST.fullmatch(text):
        raise ValueError(f"{name} must use sha256:<64 lowercase hex>")
    return text


class Contract:
    format: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        return value

    def canonical_bytes(self) -> bytes:
        return canonical_json(self.to_dict()).encode("utf-8")

    def digest(self) -> str:
        return f"sha256:{sha256_hex(self.canonical_bytes())}"


@dataclass(frozen=True, slots=True)
class AuthorityScope(Contract):
    format: ClassVar[str] = "atmem-authority-scope-v1"
    subject_id: str
    agent_id: str
    workspace_id: str

    def __post_init__(self) -> None:
        _required_id("subject_id", self.subject_id)
        _required_id("agent_id", self.agent_id)
        _required_id("workspace_id", self.workspace_id)


@dataclass(frozen=True, slots=True)
class SourceBinding(Contract):
    format: ClassVar[str] = "atmem-source-binding-v1"
    method: Literal[
        "host_authenticated_turn",
        "operator_authenticated",
        "host_asserted",
        "caller_asserted",
    ]
    source_sha256: str
    assurance: Literal[
        "verified_by_atmem", "host_authenticated", "host_asserted", "caller_asserted"
    ] = "caller_asserted"

    def __post_init__(self) -> None:
        _digest("source_sha256", self.source_sha256)


@dataclass(frozen=True, slots=True)
class InterpreterIdentity(Contract):
    format: ClassVar[str] = "atmem-interpreter-v1"
    provider: str
    model: str
    prompt_version: str
    calibration_id: str = "uncalibrated"
    assurance: Literal["model_interpreted", "rule_extracted", "human_verified"] = (
        "model_interpreted"
    )
    egress_class: Literal["local", "remote", "none"] = "local"

    def __post_init__(self) -> None:
        _required_id("provider", self.provider)
        if not str(self.model).strip():
            raise ValueError("model is required")
        _required_id("prompt_version", self.prompt_version)


@dataclass(frozen=True, slots=True)
class SourceCaptureRequest(Contract):
    format: ClassVar[str] = "atmem-source-capture-request-v1"
    source_id: str
    idempotency_key: str
    scope: AuthorityScope
    message: str
    source_type: Literal[
        "user_message", "agent_message", "tool_output", "website", "document"
    ] = "user_message"
    session_id: str | None = None
    turn_id: str | None = None
    host_message_id: str | None = None
    binding_method: str = "host_authenticated_turn"
    binding_assurance: str = "host_authenticated"
    retain_body: bool = True

    def __post_init__(self) -> None:
        _required_id("source_id", self.source_id)
        if not str(self.idempotency_key).strip():
            raise ValueError("idempotency_key is required")
        if not str(self.message).strip():
            raise ValueError("message is required")

    @property
    def source_sha256(self) -> str:
        return f"sha256:{sha256_hex(self.message)}"


@dataclass(frozen=True, slots=True)
class SourceCaptureResult(Contract):
    format: ClassVar[str] = "atmem-source-capture-result-v1"
    source_id: str
    episode_id: str
    source_sha256: str
    replayed: bool
    retained: bool
    scope: AuthorityScope
    audit_event_id: str


Relationship = Literal[
    "add", "duplicate", "supports", "extends", "contradicts", "supersedes", "uncertain"
]


@dataclass(frozen=True, slots=True)
class MemoryProposal(Contract):
    format: ClassVar[str] = "atmem-memory-proposal-v1"
    proposal_id: str
    idempotency_key: str
    scope: AuthorityScope
    fact: str
    source_ids: tuple[str, ...]
    interpreter: InterpreterIdentity
    source_binding: SourceBinding
    fact_key: str | None = None
    confidence: float = 0.0
    entities: tuple[dict[str, str], ...] = ()
    suggested_action: Relationship = "add"
    related_record_ids: tuple[str, ...] = ()
    sensitivity: Literal[
        "public", "internal", "personal", "sensitive", "restricted"
    ] = "personal"
    session_id: str | None = None
    turn_id: str | None = None

    def __post_init__(self) -> None:
        _required_id("proposal_id", self.proposal_id)
        if not str(self.idempotency_key).strip():
            raise ValueError("idempotency_key is required")
        if not str(self.fact).strip() or len(self.fact) > 2_000:
            raise ValueError("fact must contain 1 to 2,000 characters")
        if not self.source_ids:
            raise ValueError("at least one source_id is required")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def semantic_payload(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("idempotency_key", None)
        return value

    def payload_digest(self) -> str:
        return f"sha256:{sha256_hex(canonical_json(self.semantic_payload()))}"


AdmissionDecision = Literal[
    "active", "quarantined", "duplicate", "conflict", "rejected", "invalid"
]


@dataclass(frozen=True, slots=True)
class MemoryAdmission(Contract):
    format: ClassVar[str] = "atmem-memory-admission-v1"
    proposal_id: str
    decision: AdmissionDecision
    reason_codes: tuple[str, ...]
    record_ids: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    related_record_ids: tuple[str, ...] = ()
    review_required: bool = False
    audit_event_id: str | None = None
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class RecallRequest(Contract):
    format: ClassVar[str] = "atmem-recall-request-v1"
    request_id: str
    scope: AuthorityScope
    query: str
    limit: int = 8
    candidate_limit: int = 200
    signals: tuple[str, ...] = ("lexical", "semantic", "graph", "trust", "recency")
    context_budget_chars: int = 1_800
    reranker_provider: str = "none"
    reranker_model: str = "none"
    egress_class: Literal["local", "remote", "none"] = "local"
    min_score: float = 0.0

    def __post_init__(self) -> None:
        _required_id("request_id", self.request_id)
        if not str(self.query).strip():
            raise ValueError("query is required")
        if not 1 <= int(self.limit) <= 100:
            raise ValueError("limit must be between 1 and 100")
        if not self.signals:
            raise ValueError("at least one recall signal is required")


@dataclass(frozen=True, slots=True)
class EligibleCandidate(Contract):
    format: ClassVar[str] = "atmem-eligible-candidate-v1"
    record_id: str
    content: str
    score: float
    rank: int
    source_type: str
    trust_tier: str
    created_at: str
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EligibleCandidateSet(Contract):
    format: ClassVar[str] = "atmem-eligible-candidate-set-v1"
    candidate_set_id: str
    request_id: str
    scope: AuthorityScope
    candidates: tuple[EligibleCandidate, ...]
    generation: int
    expires_at: str
    candidate_digest: str
    audit_event_id: str


@dataclass(frozen=True, slots=True)
class ContextRequest(Contract):
    format: ClassVar[str] = "atmem-context-request-v1"
    context_id: str
    candidate_set_id: str
    scope: AuthorityScope
    record_ids: tuple[str, ...]
    budget_chars: int = 1_800


@dataclass(frozen=True, slots=True)
class ContextPackage(Contract):
    format: ClassVar[str] = "atmem-context-package-v1"
    context_id: str
    scope: AuthorityScope
    record_ids: tuple[str, ...]
    context: str
    context_sha256: str
    serializer_version: str
    generation: int
    expires_at: str
    preparation_id: str


@dataclass(frozen=True, slots=True)
class ExposureConfirmation(Contract):
    format: ClassVar[str] = "atmem-exposure-confirmation-v1"
    confirmation_id: str
    preparation_id: str
    scope: AuthorityScope
    context_sha256: str
    host_run_id: str


@dataclass(frozen=True, slots=True)
class ExposureReceipt(Contract):
    format: ClassVar[str] = "atmem-exposure-receipt-v1"
    receipt_id: str
    preparation_id: str
    scope: AuthorityScope
    context_sha256: str
    exposed_at: str
    audit_event_id: str
    replayed: bool = False
