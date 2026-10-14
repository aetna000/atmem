"""Publish a completed viewer-ready dataset to the public AtMem HF org."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from huggingface_hub import HfApi
import pyarrow.parquet as pq

from research.laya_memory_evidence.policy import validate_final_manifest


DEFAULT_REPO = "atmem/atmem-laya-memory-decisions-v1"


def _row_count(root: Path) -> int:
    return sum(
        pq.ParquetFile(root / "data" / f"{split}.parquet").metadata.num_rows
        for split in ("train", "validation", "calibration", "test")
    )


def publish(root: Path, repo_id: str, expected_rows: int, confirm_public: bool) -> str:
    if not confirm_public:
        raise ValueError("public publication requires --confirm-public")
    if not repo_id.casefold().startswith("atmem/"):
        raise ValueError("dataset must be published under the atmem organization")
    if _row_count(root) != expected_rows:
        raise ValueError(f"public dataset must contain exactly {expected_rows:,} accepted rows")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("public dataset is missing its authentic final manifest")
    import json
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_final_manifest(manifest, expected_rows=expected_rows)
    card = (root / "README.md").read_text(encoding="utf-8")
    if "| ID | Expected | Category | Observation | Why |" not in card:
        raise ValueError("dataset card is missing the required visible preview table")
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(repo_id, repo_type="dataset", private=False, exist_ok=True)
    commit = api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=root,
        commit_message=f"Publish {expected_rows:,} accepted multilingual memory decisions",
        ignore_patterns=["._*", "**/._*", ".DS_Store", "**/.DS_Store"],
    )
    api.update_repo_settings(repo_id=repo_id, repo_type="dataset", private=False)
    return commit.oid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repo-id", default=DEFAULT_REPO)
    parser.add_argument("--expected-rows", type=int, default=100_000)
    parser.add_argument("--confirm-public", action="store_true")
    args = parser.parse_args()
    print(publish(args.root, args.repo_id, args.expected_rows, args.confirm_public))


if __name__ == "__main__":
    main()
