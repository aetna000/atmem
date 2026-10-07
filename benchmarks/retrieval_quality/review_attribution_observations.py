#!/usr/bin/env python3
"""Create or finalize evaluator-only requirement review packets.

Initialization deliberately emits invalid ``unreviewed`` states and no digest.
Only ``finalize`` can sign a packet, and it first applies the same strict
validator used by the ledger builders.  This prevents an empty template from
being mistaken for benchmark evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from atmem.benchmark.attribution import (  # noqa: E402
    PIPELINE_STAGES,
    REVIEWED_OBSERVATIONS_FORMAT,
    validate_requirement_manifest,
    validate_review_protocol,
    validate_reviewed_observations,
)
from atmem.benchmark.contracts import canonical_digest  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def initialize_packet(
    *, manifest: dict, review_protocol: dict, reviewer_identity: str
) -> dict:
    validate_requirement_manifest(
        manifest, expected_case_ids=[row["case_id"] for row in manifest["cases"]]
    )
    protocol = validate_review_protocol(review_protocol)
    if not reviewer_identity.strip():
        raise ValueError("reviewer identity cannot be empty")
    return {
        "format": REVIEWED_OBSERVATIONS_FORMAT,
        "benchmark": manifest["benchmark"],
        "visibility": "evaluator_only",
        "available_to_product": False,
        "manifest_sha256": manifest["manifest_sha256"],
        "review_protocol_sha256": protocol["review_protocol_sha256"],
        "reviewer_identity": reviewer_identity.strip(),
        "review_status": "unreviewed",
        "cases": [{
            "case_id": case["case_id"],
            "terminal_outcome": None,
            "requirements": {
                requirement["requirement_id"]: {
                    stage: {
                        "state": "unreviewed",
                        "evidence_refs": [],
                        "reason": "REVIEW REQUIRED",
                    }
                    for stage in PIPELINE_STAGES
                }
                for requirement in case["requirements"]
            },
        } for case in manifest["cases"]],
    }


def finalize_packet(*, packet: dict, manifest: dict, review_protocol: dict) -> dict:
    value = dict(packet)
    value["review_status"] = "complete"
    value.pop("observations_sha256", None)
    value["observations_sha256"] = canonical_digest(value)
    return validate_reviewed_observations(
        value, manifest=manifest, review_protocol=review_protocol
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    initialize = subparsers.add_parser("init")
    initialize.add_argument("--manifest", required=True, type=Path)
    initialize.add_argument("--review-protocol", required=True, type=Path)
    initialize.add_argument("--reviewer-identity", required=True)
    initialize.add_argument("--output", required=True, type=Path)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--manifest", required=True, type=Path)
    finalize.add_argument("--review-protocol", required=True, type=Path)
    finalize.add_argument("--input", required=True, type=Path)
    finalize.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = _load(args.manifest)
    protocol = _load(args.review_protocol)
    if args.command == "init":
        value = initialize_packet(
            manifest=manifest, review_protocol=protocol,
            reviewer_identity=args.reviewer_identity,
        )
    else:
        value = finalize_packet(
            packet=_load(args.input), manifest=manifest, review_protocol=protocol
        )
    _write(args.output, value)
    print(json.dumps({
        "command": args.command,
        "case_count": len(value["cases"]),
        "review_status": value["review_status"],
        "output": str(args.output.resolve()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
