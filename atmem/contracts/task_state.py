"""Dependency-free contracts for Governed Task State.

These types are the boundary between what an agent, host, or model may *say*
and what AtMem will *accept*. They are deliberately closed: an unknown field is
an error rather than a silently ignored extension, because a proposal carrying
a field AtMem does not understand is a proposal AtMem cannot claim to have
validated.

Nothing here reaches a database or a model. Parsing, bounds, and canonical
serialization live here so that every later layer — persistence, policy,
context, adapters — agrees on exactly one shape and exactly one byte encoding.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import re
from typing import Any, ClassVar, Iterable, Mapping

from atmem.contracts.models import AuthorityScope, Contract
from atmem.core.canonical import canonical_json, sha256_hex


SERIALIZER_VERSION = "atmem-task-context-utf8-v1"

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_REASON = re.compile(r"^[a-z][a-z0-9_]{2,63}$")

MAX_GOAL_CHARS = 2_000
MAX_TEXT_CHARS = 2_000
MAX_ITEMS = 500
MAX_CONSTRAINTS = 100
MAX_OPERATIONS = 50


class TaskLifecycle(str, Enum):
    """Exactly five lifecycle values; the last three are terminal."""

    OPEN = "open"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

    @property
    def terminal(self) -> bool:
        return self in {
            TaskLifecycle.COMPLETED,
            TaskLifecycle.CANCELLED,
            TaskLifecycle.EXPIRED,
        }


class ItemStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"

    @property
    def settled(self) -> bool:
        """True when an item needs no further work to satisfy a completion gate."""
        return self in {ItemStatus.COMPLETED, ItemStatus.SKIPPED}


class StepOutcome(str, Enum):
    """The four outcomes every observed workflow step resolves to."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONFLICT = "conflict"
    NO_CHANGE = "no_change"


class Assurance(str, Enum):
    """How strongly an outcome is actually evidenced.

    Ordered weakest to strongest. `HOST_REPORTED` is the honest ceiling for a
    tool result the host says succeeded: useful, but not independent proof.
    """

    ASSERTED = "asserted"
    MODEL_INTERPRETED = "model_interpreted"
    RULE_EXTRACTED = "rule_extracted"
    HOST_REPORTED = "host_reported"
    OPERATOR_CONFIRMED = "operator_confirmed"
    INDEPENDENTLY_VERIFIED = "independently_verified"

    @property
    def rank(self) -> int:
        return _ASSURANCE_ORDER.index(self)


_ASSURANCE_ORDER = [
    Assurance.ASSERTED,
    Assurance.MODEL_INTERPRETED,
    Assurance.RULE_EXTRACTED,
    Assurance.HOST_REPORTED,
    Assurance.OPERATOR_CONFIRMED,
    Assurance.INDEPENDENTLY_VERIFIED,
]


class ActorRole(str, Enum):
    """A trusted capability, never merely an actor-supplied string."""

    ATMEM_AUTHORITY = "atmem_authority"
    POLICY_EVALUATOR = "policy_evaluator"
    ATBOT_INTELLIGENCE = "atbot_intelligence"
    HOST_AGENT = "host_agent"
    OPERATOR = "operator"
    ADMINISTRATOR = "administrator"
    VERIFIER = "verifier"
    AUDITOR = "auditor"
    DELEGATED_PROVIDER = "delegated_provider"


class GuardType(str, Enum):
    NO_PROGRESS = "no_progress"
    DEPENDENCY_UNSATISFIED = "dependency_unsatisfied"
    OUT_OF_SCOPE = "out_of_scope"
    COMPLETION_NOT_ALLOWED = "completion_not_allowed"


class ContextDisposition(str, Enum):
    INJECTED = "injected"
    WITHHELD = "withheld"


class OperationKind(str, Enum):
    """The bounded delta operations a proposal may request.

    Deliberately small. There is no "replace state" operation: a full
    replacement would let a proposer overwrite work it never saw.
    """

    SET_PHASE = "set_phase"
    SET_ITEM_STATUS = "set_item_status"
    ADD_ITEM = "add_item"
    SET_ITEM_CONTENT = "set_item_content"
    SET_ITEM_BLOCKER = "set_item_blocker"
    ADD_CONSTRAINT = "add_constraint"
    SATISFY_CONSTRAINT = "satisfy_constraint"
    MARK_SOURCE_INSPECTED = "mark_source_inspected"
    LOCK_SCHEMA = "lock_schema"


# Stable, human-readable reason codes. Every decision cites one of these, and
# the set is closed so operators and tests can rely on the vocabulary.
REASON_CODES: frozenset[str] = frozenset(
    {
        # accepted
        "transition_accepted",
        "operator_correction_accepted",
        "lifecycle_change_accepted",
        # no_change
        "state_already_matches",
        "duplicate_idempotency_key",
        # conflict
        "stale_base_revision",
        "concurrent_successor_committed",
        # rejected — authority and scope
        "scope_mismatch",
        "capability_denied",
        "task_not_eligible",
        "task_is_terminal",
        "task_is_paused",
        # rejected — structure
        "unknown_item",
        "unknown_constraint",
        "unknown_source",
        "duplicate_item_id",
        "schema_is_locked",
        "full_replacement_refused",
        "operation_not_permitted_by_profile",
        "too_many_operations",
        "empty_delta",
        # rejected — transitions
        "illegal_phase_transition",
        "illegal_status_transition",
        "dependency_unsatisfied",
        "required_items_incomplete",
        "constraint_unsatisfied",
        # rejected — evidence
        "unknown_evidence",
        "evidence_required",
        "assurance_ceiling_exceeded",
        "reason_required",
        # lifecycle and policy
        "expired_absolute_age",
        "expired_no_progress",
        "expiry_not_operator_initiated",
        # context
        "task_context_selection_required",
        "task_context_not_eligible",
        "task_context_budget_exceeded",
        # availability
        "task_state_disabled",
        "task_state_shadow_mode",
        "capability_unavailable",
        "integrity_check_failed",
    }
)


def _identifier(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not _ID.fullmatch(text):
        raise ValueError(f"{name} must be a non-empty protocol identifier")
    return text


def _text(name: str, value: Any, *, limit: int = MAX_TEXT_CHARS, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{name} is required")
    if len(text) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return text


def _reason_codes(value: Iterable[str]) -> tuple[str, ...]:
    codes = tuple(dict.fromkeys(str(item).strip() for item in value))
    if not codes:
        raise ValueError("at least one reason code is required")
    unknown = [code for code in codes if code not in REASON_CODES]
    if unknown:
        raise ValueError(f"unknown reason codes: {sorted(unknown)}")
    return codes


def _closed(name: str, payload: Mapping[str, Any], allowed: set[str]) -> dict[str, Any]:
    """Reject unknown keys instead of ignoring them."""
    extra = sorted(set(payload) - allowed - {"format"})
    if extra:
        raise ValueError(f"{name} has unknown fields: {extra}")
    return dict(payload)


@dataclass(frozen=True, slots=True)
class EvidenceRef(Contract):
    """A pointer to something AtMem already holds and can re-check."""

    format: ClassVar[str] = "atmem-task-evidence-ref-v1"
    kind: str
    reference_id: str
    sha256: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {
            "source",
            "record",
            "audit_event",
            "blackbox_event",
            "tool_call",
            "verifier_result",
            "operator_request",
            "policy_rule",
        }:
            raise ValueError(f"unsupported evidence kind: {self.kind!r}")
        _identifier("reference_id", self.reference_id)
        if self.sha256 is not None and not _DIGEST.fullmatch(str(self.sha256)):
            raise ValueError("evidence sha256 must use sha256:<64 lowercase hex>")


@dataclass(frozen=True, slots=True)
class Provenance(Contract):
    """Where one value came from, in terms a person can read."""

    format: ClassVar[str] = "atmem-task-provenance-v1"
    actor: str
    actor_role: ActorRole
    method: str
    assurance: Assurance
    observed_at: str
    introduced_in_revision: int
    evidence: tuple[EvidenceRef, ...] = ()
    interpreter: str | None = None
    superseded_revision: int | None = None

    def __post_init__(self) -> None:
        _text("actor", self.actor, limit=200)
        _text("method", self.method, limit=200)
        if int(self.introduced_in_revision) < 1:
            raise ValueError("introduced_in_revision starts at 1")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["actor_role"] = self.actor_role.value
        value["assurance"] = self.assurance.value
        return value


@dataclass(frozen=True, slots=True)
class ExpiryPolicy(Contract):
    """The immutable rule bound to a task when it starts.

    Absolute age runs from creation and continues while paused, so a task
    cannot be parked forever. No-progress age excludes paused intervals, so
    deliberately pausing work is not itself treated as failing to progress.
    """

    format: ClassVar[str] = "atmem-task-expiry-policy-v1"
    max_absolute_age_ms: int | None = None
    max_no_progress_age_ms: int | None = None

    def __post_init__(self) -> None:
        for name in ("max_absolute_age_ms", "max_no_progress_age_ms"):
            value = getattr(self, name)
            if value is not None and int(value) <= 0:
                raise ValueError(f"{name} must be a positive number of milliseconds")

    @property
    def enabled(self) -> bool:
        return (
            self.max_absolute_age_ms is not None
            or self.max_no_progress_age_ms is not None
        )


@dataclass(frozen=True, slots=True)
class TaskProfile(Contract):
    """Versioned rules: phases, transitions, gates, and guard thresholds."""

    format: ClassVar[str] = "atmem-task-profile-v1"
    profile_id: str
    version: str
    phases: tuple[str, ...]
    phase_transitions: tuple[tuple[str, str], ...]
    required_item_kinds: tuple[str, ...] = ()
    optional_context_fields: tuple[str, ...] = ()
    permitted_operations: tuple[OperationKind, ...] = tuple(OperationKind)
    no_progress_action_threshold: int = 3
    expiry: ExpiryPolicy = field(default_factory=ExpiryPolicy)
    allow_schema_extension_phases: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        _identifier("profile_id", self.profile_id)
        _identifier("version", self.version)
        if not self.phases:
            raise ValueError("a profile must declare at least one phase")
        if len(set(self.phases)) != len(self.phases):
            raise ValueError("profile phases must be unique")
        unknown = {
            phase
            for edge in self.phase_transitions
            for phase in edge
            if phase not in self.phases
        }
        if unknown:
            raise ValueError(f"phase transitions name unknown phases: {sorted(unknown)}")
        if int(self.no_progress_action_threshold) < 1:
            raise ValueError("no_progress_action_threshold must be at least 1")
        for phase in self.allow_schema_extension_phases:
            if phase not in self.phases:
                raise ValueError(f"unknown schema-extension phase: {phase!r}")

    @property
    def initial_phase(self) -> str:
        return self.phases[0]

    @property
    def terminal_phase(self) -> str:
        return self.phases[-1]

    def allows_phase_transition(self, source: str, target: str) -> bool:
        return (source, target) in set(self.phase_transitions)

    def allows_operation(self, kind: OperationKind) -> bool:
        return kind in set(self.permitted_operations)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["phase_transitions"] = [list(edge) for edge in self.phase_transitions]
        value["permitted_operations"] = [item.value for item in self.permitted_operations]
        return value

    def profile_digest(self) -> str:
        return f"sha256:{sha256_hex(canonical_json(self.to_dict()))}"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TaskProfile":
        data = _closed("task profile", payload, set(cls.__slots__))
        return cls(
            profile_id=str(data["profile_id"]),
            version=str(data["version"]),
            phases=tuple(str(item) for item in data["phases"]),
            phase_transitions=tuple(
                (str(edge[0]), str(edge[1])) for edge in data.get("phase_transitions") or ()
            ),
            required_item_kinds=tuple(
                str(item) for item in data.get("required_item_kinds") or ()
            ),
            optional_context_fields=tuple(
                str(item) for item in data.get("optional_context_fields") or ()
            ),
            permitted_operations=tuple(
                OperationKind(str(item))
                for item in data.get("permitted_operations") or [k.value for k in OperationKind]
            ),
            no_progress_action_threshold=int(data.get("no_progress_action_threshold", 3)),
            expiry=ExpiryPolicy(
                max_absolute_age_ms=(data.get("expiry") or {}).get("max_absolute_age_ms"),
                max_no_progress_age_ms=(data.get("expiry") or {}).get(
                    "max_no_progress_age_ms"
                ),
            ),
            allow_schema_extension_phases=tuple(
                str(item) for item in data.get("allow_schema_extension_phases") or ()
            ),
            description=str(data.get("description") or ""),
        )


@dataclass(frozen=True, slots=True)
class TaskStartRequest(Contract):
    """An explicit request to begin governing one task."""

    format: ClassVar[str] = "atmem-task-start-request-v1"
    task_id: str
    scope: AuthorityScope
    profile_id: str
    profile_version: str
    goal: str
    actor: str
    actor_role: ActorRole
    idempotency_key: str
    constraints: tuple[str, ...] = ()
    sources_to_inspect: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    continues_task_id: str | None = None

    def __post_init__(self) -> None:
        _identifier("task_id", self.task_id)
        _identifier("profile_id", self.profile_id)
        _text("goal", self.goal, limit=MAX_GOAL_CHARS)
        _text("actor", self.actor, limit=200)
        _text("idempotency_key", self.idempotency_key, limit=256)
        if len(self.constraints) > MAX_CONSTRAINTS:
            raise ValueError(f"a task may start with at most {MAX_CONSTRAINTS} constraints")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["actor_role"] = self.actor_role.value
        return value


@dataclass(frozen=True, slots=True)
class TaskItem(Contract):
    """One actionable unit with a stable identity and exactly one status."""

    format: ClassVar[str] = "atmem-task-item-v1"
    item_id: str
    kind: str
    title: str
    status: ItemStatus = ItemStatus.PENDING
    content: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    blocker_reason: str | None = None
    skip_reason: str | None = None
    assurance: Assurance = Assurance.ASSERTED
    evidence: tuple[EvidenceRef, ...] = ()
    required: bool = False

    def __post_init__(self) -> None:
        _identifier("item_id", self.item_id)
        _text("kind", self.kind, limit=100)
        _text("title", self.title, limit=MAX_TEXT_CHARS)
        if self.status is ItemStatus.BLOCKED and not self.blocker_reason:
            raise ValueError("a blocked item must record why it is blocked")
        if self.status is ItemStatus.SKIPPED and not self.skip_reason:
            raise ValueError("a skipped item must record why it was skipped")
        if self.item_id in set(self.depends_on):
            raise ValueError("an item cannot depend on itself")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["status"] = self.status.value
        value["assurance"] = self.assurance.value
        return value


@dataclass(frozen=True, slots=True)
class TaskConstraint(Contract):
    format: ClassVar[str] = "atmem-task-constraint-v1"
    constraint_id: str
    text: str
    satisfied: bool = False
    required_for_completion: bool = True

    def __post_init__(self) -> None:
        _identifier("constraint_id", self.constraint_id)
        _text("text", self.text)


@dataclass(frozen=True, slots=True)
class TaskState(Contract):
    """One immutable canonical snapshot of a task at a revision."""

    format: ClassVar[str] = "atmem-task-state-v1"
    task_id: str
    scope: AuthorityScope
    revision: int
    lifecycle: TaskLifecycle
    phase: str
    goal: str
    profile_id: str
    profile_version: str
    items: tuple[TaskItem, ...] = ()
    constraints: tuple[TaskConstraint, ...] = ()
    sources_to_inspect: tuple[str, ...] = ()
    completed_sources: tuple[str, ...] = ()
    schema_locked: bool = False
    created_at: str = ""
    updated_at: str = ""
    last_progress_at: str = ""
    parent_revision: int | None = None
    policy_generation: int = 1

    def __post_init__(self) -> None:
        _identifier("task_id", self.task_id)
        if int(self.revision) < 1:
            raise ValueError("revisions start at 1")
        if len(self.items) > MAX_ITEMS:
            raise ValueError(f"a task may hold at most {MAX_ITEMS} items")
        identities = [item.item_id for item in self.items]
        if len(set(identities)) != len(identities):
            raise ValueError("task item identities must be unique")
        known = set(identities)
        for item in self.items:
            unknown = set(item.depends_on) - known
            if unknown:
                raise ValueError(
                    f"item {item.item_id} depends on unknown items: {sorted(unknown)}"
                )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["lifecycle"] = self.lifecycle.value
        value["items"] = [item.to_dict() for item in self.items]
        return value

    def item(self, item_id: str) -> TaskItem | None:
        return next((item for item in self.items if item.item_id == item_id), None)

    def constraint(self, constraint_id: str) -> TaskConstraint | None:
        return next(
            (row for row in self.constraints if row.constraint_id == constraint_id),
            None,
        )

    def semantic_digest(self) -> str:
        """Digest of meaning, excluding timestamps and revision bookkeeping.

        Two snapshots with the same semantic digest represent the same task
        state, which is what makes an honest `no_change` outcome possible.
        """
        value = self.to_dict()
        for volatile in (
            "revision",
            "parent_revision",
            "created_at",
            "updated_at",
            "last_progress_at",
        ):
            value.pop(volatile, None)
        return f"sha256:{sha256_hex(canonical_json(value))}"

    def state_digest(self) -> str:
        return f"sha256:{sha256_hex(canonical_json(self.to_dict()))}"


@dataclass(frozen=True, slots=True)
class TaskOperation(Contract):
    """One bounded change request inside a delta."""

    format: ClassVar[str] = "atmem-task-operation-v1"
    kind: OperationKind
    item_id: str | None = None
    constraint_id: str | None = None
    source_id: str | None = None
    phase: str | None = None
    status: ItemStatus | None = None
    text: str | None = None
    content: dict[str, Any] | None = None
    depends_on: tuple[str, ...] | None = None
    kind_label: str | None = None
    required: bool | None = None
    reason: str | None = None
    assurance: Assurance = Assurance.ASSERTED

    def __post_init__(self) -> None:
        requires_item = {
            OperationKind.SET_ITEM_STATUS,
            OperationKind.ADD_ITEM,
            OperationKind.SET_ITEM_CONTENT,
            OperationKind.SET_ITEM_BLOCKER,
        }
        if self.kind in requires_item and not self.item_id:
            raise ValueError(f"{self.kind.value} requires item_id")
        if self.kind is OperationKind.SET_ITEM_STATUS and self.status is None:
            raise ValueError("set_item_status requires status")
        if self.kind is OperationKind.SET_PHASE and not self.phase:
            raise ValueError("set_phase requires phase")
        if self.kind is OperationKind.ADD_CONSTRAINT and not (
            self.constraint_id and self.text
        ):
            raise ValueError("add_constraint requires constraint_id and text")
        if self.kind is OperationKind.SATISFY_CONSTRAINT and not self.constraint_id:
            raise ValueError("satisfy_constraint requires constraint_id")
        if self.kind is OperationKind.MARK_SOURCE_INSPECTED and not self.source_id:
            raise ValueError("mark_source_inspected requires source_id")
        if self.kind is OperationKind.ADD_ITEM and not (self.kind_label and self.text):
            raise ValueError("add_item requires kind_label and text")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["kind"] = self.kind.value
        value["status"] = self.status.value if self.status else None
        value["assurance"] = self.assurance.value
        return value


@dataclass(frozen=True, slots=True)
class TaskStateProposal(Contract):
    """An untrusted typed delta against an exact base revision."""

    format: ClassVar[str] = "atmem-task-state-proposal-v1"
    proposal_id: str
    task_id: str
    scope: AuthorityScope
    base_revision: int
    idempotency_key: str
    actor: str
    actor_role: ActorRole
    operations: tuple[TaskOperation, ...]
    evidence: tuple[EvidenceRef, ...] = ()
    interpreter: str | None = None
    assurance: Assurance = Assurance.ASSERTED
    reason: str | None = None
    action_fingerprint: str | None = None

    def __post_init__(self) -> None:
        _identifier("proposal_id", self.proposal_id)
        _identifier("task_id", self.task_id)
        _text("actor", self.actor, limit=200)
        _text("idempotency_key", self.idempotency_key, limit=256)
        if int(self.base_revision) < 1:
            raise ValueError("base_revision starts at 1")
        if not self.operations:
            raise ValueError("a proposal must request at least one operation")
        if len(self.operations) > MAX_OPERATIONS:
            raise ValueError(f"a proposal may carry at most {MAX_OPERATIONS} operations")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["actor_role"] = self.actor_role.value
        value["assurance"] = self.assurance.value
        value["operations"] = [operation.to_dict() for operation in self.operations]
        return value

    def payload_digest(self) -> str:
        value = self.to_dict()
        value.pop("idempotency_key", None)
        value.pop("proposal_id", None)
        return f"sha256:{sha256_hex(canonical_json(value))}"


@dataclass(frozen=True, slots=True)
class TransitionDecision(Contract):
    """AtMem's answer to one observed workflow step."""

    format: ClassVar[str] = "atmem-task-transition-decision-v1"
    decision_id: str
    proposal_id: str
    task_id: str
    scope: AuthorityScope
    outcome: StepOutcome
    reason_codes: tuple[str, ...]
    base_revision: int
    resulting_revision: int | None = None
    decided_at: str = ""
    decided_by: str = "atmem-authority"
    assurance: Assurance = Assurance.ASSERTED
    evidence: tuple[EvidenceRef, ...] = ()
    guards: tuple["GuardSignal", ...] = ()
    replayed: bool = False

    def __post_init__(self) -> None:
        _reason_codes(self.reason_codes)
        if self.outcome is StepOutcome.ACCEPTED and self.resulting_revision is None:
            raise ValueError("an accepted transition must name its resulting revision")
        if self.outcome is not StepOutcome.ACCEPTED and self.resulting_revision not in (
            None,
            self.base_revision,
        ):
            raise ValueError("only an accepted transition may advance the revision")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["outcome"] = self.outcome.value
        value["assurance"] = self.assurance.value
        value["guards"] = [guard.to_dict() for guard in self.guards]
        return value


@dataclass(frozen=True, slots=True)
class GuardSignal(Contract):
    """An explainable warning or denial, never an executed action.

    AtMem detects; only an adapter that reports enforcement may claim to have
    prevented anything.
    """

    format: ClassVar[str] = "atmem-task-guard-signal-v1"
    guard_type: GuardType
    task_id: str
    revision: int
    message: str
    blocking_item_ids: tuple[str, ...] = ()
    repeated_action_count: int = 0
    enforced: bool = False

    def __post_init__(self) -> None:
        _text("message", self.message)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["guard_type"] = self.guard_type.value
        return value


@dataclass(frozen=True, slots=True)
class TaskContextPackage(Contract):
    """Bounded, byte-stable current state delivered at a model boundary."""

    format: ClassVar[str] = "atmem-task-context-package-v1"
    context_id: str
    task_id: str
    scope: AuthorityScope
    revision: int
    disposition: ContextDisposition
    context: str = ""
    context_sha256: str = ""
    reason_codes: tuple[str, ...] = ()
    serializer_version: str = SERIALIZER_VERSION
    profile_version: str = ""
    policy_generation: int = 1
    omitted_fields: tuple[str, ...] = ()
    prepared_at: str = ""
    preparation_id: str = ""

    def __post_init__(self) -> None:
        _reason_codes(self.reason_codes) if self.reason_codes else None
        if self.disposition is ContextDisposition.WITHHELD and self.context:
            raise ValueError("a withheld package must carry no task-state bytes")
        if self.disposition is ContextDisposition.INJECTED and not self.context:
            raise ValueError("an injected package must carry the authorized bytes")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["disposition"] = self.disposition.value
        return value

    def cache_key(self) -> str:
        """Identity bound to everything that could change the bytes."""
        identity = {
            "subject_id": self.scope.subject_id,
            "agent_id": self.scope.agent_id,
            "workspace_id": self.scope.workspace_id,
            "task_id": self.task_id,
            "revision": self.revision,
            "profile_version": self.profile_version,
            "policy_generation": self.policy_generation,
            "serializer_version": self.serializer_version,
        }
        return f"sha256:{sha256_hex(canonical_json(identity))}"


@dataclass(frozen=True, slots=True)
class GovernanceCapability(Contract):
    """What one actor role may actually do, derived rather than asserted."""

    format: ClassVar[str] = "atmem-task-governance-capability-v1"
    actor_role: ActorRole
    read_state: bool = False
    propose_delta: bool = False
    commit_state: bool = False
    correct_state: bool = False
    register_profile: bool = False
    change_lifecycle: bool = False
    expire_task: bool = False
    deliver_context: bool = False
    delete_state: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["actor_role"] = self.actor_role.value
        return value

    def permits(self, action: str) -> bool:
        if not hasattr(self, action):
            raise ValueError(f"unknown governance action: {action!r}")
        return bool(getattr(self, action))


__all__ = [
    "ActorRole",
    "Assurance",
    "ContextDisposition",
    "EvidenceRef",
    "ExpiryPolicy",
    "GovernanceCapability",
    "GuardSignal",
    "GuardType",
    "ItemStatus",
    "MAX_CONSTRAINTS",
    "MAX_ITEMS",
    "MAX_OPERATIONS",
    "OperationKind",
    "Provenance",
    "REASON_CODES",
    "SERIALIZER_VERSION",
    "StepOutcome",
    "TaskConstraint",
    "TaskContextPackage",
    "TaskItem",
    "TaskLifecycle",
    "TaskOperation",
    "TaskProfile",
    "TaskStartRequest",
    "TaskState",
    "TaskStateProposal",
    "TransitionDecision",
]
