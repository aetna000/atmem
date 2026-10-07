#!/usr/bin/env python3
"""Build final LongMem ledgers from controlled runs and reviewed observations.

This tool does not infer missing stages. The evaluator must provide an explicit
four-state observation with evidence references/reasons for every requirement
and every stage; otherwise ledger construction fails.
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
    build_stage_ledger,
    classify_longmem_outcome,
    validate_requirement_manifest,
    validate_reviewed_observations,
)


METHOD_VARIANTS = {
    "typed-local": "product_context",
    "verified-evidence": "verified_minimal_evidence",
    "no-retrieval": "no_memory",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def build_ledgers(*, manifest: dict, progress: dict, observations: dict,
                  review_protocol: dict, output_root: Path) -> list[dict]:
    cases = {str(row["case_id"]): row for row in manifest["cases"]}
    validate_requirement_manifest(manifest, expected_case_ids=cases)
    validate_reviewed_observations(
        observations, manifest=manifest, review_protocol=review_protocol
    )
    observed_cases = {
        str(row.get("case_id") or ""): row
        for row in observations.get("cases") or ()
        if isinstance(row, dict)
    }
    if set(observed_cases) != set(cases) or len(observed_cases) != len(cases):
        raise ValueError("reviewed observations must cover all 23 cases exactly once")
    controlled: dict[str, dict[str, dict]] = {}
    for row in progress.get("cases") or ():
        method = str(row.get("method") or "")
        if method in METHOD_VARIANTS:
            controlled.setdefault(str(row["question_id"]), {})[
                METHOD_VARIANTS[method]
            ] = row
    outputs = []
    for case_id, requirement_case in cases.items():
        variants = controlled.get(case_id) or {}
        if set(variants) != set(METHOD_VARIANTS.values()):
            raise ValueError(f"controlled reader results are incomplete: {case_id}")
        observation = observed_cases[case_id]
        per_requirement = observation.get("requirements")
        if not isinstance(per_requirement, dict):
            raise ValueError(f"reviewed requirement observations are missing: {case_id}")
        expected_ids = {row["requirement_id"] for row in requirement_case["requirements"]}
        if set(per_requirement) != expected_ids:
            raise ValueError(f"reviewed requirement coverage differs: {case_id}")
        normalized = {}
        for requirement_id, stages in per_requirement.items():
            if not isinstance(stages, dict) or set(stages) != set(PIPELINE_STAGES):
                raise ValueError(f"reviewed stages are incomplete: {requirement_id}")
            normalized[requirement_id] = {stage: dict(stages[stage]) for stage in PIPELINE_STAGES}
        earliest = {}
        for stage in PIPELINE_STAGES:
            states = {
                str(normalized[requirement_id][stage].get("state") or "")
                for requirement_id in normalized
            }
            if "failed" in states:
                earliest[stage] = "failed"
            elif states <= {"passed", "not_applicable"} and "passed" in states:
                earliest[stage] = "passed"
            else:
                earliest[stage] = "not_reached"
        results = {
            name: {
                "correct": row.get("score_bool") is True,
                "error_type": row.get("error_type"),
            }
            for name, row in variants.items()
        }
        product_complete = all(
            normalized[requirement_id][stage].get("state") == "passed"
            for requirement_id in normalized
            for stage in ("packed", "delivered")
        )
        terminal = classify_longmem_outcome(
            stages=earliest,
            product_complete=product_complete,
            product_reader=results["product_context"],
            verified_reader=results["verified_minimal_evidence"],
            no_memory_reader=results["no_memory"],
        )
        ledger = build_stage_ledger(
            case_id=case_id,
            terminal_outcome=terminal,
            requirement_observations=normalized,
        )
        ledger["controlled_reader"] = results
        ledger["product_context_complete"] = product_complete
        # Re-sign after adding controlled evidence.
        ledger.pop("ledger_sha256", None)
        from atmem.benchmark.contracts import canonical_digest
        ledger["ledger_sha256"] = canonical_digest(ledger)
        _write(output_root / f"{case_id}.json", ledger)
        outputs.append(ledger)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--progress", required=True, type=Path)
    parser.add_argument("--reviewed-observations", required=True, type=Path)
    parser.add_argument("--review-protocol", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    ledgers = build_ledgers(
        manifest=_load(args.manifest), progress=_load(args.progress),
        observations=_load(args.reviewed_observations),
        review_protocol=_load(args.review_protocol),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps({"case_count": len(ledgers), "output_root": str(args.output_root.resolve())}))


if __name__ == "__main__":
    main()
