import copy

import pytest

from research.laya_memory_evidence.scale_manifest import (
    FULL_ALLOCATION,
    allocate_scope_groups,
    requested_allocation,
    validate_scale_manifest,
)
from research.laya_memory_evidence.init_stateful_experiment import _history_mix


def test_ten_percent_matches_authorized_allocation():
    assert requested_allocation(10) == {
        "state_history": 5_000,
        "train": 2_000,
        "validation": 500,
        "calibration": 500,
        "sealed_test": 2_000,
        "holdback": 3_000,
    }


def test_full_scale_matches_frozen_protocol():
    assert requested_allocation(100) == FULL_ALLOCATION


@pytest.mark.parametrize("scale", [0, -1, 100.01, "nan", "not-a-number"])
def test_invalid_scale_fails_closed(scale):
    with pytest.raises(ValueError, match="experiment_scale_percent"):
        requested_allocation(scale)


def test_allocator_is_deterministic_and_never_splits_groups():
    groups = [
        {"group_id": f"scope-component-{index:05d}", "history_count": int(index < 5_000), "challenge_count": 1}
        for index in range(8_000)
    ]
    first = allocate_scope_groups(groups, experiment_scale_percent=10, seed=410)
    second = allocate_scope_groups(reversed(groups), experiment_scale_percent="10.0", seed=410)
    assert first["requested_counts"] == requested_allocation(10)
    assert first["achieved_counts"] == first["requested_counts"]
    assert first["shortfall_counts"] == {name: 0 for name in FULL_ALLOCATION}
    assert first["assignments"] == second["assignments"]
    assert first["group_assignment_digest"] == second["group_assignment_digest"]
    assigned = [row["group_id"] for row in first["assignments"]]
    assert len(assigned) == len(set(assigned)) == 8_000


def test_scale_change_uses_same_allocator_and_stable_prefix_assignments():
    groups = [
        {"group_id": f"group-{index:06d}", "history_count": int(index < 50_000), "challenge_count": 1}
        for index in range(80_000)
    ]
    tenth = allocate_scope_groups(groups, experiment_scale_percent=10, seed=410)
    full = allocate_scope_groups(groups, experiment_scale_percent=100, seed=410)
    full_by_id = {row["group_id"]: row["split_family"] for row in full["assignments"]}
    assert all(full_by_id[row["group_id"]] == row["split_family"] for row in tenth["assignments"])


def test_group_larger_than_capacity_is_recorded_not_split():
    manifest = allocate_scope_groups(
        [{"group_id": "large", "history_count": 5_001, "challenge_count": 1}],
        experiment_scale_percent=10,
        seed=1,
    )
    assert manifest["assignments"] == []
    assert manifest["excluded_groups"][0]["reason"] == "state_history_capacity"
    assert manifest["shortfall_counts"] == manifest["requested_counts"]
    with pytest.raises(ValueError, match="90% publication floor"):
        validate_scale_manifest(manifest, require_minimum=True)


def test_manifest_digest_detects_assignment_tampering():
    manifest = allocate_scope_groups(
        [{"group_id": "one", "history_count": 1, "challenge_count": 1}],
        experiment_scale_percent=10,
        seed=1,
    )
    tampered = copy.deepcopy(manifest)
    tampered["assignments"][0]["split_family"] = "sealed_test"
    with pytest.raises(ValueError, match="digest mismatch"):
        validate_scale_manifest(tampered)


def test_history_mix_includes_empty_single_and_multi_turn_states():
    mix = _history_mix({0: 10_000, 1: 10_000, 2: 10_000, 3: 10_000}, 8_000, 5_000)
    assert mix == {0: 4_500, 1: 2_500, 2: 500, 3: 500}
    assert sum(mix.values()) == 8_000
    assert sum(length * count for length, count in mix.items()) == 5_000
