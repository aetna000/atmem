from __future__ import annotations

from dataclasses import replace
import json

import pytest

from atmem.context_engine.contracts import (
    ContextPackageV3,
    ContextRequestV3,
    EvidenceObligation,
    EvidenceRange,
    FormationReceiptV2,
    FormationRequestV2,
    NavigationReceipt,
    QueryPlan,
    SufficiencyDecisionV2,
)
from atmem.contracts.models import ActionConstraint, AuthorityScope, RetrievalBudget
from atmem.core.canonical import sha256_hex


def _scope() -> AuthorityScope:
    return AuthorityScope(subject_id="user-1", agent_id="agent-a", workspace_id="work-1")


def _range() -> EvidenceRange:
    return EvidenceRange(
        source_id="source-1",
        part_id="part-1",
        start=0,
        end=11,
        source_sha256="sha256:" + "1" * 64,
    )


def _plan() -> QueryPlan:
    return QueryPlan(
        plan_id="plan-1",
        query_sha256="sha256:" + "2" * 64,
        obligations=(
            EvidenceObligation(
                obligation_id="obligation-1",
                kind="subject_relation_value",
                entity="deployment room",
                relation_or_action="current value",
            ),
        ),
        pool_queries={"atomic_fact": ("deployment room",)},
        planner_identity="deterministic-v1",
        deterministic_fallback=True,
    )


def _package(status: str = "sufficient") -> ContextPackageV3:
    sufficient = status == "sufficient"
    evidence_ids = ("unit-1",) if sufficient else ()
    missing = () if sufficient else ("obligation-1",)
    conflicting = ("unit-2",) if status == "conflicted" else ()
    context = "room cobalt" if sufficient else ""
    source_range = _range()
    return ContextPackageV3(
        context_id="context-1",
        scope=_scope(),
        profile_id="context-fast",
        generation=3,
        expires_at="2026-10-01T12:00:00+00:00",
        preparation_id="prepare-1",
        status=status,
        context=context,
        context_sha256="sha256:" + sha256_hex(context),
        sufficiency=SufficiencyDecisionV2(
            decision_id="decision-1",
            status=status,
            required_obligation_ids=("obligation-1",),
            covered_obligation_ids=("obligation-1",) if sufficient else (),
            missing_obligation_ids=missing,
            evidence_unit_ids=evidence_ids,
            conflicting_unit_ids=conflicting,
        ),
        selected_unit_ids=evidence_ids,
        selected_ranges=(source_range,) if sufficient else (),
        excluded_evidence=(),
        plan=_plan(),
        navigation=(
            None
            if status == "withheld_by_policy"
            else NavigationReceipt(
                plan_id="plan-1",
                searched_views=("atomic_fact",),
                inspected_ranges=(source_range,),
                submitted_ranges=(source_range,) if sufficient else (),
                operations_used=1,
                bytes_used=11,
                elapsed_ms=2,
                exhausted=not sufficient,
            )
        ),
        budget=RetrievalBudget(),
        audit_event_id="audit-1",
    )


def test_context_package_v3_round_trips_canonically() -> None:
    package = _package()
    restored = ContextPackageV3.from_dict(json.loads(json.dumps(package.to_dict())))
    assert restored == package
    assert restored.canonical_bytes() == package.canonical_bytes()


def test_formation_v2_round_trips_and_keeps_loss_distinct() -> None:
    request = FormationRequestV2(
        formation_id="formation-1",
        episode_id="episode-1",
        scope=_scope(),
        profile_id="context-fast",
        source_generation=4,
    )
    assert FormationRequestV2.from_dict(
        json.loads(json.dumps(request.to_dict()))
    ) == request
    receipt = FormationReceiptV2(
        formation_id="formation-1",
        episode_id="episode-1",
        generation_id="generation-1",
        source_generation=4,
        producer_id="deterministic-v1",
        represented_ranges=(_range(),),
        loss_ranges=(),
        units_created=1,
        units_reconciled=0,
        units_rejected=0,
        storage_bytes_by_category={"atomic_fact": 64},
        processing_complete=True,
        representation_complete=True,
    )
    assert FormationReceiptV2.from_dict(
        json.loads(json.dumps(receipt.to_dict()))
    ) == receipt


def test_formation_v2_rejects_complete_representation_with_loss() -> None:
    with pytest.raises(ValueError, match="loss ranges"):
        FormationReceiptV2(
            formation_id="formation-1",
            episode_id="episode-1",
            generation_id="generation-1",
            source_generation=4,
            producer_id="deterministic-v1",
            represented_ranges=(),
            loss_ranges=(_range(),),
            units_created=0,
            units_reconciled=0,
            units_rejected=0,
            storage_bytes_by_category={},
            processing_complete=True,
            representation_complete=True,
        )


@pytest.mark.parametrize(
    "status,reason",
    [
        ("partial", "v3_partial"),
        ("conflicted", "v3_conflicted"),
        ("contradicted", "v3_contradicted"),
        ("stale", "v3_stale"),
        ("not_found_within_budget", "v3_not_found_within_budget"),
        ("withheld_by_policy", "v3_withheld_by_policy"),
    ],
)
def test_v3_to_v2_projection_fails_closed(status: str, reason: str) -> None:
    projected = _package(status).to_v2()
    assert projected.context == ""
    assert projected.record_ids == ()
    assert projected.sufficiency.status == "unsupported"
    assert reason in projected.reason_codes
    assert projected.to_v1().context == ""


def test_sufficient_v3_projection_preserves_only_representable_evidence() -> None:
    projected = _package().to_v2()
    assert projected.context == "room cobalt"
    assert projected.record_ids == ("unit-1",)
    assert projected.source_ids == ("source-1",)
    assert projected.sufficiency.status == "sufficient"


def test_v3_parser_rejects_unknown_fields_and_formats() -> None:
    payload = _package().to_dict()
    payload["answer"] = "cobalt"
    with pytest.raises(ValueError, match="unknown fields"):
        ContextPackageV3.from_dict(payload)
    payload = _package().to_dict()
    payload["format"] = "atmem-context-package-v4"
    with pytest.raises(ValueError, match="unsupported context package"):
        ContextPackageV3.from_dict(payload)
    payload = _package().to_dict()
    payload["status"] = "maybe"
    payload["sufficiency"]["status"] = "maybe"
    with pytest.raises(ValueError, match="unsupported V3 sufficiency"):
        ContextPackageV3.from_dict(payload)
    payload = _package().to_dict()
    del payload["generation"]
    with pytest.raises(ValueError, match="missing fields"):
        ContextPackageV3.from_dict(payload)


def test_non_sufficient_package_cannot_smuggle_context() -> None:
    package = _package("partial")
    with pytest.raises(ValueError, match="fail closed"):
        replace(
            package,
            context="unreviewed text",
            context_sha256="sha256:" + sha256_hex("unreviewed text"),
        )


def test_context_request_requires_known_profile_and_generation() -> None:
    request = ContextRequestV3(
        context_id="context-1",
        request_id="request-1",
        scope=_scope(),
        query="Where do deployments go?",
        profile_id="context-fast",
        mode="shadow",
        generation=2,
    )
    assert request.to_dict()["scope"]["agent_id"] == "agent-a"
    with pytest.raises(ValueError, match="generation"):
        replace(request, generation=-1)


def test_valid_v3_package_cannot_defer_compatibility_errors_to_v2() -> None:
    package = _package()
    with pytest.raises(ValueError, match="action constraints"):
        replace(
            package,
            action_constraints=(
                ActionConstraint(
                    subject="deployment",
                    applies_when="releasing",
                    source_ids=("source-2",),
                    validity="current",
                    required_action="notify",
                ),
            ),
        )
    with pytest.raises(ValueError, match="media references"):
        replace(
            package,
            media_references=(
                {"reference_id": "media-1", "adjacent_source_id": "source-2"},
            ),
        )
    with pytest.raises(ValueError, match="selected and excluded"):
        replace(
            package,
            excluded_evidence=(
                {"evidence_id": "unit-1", "reason": "budget"},
            ),
        )
    with pytest.raises(ValueError, match="expires_at"):
        replace(package, expires_at="tomorrow")


def test_context_engine_contracts_are_available_from_compatibility_namespace() -> None:
    from atmem.contracts import ContextPackageV3 as ExportedContextPackageV3

    assert ExportedContextPackageV3 is ContextPackageV3
