"""Evaluator-only discovery. No eligibility, grader or solver success inferred."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

from benchmarks.code_replay.contracts import commit


def git(checkout, *args):
    return subprocess.check_output(["git", "-C", str(checkout), *args], timeout=30)


def classify(paths):
    if not paths:
        return "packaging_only"
    if all(p.startswith("docs/") or p.endswith(".md") or p.endswith(".rst") for p in paths):
        return "docs_only"
    if all(p.startswith(".github/") or p.startswith(".pre-commit") or p in {"uv.lock", "requirements.txt"} for p in paths):
        return "dependency_only"
    if not any(p.startswith("src/") for p in paths):
        return "packaging_only"
    return "functional_review_required"


def discover(checkout: Path, anchor: str):
    commit(anchor, "anchor_commit")
    if not checkout.is_dir():
        raise ValueError("evaluator checkout missing")
    revisions = git(checkout, "rev-list", "--first-parent", "--max-count=100", anchor).decode().splitlines()
    entries = []
    for revision in revisions:
        metadata = git(checkout, "show", "-s", "--format=%H%n%P%n%aI%n%cI%n%s", revision).decode().splitlines()
        parents = metadata[1].split()
        if not parents:
            break
        parent = parents[0]
        paths = git(checkout, "diff", "--name-only", "-z", parent, revision).decode().strip("\0").split("\0")
        pr = re.search(r"\(#([0-9]+)\)$", metadata[4])
        entries.append({"reference_commit": revision, "parent_commit": parent, "author_at": metadata[2],
                        "committer_at": metadata[3], "subject": metadata[4], "pull_request": int(pr[1]) if pr else None,
                        "paths": paths, "change_kind": classify(paths), "qualification": "not_reviewed"})
    license_bytes = git(checkout, "show", f"{anchor}:LICENSE.txt")
    return {"format": "atmem-click-evaluator-discovery-v1", "anchor_commit": anchor,
            "search_horizon": 100, "license_sha256": sha256(license_bytes).hexdigest(),
            "license": "BSD-3-Clause; issue text reviewed separately", "entries": entries,
            "selection_status": "not_qualified", "solver_visible": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("anchor")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = discover(args.checkout, args.anchor)
    raw = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        # Exclusive creation preserves a previous frozen discovery artifact.
        with args.output.open("x") as stream:
            stream.write(raw)
        print(json.dumps({"artifact_sha256": sha256(raw.encode()).hexdigest(), "entries": len(value["entries"]),
                          "selection_status": value["selection_status"]}))
    else:
        print(raw, end="")


if __name__ == "__main__":
    main()
