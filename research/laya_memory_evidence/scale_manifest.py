"""Deterministic scale controls for stateful memory-transition experiments."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from typing import Any, Iterable, Mapping


SCALE_MANIFEST_FORMAT = "atmem-memory-transition-scale-manifest-v1"
ALLOCATOR_VERSION = "scope-group-stable-cycle-v1"
MINIMUM_ACHIEVED_FRACTION = Decimal("0.90")
FULL_ALLOCATION = {
    "state_history": 50_000,
    "train": 20_000,
    "validation": 5_000,
    "calibration": 5_000,
    "sealed_test": 20_000,
    "holdback": 30_000,
}
CHALLENGE_PARTITIONS = ("train", "validation", "calibration", "sealed_test", "holdback")
_PARTITION_CYCLE = tuple(
    partition
    for partition, count in (
        ("train", 20), ("validation", 5), ("calibration", 5),
        ("sealed_test", 20), ("holdback", 30),
    )
    for _ in range(count)
)


def _scale(value: int, percent: Decimal) -> int:
    result = (Decimal(value) * percent / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(result)


def requested_allocation(experiment_scale_percent: int | float | str | Decimal) -> dict[str, int]:
    try:
        percent = Decimal(str(experiment_scale_percent))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("experiment_scale_percent must be numeric") from exc
    if not percent.is_finite() or percent <= 0 or percent > 100:
        raise ValueError("experiment_scale_percent must be within (0,100]")
    return {name: _scale(count, percent) for name, count in FULL_ALLOCATION.items()}


def _group_key(group_id: str, seed: int) -> bytes:
    return hashlib.sha256(f"{seed}:{group_id}".encode("utf-8")).digest()


def allocate_scope_groups(
    groups: Iterable[Mapping[str, Any]], *, experiment_scale_percent: int | float | str | Decimal,
    seed: int,
) -> dict[str, Any]:
    """Assign whole scope/duplicate groups without exceeding scaled row targets.

    Each input group represents one already-combined leakage component and must
    provide ``group_id``, ``history_count`` and ``challenge_count``.  The
    allocator never splits a group.  It records shortfalls rather than filling a
    partition with rows from a different split family.
    """

    requested = requested_allocation(experiment_scale_percent)
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in groups:
        group_id = raw.get("group_id")
        if not isinstance(group_id, str) or not group_id or group_id in seen:
            raise ValueError("group_id must be unique and non-empty")
        seen.add(group_id)
        history_count = raw.get("history_count")
        challenge_count = raw.get("challenge_count")
        for name, value in (("history_count", history_count), ("challenge_count", challenge_count)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if history_count + challenge_count == 0:
            raise ValueError("a group cannot be empty")
        normalized.append({
            "group_id": group_id,
            "history_count": history_count,
            "challenge_count": challenge_count,
        })

    normalized.sort(key=lambda row: (_group_key(row["group_id"], seed), row["group_id"]))
    achieved = {name: 0 for name in FULL_ALLOCATION}
    assignments: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for index, group in enumerate(normalized):
        if achieved["state_history"] + group["history_count"] > requested["state_history"]:
            excluded.append({**group, "reason": "state_history_capacity"})
            continue
        # Partition identity is independent of scale.  Increasing 10% to 100%
        # therefore adds groups without moving an earlier test group into train.
        partition = _PARTITION_CYCLE[index % len(_PARTITION_CYCLE)]
        if achieved[partition] + group["challenge_count"] > requested[partition]:
            excluded.append({**group, "reason": f"{partition}_capacity"})
            continue
        assignment = {**group, "split_family": partition}
        assignments.append(assignment)
        achieved["state_history"] += group["history_count"]
        achieved[partition] += group["challenge_count"]

    assignment_bytes = json.dumps(assignments, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    shortfall = {name: requested[name] - achieved[name] for name in FULL_ALLOCATION}
    manifest = {
        "format": SCALE_MANIFEST_FORMAT,
        "allocator_version": ALLOCATOR_VERSION,
        "experiment_scale_percent": str(Decimal(str(experiment_scale_percent)).normalize()),
        "seed": seed,
        "full_allocation": dict(FULL_ALLOCATION),
        "requested_counts": requested,
        "achieved_counts": achieved,
        "shortfall_counts": shortfall,
        "assignments": assignments,
        "excluded_groups": excluded,
        "group_assignment_digest": "sha256:" + hashlib.sha256(assignment_bytes).hexdigest(),
    }
    validate_scale_manifest(manifest)
    return manifest


def validate_scale_manifest(manifest: Mapping[str, Any], *, require_minimum: bool = False) -> None:
    if manifest.get("format") != SCALE_MANIFEST_FORMAT:
        raise ValueError("unsupported scale manifest format")
    if manifest.get("allocator_version") != ALLOCATOR_VERSION:
        raise ValueError("unsupported scale allocator version")
    requested = requested_allocation(manifest.get("experiment_scale_percent"))
    if manifest.get("full_allocation") != FULL_ALLOCATION:
        raise ValueError("full allocation differs from the frozen protocol")
    if manifest.get("requested_counts") != requested:
        raise ValueError("requested counts do not match experiment scale")
    achieved = manifest.get("achieved_counts")
    shortfall = manifest.get("shortfall_counts")
    if not isinstance(achieved, Mapping) or not isinstance(shortfall, Mapping):
        raise ValueError("achieved and shortfall counts are required")
    for name, target in requested.items():
        value = achieved.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= target:
            raise ValueError(f"invalid achieved count for {name}")
        if shortfall.get(name) != target - value:
            raise ValueError(f"invalid shortfall count for {name}")
        if require_minimum and target and Decimal(value) / Decimal(target) < MINIMUM_ACHIEVED_FRACTION:
            raise ValueError(f"achieved count for {name} is below the 90% publication floor")
    assignments = manifest.get("assignments")
    if not isinstance(assignments, list):
        raise ValueError("assignments must be an array")
    group_ids = [item.get("group_id") for item in assignments if isinstance(item, Mapping)]
    if len(group_ids) != len(assignments) or len(group_ids) != len(set(group_ids)):
        raise ValueError("a leakage group may be assigned only once")
    if any(item.get("split_family") not in CHALLENGE_PARTITIONS for item in assignments):
        raise ValueError("unknown split family")
    assignment_bytes = json.dumps(assignments, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_digest = "sha256:" + hashlib.sha256(assignment_bytes).hexdigest()
    if manifest.get("group_assignment_digest") != expected_digest:
        raise ValueError("group assignment digest mismatch")
