"""Typed, evidence-bound contracts for governed memory extraction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, ClassVar, TypeAlias

from atmem.contracts import AuthorityScope, MemoryProposal
from atmem.core.canonical import canonical_json, sha256_hex


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")


class MemoryClass(str, Enum):
    DURABLE_FACT = "durable_fact"
    TEMPORARY_STATE = "temporary_state"
    EPISODE = "episode"
    PROCEDURE = "procedure"
    NON_MEMORY = "non_memory"


class ProposalAction(str, Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    SUPERSEDE = "SUPERSEDE"
    REJECT = "REJECT"
    NOOP = "NOOP"


class MemoryUnitKind(str, Enum):
    ATOMIC_FACT = "atomic_fact"
    DURABLE_RULE = "durable_rule"
    ENVIRONMENT_STATE = "environment_state"
    STATE_TRANSITION = "state_transition"
    PROCEDURE = "procedure"
    FAILURE_GOTCHA = "failure_gotcha"
    PREMISE_CONSTRAINT = "premise_constraint"


class Polarity(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class EvidenceStatus(str, Enum):
    OBSERVED = "observed"
    INFERRED = "inferred"


@dataclass(frozen=True, slots=True)
class AtomicFactPayload:
    subject: str
    relation: str
    value: str
    polarity: Polarity = Polarity.POSITIVE

    def __post_init__(self) -> None:
        _require_text_fields(self, "subject", "relation", "value")
        _require_enum("polarity", self.polarity, Polarity)


@dataclass(frozen=True, slots=True)
class DurableRulePayload:
    condition: str
    required_action: str | None = None
    prohibited_action: str | None = None
    exceptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text_fields(self, "condition")
        if self.required_action is not None:
            _require_text_fields(self, "required_action")
        if self.prohibited_action is not None:
            _require_text_fields(self, "prohibited_action")
        if not self.required_action and not self.prohibited_action:
            raise ValueError("durable rule requires a required or prohibited action")
        _require_text_sequence("exceptions", self.exceptions)


@dataclass(frozen=True, slots=True)
class EnvironmentStatePayload:
    entity: str
    relation: str
    value: str
    polarity: Polarity = Polarity.POSITIVE

    def __post_init__(self) -> None:
        _require_text_fields(self, "entity", "relation", "value")
        _require_enum("polarity", self.polarity, Polarity)


@dataclass(frozen=True, slots=True)
class StateTransitionPayload:
    entity: str
    relation: str
    before: str
    action: str
    after: str
    transition_basis: EvidenceStatus = EvidenceStatus.OBSERVED

    def __post_init__(self) -> None:
        _require_text_fields(self, "entity", "relation", "before", "action", "after")
        _require_enum("transition_basis", self.transition_basis, EvidenceStatus)


@dataclass(frozen=True, slots=True)
class ProcedureStep:
    ordinal: int
    instruction: str
    condition: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool) or self.ordinal < 1:
            raise ValueError("procedure steps require a positive ordinal and instruction")
        _require_text_fields(self, "instruction")
        if self.condition is not None:
            _require_text_fields(self, "condition")


@dataclass(frozen=True, slots=True)
class ProcedurePayload:
    goal: str
    steps: tuple[ProcedureStep, ...]
    prerequisites: tuple[str, ...] = ()
    completion_evidence: tuple[str, ...] = ()
    failure_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.goal.strip() or not self.steps:
            raise ValueError("procedure requires a goal and at least one step")
        if tuple(step.ordinal for step in self.steps) != tuple(range(1, len(self.steps) + 1)):
            raise ValueError("procedure step ordinals must be consecutive and ordered")
        if len(self.steps) > 64:
            raise ValueError("procedure cannot exceed 64 steps")
        _require_text_sequence("prerequisites", self.prerequisites)
        _require_text_sequence("completion_evidence", self.completion_evidence)
        _require_text_sequence("failure_conditions", self.failure_conditions)


@dataclass(frozen=True, slots=True)
class FailureGotchaPayload:
    trigger: str
    failure: str
    required_action: str | None = None
    prohibited_action: str | None = None

    def __post_init__(self) -> None:
        if not self.trigger.strip() or not self.failure.strip():
            raise ValueError("failure gotcha requires trigger and failure")
        _require_text_fields(self, "trigger", "failure")
        if self.required_action is not None:
            _require_text_fields(self, "required_action")
        if self.prohibited_action is not None:
            _require_text_fields(self, "prohibited_action")


@dataclass(frozen=True, slots=True)
class PremiseConstraintPayload:
    proposition: str
    polarity: Polarity
    applies_when: str | None = None
    excluded_when: str | None = None

    def __post_init__(self) -> None:
        _require_text_fields(self, "proposition")
        _require_enum("polarity", self.polarity, Polarity)
        if self.applies_when is not None:
            _require_text_fields(self, "applies_when")
        if self.excluded_when is not None:
            _require_text_fields(self, "excluded_when")


MemoryUnitPayload: TypeAlias = (
    AtomicFactPayload
    | DurableRulePayload
    | EnvironmentStatePayload
    | StateTransitionPayload
    | ProcedurePayload
    | FailureGotchaPayload
    | PremiseConstraintPayload
)


@dataclass(frozen=True, slots=True)
class ProposalEvidence:
    source_id: str
    source_sha256: str
    start_offset: int
    end_offset: int
    excerpt_sha256: str

    def __post_init__(self) -> None:
        _require_id("source_id", self.source_id)
        _require_digest("source_sha256", self.source_sha256)
        _require_digest("excerpt_sha256", self.excerpt_sha256)
        if (
            not isinstance(self.start_offset, int)
            or isinstance(self.start_offset, bool)
            or not isinstance(self.end_offset, int)
            or isinstance(self.end_offset, bool)
            or self.start_offset < 0
            or self.end_offset <= self.start_offset
        ):
            raise ValueError("evidence offsets must identify a non-empty source span")


@dataclass(frozen=True, slots=True)
class MemoryUnit:
    """A source-linked typed derivative; source evidence remains authoritative."""

    format: ClassVar[str] = "atmem-memory-unit-v2"
    unit_id: str
    formation_id: str
    kind: MemoryUnitKind
    scope: AuthorityScope
    payload: MemoryUnitPayload
    evidence: tuple[ProposalEvidence, ...]
    confidence: float
    evidence_status: EvidenceStatus = EvidenceStatus.OBSERVED
    formation_version: str = "typed-formation-v1"
    observed_at: str | None = None
    event_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    lifecycle: str = "proposed"

    def __post_init__(self) -> None:
        _require_id("unit_id", self.unit_id)
        _require_id("formation_id", self.formation_id)
        if not self.evidence:
            raise ValueError("typed memory requires exact source evidence")
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("typed memory evidence must be unique")
        if (
            not isinstance(self.confidence, (int, float))
            or isinstance(self.confidence, bool)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError("confidence must be between 0 and 1")
        if not isinstance(self.kind, MemoryUnitKind):
            raise ValueError("kind must be a MemoryUnitKind")
        if not isinstance(self.evidence_status, EvidenceStatus):
            raise ValueError("evidence_status must be observed or inferred")
        if not self.formation_version.strip():
            raise ValueError("formation_version is required")
        if self.lifecycle not in {"proposed", "active", "quarantined", "superseded", "revoked", "deleted"}:
            raise ValueError("typed memory lifecycle is invalid")
        expected = {
            MemoryUnitKind.ATOMIC_FACT: AtomicFactPayload,
            MemoryUnitKind.DURABLE_RULE: DurableRulePayload,
            MemoryUnitKind.ENVIRONMENT_STATE: EnvironmentStatePayload,
            MemoryUnitKind.STATE_TRANSITION: StateTransitionPayload,
            MemoryUnitKind.PROCEDURE: ProcedurePayload,
            MemoryUnitKind.FAILURE_GOTCHA: FailureGotchaPayload,
            MemoryUnitKind.PREMISE_CONSTRAINT: PremiseConstraintPayload,
        }[self.kind]
        if not isinstance(self.payload, expected):
            raise ValueError(f"{self.kind.value} requires {expected.__name__}")
        if (
            isinstance(self.payload, StateTransitionPayload)
            and self.payload.transition_basis is not self.evidence_status
        ):
            raise ValueError("state transition basis must match unit evidence_status")
        for name in ("observed_at", "event_at", "valid_from", "valid_until"):
            if getattr(self, name) is not None:
                _parse_time(name, getattr(self, name))
        if self.valid_from and self.valid_until and _parse_time(
            "valid_until", self.valid_until
        ) < _parse_time("valid_from", self.valid_from):
            raise ValueError("valid_until cannot precede valid_from")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["kind"] = self.kind.value
        value["evidence_status"] = self.evidence_status.value
        value["payload"] = _enum_values(value["payload"])
        value["evidence"] = [asdict(item) for item in self.evidence]
        return value

    def semantic_identity(self) -> str:
        value = self.to_dict()
        occurrence = None
        if self.kind in {
            MemoryUnitKind.ENVIRONMENT_STATE,
            MemoryUnitKind.STATE_TRANSITION,
        }:
            occurrence = [
                {
                    "source_id": row.source_id,
                    "source_sha256": row.source_sha256,
                    "start_offset": row.start_offset,
                    "end_offset": row.end_offset,
                }
                for row in self.evidence
            ]
        for key in (
            "unit_id", "formation_id", "confidence", "lifecycle",
            "formation_version", "evidence",
        ):
            value.pop(key, None)
        if occurrence is not None:
            value["occurrence"] = occurrence
        for key in ("observed_at", "event_at", "valid_from", "valid_until"):
            if value.get(key):
                value[key] = _parse_time(key, value[key]).astimezone(timezone.utc).isoformat()
        return f"sha256:{sha256_hex(canonical_json(value))}"

    def exclusion_identity(self) -> str:
        """Stable claim occurrence identity used to preserve user exclusions."""
        value = self.to_dict()
        for key in (
            "unit_id", "formation_id", "confidence", "lifecycle",
            "formation_version", "evidence",
        ):
            value.pop(key, None)
        for key in ("observed_at", "event_at", "valid_from", "valid_until"):
            if value.get(key):
                value[key] = _parse_time(key, value[key]).astimezone(
                    timezone.utc
                ).isoformat()
        return f"sha256:{sha256_hex(canonical_json(value))}"

    def canonical_text(self) -> str:
        """Deterministic human-readable projection; payload remains canonical."""
        value = self.payload
        if isinstance(value, AtomicFactPayload):
            return f"{value.subject} {value.relation}: {value.value} ({value.polarity.value})"
        if isinstance(value, EnvironmentStatePayload):
            return f"{value.entity} {value.relation}: {value.value} ({value.polarity.value})"
        if isinstance(value, StateTransitionPayload):
            return f"{value.entity} {value.relation}: {value.before} --{value.action}--> {value.after}"
        if isinstance(value, DurableRulePayload):
            actions: list[str] = []
            if value.required_action:
                actions.append(f"required: {value.required_action}")
            if value.prohibited_action:
                actions.append(f"prohibited: {value.prohibited_action}")
            exceptions = (
                f"; exceptions: {', '.join(value.exceptions)}" if value.exceptions else ""
            )
            return f"When {value.condition}; {'; '.join(actions)}{exceptions}"
        if isinstance(value, ProcedurePayload):
            steps = "; ".join(
                f"{step.ordinal}. {step.instruction}"
                + (f" when {step.condition}" if step.condition else "")
                for step in value.steps
            )
            prerequisites = (
                f" Prerequisites: {', '.join(value.prerequisites)}."
                if value.prerequisites else ""
            )
            completion = (
                f" Completion evidence: {', '.join(value.completion_evidence)}."
                if value.completion_evidence else ""
            )
            failures = (
                f" Failure conditions: {', '.join(value.failure_conditions)}."
                if value.failure_conditions else ""
            )
            return f"Procedure: {value.goal}.{prerequisites} {steps}.{completion}{failures}".strip()
        if isinstance(value, FailureGotchaPayload):
            actions: list[str] = []
            if value.required_action:
                actions.append(f"required action: {value.required_action}")
            if value.prohibited_action:
                actions.append(f"prohibited action: {value.prohibited_action}")
            return f"When {value.trigger}, risk: {value.failure}; {'; '.join(actions)}"
        if isinstance(value, PremiseConstraintPayload):
            conditions = ""
            if value.applies_when:
                conditions += f"; applies when: {value.applies_when}"
            if value.excluded_when:
                conditions += f"; excluded when: {value.excluded_when}"
            return f"Premise ({value.polarity.value}): {value.proposition}{conditions}"
        raise TypeError("unsupported typed memory payload")

    def grounding_claims(self) -> tuple[str, ...]:
        """Payload phrases that must occur verbatim in retained source evidence."""
        value = self.payload
        if isinstance(value, (AtomicFactPayload, EnvironmentStatePayload)):
            return (value.value,)
        if isinstance(value, StateTransitionPayload):
            return (value.before, value.action, value.after)
        if isinstance(value, DurableRulePayload):
            return tuple(
                item for item in (
                    value.condition, value.required_action, value.prohibited_action,
                    *value.exceptions,
                ) if item
            )
        if isinstance(value, ProcedurePayload):
            return (
                value.goal,
                *(step.instruction for step in value.steps),
                *value.prerequisites,
                *value.completion_evidence,
                *value.failure_conditions,
            )
        if isinstance(value, FailureGotchaPayload):
            return tuple(
                item for item in (
                    value.trigger, value.failure, value.required_action,
                    value.prohibited_action,
                ) if item
            )
        if isinstance(value, PremiseConstraintPayload):
            return tuple(
                item for item in (
                    value.proposition, value.applies_when, value.excluded_when,
                ) if item
            )
        raise TypeError("unsupported typed memory payload")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryUnit":
        data = dict(payload)
        if data.get("format", cls.format) != cls.format:
            raise ValueError("memory unit format is unsupported")
        allowed = {
            "format", "unit_id", "formation_id", "kind", "scope", "payload",
            "evidence", "confidence", "evidence_status", "formation_version",
            "observed_at", "event_at", "valid_from", "valid_until", "lifecycle",
        }
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"memory unit contains unknown fields: {', '.join(sorted(unknown))}")
        kind = MemoryUnitKind(data["kind"])
        raw = dict(data["payload"])
        payload_types: dict[MemoryUnitKind, type[Any]] = {
            MemoryUnitKind.ATOMIC_FACT: AtomicFactPayload,
            MemoryUnitKind.DURABLE_RULE: DurableRulePayload,
            MemoryUnitKind.ENVIRONMENT_STATE: EnvironmentStatePayload,
            MemoryUnitKind.STATE_TRANSITION: StateTransitionPayload,
            MemoryUnitKind.PROCEDURE: ProcedurePayload,
            MemoryUnitKind.FAILURE_GOTCHA: FailureGotchaPayload,
            MemoryUnitKind.PREMISE_CONSTRAINT: PremiseConstraintPayload,
        }
        if "polarity" in raw:
            raw["polarity"] = Polarity(raw["polarity"])
        if kind is MemoryUnitKind.STATE_TRANSITION:
            raw["transition_basis"] = EvidenceStatus(raw.get("transition_basis", "observed"))
        if kind is MemoryUnitKind.PROCEDURE:
            raw["steps"] = tuple(ProcedureStep(**item) for item in raw.get("steps") or ())
            for name in ("prerequisites", "completion_evidence", "failure_conditions"):
                raw[name] = tuple(raw.get(name) or ())
        if kind is MemoryUnitKind.DURABLE_RULE:
            raw["exceptions"] = tuple(raw.get("exceptions") or ())
        scope = data["scope"]
        return cls(
            unit_id=data["unit_id"],
            formation_id=data["formation_id"],
            kind=kind,
            scope=AuthorityScope(**scope),
            payload=payload_types[kind](**raw),
            evidence=tuple(ProposalEvidence(**item) for item in data["evidence"]),
            confidence=data["confidence"],
            evidence_status=EvidenceStatus(data.get("evidence_status", "observed")),
            formation_version=data.get("formation_version", "typed-formation-v1"),
            observed_at=data.get("observed_at"),
            event_at=data.get("event_at"),
            valid_from=data.get("valid_from"),
            valid_until=data.get("valid_until"),
            lifecycle=data.get("lifecycle", "proposed"),
        )


@dataclass(frozen=True, slots=True)
class ProposalPrecondition:
    record_id: str
    generation: int
    status: str
    content_sha256: str

    def __post_init__(self) -> None:
        if not self.record_id or not self.status:
            raise ValueError("precondition record_id and status are required")
        if self.generation < 0:
            raise ValueError("precondition generation cannot be negative")
        _require_digest("content_sha256", self.content_sha256)


@dataclass(frozen=True, slots=True)
class ExtractionProposal:
    """A single explicit extraction outcome; it never commits by itself."""

    format: ClassVar[str] = "atmem-memory-proposal-v2"
    proposal_id: str
    idempotency_key: str
    scope: AuthorityScope
    action: ProposalAction
    memory_class: MemoryClass
    confidence: float
    reason_codes: tuple[str, ...]
    evidence: tuple[ProposalEvidence, ...]
    fact: str | None = None
    fact_key: str | None = None
    affected_record_ids: tuple[str, ...] = ()
    preconditions: tuple[ProposalPrecondition, ...] = ()
    review_required: bool = False
    unit: MemoryUnit | None = None

    def __post_init__(self) -> None:
        if not self.proposal_id or not self.idempotency_key:
            raise ValueError("proposal_id and idempotency_key are required")
        if (
            not isinstance(self.confidence, (int, float))
            or isinstance(self.confidence, bool)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError("confidence must be between 0 and 1")
        if not self.reason_codes:
            raise ValueError("at least one bounded reason code is required")
        if not self.evidence:
            raise ValueError("at least one exact source evidence span is required")
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("proposal evidence must be unique")
        mutations = {ProposalAction.ADD, ProposalAction.UPDATE, ProposalAction.SUPERSEDE}
        if self.action in mutations and not self.fact:
            raise ValueError("mutating proposals require a screened fact")
        if self.fact is not None and len(self.fact) > 2_000:
            raise ValueError("proposal fact must contain at most 2,000 characters")
        if self.unit is not None and self.unit.scope != self.scope:
            raise ValueError("typed unit scope must equal proposal scope")
        if self.unit is not None and not set(self.unit.evidence) <= set(self.evidence):
            raise ValueError("typed unit evidence must be included in proposal evidence")
        if self.unit is not None and self.unit.lifecycle != "proposed":
            raise ValueError("proposal units must have proposed lifecycle")
        if self.action in {ProposalAction.UPDATE, ProposalAction.SUPERSEDE}:
            if not self.affected_record_ids or not self.preconditions:
                raise ValueError("updates require affected records and lifecycle preconditions")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["action"] = self.action.value
        value["memory_class"] = self.memory_class.value
        if self.unit is not None:
            value["unit"] = self.unit.to_dict()
        else:
            value.pop("unit", None)
        return value

    def digest(self) -> str:
        return f"sha256:{sha256_hex(canonical_json(self.to_dict()))}"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExtractionProposal":
        data = dict(payload)
        if data.get("format", cls.format) != cls.format:
            raise ValueError("memory proposal format is unsupported")
        return cls(
            proposal_id=data["proposal_id"],
            idempotency_key=data["idempotency_key"],
            scope=AuthorityScope(**data["scope"]),
            action=ProposalAction(data["action"]),
            memory_class=MemoryClass(data["memory_class"]),
            confidence=data["confidence"],
            reason_codes=tuple(data.get("reason_codes") or ()),
            evidence=tuple(ProposalEvidence(**item) for item in data.get("evidence") or ()),
            fact=data.get("fact"),
            fact_key=data.get("fact_key"),
            affected_record_ids=tuple(data.get("affected_record_ids") or ()),
            preconditions=tuple(ProposalPrecondition(**item) for item in data.get("preconditions") or ()),
            review_required=bool(data.get("review_required")),
            unit=MemoryUnit.from_dict(data["unit"]) if data.get("unit") is not None else None,
        )


def from_legacy_proposal(
    proposal: MemoryProposal,
    *,
    evidence: tuple[ProposalEvidence, ...],
) -> ExtractionProposal:
    """Normalize a v1 proposal without silently strengthening its assurance."""

    actions = {
        "add": ProposalAction.ADD,
        "supports": ProposalAction.NOOP,
        "duplicate": ProposalAction.NOOP,
        "extends": ProposalAction.UPDATE,
        "contradicts": ProposalAction.SUPERSEDE,
        "supersedes": ProposalAction.SUPERSEDE,
        "uncertain": ProposalAction.REJECT,
    }
    action = actions[proposal.suggested_action]
    requires_target = action in {ProposalAction.UPDATE, ProposalAction.SUPERSEDE}
    if requires_target:
        # v1 carried no generation-bound preconditions, so it cannot safely
        # be promoted into a mutation without a later validation stage.
        action = ProposalAction.REJECT
    return ExtractionProposal(
        proposal_id=proposal.proposal_id,
        idempotency_key=proposal.idempotency_key,
        scope=proposal.scope,
        action=action,
        memory_class=MemoryClass.DURABLE_FACT,
        confidence=proposal.confidence,
        reason_codes=(f"legacy_{proposal.suggested_action}",),
        evidence=evidence,
        fact=proposal.fact,
        fact_key=proposal.fact_key,
        affected_record_ids=(),
        review_required=(proposal.suggested_action == "uncertain" or requires_target),
    )


def _require_digest(name: str, value: str) -> None:
    if not _DIGEST.fullmatch(str(value)):
        raise ValueError(f"{name} must use sha256:<64 lowercase hex>")


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name} must be a bounded protocol identifier")


def _enum_values(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _enum_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_enum_values(item) for item in value]
    return value


def _require_text_fields(value: Any, *names: str) -> None:
    if any(
        not isinstance(getattr(value, name), str)
        or not getattr(value, name).strip()
        or len(getattr(value, name)) > 2_000
        for name in names
    ):
        raise ValueError(f"{type(value).__name__} requires non-empty {', '.join(names)}")


def _require_text_sequence(name: str, values: tuple[str, ...]) -> None:
    if (
        not isinstance(values, tuple)
        or len(values) > 64
        or any(not isinstance(value, str) or not value.strip() or len(value) > 2_000 for value in values)
    ):
        raise ValueError(f"{name} must contain at most 64 bounded non-empty values")


def _require_enum(name: str, value: Any, expected: type[Enum]) -> None:
    if not isinstance(value, expected):
        raise ValueError(f"{name} must be a {expected.__name__}")


def _parse_time(name: str, value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset")
    return parsed
