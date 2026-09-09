from __future__ import annotations

from copy import deepcopy

import pytest

from atmem.semantic.health import (
    HardwareProfile,
    SemanticHealthStatus,
    detect_accelerator,
    evaluate_semantic_health,
    load_model_catalog,
    recommend_local_models,
)


def _epoch(**changes):
    identity = {
        "provider": "sentence-transformers",
        "model": "BAAI/bge-small-en-v1.5",
        "version": "1",
        "normalization": "l2",
    }
    value = {
        "epoch_id": "vidx_1",
        "subject_id": "user-1",
        "provider": identity["provider"],
        "model": identity["model"],
        "model_version": identity["version"],
        "identity": identity,
        "identity_sha256": "a" * 64,
        "dimensions": 384,
        "status": "active",
        "dirty": 0,
        "entry_count": 3,
        "created_at": "2026-09-05T00:00:00Z",
    }
    value.update(changes)
    return value


def _health(epoch=None, *, epochs=None, verification=None, expected_identity=None):
    active = _epoch() if epoch is None else epoch
    return evaluate_semantic_health(
        "user-1",
        active_epoch=active,
        epochs=[active] if epochs is None and active else (epochs or []),
        verification=verification or {"valid": True, "report_sha256": "b" * 64},
        expected_identity=expected_identity,
        source_sha256=f"sha256:{'c' * 64}",
        canonical_generation=4,
    )


@pytest.mark.parametrize(
    ("health", "expected"),
    [
        (
            evaluate_semantic_health("user-1", active_epoch=None),
            SemanticHealthStatus.MISSING,
        ),
        (
            evaluate_semantic_health(
                "user-1",
                active_epoch=None,
                epochs=[{"status": "building"}],
            ),
            SemanticHealthStatus.REBUILDING,
        ),
        (
            _health(
                epochs=[_epoch(), {"status": "building", "epoch_id": "partial"}]
            ),
            SemanticHealthStatus.REBUILDING,
        ),
        (
            _health(_epoch(identity_sha256=None)),
            SemanticHealthStatus.LEGACY,
        ),
        (
            _health(
                _epoch(
                    provider="hashing-diagnostic",
                    identity={
                        "provider": "hashing-diagnostic",
                        "model": "blake2b-token-v1",
                        "version": "1",
                        "normalization": "l2",
                    },
                )
            ),
            SemanticHealthStatus.WEAK,
        ),
        (_health(_epoch(dirty=1)), SemanticHealthStatus.STALE),
        (
            _health(
                verification={
                    "valid": False,
                    "coverage_gaps": ["mem_1"],
                    "report_sha256": "d" * 64,
                }
            ),
            SemanticHealthStatus.STALE,
        ),
        (_health(_epoch(dimensions=0)), SemanticHealthStatus.INCOMPATIBLE),
        (
            _health(expected_identity={"model": "different-model"}),
            SemanticHealthStatus.INCOMPATIBLE,
        ),
        (_health(), SemanticHealthStatus.HEALTHY),
    ],
)
def test_semantic_health_states(health, expected) -> None:
    assert health.status is expected
    assert health.to_dict()["status"] == expected.value


def test_model_recommendations_are_compatible_and_deterministic() -> None:
    catalog = load_model_catalog()
    hardware = HardwareProfile(memory_gib=6, architecture="arm64", cpu_count=8)
    first = recommend_local_models(hardware, catalog)
    reversed_catalog = deepcopy(catalog)
    reversed_catalog["models"].reverse()
    second = recommend_local_models(hardware, reversed_catalog)

    assert first == second
    assert [item["model"] for item in first] == [
        "nomic-embed-text",
        "BAAI/bge-small-en-v1.5",
        "sentence-transformers/all-MiniLM-L6-v2",
    ]
    assert all(item["memory_unverified"] is False for item in first)
    assert recommend_local_models(
        HardwareProfile(memory_gib=1, architecture="x86_64"), catalog
    ) == []


def test_catalog_offers_more_than_one_runtime() -> None:
    catalog = load_model_catalog()
    providers = {model["provider"] for model in catalog["models"]}
    assert {"ollama", "sentence-transformers"} <= providers


def test_unmeasurable_memory_is_unknown_rather_than_zero() -> None:
    unknown = HardwareProfile(memory_gib=None, architecture="x86_64")

    assert unknown.memory_known is False
    assert unknown.to_dict()["memory_known"] is False

    # An unmeasurable platform gets a caveated list, never an empty one that
    # would read as "no model fits this hardware".
    recommendations = recommend_local_models(unknown, load_model_catalog())
    assert recommendations
    assert all(item["memory_unverified"] is True for item in recommendations)


def test_detect_reports_unknown_memory_when_sysconf_is_unavailable(monkeypatch) -> None:
    def unavailable(_name):
        raise AttributeError("sysconf is not available on this platform")

    monkeypatch.setattr("atmem.semantic.health.os.sysconf", unavailable)

    profile = HardwareProfile.detect()

    assert profile.memory_gib is None
    assert profile.memory_known is False


def test_detected_accelerator_reflects_observed_platform(monkeypatch) -> None:
    monkeypatch.setattr("atmem.semantic.health.platform.system", lambda: "Darwin")
    monkeypatch.setattr("atmem.semantic.health.platform.machine", lambda: "arm64")
    assert detect_accelerator() == "metal"

    monkeypatch.setattr("atmem.semantic.health.platform.system", lambda: "Linux")
    monkeypatch.setattr("atmem.semantic.health.platform.machine", lambda: "x86_64")
    monkeypatch.setattr(
        "atmem.semantic.health.shutil.which",
        lambda name: "/usr/bin/nvidia-smi" if name == "nvidia-smi" else None,
    )
    assert detect_accelerator() == "cuda"

    monkeypatch.setattr("atmem.semantic.health.shutil.which", lambda _name: None)
    assert detect_accelerator() == "none"
