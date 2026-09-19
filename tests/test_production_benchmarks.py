from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.production_benchmarks.locomo import load_locomo, run_locomo
from research.production_benchmarks.manifest import BenchmarkManifest


def _fixture(path: Path) -> None:
    path.write_text(json.dumps([{"sample_id": "fixture", "conversation": {"session_1_date_time": "today", "session_1": [{"speaker": "A", "dia_id": "D1:1", "text": "I prefer morning flights."}, {"speaker": "B", "dia_id": "D1:2", "text": "That is useful to know."}]}, "qa": [{"question": "What flights does the person prefer?", "answer": "morning", "evidence": ["D1:1"], "category": 1}]}]), encoding="utf-8")


def test_locomo_loader_rejects_unknown_evidence(tmp_path):
    path = tmp_path / "bad.json"
    _fixture(path)
    data = json.loads(path.read_text())
    data[0]["qa"][0]["evidence"] = ["D9:9"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unknown evidence"):
        load_locomo(path)


def test_evidence_token_normalization_allows_explicit_diagnostic_mode(tmp_path):
    data = tmp_path / "locomo.json"
    _fixture(data)
    raw = json.loads(data.read_text())
    raw[0]["qa"][0]["evidence"] = ["D1:1; D1:2"]
    data.write_text(json.dumps(raw))
    assert load_locomo(data, strict=False)


def test_locomo_run_is_real_atmem_and_exploratory_without_digest(tmp_path):
    data = tmp_path / "locomo.json"
    _fixture(data)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"name": "LoCoMo", "version": "fixture", "source_url": "https://example.invalid", "license": "fixture-only", "source_ref": "fixture", "expected_sha256": "", "task": "retrieval-only QA evidence recall", "status": "exploratory"}))
    result = run_locomo(data, manifest_path=manifest, sample=1)
    assert result["claim_status"] == "exploratory"
    assert result["metrics"]["questions"] == 1
    assert result["metrics"]["recall_at_1"] == 1.0
    assert result["rows"][0]["ranked_ids"]


def test_manifest_digest_mismatch(tmp_path):
    data = tmp_path / "data.json"
    data.write_text("{}")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"name": "x", "version": "1", "source_url": "x", "license": "x", "source_ref": "x", "expected_sha256": "0" * 64, "task": "x", "status": "exploratory"}))
    with pytest.raises(ValueError, match="digest mismatch"):
        BenchmarkManifest.load(manifest).validate_file(data)
