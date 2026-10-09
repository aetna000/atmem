#!/usr/bin/env python3
"""Render fail-closed LongMem and Dolphin attribution evidence tables."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from atmem.benchmark.attribution import (  # noqa: E402
    assess_dolphin_action_gate_pair,
    validate_requirement_manifest,
    validate_stage_ledger,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _failure_column(stages: list[dict], terminal: str) -> str | None:
    failed = next((row["stage"] for row in stages if row["state"] == "failed"), None)
    if failed == "source_exists" or terminal == "source_dataset_failure":
        return "source_dataset_failure"
    if failed == "represented":
        return "formation_missing"
    if failed in {"nominated", "expanded", "packed", "delivered"}:
        return "retrieval_packing_failure"
    if terminal in {"reader_use_noise_failure", "reader_capability_prompt_failure"}:
        return "reader_failure"
    if terminal in {"parsing_failure", "provider_system_failure"}:
        return "system_failure"
    return None


def render_longmem(manifest: dict, ledgers: list[dict]) -> tuple[list[dict], str]:
    cases = {str(row["case_id"]): row for row in manifest["cases"]}
    if {row.get("case_id") for row in ledgers} != set(cases) or len(ledgers) != len(cases):
        raise ValueError("LongMem attribution tables require exactly one ledger per frozen case")
    counts: dict[str, Counter] = {}
    for ledger in ledgers:
        case = cases[str(ledger["case_id"])]
        requirements = {row["requirement_id"]: row for row in case["requirements"]}
        validate_stage_ledger(ledger, expected_requirement_ids=requirements)
        rows = {row["requirement_id"]: row for row in ledger["requirements"]}
        for requirement_id, requirement in requirements.items():
            column = _failure_column(rows[requirement_id]["stages"], ledger["terminal_outcome"])
            for class_name in requirement["classes"]:
                counter = counts.setdefault(class_name, Counter())
                counter["total"] += 1
                if column:
                    counter[column] += 1
    table = [{
        "requirement_class": class_name,
        "total": row["total"],
        "source_dataset_failure": row["source_dataset_failure"],
        "formation_missing": row["formation_missing"],
        "retrieval_packing_failure": row["retrieval_packing_failure"],
        "reader_failure": row["reader_failure"],
        "system_failure": row["system_failure"],
    } for class_name, row in sorted(counts.items())]
    lines = [
        "| Requirement class | Total | Source/dataset failure | Formation missing | Retrieval/packing failure | Reader failure | System failure |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        f"| {row['requirement_class']} | {row['total']} | {row['source_dataset_failure']} | "
        f"{row['formation_missing']} | "
        f"{row['retrieval_packing_failure']} | {row['reader_failure']} | {row['system_failure']} |"
        for row in table
    )
    return table, "\n".join(lines)


def render_dolphin(manifest: dict, pairs: list[dict]) -> tuple[list[dict], str]:
    case_ids = {str(row["case_id"]) for row in manifest["cases"]}
    if {row.get("case_id") for row in pairs} != case_ids or len(pairs) != len(case_ids):
        raise ValueError("Dolphin tables require exactly one removal/positive pair per task")
    table = []
    for pair in sorted(pairs, key=lambda row: str(row["case_id"])):
        assessment = assess_dolphin_action_gate_pair(pair)
        removal = pair["removal"]
        table.append({
            "task": pair["case_id"],
            "removed_requirement": pair["removed_requirement_id"],
            "gate_decision": removal["outcome"],
            "model_invoked": removal["model_invoked"],
            "tool_calls": removal["tool_calls"],
            "actual_reason": removal["actual_reason"],
            "control_passed": assessment["passed"],
            "failure_reason": assessment["failure_reason"],
        })
    lines = [
        "| Task | Removed requirement | Gate decision | Model invoked | Tool calls | Actual reason |",
        "|---|---|---|---|---:|---|",
    ]
    lines.extend(
        f"| {row['task']} | {row['removed_requirement']} | {row['gate_decision']} | "
        f"{str(row['model_invoked']).lower()} | {row['tool_calls']} | {row['actual_reason']} |"
        for row in table
    )
    return table, "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--longmem-manifest", required=True, type=Path)
    parser.add_argument("--longmem-ledger-root", required=True, type=Path)
    parser.add_argument("--dolphin-manifest", required=True, type=Path)
    parser.add_argument("--dolphin-ledger-root", required=True, type=Path)
    parser.add_argument("--dolphin-pairs", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    long_manifest = _load(args.longmem_manifest)
    dolphin_manifest = _load(args.dolphin_manifest)
    validate_requirement_manifest(
        long_manifest, expected_case_ids=[row["case_id"] for row in long_manifest["cases"]]
    )
    validate_requirement_manifest(
        dolphin_manifest, expected_case_ids=[row["case_id"] for row in dolphin_manifest["cases"]]
    )
    ledgers = [_load(path) for path in sorted(args.longmem_ledger_root.glob("*.json"))]
    dolphin_ledgers = [
        _load(path) for path in sorted(args.dolphin_ledger_root.glob("*.json"))
    ]
    pair_report = _load(args.dolphin_pairs)
    long_table, long_markdown = render_longmem(long_manifest, ledgers)
    dolphin_table, dolphin_markdown = render_dolphin(
        dolphin_manifest, list(pair_report.get("pairs") or ())
    )
    dolphin_requirement_table, dolphin_requirement_markdown = render_longmem(
        dolphin_manifest, dolphin_ledgers
    )
    output = {
        "format": "atmem-five-percent-attribution-tables-v1",
        "longmemeval": long_table,
        "dolphinbench": dolphin_table,
        "dolphinbench_requirements": dolphin_requirement_table,
    }
    _write(args.output_root / "attribution-tables.json", json.dumps(output, indent=2, sort_keys=True) + "\n")
    _write(
        args.output_root / "attribution-tables.md",
        "# LongMemEval-V2 requirement attribution\n\n" + long_markdown
        + "\n\n# DolphinBench removal controls\n\n"
        + dolphin_markdown
        + "\n\n# DolphinBench requirement attribution\n\n"
        + dolphin_requirement_markdown
        + "\n",
    )


if __name__ == "__main__":
    main()
