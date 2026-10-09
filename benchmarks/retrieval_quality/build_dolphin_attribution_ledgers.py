#!/usr/bin/env python3
"""Build complete Dolphin requirement ledgers from reviewed run evidence."""

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
    assess_dolphin_action_gate_pair,
    build_stage_ledger,
    validate_requirement_manifest,
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


def build_ledgers(*, manifest: dict, observations: dict, pair_report: dict,
                  review_protocol: dict, output_root: Path) -> list[dict]:
    cases = {str(row["case_id"]): row for row in manifest["cases"]}
    validate_requirement_manifest(manifest, expected_case_ids=cases)
    validate_reviewed_observations(
        observations, manifest=manifest, review_protocol=review_protocol
    )
    observed = {str(row.get("case_id") or ""): row for row in observations.get("cases") or ()}
    pairs = {str(row.get("case_id") or ""): row for row in pair_report.get("pairs") or ()}
    if set(observed) != set(cases) or len(observed) != len(cases):
        raise ValueError("reviewed Dolphin observations must cover all 30 tasks")
    if set(pairs) != set(cases) or len(pairs) != len(cases):
        raise ValueError("Dolphin removal/positive pairs must cover all 30 tasks")
    outputs = []
    for case_id, requirement_case in cases.items():
        row = observed[case_id]
        requirements = row.get("requirements")
        expected_ids = {item["requirement_id"] for item in requirement_case["requirements"]}
        if not isinstance(requirements, dict) or set(requirements) != expected_ids:
            raise ValueError(f"reviewed Dolphin requirement coverage differs: {case_id}")
        normalized = {}
        for requirement_id, stages in requirements.items():
            if not isinstance(stages, dict) or set(stages) != set(PIPELINE_STAGES):
                raise ValueError(f"reviewed Dolphin stages are incomplete: {requirement_id}")
            normalized[requirement_id] = {stage: dict(stages[stage]) for stage in PIPELINE_STAGES}
        terminal = str(row.get("terminal_outcome") or "")
        ledger = build_stage_ledger(
            case_id=case_id,
            terminal_outcome=terminal,
            requirement_observations=normalized,
        )
        ledger["action_gate_control"] = assess_dolphin_action_gate_pair(pairs[case_id])
        ledger.pop("ledger_sha256", None)
        ledger["ledger_sha256"] = canonical_digest(ledger)
        _write(output_root / f"{case_id.replace(':', '-')}.json", ledger)
        outputs.append(ledger)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--reviewed-observations", required=True, type=Path)
    parser.add_argument("--review-protocol", required=True, type=Path)
    parser.add_argument("--action-gate-pairs", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    ledgers = build_ledgers(
        manifest=_load(args.manifest),
        observations=_load(args.reviewed_observations),
        review_protocol=_load(args.review_protocol),
        pair_report=_load(args.action_gate_pairs),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps({"case_count": len(ledgers), "output_root": str(args.output_root.resolve())}))


if __name__ == "__main__":
    main()
