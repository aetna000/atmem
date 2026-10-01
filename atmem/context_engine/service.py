"""Governance shell for Context Engine V3.

The service owns authority and canonical evidence. Retrieval engines receive an
opaque authorized manifest and can only nominate identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Protocol

from atmem.contracts.models import ActionConstraint, AuthorityScope
from atmem.core.canonical import sha256_hex

from .contracts import (
    ContextPackageV3,
    ContextRequestV3,
    ContextStatus,
    EvidenceRange,
    NavigationReceipt,
    QueryPlan,
    SufficiencyDecisionV2,
)


class StoredContextEngine:
    """Deterministic V3 engine over one verified derived generation."""

    def __init__(self, store: object, *, generation_id: str) -> None:
        self.store = store
        self.generation_id = generation_id

    def select(
        self, request: ContextRequestV3, manifest: AuthorizedManifest
    ) -> EngineSelection:
        from .packing import derive_action_constraints, pack_context
        from .planner import DeterministicPlanner
        from .retrieval import DeterministicRetriever
        from .sufficiency import decide_sufficiency

        plan = DeterministicPlanner().plan(request.query)
        result = DeterministicRetriever(self.store).retrieve(
            generation_id=self.generation_id,
            query=request.query,
            plan=plan,
            max_sources=max(1, min(12, request.budget.total_candidates)),
            allowed_unit_ids=frozenset(manifest.authorized_unit_ids),
        )
        decision = decide_sufficiency(plan, result)
        packed = pack_context(
            plan, result, decision, max_bytes=request.budget.context_bytes
        )
        selected = tuple(item.unit_id for item in result.candidates)
        reason_codes = list(decision.reason_codes)
        if decision.status == "sufficient" and not packed.complete:
            covered = {
                obligation_id
                for item in result.candidates
                if item.unit_id in packed.included_unit_ids
                for obligation_id in item.matched_obligation_ids
            }
            required = decision.required_obligation_ids
            decision = SufficiencyDecisionV2(
                decision_id=decision.decision_id,
                status="partial",
                required_obligation_ids=required,
                covered_obligation_ids=tuple(item for item in required if item in covered),
                missing_obligation_ids=tuple(item for item in required if item not in covered),
                evidence_unit_ids=packed.included_unit_ids,
                reason_codes=("context_budget_exhausted",),
            )
            selected = packed.included_unit_ids
            reason_codes.append("context_budget_exhausted")
        return EngineSelection(
            status=decision.status,
            selected_unit_ids=selected,
            sufficiency=decision,
            plan=plan,
            excluded_evidence=tuple(
                {"evidence_id": unit_id, "reason": "context_budget"}
                for unit_id in packed.excluded_unit_ids
            ),
            action_constraints=derive_action_constraints(request.query, result, decision),
            reason_codes=tuple(reason_codes),
        )


def stored_manifest(
    store: object, request: ContextRequestV3, *, generation_id: str,
) -> AuthorizedManifest:
    """Build a content-free exact-scope manifest from canonical generation state."""
    row = store._conn.execute(
        """SELECT * FROM context_view_generations WHERE generation_id=?
           AND subject_id=? AND agent_id=? AND workspace_id=?
           AND state IN ('verified','active')""",
        (
            generation_id, request.scope.subject_id, request.scope.agent_id,
            request.scope.workspace_id,
        ),
    ).fetchone()
    if row is None:
        raise GovernanceViolation("derived generation is not authorized for this request")
    units = tuple(
        str(item["unit_id"])
        for item in store._conn.execute(
            """SELECT unit_id FROM context_evidence_units
               WHERE generation_id=? AND lifecycle='active' ORDER BY unit_id""",
            (generation_id,),
        ).fetchall()
    )
    digest = "sha256:" + sha256_hex("\n".join(units))
    return AuthorizedManifest(
        request_id=request.request_id, scope=request.scope,
        generation=request.generation, authorized_unit_ids=units,
        authority_sha256=digest,
    )


def load_stored_canonical(
    store: object, scope: AuthorityScope, generation_id: str,
    unit_ids: tuple[str, ...], canonical_generation: int,
) -> tuple[CanonicalEvidence, ...]:
    """Reload exact source bytes for final service-boundary revalidation."""
    values: list[CanonicalEvidence] = []
    for unit_id in unit_ids:
        row = store._conn.execute(
            """SELECT u.lifecycle, r.source_id, r.part_id, r.start_offset,
                      r.end_offset, r.source_sha256, p.content_bytes,
                      g.subject_id, g.agent_id, g.workspace_id
               FROM context_evidence_units u
               JOIN context_view_generations g USING(generation_id)
               JOIN context_unit_ranges ur
                 ON ur.generation_id=u.generation_id AND ur.unit_id=u.unit_id
               JOIN context_source_ranges r USING(range_id)
               JOIN context_source_parts p
                 ON p.source_id=r.source_id AND p.part_id=r.part_id
               WHERE u.generation_id=? AND u.unit_id=? ORDER BY ur.ordinal LIMIT 1""",
            (generation_id, unit_id),
        ).fetchone()
        if row is None:
            continue
        source_scope = AuthorityScope(
            str(row["subject_id"]), str(row["agent_id"]), str(row["workspace_id"])
        )
        start, end = int(row["start_offset"]), int(row["end_offset"])
        values.append(CanonicalEvidence(
            unit_id=unit_id, scope=source_scope, generation=canonical_generation,
            source_range=EvidenceRange(
                source_id=str(row["source_id"]), part_id=str(row["part_id"]),
                start=start, end=end, source_sha256=str(row["source_sha256"]),
            ),
            text=bytes(row["content_bytes"])[start:end].decode("utf-8", errors="replace"),
            lifecycle=str(row["lifecycle"]),
        ))
    return tuple(values)


class GovernanceViolation(RuntimeError):
    """The selected generation, scope or canonical lifecycle failed closed."""


@dataclass(frozen=True, slots=True)
class AuthorizedManifest:
    request_id: str
    scope: AuthorityScope
    generation: int
    authorized_unit_ids: tuple[str, ...]
    authority_sha256: str
    egress_allowed: bool = False

    def __post_init__(self) -> None:
        if not self.request_id or self.generation < 0:
            raise ValueError("authorized manifest identity is invalid")
        if len(self.authorized_unit_ids) != len(set(self.authorized_unit_ids)):
            raise ValueError("authorized manifest unit IDs must be unique")
        if not self.authority_sha256.startswith("sha256:"):
            raise ValueError("authorized manifest requires an authority digest")


@dataclass(frozen=True, slots=True)
class CanonicalEvidence:
    unit_id: str
    scope: AuthorityScope
    generation: int
    source_range: EvidenceRange
    text: str
    lifecycle: str = "active"


@dataclass(frozen=True, slots=True)
class EngineSelection:
    status: ContextStatus
    selected_unit_ids: tuple[str, ...]
    sufficiency: SufficiencyDecisionV2
    plan: QueryPlan
    navigation: NavigationReceipt | None = None
    excluded_evidence: tuple[dict[str, str], ...] = ()
    action_constraints: tuple[ActionConstraint, ...] = ()
    media_references: tuple[dict[str, str], ...] = ()
    reason_codes: tuple[str, ...] = ()
    egress_used: bool = False
    egress_provider: str | None = None


class ContextEngine(Protocol):
    def select(
        self, request: ContextRequestV3, manifest: AuthorizedManifest
    ) -> EngineSelection: ...


Authorize = Callable[[ContextRequestV3], AuthorizedManifest]
CanonicalLoad = Callable[[tuple[str, ...], int], tuple[CanonicalEvidence, ...]]
Audit = Callable[[ContextRequestV3, EngineSelection, tuple[CanonicalEvidence, ...]], str]


class ContextEngineService:
    def __init__(
        self,
        *,
        authorize: Authorize,
        load_canonical: CanonicalLoad,
        audit: Audit,
        expires_at: Callable[[], str],
    ) -> None:
        self._authorize = authorize
        self._load_canonical = load_canonical
        self._audit = audit
        self._expires_at = expires_at

    def prepare(
        self, request: ContextRequestV3, engine: ContextEngine
    ) -> ContextPackageV3:
        manifest = self._authorize(request)
        if (
            manifest.request_id != request.request_id
            or manifest.scope != request.scope
            or manifest.generation != request.generation
        ):
            raise GovernanceViolation("authorization manifest does not bind the request")

        selection = engine.select(request, manifest)
        if selection.status != selection.sufficiency.status:
            raise GovernanceViolation("engine selection and sufficiency statuses differ")
        if selection.egress_used and not manifest.egress_allowed:
            raise GovernanceViolation("engine used egress without authority")
        if selection.egress_used != bool(selection.egress_provider):
            raise GovernanceViolation("engine egress usage requires an exact provider identity")
        selected = tuple(selection.selected_unit_ids)
        if len(selected) != len(set(selected)):
            raise GovernanceViolation("engine returned duplicate evidence identifiers")
        if set(selected) - set(manifest.authorized_unit_ids):
            raise GovernanceViolation("engine selected evidence outside its authorized manifest")
        if set(selection.sufficiency.evidence_unit_ids) - set(selected):
            raise GovernanceViolation("sufficiency cites evidence outside the selection")
        required_plan_ids = {
            item.obligation_id for item in selection.plan.obligations if item.required
        }
        if required_plan_ids != set(selection.sufficiency.required_obligation_ids):
            raise GovernanceViolation("sufficiency does not cover the required query plan")
        if selection.status == "withheld_by_policy" and (
            selected
            or selection.excluded_evidence
            or selection.media_references
            or (
                selection.navigation is not None
                and (
                    selection.navigation.inspected_ranges
                    or selection.navigation.submitted_ranges
                )
            )
        ):
            raise GovernanceViolation("policy-withheld selection disclosed evidence metadata")

        canonical = self._load_canonical(selected, request.generation)
        if tuple(item.unit_id for item in canonical) != selected:
            raise GovernanceViolation("canonical reload did not return the exact selection")
        for item in canonical:
            if item.scope != request.scope:
                raise GovernanceViolation("canonical evidence scope changed after selection")
            if item.generation != request.generation:
                raise GovernanceViolation("canonical evidence generation changed after selection")
            if item.lifecycle != "active":
                raise GovernanceViolation("canonical evidence is no longer active")

        context = (
            "\n\n".join(item.text for item in canonical)
            if selection.status == "sufficient"
            else ""
        )
        if len(context.encode()) > request.budget.context_bytes:
            raise GovernanceViolation("canonical context exceeds the authorized budget")
        package = ContextPackageV3(
            context_id=request.context_id,
            scope=request.scope,
            profile_id=request.profile_id,
            generation=request.generation,
            expires_at=self._expires_at(),
            preparation_id=f"prepare:{request.request_id}",
            status=selection.status,
            context=context,
            context_sha256="sha256:" + sha256_hex(context),
            sufficiency=selection.sufficiency,
            selected_unit_ids=selected,
            selected_ranges=tuple(item.source_range for item in canonical),
            excluded_evidence=selection.excluded_evidence,
            plan=selection.plan,
            navigation=selection.navigation,
            budget=request.budget,
            audit_event_id="pending-audit",
            action_constraints=selection.action_constraints,
            media_references=selection.media_references,
            reason_codes=selection.reason_codes,
        )
        audit_event_id = self._audit(request, selection, canonical)
        if not audit_event_id:
            raise GovernanceViolation("audit boundary did not return an event identity")
        return replace(package, audit_event_id=audit_event_id)
