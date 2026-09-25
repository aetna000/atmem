"""Record built baseline artifacts without modifying the immutable protocol lock."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import zipfile

from .manifest import file_digest, git_head


def wheel_record(path: Path) -> dict:
    with zipfile.ZipFile(path) as wheel:
        metadata_files = [name for name in wheel.namelist() if name.endswith('.dist-info/METADATA')]
        if len(metadata_files) != 1:
            raise ValueError("wheel must have exactly one METADATA")
        metadata = wheel.read(metadata_files[0]).decode()
        name = next(line[6:] for line in metadata.splitlines() if line.startswith("Name: "))
        version = next(line[9:] for line in metadata.splitlines() if line.startswith("Version: "))
    return {"filename": path.name, "sha256": file_digest(path), "name": name, "version": version}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atmem-wheel", type=Path, required=True)
    parser.add_argument("--atflows-wheel", type=Path, required=True)
    parser.add_argument("--atflows-repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    trees = [(root, ["atmem", "pyproject.toml"]),
             (args.atflows_repo, ["apps", "packages", "atflows", "pyproject.toml", "package.json"])]
    for repo, paths in trees:
        if subprocess.check_output(["git", "status", "--porcelain", "--", *paths], cwd=repo, text=True).strip():
            raise ValueError(f"baseline runtime sources are dirty in {repo.name}")
    record = {"schema_version": 1, "purpose": "current-product artifacts before fixes",
              "source_commits": {"atmem": git_head(root), "atflows": git_head(args.atflows_repo)},
              "wheels": [wheel_record(args.atmem_wheel), wheel_record(args.atflows_wheel)],
              "protocol_sha256": file_digest(Path(__file__).with_name("protocol-lock.json")),
              "contract_sha256": file_digest(root / "specs/benchmarking/002-agent-continuity/contracts/continuity-v1.md"),
              "installed_artifact_tests": "not_yet_run"}
    with args.output.open("x") as output:
        json.dump(record, output, indent=2, sort_keys=True)
        output.write("\n")


if __name__ == "__main__":
    main()
