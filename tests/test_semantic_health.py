from __future__ import annotations

from copy import deepcopy

import pytest

from atmem.semantic.health import (
    HardwareProfile,
    SemanticHealthStatus,
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
        "BAAI/bge-small-en-v1.5",
        "sentence-transformers/all-MiniLM-L6-v2",
    ]
    assert recommend_local_models(
        HardwareProfile(memory_gib=1, architecture="x86_64"), catalog
    ) == []
