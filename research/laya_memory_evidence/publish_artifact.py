"""Stage, verify, publish and anonymously redownload a Hugging Face artifact."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any

from huggingface_hub import HfApi, snapshot_download


_SECRET = re.compile(
    rb"(?:\bhf_[A-Za-z0-9]{20,}\b|\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}\b|"
    rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
    rb"\bxox[baprs]-[A-Za-z0-9-]{16,}\b|\bAKIA[0-9A-Z]{16}\b|"
    rb"(?<![A-Za-z0-9_])(?:[A-Za-z0-9_]{0,32})?"
    rb"(?:api[_-]?key|access[_-]?token|auth[_-]?token|private[_-]?key|secret)"
    rb"\s*[:=]\s*['\"]?(?:https?://[^\s'\"]+/[A-Za-z0-9_-]{20,}|[A-Za-z0-9_./+=-]{20,})|"
    rb"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)", re.IGNORECASE,
)


def _contains_secret(path: Path) -> bool:
    overlap = b""
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value = overlap + block
            if _SECRET.search(value):
                return True
            overlap = value[-2048:]
    return False


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(root).as_posix(), "size": path.stat().st_size, "sha256": _sha(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.name != ".DS_Store"
        and not path.name.endswith(("-wal", "-shm"))
        and ".cache" not in path.parts
    ]


def _verify_tree(root: Path, expected: list[dict[str, Any]]) -> None:
    actual = _inventory(root)
    # Hugging Face may materialize card metadata files. Every uploaded file must
    # match; unexpected service metadata is harmless and is ignored.
    by_path = {item["path"]: item for item in actual}
    for item in expected:
        if by_path.get(item["path"]) != item:
            raise RuntimeError(f"downloaded artifact differs: {item['path']}")
    unexpected = sorted(
        path for path in set(by_path) - {item["path"] for item in expected} - {".gitattributes"}
        if not path.startswith(".cache/huggingface/")
    )
    if unexpected:
        raise RuntimeError(f"downloaded artifact contains unexpected files: {unexpected}")
    findings = []
    for item in actual:
        path = root / item["path"]
        if _contains_secret(path):
            findings.append(item["path"])
        if path.suffix in {".sqlite3", ".db"}:
            connection = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
            try:
                if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise RuntimeError(f"SQLite integrity failed: {item['path']}")
            finally:
                connection.close()
    if findings:
        raise RuntimeError(f"secret-like material found: {findings}")


def publish(root: Path, repo_id: str, repo_type: str, receipt_path: Path) -> dict[str, Any]:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is required")
    expected = _inventory(root)
    _verify_tree(root, expected)
    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type=repo_type, private=True, exist_ok=True)
    commit = api.upload_folder(
        repo_id=repo_id, repo_type=repo_type, folder_path=str(root),
        commit_message="Publish frozen stateful memory artifact",
        ignore_patterns=[
            ".DS_Store", "._*", "__pycache__/*", "*-wal", "*-shm",
            ".cache/*", ".cache/**/*",
        ],
    )
    revision = str(commit.oid)
    with tempfile.TemporaryDirectory(prefix="atmem-hf-private-") as temporary:
        downloaded = Path(snapshot_download(
            repo_id=repo_id, repo_type=repo_type, revision=revision,
            token=token, local_dir=temporary,
        ))
        _verify_tree(downloaded, expected)
    api.update_repo_settings(repo_id=repo_id, repo_type=repo_type, private=False)
    with tempfile.TemporaryDirectory(prefix="atmem-hf-public-") as temporary:
        downloaded = Path(snapshot_download(
            repo_id=repo_id, repo_type=repo_type, revision=revision,
            token=False, local_dir=temporary,
        ))
        _verify_tree(downloaded, expected)
    receipt = {
        "format": "atmem-hugging-face-publication-receipt-v2",
        "repo_id": repo_id, "repo_type": repo_type, "revision": revision,
        "url": f"https://huggingface.co/{'datasets/' if repo_type == 'dataset' else ''}{repo_id}",
        "private_stage_verified": True, "public_anonymous_redownload_verified": True,
        "inventory": expected,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--repo-type", choices=("dataset", "model"), required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.root, args.repo_id, args.repo_type, args.receipt), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
