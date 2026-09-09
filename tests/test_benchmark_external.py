from __future__ import annotations

import json
import importlib.util
from pathlib import Path

import pytest

from atmem.benchmark.external import compare_results, import_longmemeval, load_external


FIXTURES = Path(__file__).parent / "fixtures" / "benchmarks"
ROOT = Path(__file__).resolve().parents[1]


def _campaign_module():
    path = ROOT / "tools" / "run_longmemeval_retrieval.py"
    spec = importlib.util.spec_from_file_location("longmemeval_campaign", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_longmemeval_import_accounts_for_every_row() -> None:
    result = import_longmemeval(FIXTURES / "longmemeval-small.jsonl")
    assert result["counts"] == {"input": 3, "supported": 1, "skipped": 1, "unsupported": 1}
    assert result["cases"][0]["id"] == "lme-1"


def test_campaign_focused_case_selection_is_exact_and_validated(tmp_path) -> None:
    dataset = tmp_path / "longmemeval.json"
    dataset.write_text(
        json.dumps(
            [
                {
                    "question_id": "case-a",
                    "question_type": "single-session-user",
                    "question": "A?",
                    "answer_session_ids": ["s-a"],
                    "haystack_session_ids": ["s-a"],
                    "haystack_sessions": [[{"role": "user", "content": "A"}]],
                },
                {
                    "question_id": "case-b",
                    "question_type": "single-session-user",
                    "question": "B?",
                    "answer_session_ids": ["s-b"],
                    "haystack_session_ids": ["s-b"],
                    "haystack_sessions": [[{"role": "user", "content": "B"}]],
                },
            ]
        ),
        encoding="utf-8",
    )
    campaign = _campaign_module()
    selected = campaign._load_cases(dataset, 2, ["case-b"])
    assert [row["question_id"] for row in selected] == ["case-b"]
    with pytest.raises(ValueError, match="unavailable or ineligible"):
        campaign._load_cases(dataset, 2, ["missing"])


def test_campaign_atmem_chunk_aggregation_retains_per_case_signals() -> None:
    campaign = _campaign_module()
    sessions, evidence = campaign._aggregate_atmem_chunks(
        [
            {"record_id": "supported", "similarity": 0.80},
            {"record_id": "peer", "similarity": 0.75},
            {"record_id": "decoy", "similarity": 0.81},
        ],
        {"supported": "session-a", "peer": "session-a", "decoy": "session-b"},
        2,
    )
    assert sessions == ["session-a", "session-b"]
    assert evidence[0]["record_id"] == "supported"
    assert evidence[0]["signals"]["aggregate_score"] > 0.81
    assert evidence[0]["signals"]["support_group_id"].startswith("sgrp_")


def test_compatible_external_results_compare_side_by_side() -> None:
    left = load_external(FIXTURES / "external-result-small.json")
    right = {**left, "system": "mem0-oss", "metrics": {"answerable_recall": 0.5}}
    result = compare_results(left, right)
    assert result["fair_comparison"] is True
    assert result["metrics"]["answerable_recall"]["values"] == {"atmem": 1.0, "mem0-oss": 0.5}
    assert result["metrics"]["answerable_recall"]["winner"] == "atmem"
    assert result["overall"]["outcome"] == "atmem_better"
    assert result["overall"]["statement"] == "AtMem performed better than Mem0 on this benchmark."


@pytest.mark.parametrize(
    ("atmem_value", "mem0_value", "outcome"),
    [(0.5, 1.0, "mem0_better"), (1.0, 1.0, "equal")],
)
def test_comparison_selects_worse_or_equal_outcome(atmem_value, mem0_value, outcome) -> None:
    left = load_external(FIXTURES / "external-result-small.json")
    left["metrics"] = {"answerable_recall": atmem_value}
    right = {**left, "system": "mem0-oss", "metrics": {"answerable_recall": mem0_value}}
    assert compare_results(left, right)["overall"]["outcome"] == outcome


def test_comparison_reports_mixed_when_each_system_wins() -> None:
    left = load_external(FIXTURES / "external-result-small.json")
    left["metrics"] = {"answerable_recall": 1.0, "incorrect_injection_rate": 0.2}
    right = {
        **left,
        "system": "mem0-oss",
        "metrics": {"answerable_recall": 0.5, "incorrect_injection_rate": 0.0},
    }
    result = compare_results(left, right)
    assert result["overall"]["outcome"] == "mixed"
    assert result["overall"]["winner"] is None


def test_comparison_treats_longmemeval_session_metrics_as_quality() -> None:
    left = load_external(FIXTURES / "external-result-small.json")
    left["metrics"] = {
        "session_recall_any_at_5": 1.0,
        "session_recall_all_at_5": 1.0,
        "session_mrr_at_5": 0.95,
    }
    right = {
        **left,
        "system": "mem0-oss",
        "metrics": {
            "session_recall_any_at_5": 1.0,
            "session_recall_all_at_5": 1.0,
            "session_mrr_at_5": 1.0,
        },
    }
    result = compare_results(left, right)
    assert result["overall"]["outcome"] == "mem0_better"
    assert result["metrics"]["session_mrr_at_5"]["winner"] == "mem0-oss"


@pytest.mark.parametrize("field", ["dataset", "case_ids", "model_configuration"])
def test_comparison_rejects_mismatched_identity(field) -> None:
    left = load_external(FIXTURES / "external-result-small.json")
    right = json.loads(json.dumps(left))
    right["system"] = "mem0-oss"
    if field == "dataset":
        right[field]["sha256"] = "sha256:" + "b" * 64
    elif field == "case_ids":
        right[field] = ["different"]
    else:
        right[field]["generator"] = "different-model"
    with pytest.raises(ValueError, match="not a fair comparison"):
        compare_results(left, right)
