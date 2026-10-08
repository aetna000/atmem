"""Run the pinned AGMI AtMem T1-T9 rows without historical score assertions."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.append(str(ROOT))

from research.production_benchmarks.installed_product import (  # noqa: E402
    installed_atmem_identity,
)
from research.production_benchmarks.local_resources import (  # noqa: E402
    configure_local_resource_limits,
)


PROTOCOL = ROOT / "benchmarks/retrieval_quality/protocols/agmi-atmem-v1.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_checkout(checkout: Path, protocol: dict) -> dict[str, object]:
    if not checkout.is_dir():
        raise RuntimeError("pinned AGMI checkout does not exist")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=checkout, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    if commit != protocol["source_commit"]:
        raise RuntimeError(f"AGMI checkout differs from pinned commit: {commit}")
    for relative, expected in protocol["files"].items():
        path = checkout / relative
        if not path.is_file() or _sha256(path) != expected:
            raise RuntimeError(f"pinned AGMI file differs: {relative}")
    pyproject = (checkout / "pyproject.toml").read_text(encoding="utf-8")
    if f'version = "{protocol["package_version"]}"' not in pyproject:
        raise RuntimeError("AGMI package version differs from protocol")
    return {
        "repository": protocol["repository"],
        "commit": commit,
        "package_version": protocol["package_version"],
        "files": dict(protocol["files"]),
    }


def main() -> int:
    local_resources = configure_local_resource_limits()
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--confirm-run", action="store_true")
    args = parser.parse_args()
    if not args.confirm_run:
        raise SystemExit("refusing AGMI qualification without --confirm-run")
    if subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip():
        raise SystemExit("AGMI qualification requires the exact clean reviewed commit")

    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    installed = installed_atmem_identity(protocol["candidate_atmem_version"])
    checkout = Path(args.checkout).expanduser().resolve()
    source = _verify_checkout(checkout, protocol)
    if str(checkout) not in sys.path:
        sys.path.insert(0, str(checkout))

    from agmi.adapters.atmem import AtMemAnchoredAdapter, AtMemChainAdapter
    from agmi.attacks.at_rest import AT_REST_ATTACKS_WITH_SNAPSHOT

    attack_names = [attack.name for attack in AT_REST_ATTACKS_WITH_SNAPSHOT]
    if attack_names != protocol["attacks"]:
        raise RuntimeError("AGMI attack order or membership differs from protocol")
    profiles = (AtMemChainAdapter, AtMemAnchoredAdapter)
    if [profile.name for profile in profiles] != protocol["profiles"]:
        raise RuntimeError("AGMI AtMem profiles differ from protocol")

    started = time.time()
    results: list[dict[str, object]] = []
    for profile in profiles:
        for attack in AT_REST_ATTACKS_WITH_SNAPSHOT:
            result = attack().run(profile())
            row = asdict(result)
            row["status"] = result.status
            results.append(row)
    summary = {}
    for profile in protocol["profiles"]:
        rows = [row for row in results if row["tool"] == profile]
        summary[profile] = {
            "detected": sum(row["detected"] is True and not row["error"] and not row["guard"] for row in rows),
            "accepted": sum(row["detected"] is False and not row["error"] and not row["guard"] for row in rows),
            "errors": sum(bool(row["error"] or row["guard"]) for row in rows),
            "total": len(rows),
        }
    report = {
        "format": "atmem-agmi-qualification-v1",
        "claim": "installed-candidate-development-remeasurement",
        "protocol_sha256": "sha256:" + _sha256(PROTOCOL),
        "source": source,
        "installed_product": installed,
        "installed_distribution_version": metadata.version("atmem"),
        "execution_topology": "mac-controller;no-model-or-gpu-required",
        "local_resources": local_resources,
        "started_unix": started,
        "completed_unix": time.time(),
        "historical_published_result": protocol["published_2_3_7"],
        "results": results,
        "summary": summary,
    }
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
