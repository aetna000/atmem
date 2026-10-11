from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

from research.laya_formation.training.contracts import secret_findings
from research.laya_formation.training.smoke import sha256_file


def publish_private(
    *, repo_id: str, export_root: Path, model_card: Path, license_path: Path, token: str
) -> dict[str, Any]:
    if not token:
        raise RuntimeError("a Hugging Face token is required on stdin")
    artifact_manifest = json.loads((export_root / "artifact-manifest.json").read_text(encoding="utf-8"))
    for item in artifact_manifest["inventory"]:
        path = export_root / item["path"]
        if path.stat().st_size != item["size"] or sha256_file(path) != item["sha256"]:
            raise ValueError(f"export inventory mismatch: {item['path']}")
    candidate_text = [model_card.read_text(encoding="utf-8"), license_path.read_text(encoding="utf-8")]
    candidate_text.extend(
        path.read_text(encoding="utf-8")
        for path in export_root.rglob("*.json")
    )
    if secret_findings(candidate_text):
        raise RuntimeError("secret-like material found in the model publication inventory")
    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="model", private=True, exist_ok=True)
    existing = api.list_repo_files(repo_id=repo_id, repo_type="model")
    operations = [
        CommitOperationDelete(path_in_repo=path)
        for path in existing if path.startswith("training/")
    ]
    operations.extend(
        CommitOperationAdd(path_in_repo=path.relative_to(export_root).as_posix(), path_or_fileobj=str(path))
        for path in sorted(export_root.rglob("*")) if path.is_file()
    )
    operations.extend([
        CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=str(model_card)),
        CommitOperationAdd(path_in_repo="LICENSE", path_or_fileobj=str(license_path)),
    ])
    commit = api.create_commit(
        repo_id=repo_id, repo_type="model", operations=operations,
        commit_message="Publish private verified AtMem Laya formation candidate",
    )
    return {
        "repo_id": repo_id, "revision": commit.oid, "url": commit.commit_url,
        "export_digest": artifact_manifest["digest"],
        "intended_files": len(artifact_manifest["inventory"]) + 3,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish the verified Spec 041 model candidate privately")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--model-card", type=Path, required=True)
    parser.add_argument("--license", type=Path, required=True)
    args = parser.parse_args(argv)
    result = publish_private(
        repo_id=args.repo_id, export_root=args.export_root.resolve(),
        model_card=args.model_card.resolve(), license_path=args.license.resolve(),
        token=sys.stdin.readline().strip(),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
