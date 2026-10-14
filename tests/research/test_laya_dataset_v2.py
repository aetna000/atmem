from __future__ import annotations

import json
from pathlib import Path

from atmem.laya_formation.governance import (
    AuthoritySnapshot,
    CandidateSnapshot,
    FormationGovernanceAdapter,
    SourceRangeSnapshot,
)
from atmem.contracts.models import AuthorityScope
from atmem.core.canonical import canonical_json, sha256_hex
from research.laya_formation.dataset_v2 import generate_examples, validate_examples
from research.laya_formation.dataset_v2.training_view import (
    QUESTION_INSTRUCTIONS_V2,
    iter_decision_rows,
    to_laya_rows_v2,
)
from research.laya_formation.dataset_v2.eval import qualify_training_data
from research.laya_formation.dataset_v2.laps import build_counterfactual_examples
from research.laya_formation.dataset_v2.model_eval import score_dispositions


FROZEN = Path("research/laya_formation/runs/openclaw-100-20261012/corpus.json")


def test_v2_is_balanced_grouped_and_excludes_frozen_regression_rows() -> None:
    rows = list(generate_examples(200))
    report = validate_examples(rows, frozen_rows=json.loads(FROZEN.read_text()))
    assert report["examples"] == 1_000
    assert report["semantic_families"] == 200
    assert set(report["disposition_counts"].values()) == {200}
    assert report["frozen_rows_used_for_training"] == 0
    assert report["maximum_frozen_similarity"] <= 0.35
    assert report["lexical_baseline_accuracy"] < 0.90
    assert report["maximum_exact_semantic_repetition"] <= 5


def test_counterfactual_group_holds_evidence_constant_for_core_operations() -> None:
    rows = list(generate_examples(20))
    family = [row for row in rows if row["semantic_family_id"] == "semantic-family-000000"]
    by_label = {row["expected"]["disposition"]: row for row in family}
    evidence = {
        label: row["state"]["authorized_evidence"][0]["text"]
        for label, row in by_label.items()
        if label in {"STORE", "UPDATE", "DUPLICATE"}
    }
    assert len(set(evidence.values())) == 1
    assert by_label["STORE"]["state"]["authorized_candidates"] == []
    assert by_label["UPDATE"]["state"]["authorized_candidates"][0]["content"]["value"] != by_label["DUPLICATE"]["state"]["authorized_candidates"][0]["content"]["value"]


def test_training_state_matches_governance_live_schema() -> None:
    row = next(generate_examples(20))
    state = row["state"]
    evidence = state["authorized_evidence"][0]
    snapshot = AuthoritySnapshot(
        scope=AuthorityScope(**state["scope"]), generation_id="gen", canonical_generation=1,
        source_ranges={evidence["range_id"]: SourceRangeSnapshot(
            range_id=evidence["range_id"], source_id=evidence["source_id"],
            start=evidence["start"], end=evidence["end"], text=evidence["text"],
            source_type=evidence["source_type"], binding_assurance=evidence["binding_assurance"],
            digest="sha256:" + "a" * 64,
        )},
        candidates={}, policy_allowed=True,
    )
    live = FormationGovernanceAdapter.authorized_state_v2(
        snapshot, list(snapshot.source_ranges.values()), [],
    )
    assert canonical_json(live) == canonical_json(state)


def test_candidate_content_digest_is_bound_in_live_schema() -> None:
    content = {"subject": "u", "relation": "theme", "value": "dark"}
    candidate = CandidateSnapshot(
        candidate_id="candidate-1", generation_id="gen", lifecycle="active",
        digest="sha256:" + "b" * 64, kind="preference", content=content,
    )
    snapshot = AuthoritySnapshot(
        scope=AuthorityScope(subject_id="u", agent_id="a", workspace_id="w"),
        generation_id="gen", canonical_generation=1, source_ranges={},
        candidates={candidate.candidate_id: candidate}, policy_allowed=True,
    )
    state = FormationGovernanceAdapter.authorized_state_v2(snapshot, [], [candidate])
    assert state["authorized_candidates"][0]["digest"] == "sha256:" + sha256_hex(canonical_json(content))


def test_v2_training_view_has_one_coherent_disposition_head() -> None:
    examples = list(generate_examples(20))
    decisions = list(iter_decision_rows(examples))
    assert len(decisions) == len(examples)
    assert {row["question_id"] for row in decisions} == set(QUESTION_INSTRUCTIONS_V2)
    converted = to_laya_rows_v2(decisions[:2])
    assert converted[0]["state"]["format"] == "atmem-laya-live-state-v2"
    assert set(converted[0]["questions"]) == {"disposition_v2"}


def test_data_qualification_detects_no_model_visible_label_clues() -> None:
    report = qualify_training_data(generate_examples(200))
    assert report["passed"] is True
    assert report["answer_label_token_hits"] == []
    assert report["identifier_label_hits"] == []
    assert report["evidence_only_core_accuracy"] <= 0.34


def test_laps_anchor_creates_natural_core_counterfactuals() -> None:
    anchors = [
        {
            "anchor_id": "a1", "domain": "recipe", "worker_hash": "w1",
            "session_index": 0, "relation": "recipe:cuisine", "value": "Thai",
            "evidence": "I usually enjoy Thai food on weekends.", "alignment_recall": 1.0,
            "source_split": "train",
        },
        {
            "anchor_id": "a2", "domain": "recipe", "worker_hash": "w2",
            "session_index": 0, "relation": "recipe:cuisine", "value": "Italian",
            "evidence": "Italian dishes are my usual choice.", "alignment_recall": 1.0,
            "source_split": "train",
        },
    ]
    rows = list(build_counterfactual_examples(anchors, output_split="train"))
    first = [row for row in rows if row["semantic_family_id"] == "a1"]
    assert {row["expected"]["disposition"] for row in first} == {"STORE", "DUPLICATE"}
    assert len({row["state"]["authorized_evidence"][0]["text"] for row in first}) == 1
    assert all(row["provenance"]["license"] == "MIT" for row in first)
    duplicate = next(row for row in first if row["expected"]["disposition"] == "DUPLICATE")
    assert duplicate["state"]["authorized_candidates"][0]["content"]["text"] == anchors[0]["evidence"]


def test_model_eval_keeps_abstention_and_harmful_store_visible() -> None:
    rows = list(generate_examples(20))[:5]
    predictions = {
        rows[0]["example_id"]: rows[0]["expected"]["disposition"],
        rows[-1]["example_id"]: "STORE",
    }
    report = score_dispositions(rows, predictions)
    assert report["abstentions"] == 3
    assert report["coverage"] == 0.4
    assert report["harmful_false_store_rate"] > 0
