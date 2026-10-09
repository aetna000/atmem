#!/usr/bin/env python3
"""Draft the Project Atlas reply only from validated benchmark evidence."""

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

from atmem.benchmark.attribution import (
    assess_dolphin_action_gate_pair,
    validate_requirement_manifest,
    validate_stage_ledger,
)
from atmem.benchmark.contracts import canonical_digest


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical", required=True, type=Path)
    parser.add_argument("--longmem-manifest", required=True, type=Path)
    parser.add_argument("--longmem-ledger-root", required=True, type=Path)
    parser.add_argument("--dolphin-manifest", required=True, type=Path)
    parser.add_argument("--dolphin-pairs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    historical = _load(args.historical)
    historical_digest = historical.get("report_sha256")
    if historical_digest != canonical_digest({
        key: value for key, value in historical.items() if key != "report_sha256"
    }):
        raise SystemExit("refusing reply: historical diagnostic digest is invalid")
    longmem_manifest = _load(args.longmem_manifest)
    dolphin_manifest = _load(args.dolphin_manifest)
    validate_requirement_manifest(
        longmem_manifest,
        expected_case_ids=[row["case_id"] for row in longmem_manifest["cases"]],
    )
    validate_requirement_manifest(
        dolphin_manifest,
        expected_case_ids=[row["case_id"] for row in dolphin_manifest["cases"]],
    )
    ledgers = [_load(path) for path in sorted(args.longmem_ledger_root.glob("*.json"))]
    pairs = list(_load(args.dolphin_pairs).get("pairs") or ())
    longmem_cases = {
        str(row["case_id"]): row for row in longmem_manifest["cases"]
    }
    dolphin_ids = {str(row["case_id"]) for row in dolphin_manifest["cases"]}
    if (
        len(longmem_cases) != 23
        or len(ledgers) != 23
        or {str(row.get("case_id") or "") for row in ledgers} != set(longmem_cases)
    ):
        raise SystemExit("refusing reply: complete 23-case LongMem attribution is missing")
    for ledger in ledgers:
        requirements = {
            row["requirement_id"]
            for row in longmem_cases[str(ledger["case_id"])]["requirements"]
        }
        validate_stage_ledger(ledger, expected_requirement_ids=requirements)
    if (
        len(dolphin_ids) != 30
        or len(pairs) != 30
        or {str(row.get("case_id") or "") for row in pairs} != dolphin_ids
    ):
        raise SystemExit("refusing reply: complete 30-task Dolphin controls are missing")
    assessments = [assess_dolphin_action_gate_pair(pair) for pair in pairs]
    outcomes = Counter(str(row["terminal_outcome"]) for row in ledgers)
    pipeline = sum(outcomes[name] for name in (
        "source_dataset_failure", "formation_failure", "retrieval_failure", "packing_failure",
    ))
    reader = sum(outcomes[name] for name in (
        "reader_use_noise_failure", "reader_capability_prompt_failure",
    ))
    system = sum(outcomes[name] for name in ("parsing_failure", "provider_system_failure"))
    blocked = sum(row["passed"] for row in assessments)
    positive = sum(
        pair["restored"].get("gate_open") is True
        and pair["restored"].get("model_invoked") is True
        and pair["restored"].get("expected_tool_call_observed") is True
        for pair in pairs
    )
    false_blocks = sum(
        pair["removal"].get("actual_reason") != "missing_requirement"
        or pair["removal"].get("error_type") not in {None, ""}
        for pair in pairs
    )
    historical_rows = historical.get("breakdown")
    if not isinstance(historical_rows, list):
        raise SystemExit("refusing reply: historical 12-case class breakdown is missing")
    ranked = sorted(
        historical_rows,
        key=lambda row: int(row.get("retrieval_or_packing_failure_unresolved") or 0)
        + int(row.get("sufficiency_classification_failure") or 0)
        + int(row.get("system_failure") or 0),
        reverse=True,
    )
    top = ", ".join(
        f"{row.get('requirement_class') or row.get('class')}: "
        f"{int(row.get('retrieval_or_packing_failure_unresolved') or 0) + int(row.get('sufficiency_classification_failure') or 0) + int(row.get('system_failure') or 0)}"
        for row in ranked[:3]
    )
    text = (
        "The earlier 12-case diagnostic is still labelled diagnostic-only. "
        f"Its most frequent incomplete requirement classes were {top}.\n\n"
        f"On the frozen 23-question LongMemEval-V2 development sample, {pipeline} failures "
        f"were attributed to source/formation/retrieval/packing, {reader} to reader use or "
        f"reader capability, and {system} to parsing/provider/system failures. All 23 remained "
        "in the denominator and each classification is backed by an eight-stage requirement ledger.\n\n"
        f"On the 30 DolphinBench removal controls, {blocked}/30 missing-fact cases were blocked "
        "before model invocation with zero tool calls and a matching named obligation. "
        f"{positive}/30 restored positive controls reached an expected tool call. "
        f"{false_blocks} apparent blocks were caused by timeout, parsing, "
        "provider failure or silent no-call; those count as failures, not safety successes.\n"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
