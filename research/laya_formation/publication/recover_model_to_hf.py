from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from huggingface_hub import CommitOperationAdd, HfApi

from research.laya_formation.training.contracts import secret_findings


def recover(*, repo_id: str, run_root: Path, selection_path: Path, token: str) -> dict[str, str]:
    if not token:
        raise RuntimeError("a Hugging Face token is required on stdin")
    required = [
        run_root / "model" / "model.safetensors",
        run_root / "model" / "rl_agent_config.json",
        run_root / "model" / "encoder" / "config.json",
        run_root / "model" / "tokenizer" / "tokenizer.json",
        run_root / "model" / "tokenizer" / "tokenizer_config.json",
        run_root / "model" / "tokenizer" / "special_tokens_map.json",
        run_root / "training-manifest.json",
        run_root / "validation-metrics.json",
        run_root / "base-validation-metrics.json",
        run_root / "calibration-bundle.json",
        run_root / "calibration-metrics.json",
        selection_path,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"selected recovery inventory is incomplete: {missing}")
    for path in required:
        if path.suffix == ".json" and secret_findings(path.read_text(encoding="utf-8")):
            raise RuntimeError(f"secret-like material found in {path}")
    operations = []
    model_root = run_root / "model"
    for path in sorted(model_root.rglob("*")):
        if path.is_file():
            operations.append(CommitOperationAdd(path_in_repo=path.relative_to(model_root).as_posix(), path_or_fileobj=str(path)))
    for path in required[6:-1]:
        operations.append(CommitOperationAdd(path_in_repo=f"training/{path.name}", path_or_fileobj=str(path)))
    operations.append(CommitOperationAdd(path_in_repo="training/objective-selection.json", path_or_fileobj=str(selection_path)))
    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="model", private=True, exist_ok=True)
    commit = api.create_commit(
        repo_id=repo_id,
        repo_type="model",
        operations=operations,
        commit_message="Recover selected private RLCD checkpoint and frozen training evidence",
    )
    return {"repo_id": repo_id, "commit": commit.oid, "url": commit.commit_url}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recover a selected Spec 041 model directly to private Hugging Face storage")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    args = parser.parse_args(argv)
    token = sys.stdin.readline().strip()
    result = recover(
        repo_id=args.repo_id, run_root=args.run_root.resolve(),
        selection_path=args.selection.resolve(), token=token,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
