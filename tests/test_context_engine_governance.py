from __future__ import annotations

from dataclasses import replace

import pytest

from atmem.context_engine.contracts import (
    ContextRequestV3,
    EvidenceObligation,
    EvidenceRange,
    QueryPlan,
    NavigationReceipt,
    SufficiencyDecisionV2,
)
from atmem.context_engine.service import (
    AuthorizedManifest,
    CanonicalEvidence,
    ContextEngineService,
    EngineSelection,
    GovernanceViolation,
)
from atmem.context_engine.profiles import (
    EngineProfileState,
    initial_profile_state,
    load_profile_state,
    save_profile_state,
)
from atmem.contracts.models import AuthorityScope
from atmem.control.store import ControlStore


SCOPE = AuthorityScope(subject_id="user-1", agent_id="agent-a", workspace_id="work-1")
OTHER_SCOPE = AuthorityScope(subject_id="user-1", agent_id="agent-b", workspace_id="work-1")
SOURCE_RANGE = EvidenceRange(
    source_id="source-1",
    part_id="part-1",
    start=0,
    end=11,
    source_sha256="sha256:" + "1" * 64,
)


def _request() -> ContextRequestV3:
    return ContextRequestV3(
        context_id="context-1",
        request_id="request-1",
        scope=SCOPE,
        query="Where do deployments go?",
        profile_id="context-fast",
        mode="shadow",
        generation=3,
    )


def _selection(unit_ids: tuple[str, ...] = ("unit-1",)) -> EngineSelection:
    obligation = EvidenceObligation(
        obligation_id="obligation-1",
        kind="subject_relation_value",
        entity="deployment",
        relation_or_action="room",
    )
    plan = QueryPlan(
        plan_id="plan-1",
        query_sha256="sha256:" + "2" * 64,
        obligations=(obligation,),
        pool_queries={"atomic_fact": ("deployment room",)},
        planner_identity="deterministic-v1",
        deterministic_fallback=True,
    )
    return EngineSelection(
        status="sufficient",
        selected_unit_ids=unit_ids,
        sufficiency=SufficiencyDecisionV2(
            decision_id="decision-1",
            status="sufficient",
            required_obligation_ids=("obligation-1",),
            covered_obligation_ids=("obligation-1",),
            evidence_unit_ids=unit_ids,
        ),
        plan=plan,
    )


class Engine:
    def __init__(self, events: list[str], selection: EngineSelection | None = None) -> None:
        self.events = events
        self.selection = selection or _selection()
        self.manifest: AuthorizedManifest | None = None

    def select(self, request: ContextRequestV3, manifest: AuthorizedManifest) -> EngineSelection:
        self.events.append("engine")
        self.manifest = manifest
        return self.selection


def _harness(
    *, canonical_scope: AuthorityScope = SCOPE, lifecycle: str = "active",
    manifest_generation: int = 3,
) -> tuple[ContextEngineService, list[str]]:
    events: list[str] = []

    def authorize(request: ContextRequestV3) -> AuthorizedManifest:
        events.append("authorize")
        return AuthorizedManifest(
            request_id=request.request_id,
            scope=request.scope,
            generation=manifest_generation,
            authorized_unit_ids=("unit-1",),
            authority_sha256="sha256:" + "3" * 64,
        )

    def load(unit_ids: tuple[str, ...], generation: int) -> tuple[CanonicalEvidence, ...]:
        events.append("load")
        return tuple(
            CanonicalEvidence(
                unit_id=unit_id,
                scope=canonical_scope,
                generation=generation,
                source_range=SOURCE_RANGE,
                text="room cobalt",
                lifecycle=lifecycle,
            )
            for unit_id in unit_ids
        )

    def audit(*_args: object) -> str:
        events.append("audit")
        return "audit-1"

    service = ContextEngineService(
        authorize=authorize,
        load_canonical=load,
        audit=audit,
        expires_at=lambda: "2026-10-01T12:00:00+00:00",
    )
    return service, events


def test_authority_precedes_engine_and_canonical_revalidation_precedes_audit() -> None:
    service, events = _harness()
    engine = Engine(events)
    package = service.prepare(_request(), engine)
    assert events == ["authorize", "engine", "load", "audit"]
    assert package.context == "room cobalt"
    assert package.audit_event_id == "audit-1"
    assert engine.manifest is not None
    assert not hasattr(engine.manifest, "text")


def test_manifest_generation_mismatch_stops_before_intelligence() -> None:
    service, events = _harness(manifest_generation=2)
    with pytest.raises(GovernanceViolation, match="bind the request"):
        service.prepare(_request(), Engine(events))
    assert events == ["authorize"]


def test_engine_cannot_select_outside_authorized_manifest() -> None:
    service, events = _harness()
    with pytest.raises(GovernanceViolation, match="outside"):
        service.prepare(_request(), Engine(events, _selection(("unit-2",))))
    assert events == ["authorize", "engine"]


def test_engine_cannot_use_unapproved_egress() -> None:
    service, events = _harness()
    selection = replace(
        _selection(), egress_used=True, egress_provider="remote-planner"
    )
    with pytest.raises(GovernanceViolation, match="egress without authority"):
        service.prepare(_request(), Engine(events, selection))
    assert events == ["authorize", "engine"]


def test_policy_withheld_cannot_disclose_ids_ranges_or_navigation() -> None:
    service, events = _harness()
    base = _selection()
    withheld = replace(
        base,
        status="withheld_by_policy",
        selected_unit_ids=(),
        sufficiency=SufficiencyDecisionV2(
            decision_id="decision-1",
            status="withheld_by_policy",
            required_obligation_ids=("obligation-1",),
            covered_obligation_ids=(),
            missing_obligation_ids=("obligation-1",),
            evidence_unit_ids=(),
        ),
        navigation=NavigationReceipt(
            plan_id="plan-1",
            searched_views=("atomic_fact",),
            inspected_ranges=(SOURCE_RANGE,),
            submitted_ranges=(),
            operations_used=1,
            bytes_used=11,
            elapsed_ms=1,
            exhausted=False,
        ),
    )
    with pytest.raises(GovernanceViolation, match="disclosed evidence metadata"):
        service.prepare(_request(), Engine(events, withheld))
    assert events == ["authorize", "engine"]


def test_valid_policy_withheld_package_is_empty_and_audited() -> None:
    service, events = _harness()
    base = _selection()
    withheld = replace(
        base,
        status="withheld_by_policy",
        selected_unit_ids=(),
        sufficiency=SufficiencyDecisionV2(
            decision_id="decision-1",
            status="withheld_by_policy",
            required_obligation_ids=("obligation-1",),
            covered_obligation_ids=(),
            missing_obligation_ids=("obligation-1",),
            evidence_unit_ids=(),
        ),
    )
    package = service.prepare(_request(), Engine(events, withheld))
    assert package.context == ""
    assert package.selected_unit_ids == ()
    assert package.selected_ranges == ()
    assert events == ["authorize", "engine", "load", "audit"]


def test_required_plan_obligations_cannot_be_omitted() -> None:
    service, events = _harness()
    base = _selection()
    second = EvidenceObligation(
        obligation_id="obligation-2",
        kind="comparison_side",
        entity="south",
    )
    plan = replace(base.plan, obligations=(*base.plan.obligations, second))
    with pytest.raises(GovernanceViolation, match="required query plan"):
        service.prepare(_request(), Engine(events, replace(base, plan=plan)))
    assert events == ["authorize", "engine"]


def test_budget_failure_occurs_before_audit() -> None:
    service, events = _harness()
    request = replace(
        _request(), budget=replace(_request().budget, context_bytes=3)
    )
    with pytest.raises(GovernanceViolation, match="authorized budget"):
        service.prepare(request, Engine(events))
    assert events == ["authorize", "engine", "load"]


@pytest.mark.parametrize(
    "selection,reason",
    [
        (replace(_selection(), status="partial"), "statuses differ"),
        (_selection(("unit-1", "unit-1")), "duplicate"),
        (
            replace(
                _selection(),
                sufficiency=replace(
                    _selection().sufficiency,
                    evidence_unit_ids=("unit-2",),
                ),
            ),
            "outside the selection",
        ),
    ],
)
def test_malformed_engine_selections_fail_before_canonical_load(
    selection: EngineSelection, reason: str
) -> None:
    service, events = _harness()
    with pytest.raises(GovernanceViolation, match=reason):
        service.prepare(_request(), Engine(events, selection))
    assert events == ["authorize", "engine"]


@pytest.mark.parametrize(
    "scope,lifecycle,reason",
    [
        (OTHER_SCOPE, "active", "scope changed"),
        (SCOPE, "deleted", "no longer active"),
    ],
)
def test_canonical_scope_and_lifecycle_are_revalidated(
    scope: AuthorityScope, lifecycle: str, reason: str
) -> None:
    service, events = _harness(canonical_scope=scope, lifecycle=lifecycle)
    with pytest.raises(GovernanceViolation, match=reason):
        service.prepare(_request(), Engine(events))
    assert events == ["authorize", "engine", "load"]


def test_request_scope_change_cannot_receive_other_agent_canonical_evidence() -> None:
    service, events = _harness()
    changed = replace(_request(), scope=OTHER_SCOPE)
    with pytest.raises(GovernanceViolation, match="scope changed"):
        service.prepare(changed, Engine(events))
    assert events == ["authorize", "engine", "load"]


def test_upgrade_defaults_to_legacy_active_and_sampled_v3_shadow(tmp_path) -> None:
    state = initial_profile_state(
        fresh_install=False, context_fast_qualified=True, generation=7
    )
    assert state.active_profile == "legacy-control"
    assert state.shadow_profile == "context-fast"
    assert state.shadow_sample_rate == 0.1
    store = ControlStore(tmp_path / "control.db")
    try:
        store.create_migration("migration-1", "generic", "user-1")
        save_profile_state(store, "migration-1", state)
        assert load_profile_state(store, "migration-1") == state
    finally:
        store.close()


def test_fresh_install_activates_fast_only_after_local_qualification() -> None:
    unqualified = initial_profile_state(
        fresh_install=True, context_fast_qualified=False
    )
    qualified = initial_profile_state(
        fresh_install=True, context_fast_qualified=True
    )
    assert unqualified.active_profile == "legacy-control"
    assert qualified.active_profile == "context-fast"
    with pytest.raises(ValueError, match="locally qualified"):
        EngineProfileState(
            active_profile="context-fast",
            shadow_profile=None,
            shadow_sample_rate=0.0,
            generation=1,
            qualified_profiles=("legacy-control",),
        )
