"""Closed, bounded host-neutral feedback, RAG and guarded-call wire contracts.

Construction validates data, never grants authority. In particular, a serialized
receipt is not trusted until the service finds its authentic stored counterpart.
"""

from __future__ import annotations

from dataclasses import MISSING, dataclass, fields
from datetime import date
from hashlib import sha256
import math
import json
import re
import types
from typing import Any, ClassVar, Literal, Union, get_args, get_origin, get_type_hints

from atmem.contracts.models import AuthorityScope
from atmem.core.canonical import canonical_json
from atmem.evidence.models import EvidenceScope


MAX_BYTES = 262_144
MAX_ITEMS = 128
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z")


def identifier(value: Any) -> str:
    if type(value) is not str or not ID.fullmatch(value):
        raise ValueError("invalid bounded identifier")
    return value


def digest(value: Any) -> str:
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError("invalid content digest")
    return value


def json_data(value: Any, depth: int = 0) -> None:
    if depth > 16:
        raise ValueError("data nesting exceeds bound")
    if value is None or type(value) is bool:
        return
    if type(value) in (int, float):
        if abs(value) > 2**53 or not math.isfinite(value):
            raise ValueError("non-finite or oversized number")
    elif type(value) is str:
        if len(value.encode()) > 65_536:
            raise ValueError("text exceeds bound")
    elif type(value) in (list, tuple):
        if len(value) > MAX_ITEMS:
            raise ValueError("too many items")
        for item in value:
            json_data(item, depth + 1)
    elif type(value) is dict:
        if len(value) > MAX_ITEMS or any(type(k) is not str or len(k) > 512 for k in value):
            raise ValueError("invalid object keys")
        for item in value.values():
            json_data(item, depth + 1)
    else:
        raise ValueError("JSON data required")


def iso_date(value: str | None) -> None:
    if value is not None and (type(value) is not str or date.fromisoformat(value).isoformat() != value):
        raise ValueError("ISO calendar date required")


def _typed(annotation: Any, value: Any, *, wire: bool) -> Any:
    origin, args = get_origin(annotation), get_args(annotation)
    if annotation is Any:
        json_data(value)
        return value
    if origin in (Union, types.UnionType):
        for alternative in args:
            try:
                return _typed(alternative, value, wire=wire)
            except (ValueError, TypeError):
                continue
        raise ValueError("invalid union field")
    if origin is Literal:
        if not any(type(value) is type(v) and value == v for v in args):
            raise ValueError("invalid enumerated value")
        return value
    if origin is tuple:
        if type(value) is not (list if wire else tuple) or len(value) > MAX_ITEMS:
            raise ValueError("bounded sequence required")
        return tuple(_typed(args[0], item, wire=wire) for item in value)
    if origin is dict:
        if type(value) is not dict:
            raise ValueError("object required")
        json_data(value)
        return value
    if isinstance(annotation, type) and issubclass(annotation, Wire):
        if wire:
            return annotation.from_dict(value)
        if type(value) is not annotation:
            raise ValueError("nested contract required")
        return value
    if type(value) is not annotation:
        raise ValueError("invalid field type")
    if annotation is int and not 0 <= value <= 2**53:
        raise ValueError("nonnegative bounded integer required")
    if annotation is str and len(value.encode()) > 65_536:
        raise ValueError("text exceeds bound")
    return value


class Wire:
    format: ClassVar[str]

    def __post_init__(self) -> None:
        hints = get_type_hints(type(self))
        for field in fields(self):
            value = getattr(self, field.name)
            _typed(hints[field.name], value, wire=False)
            if field.name.endswith("_sha256"):
                digest(value)
            if field.name.endswith("_id") and value is not None:
                identifier(value)
        if len(canonical_json(self.to_dict()).encode()) > MAX_BYTES:
            raise ValueError("contract exceeds byte bound")

    def to_dict(self) -> dict[str, Any]:
        def encode(value):
            if isinstance(value, Wire):
                return value.to_dict()
            if isinstance(value, (tuple, list)):
                return [encode(v) for v in value]
            if isinstance(value, dict):
                return {k: encode(v) for k, v in value.items()}
            return value
        return {"format": self.format, **{f.name: encode(getattr(self, f.name)) for f in fields(self)}}

    @classmethod
    def from_dict(cls, value: Any):
        if type(value) is not dict or value.get("format") != cls.format:
            raise ValueError("wrong contract format")
        allowed = {f.name for f in fields(cls)}
        required = {f.name for f in fields(cls) if f.default is MISSING and f.default_factory is MISSING}
        if set(value) - allowed - {"format"} or not required <= set(value):
            raise ValueError("unknown or missing contract fields")
        json_data(value)
        encoded = canonical_json(value)
        if len(encoded.encode()) > MAX_BYTES:
            raise ValueError("contract exceeds byte bound")
        value = json.loads(encoded)
        hints = get_type_hints(cls)
        return cls(**{k: _typed(hints[k], v, wire=True) for k, v in value.items() if k != "format"})

    @property
    def content_digest(self) -> str:
        return sha256(canonical_json(self.to_dict()).encode()).hexdigest()


@dataclass(frozen=True)
class FeedbackScope(Wire):
    format = "atmem-feedback-scope-v1"
    tenant_id: str
    subject_id: str
    agent_id: str
    workspace_id: str

    def evidence_scope(self) -> EvidenceScope:
        return EvidenceScope(self.tenant_id, self.subject_id, self.workspace_id)

    def authority_scope(self) -> AuthorityScope:
        return AuthorityScope(self.subject_id, self.agent_id, self.workspace_id)

    @property
    def partition(self) -> str:
        return "feedback:" + self.content_digest


@dataclass(frozen=True)
class SourceRevision(Wire):
    format = "atmem-feedback-source-revision-v1"
    source_id: str
    revision: int
    content_sha256: str


@dataclass(frozen=True)
class ActionRequirement(Wire):
    format = "atmem-feedback-action-requirement-v1"
    action_id: str
    tool: str
    schema_version: str
    kind: Literal["read", "write"]
    checks: tuple[str, ...]

    def __post_init__(self):
        super().__post_init__()
        identifier(self.tool)
        identifier(self.schema_version)
        if not self.checks or len(set(self.checks)) != len(self.checks):
            raise ValueError("unique nonempty required checks needed")
        for item in self.checks:
            identifier(item)


@dataclass(frozen=True)
class ActionCheck(Wire):
    format = "atmem-feedback-action-check-v1"
    check_id: str
    kind: Literal["mechanical", "judged"]
    result: Literal["pass", "fail", "unknown", "disputed"]
    reason: str


@dataclass(frozen=True)
class ActionObservation(Wire):
    format = "atmem-feedback-action-observation-v1"
    action_id: str
    invocation_id: str
    tool: str
    schema_version: str
    arguments: dict[str, Any]
    result: Any
    checks: tuple[ActionCheck, ...]
    evidence_id: str | None = None

    def __post_init__(self):
        super().__post_init__()
        identifier(self.tool)
        identifier(self.schema_version)
        names = [c.check_id for c in self.checks]
        if len(set(names)) != len(names):
            raise ValueError("duplicate check for one invocation")


@dataclass(frozen=True)
class OutcomeRecord(Wire):
    format = "atmem-feedback-outcome-v1"
    outcome_id: str
    scope: FeedbackScope
    run_id: str
    turn_id: str
    required: tuple[ActionRequirement, ...]
    observations: tuple[ActionObservation, ...]
    context_receipt_id: str | None = None
    delivery: Literal["not_captured", "not_delivered", "delivered"] = "not_captured"
    revision: int = 1
    predecessor_id: str | None = None

    def __post_init__(self):
        super().__post_init__()
        ids = [v.action_id for v in self.required]
        if not ids or len(ids) != len(set(ids)) or self.revision < 1:
            raise ValueError("unique required actions and positive revision needed")
        if self.delivery == "delivered" and self.context_receipt_id is None:
            raise ValueError("delivery requires an evidence receipt")
        invocations = [v.invocation_id for v in self.observations]
        if len(set(invocations)) != len(invocations) or any(v.action_id not in ids for v in self.observations):
            raise ValueError("invalid observation linkage")


@dataclass(frozen=True)
class VerificationReceipt(Wire):
    format = "atmem-feedback-verification-v1"
    receipt_id: str
    scope: FeedbackScope
    outcome_id: str
    outcome_sha256: str
    invocation_id: str
    verifier_id: str
    verifier_version: str
    evidence_id: str
    checks: tuple[ActionCheck, ...]
    assurance: Literal["independent_readback", "human_attestation", "host_report", "model_judgement"]
    binding: Literal["state_only", "effect_receipt"] = "state_only"
    effect_status: Literal["succeeded", "failed", "not_dispatched", "unknown"] = "unknown"


@dataclass(frozen=True)
class AttributionVerification(Wire):
    format = "atmem-feedback-attribution-verification-v1"
    receipt_id: str
    scope: FeedbackScope
    attribution_id: str
    outcome_sha256: str
    invocation_id: str | None
    action_id: str
    failure_class: Literal["source_fact_absent", "retrieval_miss", "authority_withheld", "stale_conflicting_state",
                           "delivered_but_not_applied", "wrong_argument_value", "wording_precision", "no_call",
                           "execution_failure", "unknown"]
    verifier_id: str
    verifier_version: str
    registry_revision: int
    checks: tuple[ActionCheck, ...]
    evidence: dict[str, Any]
    evidence_ids: tuple[str, ...]
    sources: tuple[dict[str, Any], ...]
    verification_ids: tuple[str, ...]
    status: Literal["verified", "inconclusive", "disputed"]
    supports_classification: bool | None = None
    assurance: Literal["independent_readback"] = "independent_readback"
    claim: Literal["bounded_operational_classification"] = "bounded_operational_classification"
    verified_causality: Literal[False] = False
    qualifies_policy: Literal[False] = False

    def __post_init__(self):
        super().__post_init__()
        if (not self.checks or len({c.check_id for c in self.checks}) != len(self.checks)
                or any(c.kind != "mechanical" for c in self.checks)):
            raise ValueError("unique independent mechanical classification checks required")
        passed = all(c.result == "pass" for c in self.checks)
        if self.status == "verified" and (self.supports_classification is not True or not passed or self.failure_class == "unknown"):
            raise ValueError("verified classification requires complete positive proof")
        if self.supports_classification is True and (not passed or self.failure_class == "unknown"):
            raise ValueError("classification support conflicts with its checks")
        if self.supports_classification is False and not any(c.result == "fail" for c in self.checks):
            raise ValueError("negative classification requires a failed check")


@dataclass(frozen=True)
class RulePredicate(Wire):
    format = "atmem-feedback-rule-predicate-v1"
    operator: Literal["present", "equals", "approval_required"]
    path: tuple[str, ...]
    value: Any = None

    def __post_init__(self):
        super().__post_init__()
        if not self.path or len(self.path) > 8:
            raise ValueError("bounded argument path required")
        for item in self.path:
            identifier(item)
        if self.operator != "equals" and self.value is not None:
            raise ValueError("only equality takes a literal")
        if type(self.value) in (dict, list, tuple):
            raise ValueError("only scalar typed equality supported")


@dataclass(frozen=True)
class RuleCandidate(Wire):
    format = "atmem-feedback-rule-candidate-v1"
    rule_id: str
    scope: FeedbackScope
    tool: str
    schema_version: str
    sources: tuple[SourceRevision, ...]
    predicates: tuple[RulePredicate, ...]
    rationale: str
    revision: int = 1

    def __post_init__(self):
        super().__post_init__()
        if not self.sources or not self.predicates or self.revision < 1:
            raise ValueError("grounded nonempty rule required")
        identifier(self.tool)
        identifier(self.schema_version)


@dataclass(frozen=True)
class QualificationReceipt(Wire):
    format = "atmem-feedback-qualification-v1"
    receipt_id: str
    scope: FeedbackScope
    artifact_sha256: str
    manifest_sha256: str
    versions: dict[str, Any]
    decision: Literal["accept", "reject", "inconclusive"]
    issued_at: int
    expires_at: int
    metrics: dict[str, Any]

    def __post_init__(self):
        super().__post_init__()
        if not 0 < self.expires_at - self.issued_at <= 604800:
            raise ValueError("qualification lifetime exceeds policy")


@dataclass(frozen=True)
class RetrievalProfileCandidate(Wire):
    format = "atmem-feedback-profile-candidate-v1"
    profile_id: str
    scope: FeedbackScope
    sources: tuple[SourceRevision, ...]
    candidate_budget: int = 200
    context_bytes: int = 8192
    balanced_pools: bool = False
    revision: int = 1

    def __post_init__(self):
        super().__post_init__()
        if (not self.sources or not 1 <= self.candidate_budget <= 2000
                or not 512 <= self.context_bytes <= 65536 or self.revision < 1):
            raise ValueError("grounded bounded profile required")


@dataclass(frozen=True)
class ActivationReceipt(Wire):
    format = "atmem-feedback-activation-v1"
    activation_id: str
    scope: FeedbackScope
    artifact_sha256: str
    qualification_id: str
    actor_id: str
    generation: int
    state: Literal["proposed", "reviewed", "shadow", "qualified", "active", "suspended", "revoked", "expired", "rejected"]


@dataclass(frozen=True)
class ExampleExport(Wire):
    format = "atmem-feedback-example-export-v1"
    export_id: str
    scope: FeedbackScope
    consent_id: str
    consent_revision: int
    purpose: str
    recipient_id: str
    outcome_ids: tuple[str, ...]
    preview_sha256: str


@dataclass(frozen=True)
class MCPInvocation(Wire):
    format = "atmem-guarded-invocation-v1"
    tool: str
    schema_version: str
    arguments: dict[str, Any]
    idempotency_key: str
    approval_id: str | None = None

    def __post_init__(self):
        super().__post_init__()
        for value in (self.tool, self.schema_version, self.idempotency_key):
            identifier(value)


CONTRACTS = (FeedbackScope, SourceRevision, ActionRequirement, ActionCheck, ActionObservation, AttributionVerification,
             OutcomeRecord, VerificationReceipt, RulePredicate, RuleCandidate,
             QualificationReceipt, RetrievalProfileCandidate, ActivationReceipt, ExampleExport, MCPInvocation)


def json_schema(cls: type[Wire]) -> dict[str, Any]:
    """Generate closed structural schemas from the same runtime contract types."""
    def schema(annotation):
        origin, args = get_origin(annotation), get_args(annotation)
        if annotation is Any:
            return {}
        if origin in (Union, types.UnionType):
            return {"anyOf": [schema(a) for a in args]}
        if origin is Literal:
            return {"enum": list(args)}
        if origin is tuple:
            return {"type": "array", "maxItems": MAX_ITEMS, "items": schema(args[0])}
        if origin is dict:
            return {"type": "object", "maxProperties": MAX_ITEMS}
        if isinstance(annotation, type) and issubclass(annotation, Wire):
            return object_schema(annotation)
        return {str: {"type": "string", "maxLength": 65_536}, int: {"type": "integer", "minimum": 0, "maximum": 2**53},
                bool: {"type": "boolean"}, type(None): {"type": "null"}}[annotation]

    def object_schema(kind):
        hints = get_type_hints(kind)
        props = {"format": {"const": kind.format}, **{f.name: schema(hints[f.name]) for f in fields(kind)}}
        for field in fields(kind):
            if field.name.endswith("_id") and hints[field.name] is str:
                props[field.name] = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$", "maxLength": 256}
            elif field.name.endswith("_sha256"):
                props[field.name] = {"type": "string", "pattern": "^[a-f0-9]{64}$"}
        required = ["format", *[f.name for f in fields(kind) if f.default is MISSING and f.default_factory is MISSING]]
        return {"type": "object", "properties": props, "required": required, "additionalProperties": False}

    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": cls.format,
            **object_schema(cls)}
