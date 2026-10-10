#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


LONGMEM_HASHES = {
    "checksums.sha256": "b17a18daa52873f915808502217c3c5fab39d20638544f986401155c9e8d67a6",
    "haystacks/lme_v2_small.json": "9b5301defb23a088a5f06e45ff8d5f35e569d78305a66d492046a9fff9b46593",
    "questions.jsonl": "0a3ae5ebea938c24d7800e1e0b0828e08ae1646f939a53853b2b8cdc08e292b7",
    "trajectories.jsonl": "363cec9a8e87aa8d9101ce4e600aadbf7031d674056ebe4f969e8424abc5f3c6",
}
DOLPHIN_COMMIT = "81cb6f8405b40a9e76089cef650806a80af06ea2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_manifest(bundle: Path) -> list[str]:
    failures: list[str] = []
    manifest = bundle / "SHA256SUMS"
    if not manifest.is_file():
        return ["missing SHA256SUMS"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = bundle / relative
        if not path.is_file():
            failures.append(f"missing bundle file: {relative}")
        elif sha256(path) != expected:
            failures.append(f"bundle hash mismatch: {relative}")
    return failures


def verify_longmem(root: Path) -> list[str]:
    failures: list[str] = []
    for relative, expected in LONGMEM_HASHES.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"missing LongMem file: {relative}")
        elif sha256(path) != expected:
            failures.append(f"LongMem hash mismatch: {relative}")
    return failures


def verify_checkout(root: Path, expected: str, label: str) -> list[str]:
    try:
        actual = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return [f"cannot inspect {label} checkout: {root}"]
    return [] if actual == expected else [f"{label} commit is {actual}, expected {expected}"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--longmem-data", type=Path)
    parser.add_argument("--dolphin-checkout", type=Path)
    args = parser.parse_args()
    bundle = args.bundle.expanduser().resolve()
    failures = verify_manifest(bundle)

    metadata = json.loads((bundle / "benchmark-metadata.json").read_text(encoding="utf-8"))
    if metadata.get("release") != "2.3.8":
        failures.append("benchmark metadata release is not 2.3.8")
    if args.longmem_data:
        failures.extend(verify_longmem(args.longmem_data.expanduser().resolve()))
    if args.dolphin_checkout:
        failures.extend(verify_checkout(
            args.dolphin_checkout.expanduser().resolve(), DOLPHIN_COMMIT, "DolphinBench"
        ))

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("OK: all requested bundle and upstream checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
