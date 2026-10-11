from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any

FORBIDDEN_SUFFIXES = {".pkl", ".pickle", ".joblib"}
SECRET = re.compile(r"(?i)(?:api[_-]?key|password|secret|token)\s*[:=]\s*[A-Za-z0-9_./+-]{8,}")
TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".txt"}
PLATFORM_MANAGED_REMOTE_FILES = {".gitattributes"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _env_value(path: Path, name: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            value = line.split("=", 1)[1].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'\"', "'"}:
                value = value[1:-1]
            if value:
                return value
    raise RuntimeError(f"{name} is not configured in {path}")


def validate_local(
    root: Path,
    *,
    ignored_platform_files: frozenset[str] = frozenset(),
    ignore_snapshot_cache: bool = False,
) -> tuple[dict[str, Any], dict[str, str]]:
    manifest_path = root / "manifests" / "dataset-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {row["path"]: row for row in manifest["files"]}
    actual_paths = {
        str(path.relative_to(root)): path
        for path in root.rglob("*")
        if path.is_file()
        and not path.name.startswith("._")
        and path.name != ".DS_Store"
        and str(path.relative_to(root)) not in ignored_platform_files
        and not (ignore_snapshot_cache and ".cache" in path.relative_to(root).parts)
    }
    expected_all = set(expected) | {"manifests/dataset-manifest.json"}
    if set(actual_paths) != expected_all:
        raise ValueError("local publication files differ from the manifest inventory")
    digests: dict[str, str] = {}
    for relative, path in actual_paths.items():
        if path.is_symlink():
            raise ValueError(f"symlink is forbidden: {relative}")
        if path.suffix.casefold() in FORBIDDEN_SUFFIXES:
            raise ValueError(f"unsafe serialized file is forbidden: {relative}")
        digest = _sha256(path)
        digests[relative] = digest
        if relative in expected:
            row = expected[relative]
            if path.stat().st_size != row["size"] or digest != row["sha256"]:
                raise ValueError(f"manifest mismatch: {relative}")
        if path.suffix.casefold() in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8")
            if SECRET.search(text):
                raise ValueError(f"credential-like content detected: {relative}")
            if path.suffix.casefold() == ".json":
                json.loads(text)
            elif path.suffix.casefold() == ".jsonl":
                for number, line in enumerate(text.splitlines(), start=1):
                    try:
                        json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"invalid JSONL {relative}:{number}") from exc
    if manifest.get("generator_version") != "1.3.0" or manifest.get("synthetic_only") is not True:
        raise ValueError("unexpected dataset identity")
    return manifest, digests


def main() -> int:
    from huggingface_hub import HfApi, snapshot_download

    parser = argparse.ArgumentParser(description="Privately stage and verify the Spec 041 dataset")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest, local_digests = validate_local(root)
    token = _env_value(args.env_file, "HF_TOKEN")
    api = HfApi(token=token)
    api.create_repo(
        repo_id=args.repo_id,
        repo_type="dataset",
        visibility="private",
        exist_ok=True,
    )
    initial_info = api.repo_info(args.repo_id, repo_type="dataset")
    if initial_info.private is not True:
        raise RuntimeError("refusing to stage into a non-private dataset repository")
    commit = api.upload_folder(
        repo_id=args.repo_id,
        repo_type="dataset",
        folder_path=root,
        commit_message="Stage AtMem Laya Formation Dataset v1.3.0",
        ignore_patterns=["._*", "**/._*", ".DS_Store", "**/.DS_Store"],
    )
    info = api.repo_info(args.repo_id, repo_type="dataset", revision=commit.oid, files_metadata=True)
    if info.private is not True:
        raise RuntimeError("staged dataset repository is not private")
    remote_files = {item.rfilename for item in info.siblings}
    expected_remote_files = set(local_digests) | PLATFORM_MANAGED_REMOTE_FILES
    if remote_files != expected_remote_files:
        raise RuntimeError("remote repository membership differs from local inventory")
    with tempfile.TemporaryDirectory(prefix="atmem-laya-hf-verify-") as temporary:
        downloaded = Path(
            snapshot_download(
                repo_id=args.repo_id,
                repo_type="dataset",
                revision=commit.oid,
                token=token,
                local_dir=temporary,
            )
        )
        downloaded_files = {
            str(path.relative_to(downloaded)): path
            for path in downloaded.rglob("*")
            if path.is_file() and ".cache" not in path.parts
        }
        if set(downloaded_files) != expected_remote_files:
            raise RuntimeError("downloaded repository membership differs from local inventory")
        for relative, expected in local_digests.items():
            if _sha256(downloaded_files[relative]) != expected:
                raise RuntimeError(f"download digest mismatch: {relative}")
        validate_local(
            downloaded,
            ignored_platform_files=frozenset(PLATFORM_MANAGED_REMOTE_FILES),
            ignore_snapshot_cache=True,
        )
    receipt = {
        "format": "atmem-laya-hf-staging-receipt-v1",
        "state": "private_staged",
        "repo_id": args.repo_id,
        "repo_type": "dataset",
        "private": True,
        "commit": commit.oid,
        "url": f"https://huggingface.co/datasets/{args.repo_id}/tree/{commit.oid}",
        "staged_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": manifest["generator_version"],
        "scenario_count": manifest["scenario_count"],
        "decision_count": manifest["decision_count"],
        "file_count": len(local_digests),
        "platform_managed_files": sorted(PLATFORM_MANAGED_REMOTE_FILES),
        "dataset_manifest_sha256": local_digests["manifests/dataset-manifest.json"],
        "redownload_verified": True,
        "schema_and_secret_scan": "passed",
        "visibility_change_ready": True,
        "public": False,
    }
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
