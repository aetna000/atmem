"""Bounded public dataset downloads, pinned to authenticated Git tree objects.

No provider credentials or model inference. Run with an explicit MEM destination.
Only public benchmark inputs are written, never product memory or archives.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import urllib.request


def read_url(url: str, limit: int) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "AtMem-corpus-qualification"}), timeout=45) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("download exceeded declared byte limit")
    return data


def fetch_corpus(config: dict, destination: Path) -> dict:
    revision, repo = config["revision"], config["repository"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise ValueError("immutable Git revision and valid repository required")
    tree = json.loads(read_url(f"https://api.github.com/repos/{repo}/git/trees/{revision}?recursive=1", 5_000_000))
    if tree.get("sha") != revision or tree.get("truncated"):
        raise ValueError("incomplete or unexpected Git tree")
    files = [entry for entry in tree["tree"] if entry["type"] == "blob" and
             (entry["path"].startswith(tuple(config["prefixes"])) or entry["path"] in {"LICENSE", "README.md"})]
    if not files or sum(f["size"] for f in files) > config["max_download_bytes"]:
        raise ValueError("dataset absent or exceeds declared disk budget")
    root = destination / config["id"] / revision
    root.mkdir(parents=True, exist_ok=True)
    def fetch(entry: dict) -> dict:
        relative = PurePosixPath(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe source path")
        target = root.joinpath(*relative.parts)
        if target.is_symlink() or any(p.is_symlink() for p in target.parents):
            raise ValueError("symlink destination refused")
        data = target.read_bytes() if target.exists() else read_url(
            f"https://raw.githubusercontent.com/{repo}/{revision}/{relative}", entry["size"])
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if len(data) != entry["size"] or blob != entry["sha"]:
            raise ValueError("dataset bytes differ from pinned Git object")
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive publication: interrupted/foreign files are never overwritten.
            with target.open("xb") as stream:
                stream.write(data)
        return {"path": str(relative), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(fetch, files))
    return {"corpus": config["id"], "revision": revision, "root": str(root),
            "bytes": sum(row["bytes"] for row in receipts), "files": receipts,
            "status": "download-verified-not-dispatch-qualified"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path(__file__).with_name("corpora.json"))
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text())
    for config in registry["corpora"]:
        receipt = fetch_corpus(config, args.destination)
        # Hash receipts, not conversations/answers, are safe console output.
        print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
