"""Dependency-free typed contracts shared by Python, JSON, CLI, and MCP."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
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


def _timestamp(name: str, value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset")
    return parsed


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
    retrieval_strategy: Literal['legacy', 'core-rrf-v1'] = 'legacy'

    def to_dict(self) -> dict[str, Any]:
        value = Contract.to_dict(self)
        if self.retrieval_strategy == 'legacy':
            value.pop('retrieval_strategy')
        return value

    def __post_init__(self) -> None:
        _required_id("request_id", self.request_id)
        if self.retrieval_strategy not in {'legacy', 'core-rrf-v1'}:
            raise ValueError('unknown retrieval strategy')
        if self.retrieval_strategy == 'core-rrf-v1' and not 1 <= int(self.candidate_limit) <= 2000:
            raise ValueError('candidate_limit must be between 1 and 2000')
        if self.retrieval_strategy == 'core-rrf-v1' and not {'lexical', 'semantic', 'graph'}.intersection(self.signals):
            raise ValueError('core-rrf-v1 requires lexical, semantic or graph signals')
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


InformationNeedType = Literal[
    "exact_fact",
    "current_state",
    "state_change",
    "ordered_task",
    "exception_risk",
    "rule_application",
    "assumption_check",
    "relational_synthesis",
]

SufficiencyStatus = Literal[
    "sufficient", "partial", "contradictory", "stale", "unsupported"
]

_INFORMATION_NEEDS = frozenset(
    {"exact_fact", "current_state", "state_change", "ordered_task", "exception_risk", "rule_application", "assumption_check", "relational_synthesis"}
)
_SUFFICIENCY_STATUSES = frozenset(
    {"sufficient", "partial", "contradictory", "stale", "unsupported"}
)
_EPISODE_PART_KINDS = frozenset({"text", "state", "action", "tool", "media_reference"})
_SOURCE_TYPES = frozenset({"user_message", "agent_message", "tool_output", "website", "document"})
_POLARITIES = frozenset({"positive", "negative", "unknown"})
_VALIDITIES = frozenset({"current", "historical", "uncertain"})


@dataclass(frozen=True, slots=True)
class EpisodePart(Contract):
    format: ClassVar[str] = "atmem-episode-part-v1"
    part_id: str
    ordinal: int
    kind: Literal["text", "state", "action", "tool", "media_reference"]
    source_type: str
    content: str | None = None
    reference_id: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    observed_at: str | None = None
    content_sha256: str | None = None
    reference_sha256: str | None = None

    def __post_init__(self) -> None:
        _required_id("part_id", self.part_id)
        if self.ordinal < 0:
            raise ValueError("episode part ordinal cannot be negative")
        if self.kind not in _EPISODE_PART_KINDS:
            raise ValueError("episode part kind is invalid")
        if self.source_type not in _SOURCE_TYPES:
            raise ValueError("episode part source_type is invalid")
        if (self.content is None) == (self.reference_id is None):
            raise ValueError("episode part requires exactly one content or reference_id")
        if self.kind == "media_reference" and self.reference_id is None:
            raise ValueError("media_reference parts require a protected reference")
        if self.kind != "media_reference" and self.content is None:
            raise ValueError("non-media episode parts require inline content")
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("episode offsets must be provided together")
        if self.start_offset is not None and (
            self.start_offset < 0 or self.end_offset is None or self.end_offset <= self.start_offset
        ):
            raise ValueError("episode offsets must identify a non-empty span")
        if self.content is not None:
            if not self.content:
                raise ValueError("episode content cannot be empty")
            _digest("content_sha256", str(self.content_sha256 or ""))
            if self.content_sha256 != f"sha256:{sha256_hex(self.content)}":
                raise ValueError("content_sha256 does not match episode content")
            if self.end_offset is not None and self.end_offset > len(self.content):
                raise ValueError("episode offsets exceed content length")
            if self.reference_sha256 is not None:
                raise ValueError("content parts cannot carry reference_sha256")
        else:
            _digest("reference_sha256", str(self.reference_sha256 or ""))
            if self.content_sha256 is not None:
                raise ValueError("reference parts cannot carry content_sha256")
        if self.observed_at is not None:
            _timestamp("observed_at", self.observed_at)


@dataclass(frozen=True, slots=True)
class EpisodeIngestRequest(Contract):
    """Lossless host-neutral envelope captured through EvidenceService.capture."""

    format: ClassVar[str] = "atmem-episode-ingest-v1"
    episode_id: str
    idempotency_key: str
    scope: AuthorityScope
    parts: tuple[EpisodePart, ...]
    source_capture_format: str = "atmem-source-capture-request-v1"
    binding_method: Literal[
        "host_asserted", "caller_asserted"
    ] = "caller_asserted"
    binding_assurance: Literal[
        "host_asserted", "caller_asserted"
    ] = "caller_asserted"
    session_id: str | None = None
    turn_id: str | None = None
    host_message_id: str | None = None
    retain_body: bool = True

    def __post_init__(self) -> None:
        _required_id("episode_id", self.episode_id)
        if not self.idempotency_key.strip() or not self.parts:
            raise ValueError("episode requires idempotency_key and ordered parts")
        if not isinstance(self.scope, AuthorityScope):
            raise ValueError("episode scope must be AuthorityScope")
        ordinals = tuple(part.ordinal for part in self.parts)
        if ordinals != tuple(range(len(self.parts))):
            raise ValueError("episode part ordinals must be consecutive from zero")
        if len({part.part_id for part in self.parts}) != len(self.parts):
            raise ValueError("episode part IDs must be unique")
        if self.source_capture_format != SourceCaptureRequest.format:
            raise ValueError("episode ingest must extend source capture v1")
        # Authentication is derived by the application service from its
        # principal/session. A caller may report an assertion, never mint an
        # authenticated or AtMem-verified assurance for itself.
        allowed_assurance = {
            "caller_asserted": {"caller_asserted"},
            "host_asserted": {"host_asserted", "caller_asserted"},
        }
        if self.binding_method not in allowed_assurance or self.binding_assurance not in allowed_assurance[self.binding_method]:
            raise ValueError("binding assurance is stronger than the episode binding method")

    def to_dict(self) -> dict[str, Any]:
        value = Contract.to_dict(self)
        value["parts"] = [part.to_dict() for part in self.parts]
        return value


@dataclass(frozen=True, slots=True)
class FormationReceipt(Contract):
    format: ClassVar[str] = "atmem-formation-receipt-v1"
    formation_id: str
    episode_id: str
    source_ids: tuple[str, ...]
    source_events_observed: int
    proposals_by_kind: dict[str, int]
    admitted: int
    withheld: int
    rejected: int
    unsupported_parts: tuple[str, ...] = ()
    unrepresented_ranges: tuple[dict[str, Any], ...] = ()
    media_references: tuple[dict[str, Any], ...] = ()
    complete: bool = False
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required_id("formation_id", self.formation_id)
        _required_id("episode_id", self.episode_id)
        counts = (self.source_events_observed, self.admitted, self.withheld, self.rejected)
        if any(value < 0 for value in counts):
            raise ValueError("formation counts cannot be negative")
        if any(kind not in {"atomic_fact", "durable_rule", "environment_state", "state_transition", "procedure", "failure_gotcha", "premise_constraint"} for kind in self.proposals_by_kind):
            raise ValueError("formation receipt has an unknown memory kind")
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in self.proposals_by_kind.values()):
            raise ValueError("proposal counts must be non-negative integers")
        proposal_count = sum(self.proposals_by_kind.values())
        if proposal_count != self.admitted + self.withheld + self.rejected:
            raise ValueError("formation proposal outcomes do not reconcile")
        if self.complete and (self.unsupported_parts or self.unrepresented_ranges):
            raise ValueError("formation with visible loss cannot be complete")
        if self.complete and self.source_events_observed < 1:
            raise ValueError("complete formation requires an observed source event")


@dataclass(frozen=True, slots=True)
class InformationNeed(Contract):
    format: ClassVar[str] = "atmem-information-need-v1"
    need_id: str
    type: InformationNeedType
    entities: tuple[str, ...] = ()
    relation_or_action: str | None = None
    temporal_target: str | None = None
    polarity: Literal["positive", "negative", "unknown"] = "unknown"
    expected_form: str | None = None
    required_slots: tuple[str, ...] = ()
    parent_need_id: str | None = None

    def __post_init__(self) -> None:
        _required_id("need_id", self.need_id)
        if self.type not in _INFORMATION_NEEDS:
            raise ValueError("information need type is invalid")
        if self.polarity not in _POLARITIES:
            raise ValueError("information need polarity is invalid")
        if not self.required_slots:
            raise ValueError("information need requires at least one evidence slot")
        if len(set(self.required_slots)) != len(self.required_slots):
            raise ValueError("information need slots must be unique")


@dataclass(frozen=True, slots=True)
class RetrievalBudget(Contract):
    format: ClassVar[str] = "atmem-retrieval-budget-v1"
    source_bytes: int = 262_144
    proposals: int = 64
    optional_concurrency: int = 2
    wall_time_ms: int = 2_000
    subqueries: int = 4
    candidates_per_channel: int = 50
    total_candidates: int = 200
    graph_visits: int = 100
    neighbor_depth: int = 2
    context_bytes: int = 8_192
    optional_model_calls: int = 1
    optional_model_tokens: int = 4_096
    optional_cost_microusd: int = 0
    egress_bytes: int = 0
    peak_working_bytes: int = 536_870_912
    derived_storage_bytes: int = 67_108_864

    def __post_init__(self) -> None:
        values = asdict(self)
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values.values()):
            raise ValueError("retrieval budget values must be non-negative integers")
        positive = ("source_bytes", "proposals", "optional_concurrency", "wall_time_ms", "subqueries", "candidates_per_channel", "total_candidates", "graph_visits", "neighbor_depth", "context_bytes", "peak_working_bytes", "derived_storage_bytes")
        if any(values[name] < 1 for name in positive):
            raise ValueError("core retrieval budgets must be positive")
        if self.candidates_per_channel > self.total_candidates:
            raise ValueError("per-channel candidates cannot exceed total candidates")
        if any(value > 2**40 for value in values.values()):
            raise ValueError("retrieval budget exceeds the supported maximum")


@dataclass(frozen=True, slots=True)
class EvidencePath(Contract):
    format: ClassVar[str] = "atmem-evidence-path-v1"
    seed_record_id: str
    record_id: str
    edge_types: tuple[str, ...]
    depth: int
    reason_code: str

    def __post_init__(self) -> None:
        _required_id("seed_record_id", self.seed_record_id)
        _required_id("record_id", self.record_id)
        _required_id("reason_code", self.reason_code)
        if (
            not isinstance(self.depth, int)
            or isinstance(self.depth, bool)
            or self.depth < 0
            or self.depth != len(self.edge_types)
        ):
            raise ValueError("evidence path depth must equal edge count")
        if self.depth == 0 and self.record_id != self.seed_record_id:
            raise ValueError("zero-depth evidence paths must identify their seed")


@dataclass(frozen=True, slots=True)
class EvidenceNeighborhood(Contract):
    format: ClassVar[str] = "atmem-evidence-neighborhood-v1"
    neighborhood_id: str
    need_id: str
    seed_record_ids: tuple[str, ...]
    paths: tuple[EvidencePath, ...]
    selected_record_ids: tuple[str, ...]
    visited_count: int
    max_depth: int
    truncated: bool
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required_id("neighborhood_id", self.neighborhood_id)
        _required_id("need_id", self.need_id)
        if not self.seed_record_ids or len(set(self.seed_record_ids)) != len(self.seed_record_ids):
            raise ValueError("evidence neighborhood requires unique seeds")
        if (
            not isinstance(self.visited_count, int)
            or isinstance(self.visited_count, bool)
            or not isinstance(self.max_depth, int)
            or isinstance(self.max_depth, bool)
            or self.visited_count < 0
            or self.max_depth < 0
            or not isinstance(self.truncated, bool)
        ):
            raise ValueError("evidence neighborhood counts and truncation are invalid")
        if len(set(self.selected_record_ids)) != len(self.selected_record_ids):
            raise ValueError("selected evidence records must be unique")
        if self.visited_count < len(set(self.selected_record_ids)) or self.visited_count < len(self.seed_record_ids):
            raise ValueError("visited_count cannot be smaller than selected records")
        seeds = set(self.seed_record_ids)
        selected = set(self.selected_record_ids)
        if not seeds <= selected:
            raise ValueError("evidence neighborhood seeds must be selected")
        reached = set()
        for path in self.paths:
            if path.seed_record_id not in seeds:
                raise ValueError("evidence path seed is outside the neighborhood")
            if path.record_id not in selected:
                raise ValueError("evidence path record must be selected")
            if path.depth > self.max_depth:
                raise ValueError("evidence path exceeds neighborhood max_depth")
            reached.add(path.record_id)
        if reached != selected:
            raise ValueError("every selected evidence record requires one evidence path")


@dataclass(frozen=True, slots=True)
class SufficiencyDecision(Contract):
    format: ClassVar[str] = "atmem-sufficiency-decision-v1"
    decision_id: str
    need_id: str
    status: SufficiencyStatus
    required_slots: tuple[str, ...]
    covered_slots: tuple[str, ...]
    missing_slots: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required_id("decision_id", self.decision_id)
        if self.status not in _SUFFICIENCY_STATUSES:
            raise ValueError("sufficiency status is invalid")
        required = set(self.required_slots)
        if not required or len(required) != len(self.required_slots):
            raise ValueError("required_slots must be non-empty and unique")
        if set(self.covered_slots) - required or set(self.missing_slots) - required:
            raise ValueError("covered and missing slots must belong to required_slots")
        if set(self.covered_slots) & set(self.missing_slots):
            raise ValueError("a sufficiency slot cannot be both covered and missing")
        if set(self.covered_slots) | set(self.missing_slots) != required:
            raise ValueError("covered and missing slots must partition required_slots")
        if self.status == "sufficient" and self.missing_slots:
            raise ValueError("sufficient decisions cannot have missing slots")
        if self.status == "sufficient" and not self.evidence_ids:
            raise ValueError("sufficient decisions require supporting evidence")
        if self.status == "sufficient" and self.contradiction_ids:
            raise ValueError("sufficient decisions cannot retain contradictions")
        if self.status == "partial" and not self.missing_slots:
            raise ValueError("partial decisions require missing slots")
        if self.status == "contradictory" and not self.contradiction_ids:
            raise ValueError("contradictory decisions require contradiction evidence")
        if self.status in {"contradictory", "stale"} and not self.evidence_ids:
            raise ValueError(f"{self.status} decisions require supporting evidence")
        if set(self.evidence_ids) & set(self.contradiction_ids):
            raise ValueError("supporting and contradiction evidence must be disjoint")
        if self.status == "unsupported" and self.evidence_ids:
            raise ValueError("unsupported decisions cannot claim supporting evidence")
        if self.status == "unsupported" and self.covered_slots:
            raise ValueError("unsupported decisions cannot claim covered slots")


@dataclass(frozen=True, slots=True)
class ActionConstraint(Contract):
    format: ClassVar[str] = "atmem-action-constraint-v1"
    subject: str
    applies_when: str
    source_ids: tuple[str, ...]
    validity: Literal["current", "historical", "uncertain"]
    required_action: str | None = None
    prohibited_action: str | None = None
    target: str | None = None
    parameters: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.required_action is not None and not self.required_action.strip():
            raise ValueError("required_action cannot be blank")
        if self.prohibited_action is not None and not self.prohibited_action.strip():
            raise ValueError("prohibited_action cannot be blank")
        if not self.required_action and not self.prohibited_action:
            raise ValueError("action constraint requires a required or prohibited action")
        if not self.source_ids:
            raise ValueError("action constraint requires source evidence")
        if self.validity not in _VALIDITIES:
            raise ValueError("action constraint validity is invalid")


@dataclass(frozen=True, slots=True)
class ContextPackageV2(Contract):
    format: ClassVar[str] = "atmem-context-package-v2"
    context_id: str
    scope: AuthorityScope
    record_ids: tuple[str, ...]
    context: str
    context_sha256: str
    serializer_version: str
    generation: int
    expires_at: str
    preparation_id: str
    profile_id: str
    need: InformationNeed
    sufficiency: SufficiencyDecision
    source_ids: tuple[str, ...]
    budget: RetrievalBudget
    selected_units: tuple[dict[str, Any], ...]
    provenance: tuple[dict[str, Any], ...]
    excluded_evidence_ids: tuple[str, ...]
    action_constraints: tuple[ActionConstraint, ...] = ()
    reason_codes: tuple[str, ...] = ()
    media_references: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _digest("context_sha256", self.context_sha256)
        expected = f"sha256:{sha256_hex(self.context)}"
        if self.context_sha256 != expected:
            raise ValueError("context_sha256 does not match context")
        if self.generation < 0:
            raise ValueError("context generation cannot be negative")
        _timestamp("expires_at", self.expires_at)
        if len(self.context.encode("utf-8")) > self.budget.context_bytes:
            raise ValueError("context exceeds the declared byte budget")
        if self.need.need_id != self.sufficiency.need_id:
            raise ValueError("context need and sufficiency decision differ")
        if set(self.need.required_slots) != set(self.sufficiency.required_slots):
            raise ValueError("context need and sufficiency slots differ")
        if not set(self.sufficiency.evidence_ids) <= set(self.record_ids):
            raise ValueError("supporting evidence must be selected in the context package")
        if set(self.excluded_evidence_ids) & set(self.record_ids):
            raise ValueError("evidence cannot be both selected and excluded")
        for row in self.provenance:
            if row.get("record_id") not in self.record_ids or row.get("source_id") not in self.source_ids:
                raise ValueError("context provenance must refer to selected records and sources")
        for constraint in self.action_constraints:
            if not set(constraint.source_ids) <= set(self.source_ids):
                raise ValueError("action constraint sources must belong to the package")
            if constraint.validity == "current" and self.sufficiency.status != "sufficient":
                raise ValueError("only sufficient context may claim a current action constraint")
        for reference in self.media_references:
            if not str(reference.get("reference_id") or "").strip():
                raise ValueError("context media reference requires reference_id")
            if reference.get("adjacent_source_id") not in self.source_ids:
                raise ValueError("context media reference must be adjacent to a selected source")
        if self.sufficiency.status == "unsupported" and (
            self.record_ids or self.context or self.action_constraints
        ):
            raise ValueError("unsupported context cannot deliver records, text or constraints")

    def to_dict(self) -> dict[str, Any]:
        value = Contract.to_dict(self)
        value["need"] = self.need.to_dict()
        value["sufficiency"] = self.sufficiency.to_dict()
        value["budget"] = self.budget.to_dict()
        value["action_constraints"] = [item.to_dict() for item in self.action_constraints]
        return value

    def to_v1(self) -> ContextPackage:
        """Deterministic non-strengthening projection for existing clients."""

        # V1 has no field capable of qualifying partial/conflicted/stale
        # support, so only sufficient V2 context can be represented safely.
        support = self.projected_support_class(background_allowed=False)
        context = self.context if support != "no_useful_memory" else ""
        record_ids = self.record_ids if support != "no_useful_memory" else ()
        return ContextPackage(
            context_id=self.context_id,
            scope=self.scope,
            record_ids=record_ids,
            context=context,
            context_sha256=f"sha256:{sha256_hex(context)}",
            serializer_version="atmem-context-utf8-v1",
            generation=self.generation,
            expires_at=self.expires_at,
            preparation_id=self.preparation_id,
        )

    def projected_support_class(self, *, background_allowed: bool = False) -> str:
        """Project five sufficiency states onto the existing three-class contract."""

        if self.sufficiency.status == "sufficient":
            return "direct_support"
        if self.sufficiency.status in {"partial", "contradictory", "stale"}:
            return "background_context" if background_allowed else "no_useful_memory"
        return "no_useful_memory"


@dataclass(frozen=True, slots=True)
class ContextRequestV2(Contract):
    format: ClassVar[str] = "atmem-context-request-v2"
    context_id: str
    candidate_set_id: str
    scope: AuthorityScope
    query: str
    budget: RetrievalBudget = field(default_factory=RetrievalBudget)

    def __post_init__(self) -> None:
        _required_id("context_id", self.context_id)
        _required_id("candidate_set_id", self.candidate_set_id)
        if not isinstance(self.scope, AuthorityScope):
            raise ValueError("context request scope must be AuthorityScope")
        if not self.query.strip():
            raise ValueError("context request query is required")
        if not isinstance(self.budget, RetrievalBudget):
            raise ValueError("context request budget must be RetrievalBudget")

    def to_dict(self) -> dict[str, Any]:
        value = Contract.to_dict(self)
        value["budget"] = self.budget.to_dict()
        return value


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
