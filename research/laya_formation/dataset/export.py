from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from atmem.core.canonical import canonical_json

from .audit import build_blinded_audit_packet
from .generator import coverage, generate_scenarios
from .oracle import compile_decisions
from .validation import validate_dataset


DEFAULT_ROOT = Path("/Volumes/MEM/AtMem-Laya-Formation")
PLATFORM_METADATA_NAMES = {".DS_Store"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(canonical_json(row) + "\n")


def _remove_platform_metadata(root: Path) -> None:
    """Remove non-dataset metadata created by mounted-volume implementations."""
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file() and (path.name.startswith("._") or path.name in PLATFORM_METADATA_NAMES):
            path.unlink()


def export_dataset(
    root: Path,
    *,
    scenario_count: int = 12_000,
    seed: int = 410239,
    allow_test_root: bool = False,
    require_parquet: bool = True,
) -> dict[str, Any]:
    resolved = root.resolve()
    expected = DEFAULT_ROOT.resolve()
    if not allow_test_root and resolved != expected:
        raise ValueError(f"full dataset must use {DEFAULT_ROOT}")
    if allow_test_root and scenario_count > 100:
        raise ValueError("test roots are limited to 100 scenarios")
    if not allow_test_root and scenario_count < 12_000:
        raise ValueError("publishable dataset requires at least 12,000 scenarios")
    if not allow_test_root and not DEFAULT_ROOT.parent.exists():
        raise RuntimeError("/Volumes/MEM is not mounted")
    parquet = None
    if require_parquet:
        try:
            import pyarrow as parquet  # noqa: F401
            import pyarrow.parquet  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("pyarrow is required before publishable export starts") from exc

    scenarios = list(generate_scenarios(scenario_count, seed=seed))
    decisions = [item for row in scenarios for item in compile_decisions(row)]
    validation = validate_dataset(scenarios, decisions)
    if scenario_count >= 12_000 and len(decisions) < 60_000:
        raise AssertionError("decision minimum was not met")

    data_dir = resolved / "data"
    audit_dir = resolved / "audits"
    manifest_dir = resolved / "manifests"
    for directory in (data_dir, audit_dir, manifest_dir):
        directory.mkdir(parents=True, exist_ok=True)
    sealed_dir = resolved / "sealed"
    sealed_dir.mkdir(parents=True, exist_ok=True)
    for split in ("train", "validation", "calibration"):
        _write_jsonl(data_dir / f"scenarios-{split}.jsonl", (row.to_dict() for row in scenarios if row.split == split))
        _write_jsonl(data_dir / f"decisions-{split}.jsonl", (row.to_dict() for row in decisions if row.split == split))
    _write_jsonl(
        sealed_dir / "test-inputs.jsonl",
        (
            {
                "example_id": row.example_id,
                "scenario_id": row.scenario_id,
                "question_id": row.question_id,
                "question_type": row.question_type,
                "authorized_input": row.authorized_input,
                "choice_ids": list(row.choice_ids),
                "allow_abstain": row.allow_abstain,
                "split": row.split,
            }
            for row in decisions
            if row.split == "sealed_test"
        ),
    )
    _write_jsonl(
        sealed_dir / "test-labels.jsonl",
        (
            {
                "example_id": row.example_id,
                "expected_choice_ids": list(row.expected_choice_ids),
                "oracle_receipt": row.oracle_receipt,
                "content_digest": row.content_digest,
            }
            for row in decisions
            if row.split == "sealed_test"
        ),
    )

    if require_parquet:
        import pyarrow as pa
        import pyarrow.parquet as pq

        for split in ("train", "validation", "calibration"):
            pq.write_table(pa.Table.from_pylist([row.to_dict() for row in scenarios if row.split == split]), data_dir / f"scenarios-{split}.parquet")
            pq.write_table(pa.Table.from_pylist([row.to_dict() for row in decisions if row.split == split]), data_dir / f"decisions-{split}.parquet")

    split_manifest = {
        "format": "atmem-laya-split-manifest-v1",
        "seed": seed,
        "group_keys": ["fictional_identity_group", "template_family", "semantic_chain_id", "paraphrase_cluster_id"],
        "splits": {
            split: {
                "scenario_ids": [row.scenario_id for row in scenarios if row.split == split],
                "scenario_count": sum(row.split == split for row in scenarios),
                "decision_count": sum(row.split == split for row in decisions),
            }
            for split in ("train", "validation", "calibration", "sealed_test")
        },
        "training_allowed_splits": ["train", "validation", "calibration"],
        "sealed_label_path": "sealed/test-labels.jsonl",
    }
    (manifest_dir / "split-manifest.json").write_text(json.dumps(split_manifest, indent=2, sort_keys=True) + "\n")

    if allow_test_root:
        nonsealed_count = sum(row.split != "sealed_test" for row in decisions)
        packet, answer_key = build_blinded_audit_packet(
            scenarios,
            decisions,
            sample_size=min(400, nonsealed_count),
            minimum_per_high_risk_tag=0,
        )
    else:
        packet, answer_key = build_blinded_audit_packet(scenarios, decisions)
    (audit_dir / "nonsealed-packet.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    (audit_dir / "nonsealed-answer-key.json").write_text(json.dumps(answer_key, indent=2, sort_keys=True) + "\n")
    _remove_platform_metadata(resolved)
    files = []
    for path in sorted(resolved.rglob("*")):
        if path.is_file() and path.name != "dataset-manifest.json":
            files.append({"path": str(path.relative_to(resolved)), "size": path.stat().st_size, "sha256": _sha256(path)})
    manifest = {
        "format": "atmem-laya-dataset-manifest-v1",
        "generator_version": scenarios[0].generator_version,
        "seed": seed,
        "synthetic_only": True,
        "publishable": not allow_test_root,
        "scenario_count": len(scenarios),
        "decision_count": len(decisions),
        "validation": validation,
        "coverage": coverage(scenario_count, seed=seed),
        "split_counts": dict(Counter(row.split for row in scenarios)),
        "files": files,
    }
    manifest_path = manifest_dir / "dataset-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Spec 041 synthetic dataset")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--scenario-count", type=int, default=12_000)
    parser.add_argument("--seed", type=int, default=410239)
    parser.add_argument("--allow-test-root", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-parquet", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    manifest = export_dataset(
        args.root,
        scenario_count=args.scenario_count,
        seed=args.seed,
        allow_test_root=args.allow_test_root,
        require_parquet=not args.no_parquet,
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
