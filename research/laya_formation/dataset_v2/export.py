from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from atmem.core.canonical import canonical_json, sha256_hex

from .generator import GENERATOR_VERSION, generate_examples
from .validation import validate_examples
from .training_view import iter_decision_rows
from .eval import qualify_training_data
from .laps import LAPS_LICENSE, LAPS_REVISION, build_counterfactual_examples, disjoint_partitions


def export_dataset(
    output: Path, *, family_count: int, frozen_corpus: Path, seed: int = 902_117,
    laps_root: Path | None = None,
) -> dict[str, Any]:
    frozen_bytes = frozen_corpus.read_bytes()
    frozen_rows = json.loads(frozen_bytes)
    rows = list(generate_examples(family_count, seed=seed))
    validation = validate_examples(rows, frozen_rows=frozen_rows)
    output.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["split"]].append(row)
    transfer_rows: dict[str, list[dict[str, Any]]] = {}
    laps_metadata = None
    if laps_root is not None:
        partitions = disjoint_partitions(laps_root)
        natural_train = list(build_counterfactual_examples(partitions["train"], output_split="train"))
        by_natural_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_synthetic_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in natural_train:
            by_natural_label[row["expected"]["disposition"]].append(row)
        for row in grouped["train"]:
            by_synthetic_label[row["expected"]["disposition"]].append(row)
        target = min(len(by_synthetic_label["REVIEW"]), len(by_synthetic_label["DO_NOT_STORE"]))
        synthetic_core = max(1, target // 5)
        mixed_train = by_synthetic_label["REVIEW"][:target] + by_synthetic_label["DO_NOT_STORE"][:target]
        for label in ("STORE", "DUPLICATE"):
            natural_needed = target - synthetic_core
            if len(by_natural_label[label]) < natural_needed:
                raise ValueError(f"LAPS has insufficient {label} anchors")
            mixed_train.extend(by_synthetic_label[label][:synthetic_core])
            mixed_train.extend(by_natural_label[label][:natural_needed])
        mixed_train.extend(by_synthetic_label["UPDATE"][:target])
        grouped["train"] = sorted(mixed_train, key=lambda row: row["example_id"])
        for split in ("transfer_validation", "transfer_test"):
            transfer_rows[split] = list(build_counterfactual_examples(partitions[split], output_split=split))
        transfer_all = transfer_rows["transfer_validation"] + transfer_rows["transfer_test"]
        laps_metadata = {
            "repo": "informagi/laps", "revision": LAPS_REVISION, "license": LAPS_LICENSE,
            "train_anchors_available": len(partitions["train"]),
            "training_examples_selected": sum(
                1 for row in grouped["train"] if row.get("generator_version") == "laps-import-v1"
            ),
            "transfer_validation_examples": len(transfer_rows["transfer_validation"]),
            "transfer_test_examples": len(transfer_rows["transfer_test"]),
            "worker_disjoint": True,
        }
    else:
        transfer_all = []
    qualification = qualify_training_data(rows, transfer_rows=transfer_all)
    if not qualification["passed"]:
        raise ValueError(f"data qualification failed: {qualification}")
    files = []
    decision_root = output / "data"
    decision_root.mkdir(exist_ok=True)
    for split, split_rows in sorted(grouped.items()):
        path = output / f"{split}.jsonl"
        data = "".join(canonical_json(row) + "\n" for row in split_rows).encode()
        path.write_bytes(data)
        files.append({"path": path.name, "rows": len(split_rows), "sha256": sha256_hex(data)})
        decision_path = decision_root / f"decisions-{split}.jsonl"
        decision_rows = list(iter_decision_rows(split_rows))
        decision_data = "".join(canonical_json(row) + "\n" for row in decision_rows).encode()
        decision_path.write_bytes(decision_data)
        files.append({
            "path": decision_path.relative_to(output).as_posix(),
            "rows": len(decision_rows),
            "sha256": sha256_hex(decision_data),
        })
    if transfer_rows:
        evaluation_root = output / "evaluation"
        evaluation_root.mkdir(exist_ok=True)
        for split, split_rows in sorted(transfer_rows.items()):
            path = evaluation_root / f"laps-{split}.jsonl"
            data = "".join(canonical_json(row) + "\n" for row in split_rows).encode()
            path.write_bytes(data)
            files.append({
                "path": path.relative_to(output).as_posix(), "rows": len(split_rows),
                "sha256": sha256_hex(data), "training_access": False,
            })
    manifest = {
        "format": "atmem-laya-training-dataset-manifest-v2",
        "generator_version": GENERATOR_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "training_only": True,
        "evaluation_claims_permitted": False,
        "frozen_regression_corpus": {
            "path": str(frozen_corpus),
            "sha256": sha256_hex(frozen_bytes),
            "rows": len(frozen_rows),
            "included_in_output": False,
            "used_for_training": False,
            "used_for_calibration": False,
        },
        "validation": validation,
        "data_qualification": qualification,
        "open_data_augmentation": laps_metadata,
        "training_mixture": {
            "scenario_rows": len(grouped["train"]),
            "decision_rows": len(grouped["train"]),
            "trained_heads": ["disposition_v2"],
            "dispositions": dict(sorted(Counter(
                row["expected"]["disposition"] for row in grouped["train"]
            ).items())),
            "sources": dict(sorted(Counter(
                row["generator_version"] for row in grouped["train"]
            ).items())),
            "memory_class_annotation_trained": False,
        },
        "files": files,
    }
    manifest["manifest_digest"] = "sha256:" + sha256_hex(canonical_json(manifest))
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--families", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=902_117)
    parser.add_argument(
        "--frozen-corpus", type=Path,
        default=Path("research/laya_formation/runs/openclaw-100-20261012/corpus.json"),
    )
    parser.add_argument("--laps-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(export_dataset(
        args.output, family_count=args.families, frozen_corpus=args.frozen_corpus,
        seed=args.seed, laps_root=args.laps_root,
    ), indent=2))


if __name__ == "__main__":
    main()
