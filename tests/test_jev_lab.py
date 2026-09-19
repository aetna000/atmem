from __future__ import annotations

import json

from research.jev_lab.dataset import build_dataset, dataset_digest
from research.jev_lab.report import render
from research.jev_lab.runner import _jev_request, authority_gate, run


def test_offline_run_is_deterministic_and_secret_free(monkeypatch):
    monkeypatch.setenv("JEV_API", "do-not-leak")
    first = run(seed=7, case_count=4, offline=True)
    second = run(seed=7, case_count=4, offline=True)
    assert first == second
    serialized = json.dumps(first)
    assert "do-not-leak" not in serialized
    assert first["synthetic_only"] is True
    assert first["mode"] == "offline"


def test_authority_withholds_ineligible_candidate():
    case = build_dataset(2, 1)["cases"][0]
    restricted = next(item["id"] for item in case["candidates"] if not item["eligible"])
    assert restricted not in authority_gate(case, [restricted, case["expected_id"]])


def test_request_is_batched_and_contains_no_secret():
    dataset = build_dataset(3, 3)
    body = _jev_request(dataset, "jev-1.13.0")
    assert body["model"] == "jev-1.13.0"
    assert set(body["questions"]) == {case["id"] for case in dataset["cases"]}
    assert "JEV_API" not in json.dumps(body)


def test_report_is_inline_svg_and_escaped():
    report = run(seed=4, case_count=2, offline=True)
    page = render(report)
    assert "<svg" in page
    assert "SYNTHETIC ONLY" in page
    assert "authority gate" in page


def test_dataset_digest_changes_with_seed():
    assert dataset_digest(build_dataset(1)) != dataset_digest(build_dataset(2))


def test_live_outage_is_not_labelled_as_successful_offline(monkeypatch):
    monkeypatch.setenv("JEV_API", "synthetic-key")
    monkeypatch.setattr("research.jev_lab.runner.call_jev", lambda *args, **kwargs: (None, {"status": "unavailable", "latency_ms": 1.0}))
    result = run(seed=5, case_count=1)
    assert result["mode"] == "unavailable"
    assert result["transport"]["status"] == "unavailable"
