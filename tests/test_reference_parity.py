from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from research.reference_parity import (
    BaselineResult,
    CaseEvidenceResult,
    CassetteEnvelope,
    NormalizedRange,
    ResourceCard,
    compare_candidate,
    normalize_evidence,
    normalizer_identity,
)
from research.reference_parity.adapters import (
    AgentRunbookROfflineAdapter,
    AtMemLegacyAdapter,
    Mem0OssAdapter,
)
from research.reference_parity.adapters.agentrunbook import (
    AGENTRUNBOOK_OFFLINE_CONFIG_SHA256,
)
from research.reference_parity.adapters.atmem import ATMEM_LEGACY_CONFIG_SHA256
from research.reference_parity.adapters.mem0 import MEM0_OFFLINE_CONFIG_SHA256
from research.reference_parity.runner import load_corpus, run


def _result(system: str, passed: int) -> BaselineResult:
    return BaselineResult(
        benchmark="longmemeval-v2",
        system=system,
        sample_id="pilot-v1",
        sample_size=20,
        passed=passed,
        primary_score=passed / 20,
        source_revision="abc",
        configuration_sha256="sha256:def",
        model="reader-v1",
    )


def test_comparison_reports_relative_and_absolute_improvement() -> None:
    result = compare_candidate(_result("atmem", 12), _result("reference", 10))
    assert result["parity"] is True
    assert result["target_met"] is True
    assert result["absolute_point_delta"] == pytest.approx(10.0)
    assert result["relative_delta"] == pytest.approx(0.2)


def test_comparison_rejects_different_samples() -> None:
    reference = _result("reference", 10)
    candidate = BaselineResult(
        benchmark="longmemeval-v2", system="atmem", sample_id="other",
        sample_size=20, passed=12, primary_score=0.6, source_revision="abc",
        configuration_sha256="sha256:def", model="reader-v1",
    )
    with pytest.raises(ValueError, match="same benchmark and frozen sample"):
        compare_candidate(candidate, reference)


def test_pinned_reference_manifest_and_baseline_are_loadable() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = json.loads(
        (root / "research/reference_parity/sources.json").read_text()
    )
    baseline = json.loads(
        (root / "benchmarks/retrieval_quality/baselines/reference-parity-v1.json").read_text()
    )
    assert sources["systems"]["agentrunbook"]["commit"] == (
        "2cc8c540bdb87fe6761629b585e727e1c4704520"
    )
    assert baseline["longmemeval_v2"]["sample_size"] == 14
    assert baseline["dolphinbench"]["sample_size"] == 18


def test_neutral_corpus_has_disjoint_development_and_sealed_holdout() -> None:
    root = Path(__file__).resolve().parents[1]
    corpus = json.loads(
        (root / "research/reference_parity/fixtures/minimal-evidence-v1.json").read_text()
    )
    development = {case["id"] for case in corpus["cases"] if case["split"] == "development"}
    holdout = {case["id"] for case in corpus["cases"] if case["split"] == "holdout"}
    assert development
    assert holdout
    assert development.isdisjoint(holdout)
    assert corpus["normalizer"] == normalizer_identity()
    categories = {case["category"] for case in corpus["cases"]}
    assert {
        "exact_fact", "correction", "comparison", "negative_premise",
        "state_transition", "procedure", "failure_gotcha", "conflict",
        "temporal", "tenancy",
    } <= categories
    for case in corpus["cases"]:
        source_by_id = {source["id"]: source for source in case["sources"]}
        for evidence in case["minimal_evidence"]:
            assert evidence["quote"] in source_by_id[evidence["source_id"]]["text"]


def test_normalizer_gives_equal_credit_to_ranges_ids_and_quotes() -> None:
    sources = [{"id": "s1", "text": "North exports JSON Lines."}]
    expected = (NormalizedRange("s1", 0, 25),)
    assert normalize_evidence([{"source_id": "s1", "start": 0, "end": 25}], sources) == expected
    assert normalize_evidence([{"source_id": "s1", "quote": "North exports JSON Lines."}], sources) == expected
    assert normalize_evidence(["North exports JSON Lines."], sources) == expected


def test_normalizer_refuses_ambiguous_or_unverifiable_prose() -> None:
    sources = [
        {"id": "s1", "text": "Port 7412 is active."},
        {"id": "s2", "text": "Port 7412 is active."},
    ]
    assert normalize_evidence(["Port 7412 is active."], sources) == ()
    assert normalize_evidence(["The answer is 7412."], sources) == ()


def test_context_engine_protocol_has_complete_symmetric_resource_cards() -> None:
    root = Path(__file__).resolve().parents[1]
    protocol = json.loads(
        (root / "benchmarks/retrieval_quality/protocols/2.3.8-context-engine.yaml").read_text()
    )
    assert protocol["arm_policy"]["same_repetitions_for_every_arm"] is True
    assert protocol["arm_policy"]["best_of_selection"] is False
    assert protocol["splits"]["longmemeval_confirmation"]["inspection_resets_confirmation_status"] is True
    assert protocol["splits"]["dolphin_full"]["non_development_count"] == 582
    cards = {name: ResourceCard.from_mapping(value) for name, value in protocol["arms"].items()}
    assert set(cards) == {
        "atmem-context-navigate", "agentrunbook-c-v2", "agentrunbook-r", "mem0-oss"
    }
    assert {card.reader for card in cards.values()} == {"shared reader model"}
    assert {card.judge for card in cards.values()} == {"shared judge"}


def test_reference_source_manifest_binds_protocol_corpus_and_normalizer() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = json.loads((root / "research/reference_parity/sources.json").read_text())
    protocol = root / sources["protocol"]["path"]
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == sources["protocol"]["sha256"]
    protocol_data = json.loads(protocol.read_text())
    corpus = root / protocol_data["reference_corpus"]["path"]
    normalizer = root / "research/reference_parity/normalizer.py"
    assert hashlib.sha256(corpus.read_bytes()).hexdigest() == protocol_data["reference_corpus"]["sha256"]
    assert hashlib.sha256(normalizer.read_bytes()).hexdigest() == protocol_data["reference_corpus"]["normalizer_sha256"]
    assert sources["systems"]["atmem"]["reader_free_legacy_config_sha256"] == ATMEM_LEGACY_CONFIG_SHA256
    assert sources["systems"]["mem0-oss"]["reader_free_raw_offline_config_sha256"] == MEM0_OFFLINE_CONFIG_SHA256
    assert sources["systems"]["agentrunbook"]["configurations"]["reader-free-index-offline"] == AGENTRUNBOOK_OFFLINE_CONFIG_SHA256


def test_case_result_and_encrypted_cassette_contracts_fail_closed() -> None:
    result = CaseEvidenceResult(
        system="atmem",
        case_id="exact-fact-d",
        split="development",
        status="sufficient",
        selected_ranges=(("s1", 0, 10),),
        forbidden_source_ids=(),
        elapsed_ms=1.5,
        configuration_sha256="sha256:" + "1" * 64,
    )
    assert result.to_dict()["format"] == "atmem-reference-case-result-v1"
    CassetteEnvelope(
        provider="runpod",
        model_revision="model@revision",
        request_sha256="sha256:" + "2" * 64,
        response_sha256="sha256:" + "3" * 64,
        encrypted_external_path="MEM/reference-cassettes/case.enc",
        encryption_profile="atmem-household-v1",
    )
    with pytest.raises(ValueError, match="must not retain repository plaintext"):
        CassetteEnvelope(
            provider="runpod",
            model_revision="model@revision",
            request_sha256="sha256:" + "2" * 64,
            response_sha256="sha256:" + "3" * 64,
            encrypted_external_path="MEM/reference-cassettes/case.enc",
            encryption_profile="atmem-household-v1",
            contains_plaintext_in_repository=True,
        )


def test_atmem_legacy_adapter_exercises_public_product_boundary() -> None:
    root = Path(__file__).resolve().parents[1]
    corpus = load_corpus(
        root / "research/reference_parity/fixtures/minimal-evidence-v1.json"
    )
    adapter = AtMemLegacyAdapter(configuration_sha256="sha256:" + "4" * 64)
    report = run(adapter, {**corpus, "cases": corpus["cases"][:1]})
    assert report["system"] == "atmem-legacy-control"
    assert report["aggregate"]["error_count"] == 0
    assert report["cases"][0]["configuration_sha256"] == "sha256:" + "4" * 64


def test_agentrunbook_adapter_uses_pinned_real_search_primitive() -> None:
    root = Path(__file__).resolve().parents[1]
    checkout = Path(
        "/Volumes/MEM/atmem-benchmarks/baselines/"
        "reference-parity-20260930-108af05/sources/LongMemEval-V2-2cc8c54"
    )
    if not checkout.exists():
        pytest.skip("pinned external AgentRunbook checkout is unavailable")
    corpus = load_corpus(
        root / "research/reference_parity/fixtures/minimal-evidence-v1.json"
    )
    report = run(AgentRunbookROfflineAdapter(checkout=checkout), {
        **corpus, "cases": corpus["cases"][:1]
    })
    assert report["system"] == "agentrunbook-r-index-offline"
    assert report["aggregate"]["error_count"] == 0


def test_mem0_adapter_uses_pinned_real_raw_search_path() -> None:
    root = Path(__file__).resolve().parents[1]
    checkout = Path(
        "/Volumes/MEM/atmem-benchmarks/baselines/"
        "reference-parity-20260930-108af05/sources/mem0"
    )
    if not checkout.exists():
        pytest.skip("pinned external Mem0 checkout is unavailable")
    corpus = load_corpus(
        root / "research/reference_parity/fixtures/minimal-evidence-v1.json"
    )
    report = run(Mem0OssAdapter(checkout=checkout), {
        **corpus, "cases": corpus["cases"][:1]
    })
    assert report["system"] == "mem0-oss-raw-offline"
    assert report["aggregate"]["error_count"] == 0


def test_reader_free_baseline_is_explicitly_non_claiming() -> None:
    root = Path(__file__).resolve().parents[1]
    baseline = json.loads((
        root / "benchmarks/retrieval_quality/baselines/"
        "context-engine-reader-free-prechange.json"
    ).read_text())
    assert baseline["status"] == "complete_reader_free_baseline"
    assert len(baseline["arms"]) == 3
    assert "not an official benchmark" in baseline["claim"]
    assert baseline["limitations"]
