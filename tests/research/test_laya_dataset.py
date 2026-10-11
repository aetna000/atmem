from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import jsonschema
import pytest

from atmem.laya_formation.packing import AuthorizedRange, pack_authorized_ranges, structural_parity_bytes
from research.laya_formation.dataset.generator import build_scenario, coverage, generate_scenarios
from research.laya_formation.dataset.audit import (
    build_blinded_audit_packet,
    build_review_template,
    score_audit_review,
    sign_audit_review,
    validate_audit_result,
)
from research.laya_formation.dataset.export import DEFAULT_ROOT, export_dataset
from research.laya_formation.dataset.oracle import compile_decisions
from research.laya_formation.dataset.splits import assert_group_disjoint
from research.laya_formation.dataset.validation import near_duplicate_fingerprint, validate_dataset
from research.laya_formation.dataset.training_view import iter_training_rows


class FakeExactAdapter:
    revision = "fake-tokenizer-v1"

    def head_token_count(self, question, head_max_len):
        count = 2 + sum(len(str(value).split()) for value in question.values())
        if count > head_max_len:
            raise ValueError("head overflow")
        return count, len(question["crit"])

    def serialize_and_encode_state(self, state):
        text = json.dumps(state, sort_keys=True, separators=(",", ":"))
        return text, list(text.encode())


def test_generator_and_oracle_are_deterministic() -> None:
    first = build_scenario(42)
    second = build_scenario(42)
    assert first == second
    assert compile_decisions(first) == compile_decisions(second)
    assert len(compile_decisions(first)) == 5


def test_all_oracle_targets_belong_to_finite_choices() -> None:
    for scenario in generate_scenarios(1_200):
        for row in compile_decisions(scenario):
            assert set(row.expected_choice_ids).issubset(row.choice_ids)


def test_groups_are_disjoint_and_tampering_is_detected() -> None:
    scenarios = list(generate_scenarios(1_200))
    assert_group_disjoint(scenarios)
    examples = [row for scenario in scenarios for row in compile_decisions(scenario)]
    assert validate_dataset(scenarios, examples) == {"scenarios": 1200, "decisions": 6000, "critical_findings": 0}


def test_near_duplicate_fingerprint_ignores_synthetic_identifiers() -> None:
    left = "Recorded scenario 000001 uses synthetic-value-1000 for later recall."
    right = "Recorded scenario 999999 uses synthetic-value-9000 for later recall."
    assert near_duplicate_fingerprint(left) == near_duplicate_fingerprint(right)


def test_blinded_audit_excludes_sealed_and_meets_high_risk_floors() -> None:
    scenarios = list(generate_scenarios(1_200))
    examples = [row for scenario in scenarios for row in compile_decisions(scenario)]
    packet, answer_key = build_blinded_audit_packet(scenarios, examples)
    assert packet["sample_size"] == 400
    assert packet["sealed_rows"] == 0
    assert all(count >= 60 for tag, count in packet["high_risk_tag_counts"].items() if tag in {"sensitive", "credential", "private_scope", "cross_scope", "contradiction"})
    assert all("expected_choice_ids" not in row for row in packet["rows"])
    assert len(answer_key["rows"]) == 400


def test_audit_result_gate() -> None:
    validate_audit_result({"format": "atmem-laya-audit-result-v1", "reviewed": 400, "correct": 396, "critical_findings": 0, "reviewer": "reviewer-1", "signed_at": "2035-01-01T00:00:00Z"})
    with pytest.raises(ValueError, match="below 99"):
        validate_audit_result({"format": "atmem-laya-audit-result-v1", "reviewed": 400, "correct": 395, "critical_findings": 0, "reviewer": "reviewer-1", "signed_at": "2035-01-01T00:00:00Z"})


def test_signed_blinded_audit_review_round_trip_and_tamper_gate() -> None:
    scenarios = list(generate_scenarios(1_200))
    examples = [row for scenario in scenarios for row in compile_decisions(scenario)]
    packet, answer_key = build_blinded_audit_packet(scenarios, examples)
    review = build_review_template(packet)
    review["reviewer"]["id"] = "independent-reviewer-1"
    review["signed_at"] = "2035-01-01T00:00:00Z"
    expected = {row["example_id"]: row["expected_choice_ids"] for row in answer_key["rows"]}
    for row in review["rows"]:
        row["selected_choice_ids"] = expected[row["example_id"]]
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    signed = sign_audit_review(review, private_pem)
    result = score_audit_review(packet, answer_key, signed)
    assert result["reviewed"] == result["correct"] == 400
    tampered = json.loads(json.dumps(signed))
    tampered["rows"][0]["selected_choice_ids"] = [packet["rows"][0]["choice_ids"][-1]]
    with pytest.raises(ValueError, match="signed payload digest mismatch|signature verification"):
        score_audit_review(packet, answer_key, tampered)


def test_small_export_is_bounded_and_checksum_manifested(tmp_path: Path) -> None:
    (tmp_path / "._stale-macos-metadata").write_bytes(b"not dataset content")
    manifest = export_dataset(tmp_path, scenario_count=20, allow_test_root=True, require_parquet=False)
    assert manifest["scenario_count"] == 20
    assert manifest["decision_count"] == 100
    assert manifest["files"]
    assert not any(Path(row["path"]).name.startswith("._") for row in manifest["files"])
    assert not (tmp_path / "._stale-macos-metadata").exists()
    train_rows = list(iter_training_rows([tmp_path / "data" / "decisions-train.jsonl"]))
    assert train_rows and all(row["split"] == "train" for row in train_rows)
    sealed_input = json.loads((tmp_path / "sealed" / "test-inputs.jsonl").read_text().splitlines()[0])
    assert "expected_choice_ids" not in sealed_input
    with pytest.raises(ValueError, match="sealed paths"):
        list(iter_training_rows([tmp_path / "sealed" / "test-labels.jsonl"]))
    with pytest.raises(ValueError, match="must use"):
        export_dataset(tmp_path, scenario_count=12_000, require_parquet=False)


def test_publishable_export_refuses_missing_external_mount() -> None:
    if DEFAULT_ROOT.parent.exists():
        pytest.skip("external artifact mount is present")
    with pytest.raises(RuntimeError, match="not mounted"):
        export_dataset(DEFAULT_ROOT, require_parquet=False)


def test_required_coverage_exists_in_representative_fixture() -> None:
    report = coverage(1_200)
    assert set(report["operations"]) == {"ADD", "UPDATE", "SUPERSEDE", "NOOP", "REJECT"}
    assert set(report["questions"]) == {"operation", "memory_class", "evidence_support", "target_selection", "retrieval_usefulness"}
    for tag in ("sensitive", "credential", "private_scope", "cross_scope", "contradiction"):
        assert report["safety_tags"][tag] >= 60


def test_operations_and_memory_classes_use_balanced_semantic_pairs() -> None:
    rows = list(generate_scenarios(1_200))
    pairs = {
        (row.expected_final_state["operation"], row.expected_final_state["memory_class"])
        for row in rows
    }
    assert len(pairs) == 21
    assert not any(
        operation in {"ADD", "UPDATE", "SUPERSEDE"} and memory_class == "non_memory"
        for operation, memory_class in pairs
    )
    class_counts = Counter(row.expected_final_state["memory_class"] for row in rows)
    assert min(class_counts.values()) >= 192
    assert max(class_counts.values()) <= 288
    assert all(row.expected_final_state["operation"] == "REJECT" for row in rows if row.expected_final_state["memory_class"] == "non_memory")


def test_operation_evidence_matches_state_transition() -> None:
    for row in generate_scenarios(1_200):
        expected = row.expected_final_state
        operation = expected["operation"]
        text = " ".join(event.text for event in row.evidence_events)
        if operation == "ADD":
            assert not row.initial_state
            assert "No prior canonical record exists" in text
        elif operation == "UPDATE":
            assert row.initial_state["target:active"] != expected["canonical_state"]["target:active"]
            assert "later correction changes it" in text
        elif operation == "SUPERSEDE":
            assert row.initial_state["target:active"] != expected["canonical_state"]["target:active"]
            assert "explicitly supersedes" in text
        elif operation == "NOOP":
            assert row.initial_state == expected["canonical_state"]
            if expected["memory_class"] == "non_memory":
                assert not row.initial_state
                assert expected["target_selection"] == "target:none"
                assert "benign one-time content" in text
            else:
                assert "Duplicate evidence repeats it" in text
        else:
            assert expected["canonical_state"] == row.initial_state
            if "contradiction" in row.safety_tags:
                assert expected["evidence_support"] == "AMBIGUOUS"
                assert expected["target_selection"] == "REVIEW"
                assert "directly conflict" in text or "directly contradicts" in text
            else:
                assert expected["evidence_support"] == "UNSUPPORTED"
                assert "Unverified hypothetical draft only" in text
        if "contradiction" in row.safety_tags:
            assert operation == "REJECT"
            assert expected["evidence_support"] == "AMBIGUOUS"
            assert expected["target_selection"] == "REVIEW"
            assert expected["retrieval_usefulness"] == "INSUFFICIENT_EVIDENCE"


def test_shared_packer_is_whole_range_and_byte_deterministic() -> None:
    adapter = FakeExactAdapter()
    question = {"t": "choice", "instructions": "Choose", "crit": {"ADD": "add", "NOOP": "none"}}
    ranges = (
        AuthorizedRange("r1", "s1", 0, 5, "short"),
        AuthorizedRange("r2", "s1", 6, 200, "x" * 194),
    )
    first = pack_authorized_ranges(adapter=adapter, question=question, ranges=ranges, max_len=140, head_max_len=30)
    second = pack_authorized_ranges(adapter=adapter, question=question, ranges=ranges, max_len=140, head_max_len=30)
    assert structural_parity_bytes(first) == structural_parity_bytes(second)
    assert first.included_range_ids == ("r1",)
    assert first.lost_range_ids == ("r2",)
    assert first.overflow is True
    assert first.total_tokens <= first.max_len


def test_packer_rejects_incomplete_question_head() -> None:
    with pytest.raises(ValueError, match="head overflow"):
        pack_authorized_ranges(
            adapter=FakeExactAdapter(),
            question={"t": "choice", "instructions": "too many words " * 20, "crit": {"a": "A"}},
            ranges=(),
            max_len=64,
            head_max_len=8,
        )


@pytest.mark.parametrize(
    "schema_name,instance",
    [
        ("formation-scenario-v1.schema.json", build_scenario(1).to_dict()),
        ("typed-decision-example-v1.schema.json", compile_decisions(build_scenario(1))[0].to_dict()),
    ],
)
def test_json_schemas_accept_golden_rows(schema_name: str, instance: dict) -> None:
    root = Path("research/laya_formation/dataset/schemas")
    jsonschema.validate(instance, json.loads((root / schema_name).read_text()))
