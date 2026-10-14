"""Derive one-call V3 training rows from authentic V2 state transitions.

The converter changes only the question/option representation.  It does not
create, translate, paraphrase, or relabel conversation observations.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Iterable

from atmem.core.canonical import canonical_json
from atmem.laya_formation.selective_v3 import (
    DEFAULT_LEARNED_OPERATIONS,
    build_joint_choice_v3,
)


FORMAT = "memory-transition-example-selective-v3"
EXCLUDED_EXPECTED = frozenset({"REVIEW", "FORGET_EXISTING"})


def _identity(row: dict[str, Any]) -> str:
    return str(row["transition_id"]).split(":formation.", 1)[0]


def group_rows(rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_identity(row)].append(row)
    return dict(grouped)


def convert_transition(
    rows: list[dict[str, Any]], *,
    allowed_operations: tuple[str, ...] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    if not rows:
        raise ValueError("transition group must not be empty")
    first = rows[0]
    operation = str(first["expected_operation"])
    if operation in EXCLUDED_EXPECTED:
        return None, f"expected_{operation.lower()}_is_not_a_learned_action"
    enabled = allowed_operations
    if enabled is not None and operation not in enabled:
        return None, f"expected_{operation.lower()}_is_not_enabled"
    if any(str(item["expected_operation"]) != operation for item in rows):
        raise ValueError("expected operation drift within transition")
    request = dict(first["request"])
    target = first.get("expected_target_id")
    required = {str(target)} if target else set()
    try:
        bundle = build_joint_choice_v3(
            request_id="dataset_v3_" + hashlib.sha256(
                f"{_identity(first)}:{first['partition']}".encode()
            ).hexdigest()[:32],
            scope_id=str(request["scope_id"]),
            canonical_generation=int(request["canonical_generation"]),
            observation=dict(request["observation"]),
            retrieved_memories=list(request["retrieved_memories"]),
            allowed_operations=(enabled or DEFAULT_LEARNED_OPERATIONS),
            required_target_ids=required,
            retriever_revision=str(request["retrieval_receipt"]["retriever_revision"]),
        )
    except ValueError as exc:
        return None, f"joint_contract:{type(exc).__name__}:{exc}"
    selected = [
        item for item in bundle.bindings
        if item.operation == operation
        and item.target_memory_id == (str(target) if target else None)
    ]
    if len(selected) != 1:
        return None, "expected_action_target_not_representable"
    selected_option = selected[0].option_id
    option_ids = [item.option_id for item in bundle.bindings]
    expected_response = {
        "format": "laya-choice-response-v2", "schema_version": "2.0.0",
        "request_id": bundle.request["request_id"],
        "question_id": bundle.request["question"]["question_id"],
        "type": "choice", "choice": selected_option,
        "probabilities": {
            identity: float(identity == selected_option) for identity in option_ids
        },
        "confidence": 1.0,
    }
    result = {
        **first,
        "format": FORMAT,
        "schema_version": "3.0.0",
        "transition_id": f"{_identity(first)}:formation.joint_transition.v3",
        "request": bundle.request,
        "expected_response": expected_response,
        "v3_option_bindings": [
            {
                "option_id": item.option_id, "operation": item.operation,
                "target_alias": item.target_alias,
                "target_memory_id": item.target_memory_id,
            }
            for item in bundle.bindings
        ],
        "derivation": {
            "kind": "contract_projection_only",
            "source_transition_ids": sorted(str(item["transition_id"]) for item in rows),
            "observation_content_digest": first["provenance"]["content_digest"],
            "synthetic_content": False,
            "teacher_forced_state": True,
            "on_policy_state": False,
        },
    }
    result["viewer"] = {
        **dict(first.get("viewer") or {}),
        "question_id": "formation.joint_transition.v3",
        "question_type": "choice",
    }
    return result, None


def convert_file(
    source: Path, destination: Path, *,
    allowed_operations: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    groups = group_rows(rows)
    converted: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    for identity, group in sorted(groups.items()):
        row, reason = convert_transition(group, allowed_operations=allowed_operations)
        if row is None:
            exclusions[str(reason)] += 1
        else:
            converted.append(row)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(canonical_json(row) + "\n" for row in converted), encoding="utf-8"
    )
    operations = Counter(str(row["expected_operation"]) for row in converted)
    trajectories: dict[str, set[str]] = defaultdict(set)
    for row in converted:
        trajectories[str(row["expected_operation"])].add(str(row["trajectory_id"]))
    return {
        "source": str(source), "destination": str(destination),
        "source_transition_count": len(groups), "converted_count": len(converted),
        "excluded_count": sum(exclusions.values()),
        "exclusions": dict(sorted(exclusions.items())),
        "operation_counts": dict(sorted(operations.items())),
        "distinct_trajectory_counts": {
            key: len(value) for key, value in sorted(trajectories.items())
        },
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def materialize_training_root(
    *, source_manifest: Path, projected_dir: Path, output_root: Path,
    learned_operations: tuple[str, ...],
) -> dict[str, Any]:
    """Create a self-contained V3 training root without sealed-test rows."""

    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    if source.get("synthetic_conversation_rows") != 0 or source.get("locomo_rows") != 0:
        raise ValueError("V3 source manifest includes a prohibited source class")
    coverage = json.loads((projected_dir / "coverage.json").read_text(encoding="utf-8"))
    records = output_root / "records"
    records.mkdir(parents=True, exist_ok=True)
    inventory = []
    for split in ("train", "validation", "calibration"):
        source_path = projected_dir / f"{split}.jsonl"
        destination = records / f"decisions-{split}.jsonl"
        shutil.copyfile(source_path, destination)
        inventory.append({
            "path": destination.relative_to(output_root).as_posix(),
            "size": destination.stat().st_size,
            "sha256": "sha256:" + hashlib.sha256(destination.read_bytes()).hexdigest(),
        })
    manifest = {
        "format": "atmem-stateful-memory-transitions-manifest-v3",
        "schema_version": "3.0.0",
        "repo_id": "atmem/stateful-memory-transitions-selective-v3-research",
        "source_dataset": {
            "repo_id": "atmem/stateful-memory-transitions-10pct-v2",
            "manifest_digest": source["manifest_digest"],
            "manifest_sha256": "sha256:" + hashlib.sha256(
                source_manifest.read_bytes()
            ).hexdigest(),
        },
        "derivation": "contract_projection_only",
        "synthetic_conversation_rows": 0,
        "locomo_rows": 0,
        "sealed_test_rows_included": 0,
        "learned_operations": list(learned_operations),
        "coverage": coverage,
        "inventory": inventory,
    }
    manifest["manifest_digest"] = "sha256:" + hashlib.sha256(
        canonical_json(manifest).encode()
    ).hexdigest()
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--training-root", type=Path)
    parser.add_argument(
        "--learned-operation", action="append", dest="learned_operations",
        choices=(
            "STORE_NEW", "DO_NOT_STORE", "UPDATE_EXISTING",
            "SUPERSEDE_EXISTING", "DUPLICATE",
        ),
    )
    args = parser.parse_args()
    learned_operations = tuple(args.learned_operations or ()) or None
    reports = {}
    for name in ("train", "validation", "calibration"):
        reports[name] = convert_file(
            getattr(args, name), args.output_dir / f"{name}.jsonl",
            allowed_operations=learned_operations,
        )
    train_counts = reports["train"]["distinct_trajectory_counts"]
    reports["activation_eligible_operations"] = sorted(
        operation for operation, count in train_counts.items() if count >= 100
    )
    reports["research_only_operations"] = sorted(
        operation for operation, count in train_counts.items() if count < 100
    )
    reports["activation_eligible"] = (
        "STORE_NEW" in reports["activation_eligible_operations"]
        and "DO_NOT_STORE" in reports["activation_eligible_operations"]
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "coverage.json").write_text(
        json.dumps(reports, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if bool(args.source_manifest) != bool(args.training_root):
        raise ValueError("--source-manifest and --training-root must be supplied together")
    if args.source_manifest and args.training_root:
        materialize_training_root(
            source_manifest=args.source_manifest,
            projected_dir=args.output_dir,
            output_root=args.training_root,
            learned_operations=(learned_operations or tuple(sorted(
                reports["train"]["operation_counts"]
            ))),
        )
    print(json.dumps(reports, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
