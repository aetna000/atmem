"""Dependency-free host-neutral contracts for Context Engine V3."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Literal, Mapping

from atmem.contracts.models import (
    ActionConstraint,
    AuthorityScope,
    ContextPackageV2,
    InformationNeed,
    RetrievalBudget,
    SufficiencyDecision,
)
from atmem.core.canonical import canonical_json, sha256_hex


ContextStatus = Literal[
    "sufficient",
    "partial",
    "conflicted",
    "contradicted",
    "stale",
    "not_found_within_budget",
    "withheld_by_policy",
]
EngineMode = Literal["shadow", "active"]
_STATUSES = {
    "sufficient", "partial", "conflicted", "contradicted", "stale",
    "not_found_within_budget", "withheld_by_policy",
}
_PROFILES = {"legacy-control", "context-fast", "context-navigate"}


def _nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _closed(value: Mapping[str, Any], allowed: set[str], name: str) -> None:
    extras = set(value) - allowed
    missing = allowed - set(value)
    if extras:
        raise ValueError(f"{name} has unknown fields: {', '.join(sorted(extras))}")
    if missing:
        raise ValueError(f"{name} is missing fields: {', '.join(sorted(missing))}")


@dataclass(frozen=True, slots=True)
class V3Contract:
    format: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        return {"format": self.format, **asdict(self)}

    def canonical_bytes(self) -> bytes:
        return canonical_json(self.to_dict()).encode()


@dataclass(frozen=True, slots=True)
class EvidenceRange(V3Contract):
    format: ClassVar[str] = "atmem-evidence-range-v1"
    source_id: str
    part_id: str
    start: int
    end: int
    source_sha256: str

    def __post_init__(self) -> None:
        _nonempty("source_id", self.source_id)
        _nonempty("part_id", self.part_id)
        if self.start < 0 or self.end <= self.start:
            raise ValueError("evidence range must identify a non-empty source span")
        if not self.source_sha256.startswith("sha256:") or len(self.source_sha256) != 71:
            raise ValueError("source_sha256 must be a sha256 digest")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceRange":
        allowed = {"format", "source_id", "part_id", "start", "end", "source_sha256"}
        _closed(value, allowed, "evidence range")
        if value.get("format") != cls.format:
            raise ValueError("unsupported evidence range format")
        return cls(**{name: value[name] for name in allowed - {"format"}})


@dataclass(frozen=True, slots=True)
class FormationRequestV2(V3Contract):
    format: ClassVar[str] = "atmem-formation-request-v2"
    formation_id: str
    episode_id: str
    scope: AuthorityScope
    profile_id: str
    source_generation: int
    budget: RetrievalBudget = field(default_factory=RetrievalBudget)

    def __post_init__(self) -> None:
        _nonempty("formation_id", self.formation_id)
        _nonempty("episode_id", self.episode_id)
        if self.profile_id not in _PROFILES - {"legacy-control"}:
            raise ValueError("formation requires a V3 context profile")
        if self.source_generation < 0:
            raise ValueError("source_generation cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        value = V3Contract.to_dict(self)
        value["scope"] = self.scope.to_dict()
        value["budget"] = self.budget.to_dict()
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FormationRequestV2":
        fields = set(cls.__dataclass_fields__) - {"format"}
        _closed(value, fields | {"format"}, "formation request")
        if value.get("format") != cls.format:
            raise ValueError("unsupported formation request format")
        scope_row = value["scope"]
        budget_row = value["budget"]
        if not isinstance(scope_row, Mapping) or scope_row.get("format") != AuthorityScope.format:
            raise ValueError("invalid formation scope")
        if (
            not isinstance(budget_row, Mapping)
            or budget_row.get("format") != RetrievalBudget.format
        ):
            raise ValueError("invalid formation budget")
        budget_fields = set(RetrievalBudget.__dataclass_fields__) - {"format"}
        _closed(budget_row, budget_fields | {"format"}, "formation budget")
        return cls(
            **{
                name: value[name]
                for name in fields
                if name not in {"scope", "budget"}
            },
            scope=AuthorityScope(
                subject_id=str(scope_row["subject_id"]),
                agent_id=str(scope_row["agent_id"]),
                workspace_id=str(scope_row["workspace_id"]),
            ),
            budget=RetrievalBudget(
                **{name: budget_row[name] for name in budget_fields}
            ),
        )


@dataclass(frozen=True, slots=True)
class FormationReceiptV2(V3Contract):
    format: ClassVar[str] = "atmem-formation-receipt-v2"
    formation_id: str
    episode_id: str
    generation_id: str
    source_generation: int
    producer_id: str
    represented_ranges: tuple[EvidenceRange, ...]
    loss_ranges: tuple[EvidenceRange, ...]
    units_created: int
    units_reconciled: int
    units_rejected: int
    storage_bytes_by_category: dict[str, int]
    processing_complete: bool
    representation_complete: bool
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("formation_id", "episode_id", "generation_id", "producer_id"):
            _nonempty(name, getattr(self, name))
        if self.source_generation < 0:
            raise ValueError("source_generation cannot be negative")
        counts = (self.units_created, self.units_reconciled, self.units_rejected)
        if any(value < 0 for value in counts):
            raise ValueError("formation unit counts cannot be negative")
        if any(value < 0 for value in self.storage_bytes_by_category.values()):
            raise ValueError("storage accounting cannot be negative")
        if self.representation_complete and not self.processing_complete:
            raise ValueError("representation cannot complete before processing")
        if self.representation_complete and self.loss_ranges:
            raise ValueError("complete representation cannot retain loss ranges")

    def to_dict(self) -> dict[str, Any]:
        value = V3Contract.to_dict(self)
        value["represented_ranges"] = [item.to_dict() for item in self.represented_ranges]
        value["loss_ranges"] = [item.to_dict() for item in self.loss_ranges]
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FormationReceiptV2":
        fields = set(cls.__dataclass_fields__) - {"format"}
        _closed(value, fields | {"format"}, "formation receipt")
        if value.get("format") != cls.format:
            raise ValueError("unsupported formation receipt format")
        payload = {
            name: value[name]
            for name in fields
            if name not in {"represented_ranges", "loss_ranges"}
        }
        payload["reason_codes"] = tuple(payload["reason_codes"])
        return cls(
            **{
                name: payload[name]
                for name in payload
            },
            represented_ranges=tuple(
                EvidenceRange.from_dict(row) for row in value["represented_ranges"]
            ),
            loss_ranges=tuple(
                EvidenceRange.from_dict(row) for row in value["loss_ranges"]
            ),
        )


@dataclass(frozen=True, slots=True)
class EvidenceObligation(V3Contract):
    format: ClassVar[str] = "atmem-evidence-obligation-v1"
    obligation_id: str
    kind: Literal[
        "subject_relation_value", "condition_action", "before_action_after",
        "ordered_steps", "claim_support", "comparison_side", "premise_check",
    ]
    required: bool = True
    entity: str | None = None
    relation_or_action: str | None = None
    temporal_target: str | None = None
    polarity: Literal["positive", "negative", "unknown"] = "unknown"
    applicability: str | None = None

    def __post_init__(self) -> None:
        _nonempty("obligation_id", self.obligation_id)
        if not self.entity and not self.relation_or_action:
            raise ValueError("obligation requires an entity or relation/action")


@dataclass(frozen=True, slots=True)
class QueryPlan(V3Contract):
    format: ClassVar[str] = "atmem-query-plan-v1"
    plan_id: str
    query_sha256: str
    obligations: tuple[EvidenceObligation, ...]
    pool_queries: dict[str, tuple[str, ...]]
    planner_identity: str
    deterministic_fallback: bool

    def __post_init__(self) -> None:
        _nonempty("plan_id", self.plan_id)
        _nonempty("planner_identity", self.planner_identity)
        if not self.query_sha256.startswith("sha256:") or len(self.query_sha256) != 71:
            raise ValueError("query_sha256 must be a sha256 digest")
        if not self.obligations:
            raise ValueError("query plan requires obligations")
        ids = [item.obligation_id for item in self.obligations]
        if len(ids) != len(set(ids)):
            raise ValueError("query-plan obligation IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        value = V3Contract.to_dict(self)
        value["obligations"] = [item.to_dict() for item in self.obligations]
        return value


@dataclass(frozen=True, slots=True)
class NavigationReceipt(V3Contract):
    format: ClassVar[str] = "atmem-navigation-receipt-v1"
    plan_id: str
    searched_views: tuple[str, ...]
    inspected_ranges: tuple[EvidenceRange, ...]
    submitted_ranges: tuple[EvidenceRange, ...]
    operations_used: int
    bytes_used: int
    elapsed_ms: int
    exhausted: bool
    navigator_identity: str = "none"

    def __post_init__(self) -> None:
        _nonempty("plan_id", self.plan_id)
        _nonempty("navigator_identity", self.navigator_identity)
        if min(self.operations_used, self.bytes_used, self.elapsed_ms) < 0:
            raise ValueError("navigation usage cannot be negative")
        inspected = {tuple(asdict(item).values()) for item in self.inspected_ranges}
        submitted = {tuple(asdict(item).values()) for item in self.submitted_ranges}
        if not submitted <= inspected:
            raise ValueError("submitted ranges must have been inspected")

    def to_dict(self) -> dict[str, Any]:
        value = V3Contract.to_dict(self)
        value["inspected_ranges"] = [item.to_dict() for item in self.inspected_ranges]
        value["submitted_ranges"] = [item.to_dict() for item in self.submitted_ranges]
        return value


@dataclass(frozen=True, slots=True)
class SufficiencyDecisionV2(V3Contract):
    format: ClassVar[str] = "atmem-sufficiency-decision-v2"
    decision_id: str
    status: ContextStatus
    required_obligation_ids: tuple[str, ...]
    covered_obligation_ids: tuple[str, ...]
    evidence_unit_ids: tuple[str, ...]
    missing_obligation_ids: tuple[str, ...] = ()
    conflicting_unit_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty("decision_id", self.decision_id)
        if self.status not in _STATUSES:
            raise ValueError("unsupported V3 sufficiency status")
        required = set(self.required_obligation_ids)
        covered = set(self.covered_obligation_ids)
        missing = set(self.missing_obligation_ids)
        if not required or covered & missing or covered | missing != required:
            raise ValueError("covered and missing obligations must partition required obligations")
        if self.status == "sufficient" and (missing or not self.evidence_unit_ids):
            raise ValueError("sufficient status requires complete source-backed evidence")
        if self.status == "partial" and not missing:
            raise ValueError("partial status requires missing obligations")
        if self.status == "conflicted" and not self.conflicting_unit_ids:
            raise ValueError("conflicted status requires conflicting units")
        if self.status == "withheld_by_policy" and self.evidence_unit_ids:
            raise ValueError("policy-withheld status cannot disclose evidence IDs")


@dataclass(frozen=True, slots=True)
class ContextRequestV3(V3Contract):
    format: ClassVar[str] = "atmem-context-request-v3"
    context_id: str
    request_id: str
    scope: AuthorityScope
    query: str
    profile_id: Literal["legacy-control", "context-fast", "context-navigate"]
    mode: EngineMode
    generation: int
    budget: RetrievalBudget = field(default_factory=RetrievalBudget)
    turn_id: str | None = None
    media_reference_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty("context_id", self.context_id)
        _nonempty("request_id", self.request_id)
        _nonempty("query", self.query)
        if self.profile_id not in _PROFILES:
            raise ValueError("unknown context-engine profile")
        if self.mode not in {"shadow", "active"}:
            raise ValueError("unknown context-engine mode")
        if self.generation < 0:
            raise ValueError("context generation cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        value = V3Contract.to_dict(self)
        value["scope"] = self.scope.to_dict()
        value["budget"] = self.budget.to_dict()
        return value


@dataclass(frozen=True, slots=True)
class ContextPackageV3(V3Contract):
    format: ClassVar[str] = "atmem-context-package-v3"
    context_id: str
    scope: AuthorityScope
    profile_id: str
    generation: int
    expires_at: str
    preparation_id: str
    status: ContextStatus
    context: str
    context_sha256: str
    sufficiency: SufficiencyDecisionV2
    selected_unit_ids: tuple[str, ...]
    selected_ranges: tuple[EvidenceRange, ...]
    excluded_evidence: tuple[dict[str, str], ...]
    plan: QueryPlan
    navigation: NavigationReceipt | None
    budget: RetrievalBudget
    audit_event_id: str
    action_constraints: tuple[ActionConstraint, ...] = ()
    media_references: tuple[dict[str, str], ...] = ()
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("context_id", "profile_id", "preparation_id", "audit_event_id"):
            _nonempty(name, getattr(self, name))
        if self.status not in _STATUSES or self.status != self.sufficiency.status:
            raise ValueError("package and sufficiency statuses must match")
        if self.generation < 0:
            raise ValueError("context generation cannot be negative")
        expected = "sha256:" + sha256_hex(self.context)
        if self.context_sha256 != expected:
            raise ValueError("context_sha256 does not match context")
        if len(self.context.encode()) > self.budget.context_bytes:
            raise ValueError("context exceeds declared budget")
        if set(self.sufficiency.evidence_unit_ids) - set(self.selected_unit_ids):
            raise ValueError("sufficiency evidence must be selected")
        if self.status != "sufficient" and (self.context or self.action_constraints):
            raise ValueError("non-sufficient V3 packages fail closed")
        if self.status == "sufficient" and not self.selected_ranges:
            raise ValueError("sufficient context requires canonical source ranges")
        required_plan_ids = {
            item.obligation_id for item in self.plan.obligations if item.required
        }
        if required_plan_ids != set(self.sufficiency.required_obligation_ids):
            raise ValueError("sufficiency obligations must match the required query plan")
        if self.status == "withheld_by_policy" and (
            self.selected_unit_ids
            or self.selected_ranges
            or self.excluded_evidence
            or self.media_references
            or (
                self.navigation is not None
                and (self.navigation.inspected_ranges or self.navigation.submitted_ranges)
            )
        ):
            raise ValueError("policy-withheld packages cannot disclose evidence metadata")
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("expires_at must be an ISO-8601 timestamp") from exc
        if expires.tzinfo is None or expires.utcoffset() is None:
            raise ValueError("expires_at must include a timezone offset")
        selected_sources = {item.source_id for item in self.selected_ranges}
        excluded_ids = {
            item.get("evidence_id", "") for item in self.excluded_evidence
            if item.get("evidence_id")
        }
        if excluded_ids & set(self.selected_unit_ids):
            raise ValueError("evidence cannot be both selected and excluded")
        for constraint in self.action_constraints:
            if not set(constraint.source_ids) <= selected_sources:
                raise ValueError("action constraints require selected source evidence")
        for reference in self.media_references:
            if reference.get("adjacent_source_id") not in selected_sources:
                raise ValueError("media references require adjacent selected source evidence")

    def to_dict(self) -> dict[str, Any]:
        value = V3Contract.to_dict(self)
        value["scope"] = self.scope.to_dict()
        value["sufficiency"] = self.sufficiency.to_dict()
        value["selected_ranges"] = [item.to_dict() for item in self.selected_ranges]
        value["plan"] = self.plan.to_dict()
        value["navigation"] = self.navigation.to_dict() if self.navigation else None
        value["budget"] = self.budget.to_dict()
        value["action_constraints"] = [item.to_dict() for item in self.action_constraints]
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ContextPackageV3":
        fields = set(cls.__dataclass_fields__) - {"format"}
        _closed(value, fields | {"format"}, "context package v3")
        if value.get("format") != cls.format:
            raise ValueError("unsupported context package format")

        def nested(row: Mapping[str, Any], kind: type[V3Contract], name: str) -> dict[str, Any]:
            fields_for_kind = set(kind.__dataclass_fields__) - {"format"}
            _closed(row, fields_for_kind | {"format"}, name)
            if row.get("format") != kind.format:
                raise ValueError(f"unsupported {name} format")
            return {field_name: row[field_name] for field_name in fields_for_kind}

        scope_row = value["scope"]
        if not isinstance(scope_row, Mapping) or scope_row.get("format") != AuthorityScope.format:
            raise ValueError("invalid authority scope")
        scope = AuthorityScope(
            subject_id=str(scope_row["subject_id"]),
            agent_id=str(scope_row["agent_id"]),
            workspace_id=str(scope_row["workspace_id"]),
        )
        budget_row = value["budget"]
        if (
            not isinstance(budget_row, Mapping)
            or budget_row.get("format") != RetrievalBudget.format
        ):
            raise ValueError("invalid retrieval budget")
        budget_fields = set(RetrievalBudget.__dataclass_fields__) - {"format"}
        _closed(budget_row, budget_fields | {"format"}, "retrieval budget")
        budget = RetrievalBudget(**{name: budget_row[name] for name in budget_fields})

        sufficiency_row = value["sufficiency"]
        if not isinstance(sufficiency_row, Mapping):
            raise ValueError("invalid sufficiency decision")
        sufficiency_data = nested(
            sufficiency_row, SufficiencyDecisionV2, "sufficiency decision"
        )
        for name in (
            "required_obligation_ids", "covered_obligation_ids",
            "evidence_unit_ids", "missing_obligation_ids",
            "conflicting_unit_ids", "reason_codes",
        ):
            sufficiency_data[name] = tuple(sufficiency_data[name])
        sufficiency = SufficiencyDecisionV2(**sufficiency_data)
        plan_row = value["plan"]
        if not isinstance(plan_row, Mapping):
            raise ValueError("invalid query plan")
        plan_data = nested(plan_row, QueryPlan, "query plan")
        obligation_rows = plan_data.pop("obligations")
        plan_data["pool_queries"] = {
            str(name): tuple(queries)
            for name, queries in plan_data["pool_queries"].items()
        }
        plan = QueryPlan(
            obligations=tuple(
                EvidenceObligation(
                    **nested(row, EvidenceObligation, "evidence obligation")
                )
                for row in obligation_rows
            ),
            **plan_data,
        )
        navigation_row = value.get("navigation")
        navigation = None
        if navigation_row is not None:
            if not isinstance(navigation_row, Mapping):
                raise ValueError("invalid navigation receipt")
            navigation_data = nested(
                navigation_row, NavigationReceipt, "navigation receipt"
            )
            navigation_data["inspected_ranges"] = tuple(
                EvidenceRange.from_dict(row)
                for row in navigation_data["inspected_ranges"]
            )
            navigation_data["submitted_ranges"] = tuple(
                EvidenceRange.from_dict(row)
                for row in navigation_data["submitted_ranges"]
            )
            navigation_data["searched_views"] = tuple(
                navigation_data["searched_views"]
            )
            navigation = NavigationReceipt(**navigation_data)
        action_constraints = []
        for row in value.get("action_constraints", ()):
            if not isinstance(row, Mapping) or row.get("format") != ActionConstraint.format:
                raise ValueError("invalid action constraint")
            action_fields = set(ActionConstraint.__dataclass_fields__) - {"format"}
            _closed(row, action_fields | {"format"}, "action constraint")
            action_constraints.append(
                ActionConstraint(
                    **{
                        name: tuple(row[name]) if name == "source_ids" else row[name]
                        for name in action_fields
                    }
                )
            )
        payload = {
                name: value[name]
                for name in fields
                if name not in {
                    "scope", "sufficiency", "selected_ranges", "plan", "navigation",
                    "budget", "action_constraints",
                }
            }
        for name in (
            "selected_unit_ids", "excluded_evidence", "media_references", "reason_codes"
        ):
            payload[name] = tuple(payload[name])
        return cls(
            **payload,
            scope=scope,
            sufficiency=sufficiency,
            selected_ranges=tuple(
                EvidenceRange.from_dict(row) for row in value["selected_ranges"]
            ),
            plan=plan,
            navigation=navigation,
            budget=budget,
            action_constraints=tuple(action_constraints),
        )

    def to_v2(self) -> ContextPackageV2:
        """Fail-closed projection for existing Context Package V2 clients."""

        obligation_ids = self.sufficiency.required_obligation_ids
        need = InformationNeed(
            need_id=self.plan.plan_id,
            type="relational_synthesis",
            required_slots=obligation_ids,
        )
        if self.status == "sufficient":
            legacy_status = "sufficient"
            covered = obligation_ids
            missing: tuple[str, ...] = ()
            evidence_ids = self.selected_unit_ids
            context = self.context
            record_ids = self.selected_unit_ids
            source_ids = tuple(dict.fromkeys(item.source_id for item in self.selected_ranges))
            reason_codes = self.reason_codes
        else:
            legacy_status = "unsupported"
            covered = ()
            missing = obligation_ids
            evidence_ids = ()
            context = ""
            record_ids = ()
            source_ids = ()
            reason_codes = (*self.reason_codes, f"v3_{self.status}")
        sufficiency = SufficiencyDecision(
            decision_id=self.sufficiency.decision_id,
            need_id=need.need_id,
            status=legacy_status,
            required_slots=obligation_ids,
            covered_slots=covered,
            missing_slots=missing,
            evidence_ids=evidence_ids,
            reason_codes=reason_codes,
        )
        return ContextPackageV2(
            context_id=self.context_id,
            scope=self.scope,
            record_ids=record_ids,
            context=context,
            context_sha256="sha256:" + sha256_hex(context),
            serializer_version="atmem-context-v3-to-v2-v1",
            generation=self.generation,
            expires_at=self.expires_at,
            preparation_id=self.preparation_id,
            profile_id=self.profile_id,
            need=need,
            sufficiency=sufficiency,
            source_ids=source_ids,
            budget=self.budget,
            selected_units=(),
            provenance=(),
            excluded_evidence_ids=tuple(
                item.get("evidence_id", "") for item in self.excluded_evidence
                if item.get("evidence_id")
            ),
            action_constraints=self.action_constraints if self.status == "sufficient" else (),
            reason_codes=reason_codes,
            media_references=self.media_references if self.status == "sufficient" else (),
        )
