from collections import Counter
import json

import pyarrow.parquet as pq
import pytest

from research.laya_memory_evidence.build_dataset import (
    _allocate_language_policy,
    _allocate_quotas,
    _candidate,
    _safe_turns,
    load_lufy,
)
from research.laya_memory_evidence.label_dataset import _agreement, _language_batches, _validate
from research.laya_memory_evidence.export_public_dataset import export


def _candidate_fixture():
    return _candidate(
        source="wildchat-1m",
        group_id="conversation-1",
        record_id="record-1",
        language="chinese",
        country="China",
        turns=[
            {"turn_id": "t0000", "role": "user", "content": "我喜欢简短的回答。"},
            {"turn_id": "t0001", "role": "assistant", "content": "好的。"},
            {"turn_id": "t0002", "role": "user", "content": "以后请保持简洁。"},
        ],
        license_id="ODC-By-1.0",
        revision="revision",
        collection="organic_production_human_ai",
    )


def test_language_is_provenance_not_model_input():
    candidate = _candidate_fixture()
    assert candidate["provenance"]["language"] == "chinese"
    assert "language" not in candidate["authorized_input"]
    assert "country" not in candidate["authorized_input"]


def test_cross_scope_exact_inputs_are_retained_for_duplicate_graph():
    first = _candidate_fixture()
    second = _candidate(
        source="wildchat-1m", group_id="conversation-2", record_id="record-2",
        language="chinese", country="China",
        turns=first["authorized_input"]["turns"], license_id="ODC-By-1.0",
        revision="revision", collection="organic_production_human_ai",
    )
    assert first["model_input_digest"] == second["model_input_digest"]
    assert first["input_digest"] != second["input_digest"]


def test_language_quota_caps_english_and_raises_low_resource_share():
    quotas = _allocate_quotas(
        Counter({"english": 1_000_000, "chinese": 10_000, "arabic": 1_000}),
        100,
    )
    assert sum(quotas.values()) == 100
    assert quotas["english"] <= 50
    assert quotas["arabic"] > 0


def test_fixed_language_policy_is_exact_for_100_rows():
    inventory = Counter({language: 1_000 for language in (
        "english", "chinese", "french", "spanish", "arabic", "german",
        "portuguese", "japanese", "russian", "indonesian", "korean",
        "urdu", "hindi",
    )})
    quotas = _allocate_language_policy(inventory, 100, preselected_english=5)
    assert quotas["english"] == 45
    assert quotas["chinese"] == 20
    assert all(quotas[name] == 5 for name in ("french", "spanish", "arabic", "german"))
    assert all(quotas[name] == 1 for name in ("portuguese", "japanese", "russian", "indonesian", "korean"))
    assert quotas["urdu"] + quotas["hindi"] == 5
    assert sum(quotas.values()) + 5 == 100


def test_fixed_language_policy_refuses_to_hide_source_shortage():
    inventory = Counter({language: 1_000 for language in (
        "english", "chinese", "spanish", "french", "arabic", "german",
        "portuguese", "japanese", "russian", "indonesian", "urdu", "hindi",
    )})
    with pytest.raises(ValueError, match="korean"):
        _allocate_language_policy(inventory, 100)


def test_secret_or_pii_rejects_whole_conversation():
    assert _safe_turns([
        {"role": "user", "content": "email me at person@example.com"},
    ]) is None


def test_lufy_emits_every_authentic_user_turn_with_chronology(tmp_path):
    source = tmp_path / "turns.jsonl"
    rows = [
        {"user_name": "u", "conversation_id": "c", "role": "user", "content": "I prefer tea."},
        {"user_name": "u", "conversation_id": "c", "role": "assistant", "content": "Noted."},
        {"user_name": "u", "conversation_id": "c", "role": "user", "content": "Actually, coffee."},
    ]
    source.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    candidates = load_lufy(source)
    assert len(candidates) == 2
    assert candidates[0]["provenance"]["group_id"] == candidates[1]["provenance"]["group_id"]
    assert sorted(len(row["authorized_input"]["prior_user_turn_ids"]) for row in candidates) == [0, 1]
    assert {row["provenance"]["selection_stratum"] for row in candidates} <= {
        "memory_intent", "chronology", "representative",
    }


def test_update_requires_bound_earlier_user_turn():
    candidate = _candidate_fixture()
    label = {
        "disposition": "UPDATE",
        "memory_class": "preference",
        "evidence_turn_ids": ["t0002"],
        "supersedes_turn_ids": [],
        "duplicate_of_turn_ids": [],
        "normalized_memory": "用户偏好简洁回答。",
        "meaning": {
            "subject": "用户", "predicate": "回答风格偏好", "value": "简洁",
            "scope": "user", "valid_from": None, "valid_until": None,
            "durability": "durable", "relation_to_prior": "refines",
        },
        "confidence": 0.9,
        "rationale": "明确的长期偏好。",
    }
    with pytest.raises(ValueError, match="supersession"):
        _validate(candidate, label)
    label["supersedes_turn_ids"] = ["t0000"]
    _validate(candidate, label)


def test_agreement_uses_decision_and_evidence_not_rationale_wording():
    one = {
        "disposition": "STORE", "memory_class": "preference",
        "evidence_turn_ids": ["t0002"], "supersedes_turn_ids": [],
        "duplicate_of_turn_ids": [],
        "normalized_memory": "A", "confidence": 0.9, "rationale": "one",
        "meaning": {
            "subject": "user", "predicate": "response style", "value": "concise",
            "scope": "user", "valid_from": None, "valid_until": None,
            "durability": "durable", "relation_to_prior": "new",
        },
    }
    two = {**one, "normalized_memory": "B", "confidence": 0.8, "rationale": "two"}
    assert _agreement(one, two) == (True, [])


def test_cli_batches_never_mix_languages():
    rows = []
    for language in ("english", "chinese", "english", "french", "chinese"):
        row = _candidate_fixture()
        row = json.loads(json.dumps(row))
        row["candidate_id"] += f"-{len(rows)}"
        row["provenance"]["language"] = language
        rows.append(row)
    batches = list(_language_batches(rows, 2))
    assert sum(map(len, batches)) == len(rows)
    assert all(len({row["provenance"]["language"] for row in batch}) == 1 for batch in batches)


def test_public_export_produces_viewer_table_and_real_preview(tmp_path):
    candidate = _candidate_fixture()
    candidates = tmp_path / "candidates.jsonl"
    candidates.write_text(json.dumps(candidate, ensure_ascii=False) + "\n", encoding="utf-8")
    label = {
        "candidate_id": candidate["candidate_id"],
        "input_digest": candidate["input_digest"],
        "rubric_version": "memory-policy-rubric-v1",
        "status": "accepted",
        "accepted_label": {
            "disposition": "STORE",
            "memory_class": "preference",
            "evidence_turn_ids": ["t0002"],
            "supersedes_turn_ids": [],
            "duplicate_of_turn_ids": [],
            "normalized_memory": "用户偏好简洁回答。",
            "meaning": {
                "subject": "用户", "predicate": "回答风格偏好", "value": "简洁",
                "scope": "user", "valid_from": None, "valid_until": None,
                "durability": "durable", "relation_to_prior": "new",
            },
            "confidence": 0.98,
            "rationale": "明确、持久的沟通偏好。",
        },
    }
    labels = tmp_path / "labels.jsonl"
    labels.write_text(json.dumps(label, ensure_ascii=False) + "\n", encoding="utf-8")
    output = tmp_path / "public"

    result = export(candidates, labels, output)

    assert result["rows"] == 1
    card = (output / "README.md").read_text(encoding="utf-8")
    assert "| ID | Expected | Category | Observation | Why |" in card
    assert "以后请保持简洁。" in card
    table = pq.read_table(output / "data" / "train.parquet")
    assert table.column_names[:5] == ["id", "expected", "category", "observation", "why"]
    assert table.to_pylist()[0]["expected"] == "STORE"
