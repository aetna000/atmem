from __future__ import annotations

import json

from atmem.benchmark.runner import data_path, run_benchmark


def test_deterministic_gate_covers_all_categories_and_passes() -> None:
    report = run_benchmark()
    assert report["passed"] is True
    assert report["status"] == "passed"
    assert {row["category"] for row in report["case_results"]} == {
        "extraction", "contradiction", "recall", "no_answer",
        "incorrect_injection", "privacy", "poisoning", "fallback",
    }
    assert all(row["passed"] for row in report["case_results"])
    assert report["metrics"]["privacy_leak_count"]["value"] == 0
    assert report["metrics"]["poisoning_success_count"]["value"] == 0
    assert report["metrics"]["incorrect_injection_rate"]["value"] == 0.0


def test_quality_digest_ignores_latency() -> None:
    first = run_benchmark()
    second = run_benchmark()
    assert first["quality_sha256"] == second["quality_sha256"]
    assert [row["case_id"] for row in first["case_results"]] == [
        row["case_id"] for row in second["case_results"]
    ]


def test_quality_floor_failure_keeps_complete_report(tmp_path) -> None:
    thresholds = json.loads(data_path("thresholds-v1.json").read_text())
    thresholds["thresholds"]["answerable_recall"]["min"] = 1.1
    target = tmp_path / "thresholds.json"
    target.write_text(json.dumps(thresholds))
    report = run_benchmark(thresholds_path=target)
    assert report["passed"] is False
    assert len(report["case_results"]) == 24
    assert any("answerable_recall" in failure for failure in report["failures"])


def test_optional_profile_is_explicit_skip(monkeypatch) -> None:
    monkeypatch.delenv("ATMEM_BENCHMARK_LOCAL_ATBOT", raising=False)
    report = run_benchmark(profile_name="local-atbot")
    assert report["status"] == "skipped"
    assert report["passed"] is False
    assert report["case_results"] == []
    assert report["metrics"]["token_usage"]["value"] is None
    assert report["metrics"]["token_usage"]["unavailable_reason"]


def test_usage_and_cost_are_unknown_not_zero() -> None:
    report = run_benchmark()
    assert report["metrics"]["token_usage"]["value"] is None
    assert report["metrics"]["model_cost_usd"]["value"] is None


def test_opted_in_local_embeddings_builds_a_semantic_epoch(monkeypatch) -> None:
    from atmem.semantic import HashingEmbedder

    monkeypatch.setattr(
        "atmem.benchmark.runner.resolve_profile",
        lambda name: {
            "mode": "local-embeddings", "provider": "sentence-transformers",
            "model": "fixture", "embedding": "fixture", "egress_class": "local",
            "optional": True, "available": True, "skip_reason": None,
            "endpoint": None, "api_key_env": None, "model_version": "fixture",
        },
    )
    builds = []
    monkeypatch.setattr("atmem.semantic.create_embedder", lambda *args, **kwargs: HashingEmbedder())
    original = __import__("atmem.semantic", fromlist=["SemanticIndex"]).SemanticIndex.build

    def tracked(self, *args, **kwargs):
        builds.append(True)
        return original(self, *args, **kwargs)

    monkeypatch.setattr("atmem.semantic.SemanticIndex.build", tracked)
    report = run_benchmark(profile_name="local-embeddings")
    assert report["profile"]["mode"] == "local-embeddings"
    assert builds
    # The profile ran a real semantic epoch. Any current semantic safety gap is
    # reported as a failed benchmark rather than hidden or raised as a crash.
    assert report["status"] in {"passed", "failed"}


def test_opted_in_atbot_profile_actually_ranks_authorized_candidates(monkeypatch) -> None:
    from atmem.extract.rules import extract_facts

    monkeypatch.setattr(
        "atmem.benchmark.runner.resolve_profile",
        lambda name: {
            "mode": "local-atbot", "provider": "fixture-atbot", "model": "fixture",
            "embedding": "atmem-hashing-v1", "egress_class": "local",
            "optional": True, "available": True, "skip_reason": None,
            "health_verified": True,
        },
    )
    calls = []
    proposal_calls = []

    def propose(self, message):
        proposal_calls.append(message)
        facts = extract_facts(message, source_type=(
            "tool_output" if message.startswith("<tool_output>") else "user_message"
        ))
        return {
            "proposals": [
                {
                    "fact": fact.content, "fact_key": fact.fact_key,
                    "confidence": fact.confidence, "sensitivity": "personal",
                    "entities": [], "suggested_action": "add",
                }
                for fact in facts
            ],
            "interpreter": {
                "provider": "fixture-atbot", "model": "fixture",
                "prompt_version": "fixture-v1", "assurance": "model_interpreted",
                "egress_class": "local",
            },
            "companion": {"available": True, "fallback": False},
        }

    def rank(self, query, candidates):
        calls.append((query, tuple(row["record_id"] for row in candidates)))
        return {
            "ranked_record_ids": [row["record_id"] for row in candidates],
            "companion": {"available": True, "fallback": False},
        }

    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.query", rank)
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.propose", propose)
    report = run_benchmark(profile_name="local-atbot")
    assert calls
    assert proposal_calls
    assert report["profile"]["health_verified"] is True
    assert report["status"] in {"passed", "failed"}
