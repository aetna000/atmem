from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from huggingface_hub import CommitOperationAdd, HfApi

from research.laya_formation.training.contracts import secret_findings


def archive(*, repo_id: str, runs_root: Path, selected_run: str, token: str) -> dict[str, str | int]:
    if not token:
        raise RuntimeError("a Hugging Face token is required on stdin")
    selected = runs_root / selected_run
    if not (selected / "training-manifest.json").is_file():
        raise FileNotFoundError("selected training run is incomplete")
    included = [selected, *sorted(runs_root.glob("failed-*"))]
    files = [path for root in included for path in sorted(root.rglob("*")) if path.is_file()]
    selection = runs_root / "objective-selection.json"
    if not selection.is_file():
        raise FileNotFoundError("objective selection is missing")
    files.append(selection)
    for path in files:
        if path.suffix == ".json" and secret_findings(path.read_text(encoding="utf-8")):
            raise RuntimeError(f"secret-like material found in {path}")
    operations = []
    for path in files:
        relative = path.relative_to(runs_root).as_posix()
        operations.append(CommitOperationAdd(path_in_repo=relative, path_or_fileobj=str(path)))
    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="dataset", private=True, exist_ok=True)
    commit = api.create_commit(
        repo_id=repo_id, repo_type="dataset", operations=operations,
        commit_message="Archive selected RLCD run, epoch checkpoints, and retained failures",
    )
    return {"repo_id": repo_id, "commit": commit.oid, "url": commit.commit_url, "files": len(files)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive paid Spec 041 training evidence before instance destruction")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--selected-run", required=True)
    args = parser.parse_args(argv)
    result = archive(
        repo_id=args.repo_id, runs_root=args.runs_root.resolve(),
        selected_run=args.selected_run, token=sys.stdin.readline().strip(),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
