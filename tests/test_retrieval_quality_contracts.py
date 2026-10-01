from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from importlib.resources import files

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from atmem.contracts import (
    ActionConstraint,
    AuthorityScope,
    ContextPackageV2,
    EpisodeIngestRequest,
    EpisodePart,
    EvidenceNeighborhood,
    EvidencePath,
    FormationReceipt,
    InformationNeed,
    RetrievalBudget,
    SufficiencyDecision,
)
from atmem.core.canonical import sha256_hex
from atmem.extract import (
    AtomicFactPayload,
    DurableRulePayload,
    EnvironmentStatePayload,
    ExtractionProposal,
    FailureGotchaPayload,
    MemoryUnit,
    MemoryUnitKind,
    MemoryClass,
    Polarity,
    PremiseConstraintPayload,
    ProcedurePayload,
    ProcedureStep,
    ProposalAction,
    ProposalEvidence,
    StateTransitionPayload,
)


SCOPE = AuthorityScope(subject_id="person-1", agent_id="agent-1", workspace_id="work-1")
SOURCE_DIGEST = "sha256:" + "1" * 64
EXCERPT_DIGEST = "sha256:" + "2" * 64
EVIDENCE = (
    ProposalEvidence(
        source_id="source-1",
        source_sha256=SOURCE_DIGEST,
        start_offset=0,
        end_offset=10,
        excerpt_sha256=EXCERPT_DIGEST,
    ),
)
SCHEMA_ROOT = Path(__file__).parents[1] / "atmem/schemas"


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        (MemoryUnitKind.ATOMIC_FACT, AtomicFactPayload("user", "age", "45")),
        (
            MemoryUnitKind.DURABLE_RULE,
            DurableRulePayload("ordering food", prohibited_action="include peanuts"),
        ),
        (
            MemoryUnitKind.ENVIRONMENT_STATE,
            EnvironmentStatePayload("service", "port", "8080"),
        ),
        (
            MemoryUnitKind.STATE_TRANSITION,
            StateTransitionPayload("document", "status", "draft", "upload", "stored"),
        ),
        (
            MemoryUnitKind.PROCEDURE,
            ProcedurePayload(
                "publish release",
                (ProcedureStep(1, "run tests"), ProcedureStep(2, "publish", "approved")),
            ),
        ),
        (
            MemoryUnitKind.FAILURE_GOTCHA,
            FailureGotchaPayload("timeout", "acceptance uncertain", "reconcile receipt"),
        ),
        (
            MemoryUnitKind.PREMISE_CONSTRAINT,
            PremiseConstraintPayload("GPU is configured", Polarity.NEGATIVE),
        ),
    ],
)
def test_all_typed_units_are_source_linked_and_canonical(kind, payload) -> None:
    unit = MemoryUnit(
        unit_id="unit-1",
        formation_id="formation-1",
        kind=kind,
        scope=SCOPE,
        payload=payload,
        evidence=EVIDENCE,
        confidence=1.0,
    )
    wire = unit.to_dict()
    assert wire["kind"] == kind.value
    assert wire["evidence"][0]["source_id"] == "source-1"
    assert json.loads(json.dumps(wire))["payload"]


def test_memory_unit_identity_ignores_operational_ids_but_preserves_polarity() -> None:
    unit = MemoryUnit(
        unit_id="unit-1",
        formation_id="formation-1",
        kind=MemoryUnitKind.ATOMIC_FACT,
        scope=SCOPE,
        payload=AtomicFactPayload("user", "allergy", "peanuts", Polarity.NEGATIVE),
        evidence=EVIDENCE,
        confidence=0.9,
    )
    replay = replace(unit, unit_id="unit-2", formation_id="formation-2", confidence=0.8)
    positive = replace(unit, payload=replace(unit.payload, polarity=Polarity.POSITIVE))
    assert replay.semantic_identity() == unit.semantic_identity()
    assert positive.semantic_identity() != unit.semantic_identity()
    assert unit.to_dict()["payload"]["polarity"] == "negative"


def test_legacy_v2_proposal_digest_is_unchanged_when_no_unit_is_present() -> None:
    proposal = ExtractionProposal(
        proposal_id="proposal-1",
        idempotency_key="key-1",
        scope=SCOPE,
        action=ProposalAction.ADD,
        memory_class=MemoryClass.DURABLE_FACT,
        confidence=0.9,
        reason_codes=("rule_extracted",),
        evidence=EVIDENCE,
        fact="I am 45.",
        fact_key="age",
    )
    assert "unit" not in proposal.to_dict()
    assert proposal.digest() == "sha256:df14fe187dd77b9bbba2f0b099d7416ae1882de3306cb84a1c4c5403cf2cafa7"


def test_typed_proposal_cannot_bypass_screened_fact_or_proposal_evidence() -> None:
    unit = MemoryUnit(
        unit_id="unit-1",
        formation_id="formation-1",
        kind=MemoryUnitKind.ATOMIC_FACT,
        scope=SCOPE,
        payload=AtomicFactPayload("user", "age", "45"),
        evidence=EVIDENCE,
        confidence=1.0,
    )
    with pytest.raises(ValueError, match="screened fact"):
        ExtractionProposal(
            proposal_id="proposal-1",
            idempotency_key="key-1",
            scope=SCOPE,
            action=ProposalAction.ADD,
            memory_class=MemoryClass.DURABLE_FACT,
            confidence=1.0,
            reason_codes=("typed",),
            evidence=EVIDENCE,
            unit=unit,
        )
    other_evidence = replace(EVIDENCE[0], source_id="source-2")
    with pytest.raises(ValueError, match="included in proposal evidence"):
        ExtractionProposal(
            proposal_id="proposal-1",
            idempotency_key="key-1",
            scope=SCOPE,
            action=ProposalAction.ADD,
            memory_class=MemoryClass.DURABLE_FACT,
            confidence=1.0,
            reason_codes=("typed",),
            evidence=(other_evidence,),
            fact="I am 45.",
            unit=unit,
        )
    active = replace(unit, lifecycle="active")
    with pytest.raises(ValueError, match="proposed lifecycle"):
        ExtractionProposal(
            proposal_id="proposal-1",
            idempotency_key="key-1",
            scope=SCOPE,
            action=ProposalAction.ADD,
            memory_class=MemoryClass.DURABLE_FACT,
            confidence=1.0,
            reason_codes=("typed",),
            evidence=EVIDENCE,
            fact="I am 45.",
            unit=active,
        )


def test_typed_unit_and_proposal_round_trip_without_losing_structure() -> None:
    unit = MemoryUnit(
        unit_id="unit-1",
        formation_id="formation-1",
        kind=MemoryUnitKind.PROCEDURE,
        scope=SCOPE,
        payload=ProcedurePayload(
            "release",
            (ProcedureStep(1, "test"), ProcedureStep(2, "publish", "approved")),
            prerequisites=("clean tree",),
            completion_evidence=("release receipt",),
            failure_conditions=("tests fail",),
        ),
        evidence=EVIDENCE,
        confidence=0.9,
    )
    assert MemoryUnit.from_dict(unit.to_dict()).to_dict() == unit.to_dict()
    proposal = ExtractionProposal(
        proposal_id="proposal-1",
        idempotency_key="key-1",
        scope=SCOPE,
        action=ProposalAction.ADD,
        memory_class=MemoryClass.PROCEDURE,
        confidence=0.9,
        reason_codes=("typed",),
        evidence=EVIDENCE,
        fact="Test, then publish after approval.",
        unit=unit,
    )
    assert ExtractionProposal.from_dict(proposal.to_dict()).to_dict() == proposal.to_dict()


def test_procedure_order_and_temporal_order_fail_closed() -> None:
    with pytest.raises(ValueError, match="consecutive"):
        ProcedurePayload("release", (ProcedureStep(2, "publish"),))
    with pytest.raises(ValueError, match="valid_until"):
        MemoryUnit(
            unit_id="unit-1",
            formation_id="formation-1",
            kind=MemoryUnitKind.ENVIRONMENT_STATE,
            scope=SCOPE,
            payload=EnvironmentStatePayload("service", "state", "ready"),
            evidence=EVIDENCE,
            confidence=1.0,
            valid_from="2026-09-28T10:00:00Z",
            valid_until="2026-09-28T09:00:00Z",
        )
    equivalent = MemoryUnit(
        unit_id="unit-1",
        formation_id="formation-1",
        kind=MemoryUnitKind.ENVIRONMENT_STATE,
        scope=SCOPE,
        payload=EnvironmentStatePayload("service", "state", "ready"),
        evidence=EVIDENCE,
        confidence=1.0,
        valid_from="2026-09-28T10:00:00+10:00",
        valid_until="2026-09-28T01:00:00Z",
    )
    same_in_utc = replace(equivalent, valid_from="2026-09-28T00:00:00Z")
    assert equivalent.semantic_identity() == same_in_utc.semantic_identity()


def test_episode_ingest_is_lossless_ordered_source_capture_evolution() -> None:
    episode = EpisodeIngestRequest(
        episode_id="episode-1",
        idempotency_key="episode-key-1",
        scope=SCOPE,
        parts=(
            EpisodePart(
                "part-1", 0, "text", "user_message", content="I am 45.",
                content_sha256=f"sha256:{sha256_hex('I am 45.')}",
            ),
            EpisodePart(
                "part-2", 1, "media_reference", "document", reference_id="artifact-1",
                reference_sha256="sha256:" + "3" * 64,
            ),
        ),
    )
    assert episode.source_capture_format == "atmem-source-capture-request-v1"
    assert [part["ordinal"] for part in episode.to_dict()["parts"]] == [0, 1]
    with pytest.raises(ValueError, match="consecutive"):
        replace(episode, parts=(replace(episode.parts[0], ordinal=1),))
    with pytest.raises(ValueError, match="stronger"):
        replace(
            episode,
            binding_method="operator_authenticated",
            binding_assurance="verified_by_atmem",
        )


def test_budget_neighborhood_sufficiency_and_v1_projection_are_deterministic() -> None:
    budget = RetrievalBudget(
        candidates_per_channel=20, total_candidates=40, graph_visits=20
    )
    assert budget.to_dict()["total_candidates"] == 40
    need = InformationNeed(
        need_id="need-1",
        type="rule_application",
        entities=("deployment",),
        relation_or_action="post update",
        required_slots=("condition", "required_action", "source"),
    )
    neighborhood = EvidenceNeighborhood(
        neighborhood_id="neighbors-1",
        need_id=need.need_id,
        seed_record_ids=("record-1",),
        paths=(
            EvidencePath("record-1", "record-1", (), 0, "seed"),
            EvidencePath("record-1", "record-2", ("rule_condition",), 1, "condition"),
        ),
        selected_record_ids=("record-1", "record-2"),
        visited_count=2,
        max_depth=1,
        truncated=False,
    )
    decision = SufficiencyDecision(
        decision_id="decision-1",
        need_id=need.need_id,
        status="sufficient",
        required_slots=need.required_slots,
        covered_slots=need.required_slots,
        missing_slots=(),
        evidence_ids=neighborhood.selected_record_ids,
    )
    text = "Deployment updates must be posted to #eng-releases."
    package = ContextPackageV2(
        context_id="context-1",
        scope=SCOPE,
        record_ids=neighborhood.selected_record_ids,
        context=text,
        context_sha256=f"sha256:{sha256_hex(text)}",
        serializer_version="context-v2-test",
        generation=1,
        expires_at="2026-09-29T00:00:00Z",
        preparation_id="preparation-1",
        profile_id="procedure-action-v1",
        need=need,
        sufficiency=decision,
        source_ids=("source-1",),
        budget=budget,
        selected_units=({"unit_id": "unit-1", "kind": "durable_rule"},),
        provenance=({"record_id": "record-1", "source_id": "source-1"},),
        excluded_evidence_ids=(),
        action_constraints=(
            ActionConstraint(
                subject="deployment update",
                applies_when="release status is communicated",
                required_action="post",
                target="#eng-releases",
                source_ids=("source-1",),
                validity="current",
            ),
        ),
    )
    first = package.to_v1()
    second = package.to_v1()
    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.record_ids == package.record_ids
    assert first.context_sha256 == package.context_sha256
    assert package.projected_support_class() == "direct_support"
    schema_paths = list((SCHEMA_ROOT / "v1").glob("*.json")) + list(
        (SCHEMA_ROOT / "v2").glob("*.json")
    )
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in schema_paths]
    schemas = [schema for schema in schemas if "$id" in schema]
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    context_schema = next(
        schema for schema in schemas if schema["$id"].endswith("/v2/context-package.json")
    )
    Draft202012Validator(context_schema, registry=registry).validate(
        json.loads(package.canonical_bytes())
    )
    partial = replace(
        package,
        action_constraints=(),
        sufficiency=replace(
            decision,
            status="partial",
            covered_slots=("condition", "source"),
            missing_slots=("required_action",),
        ),
    )
    assert partial.projected_support_class() == "no_useful_memory"
    assert partial.projected_support_class(background_allowed=True) == "background_context"
    assert partial.to_v1().record_ids == ()
    assert partial.to_v1().context == ""
    assert partial.to_v1().serializer_version == "atmem-context-utf8-v1"


def test_formation_receipt_keeps_loss_visible() -> None:
    receipt = FormationReceipt(
        formation_id="formation-1",
        episode_id="episode-1",
        source_ids=("source-1",),
        source_events_observed=2,
        proposals_by_kind={"atomic_fact": 1},
        admitted=1,
        withheld=0,
        rejected=0,
        unsupported_parts=("part-2",),
        complete=False,
        reason_codes=("media_processor_unavailable",),
    )
    assert receipt.to_dict()["unsupported_parts"] == ("part-2",)


def test_sufficiency_rejects_inconsistent_slot_claims() -> None:
    with pytest.raises(ValueError, match="both covered and missing"):
        SufficiencyDecision(
            decision_id="decision-1",
            need_id="need-1",
            status="partial",
            required_slots=("value",),
            covered_slots=("value",),
            missing_slots=("value",),
            evidence_ids=("record-1",),
        )
    with pytest.raises(ValueError, match="supporting evidence"):
        SufficiencyDecision(
            decision_id="decision-1",
            need_id="need-1",
            status="sufficient",
            required_slots=("value",),
            covered_slots=("value",),
            missing_slots=(),
            evidence_ids=(),
        )


def test_runtime_enums_and_budget_bounds_fail_closed() -> None:
    with pytest.raises(ValueError, match="information need type"):
        InformationNeed(need_id="need-1", type="static-environment", required_slots=("value",))
    with pytest.raises(ValueError, match="non-negative integers"):
        RetrievalBudget(total_candidates=True)
    with pytest.raises(ValueError, match="per-channel"):
        RetrievalBudget(candidates_per_channel=51, total_candidates=50)


def test_evidence_neighborhood_rejects_unbounded_or_unselected_paths() -> None:
    with pytest.raises(ValueError, match="outside the neighborhood"):
        EvidenceNeighborhood(
            neighborhood_id="neighbors-1",
            need_id="need-1",
            seed_record_ids=("record-1",),
            paths=(EvidencePath("other", "record-2", ("next",), 1, "adjacent"),),
            selected_record_ids=("record-1", "record-2"),
            visited_count=2,
            max_depth=1,
            truncated=False,
        )


def test_typed_units_reject_storage_boundary_type_drift() -> None:
    unit = MemoryUnit(
        unit_id="unit-1",
        formation_id="formation-1",
        kind=MemoryUnitKind.ATOMIC_FACT,
        scope=SCOPE,
        payload=AtomicFactPayload("user", "age", "45"),
        evidence=EVIDENCE,
        confidence=1.0,
    )
    wire = unit.to_dict()
    wire["confidence"] = "1.0"
    with pytest.raises(ValueError, match="confidence"):
        MemoryUnit.from_dict(wire)
    wire = unit.to_dict()
    wire["format"] = "atmem-memory-unit-v3"
    with pytest.raises(ValueError, match="format"):
        MemoryUnit.from_dict(wire)
    with pytest.raises(ValueError, match="unknown fields"):
        MemoryUnit.from_dict({**unit.to_dict(), "unreviewed": True})
    with pytest.raises(ValueError, match="unique"):
        replace(unit, evidence=(EVIDENCE[0], EVIDENCE[0]))
    with pytest.raises(ValueError, match="positive ordinal"):
        ProcedureStep(True, "Do not accept booleans as ordinals")


def test_evidence_neighborhood_requires_a_path_for_every_selected_record() -> None:
    with pytest.raises(ValueError, match="one evidence path"):
        EvidenceNeighborhood(
            neighborhood_id="neighbors-1",
            need_id="need-1",
            seed_record_ids=("record-1",),
            paths=(EvidencePath("record-1", "record-1", (), 0, "seed"),),
            selected_record_ids=("record-1", "record-2"),
            visited_count=2,
            max_depth=1,
            truncated=False,
        )


def test_new_json_schemas_are_valid_and_forward_compatible() -> None:
    paths = [
        SCHEMA_ROOT / "v1/episode-ingest.json",
        SCHEMA_ROOT / "v1/formation-receipt.json",
        SCHEMA_ROOT / "v1/information-need.json",
        SCHEMA_ROOT / "v1/retrieval-budget.json",
        SCHEMA_ROOT / "v1/evidence-neighborhood.json",
        SCHEMA_ROOT / "v1/sufficiency-decision.json",
        SCHEMA_ROOT / "v2/memory-unit.json",
        SCHEMA_ROOT / "v2/context-package.json",
    ]
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    scope = json.loads((SCHEMA_ROOT / "v1/scope.json").read_text(encoding="utf-8"))
    for schema in [scope, *schemas]:
        Draft202012Validator.check_schema(schema)
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in [scope, *schemas]
    )
    budget = RetrievalBudget().to_dict()
    budget["future_optional_limit"] = 3
    Draft202012Validator(schemas[3], registry=registry).validate(budget)
    episode = EpisodeIngestRequest(
        episode_id="episode-1",
        idempotency_key="key-1",
        scope=SCOPE,
        parts=(
            EpisodePart(
                "part-1", 0, "text", "user_message", content="I am 45.",
                content_sha256=f"sha256:{sha256_hex('I am 45.')}",
            ),
        ),
    )
    Draft202012Validator(schemas[0], registry=registry).validate(
        json.loads(episode.canonical_bytes())
    )
    unit = MemoryUnit(
        unit_id="unit-1",
        formation_id="formation-1",
        kind=MemoryUnitKind.ATOMIC_FACT,
        scope=SCOPE,
        payload=AtomicFactPayload("user", "age", "45"),
        evidence=EVIDENCE,
        confidence=1.0,
    )
    Draft202012Validator(schemas[6], registry=registry).validate(
        json.loads(json.dumps(unit.to_dict()))
    )
    mismatched = unit.to_dict()
    mismatched["kind"] = "procedure"
    with pytest.raises(ValidationError):
        Draft202012Validator(schemas[6], registry=registry).validate(
            json.loads(json.dumps(mismatched))
        )


def test_v2_schemas_are_declared_as_installed_package_data() -> None:
    package_config = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert '"atmem.schemas" = ["v1/*.json", "v2/*.json"]' in package_config
    schema_root = files("atmem.schemas")
    assert schema_root.joinpath("v2/memory-unit.json").is_file()
    assert schema_root.joinpath("v2/context-package.json").is_file()


def test_information_need_schema_rejects_benchmark_vocabulary() -> None:
    schema = json.loads((SCHEMA_ROOT / "v1/information-need.json").read_text(encoding="utf-8"))
    bad = InformationNeed(
        need_id="need-1",
        type="exact_fact",
        required_slots=("value",),
    ).to_dict()
    bad["type"] = "static-environment"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(bad)


def test_product_runtime_has_no_benchmark_ability_or_harness_dependency() -> None:
    runtime_roots = [
        "extract", "retrieve", "service", "contracts", "evidence", "mcp",
        "adapters", "control", "store", "schemas",
    ]
    forbidden = (
        "static-environment",
        "dynamic-environment",
        "errors-gotchas",
        "procedure-abs",
        "longmemeval-v2",
        "dolphinbench",
        "research.production_benchmarks",
    )
    violations: list[str] = []
    package_root = Path(__file__).parents[1] / "atmem"
    for root in runtime_roots:
        root_path = package_root / root
        paths = [root_path] if root_path.is_file() else [
            path for path in root_path.rglob("*") if path.suffix in {".py", ".json"}
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8").casefold()
            for term in forbidden:
                if term in text:
                    violations.append(f"{path.relative_to(package_root)}:{term}")
    memory_module = package_root / "memory.py"
    memory_text = memory_module.read_text(encoding="utf-8").casefold()
    for term in forbidden:
        if term in memory_text:
            violations.append(f"memory.py:{term}")
    assert violations == []
