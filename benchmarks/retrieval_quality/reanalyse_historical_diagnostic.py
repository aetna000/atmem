#!/usr/bin/env python3
"""Reanalyse the frozen twelve-case diagnostic without upgrading its claim."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


CLASS_MAP = {
    "exact_fact": ("exact_fact_value", "entity_relation"),
    "correction": ("conflict_correction", "time_current_state"),
    "comparison": ("comparison_side",),
    "procedure": ("procedure_step_order",),
    "failure_gotcha": ("applicability_condition",),
    "tenancy": ("applicability_condition",),
    "negative_premise": ("polarity_negative_premise",),
    "state_transition": ("state_transition",),
    "temporal": ("time_current_state",),
    "conflict": ("conflict_correction",),
    "durable_rule": ("required_action", "prohibited_action", "action_target"),
}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--raw-result", required=True, type=Path)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--markdown-output", required=True, type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    raw = json.loads(args.raw_result.read_text(encoding="utf-8"))
    categories = {row["id"]: row["category"] for row in fixture["cases"]}
    totals: Counter[str] = Counter()
    failures: Counter[tuple[str, str]] = Counter()
    cases = []
    for row in raw["cases"]:
        case_id = row["case_id"]
        category = categories[case_id]
        classes = CLASS_MAP[category]
        if row.get("error"):
            outcome = "system_failure"
        elif row.get("complete_evidence") is not True:
            outcome = "retrieval_or_packing_failure_unresolved"
        elif row.get("typed_status_correct") is not True:
            outcome = "sufficiency_classification_failure"
        else:
            outcome = "passed"
        for requirement_class in classes:
            totals[requirement_class] += 1
            if outcome != "passed":
                failures[(requirement_class, outcome)] += 1
        cases.append({
            "case_id": case_id,
            "fixture_category": category,
            "requirement_classes": list(classes),
            "outcome": outcome,
            "complete_evidence": row.get("complete_evidence"),
            "typed_status_correct": row.get("typed_status_correct"),
        })
    breakdown = []
    for requirement_class in sorted(totals):
        row = {
            "requirement_class": requirement_class,
            "total": totals[requirement_class],
            "passed": sum(
                requirement_class in case["requirement_classes"] and case["outcome"] == "passed"
                for case in cases
            ),
        }
        for outcome in (
            "retrieval_or_packing_failure_unresolved",
            "sufficiency_classification_failure",
            "system_failure",
        ):
            row[outcome] = failures[(requirement_class, outcome)]
        breakdown.append(row)
    report = {
        "format": "atmem-historical-twelve-reanalysis-v1",
        "claim": "small-reader-free-diagnostic-only-not-benchmark-evidence",
        "case_count": 12,
        "fixture_sha256": _sha256(args.fixture),
        "raw_result_sha256": _sha256(args.raw_result),
        "limitations": [
            "The historical raw result records selected evidence but not formation, nomination, expansion, packing and delivery as separate stages.",
            "Incomplete evidence is therefore labelled retrieval_or_packing_failure_unresolved and is not retrospectively assigned to a more specific stage.",
            "No reader or action model ran, so this diagnostic cannot measure reading or action failures.",
            "This twelve-case fixture is not LongMemEval-V2 or DolphinBench evidence.",
        ],
        "breakdown": breakdown,
        "cases": cases,
    }
    report["report_sha256"] = "sha256:" + hashlib.sha256(json.dumps(
        report, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    args.json_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    columns = [
        "Requirement class", "Total", "Passed", "Retrieval/packing unresolved",
        "Sufficiency classification", "System failure",
    ]
    lines = [
        "# Historical twelve-case requirement-class reanalysis",
        "",
        "**Status:** small reader-free diagnostic only; not LongMemEval-V2 or DolphinBench evidence.",
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in breakdown:
        lines.append("| " + " | ".join(map(str, (
            row["requirement_class"], row["total"], row["passed"],
            row["retrieval_or_packing_failure_unresolved"],
            row["sufficiency_classification_failure"], row["system_failure"],
        ))) + " |")
    lines.extend((
        "",
        "The retained pre-change evidence did not record formation, nomination, expansion, packing and delivery separately. Four incomplete-evidence cases are therefore attributed only to the combined retrieval/packing boundary. They are not called formation or reader failures.",
        "",
        f"Machine-readable report: `{args.json_output.name}` (`{report['report_sha256']}`).",
    ))
    args.markdown_output.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
