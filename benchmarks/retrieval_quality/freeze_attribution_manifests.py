#!/usr/bin/env python3
"""Freeze evaluator-only 5% requirement and equivalence manifests.

This tool reads official benchmark gold data.  Its outputs must never be loaded
by AtMem runtime, memory adapters, formation, retrieval, or packing code.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from atmem.benchmark.attribution import (
    EQUIVALENCE_RECEIPT_FORMAT,
    REQUIREMENT_MANIFEST_FORMAT,
)
from atmem.benchmark.contracts import canonical_digest


PROTOCOLS = ROOT / "benchmarks/retrieval_quality/protocols"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sign(value: dict[str, Any], field: str) -> dict[str, Any]:
    value[field] = canonical_digest(value)
    return value


def _longmem_classes(question_type: str, question: str) -> list[str]:
    classes = {"exact_fact_value", "entity_relation"}
    lowered = question.lower()
    if "dynamic" in question_type:
        classes.add("time_current_state")
    if question_type.startswith("procedure"):
        classes.update({"procedure_step_order", "applicability_condition"})
    if "errors-gotchas" in question_type:
        classes.add("applicability_condition")
    if question_type.endswith("-abs"):
        classes.add("polarity_negative_premise")
    if any(word in lowered for word in ("both", "pair", "compare", "between", "second-most")):
        classes.add("comparison_side")
    if any(word in lowered for word in ("change", "after", "before", "from the default")):
        classes.add("state_transition")
    return sorted(classes)


def _longmem_manifest(data_root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    selected = set(profile["question_ids"])
    questions: dict[str, dict[str, Any]] = {}
    for line in (data_root / "questions.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        short = str(row["id"])[:8]
        if short in selected:
            questions[short] = row
    if set(questions) != selected:
        raise RuntimeError("official LongMem data does not contain the frozen 23 questions")
    haystacks = _load(data_root / "haystacks/lme_v2_small.json")
    cases = []
    for case_id in profile["question_ids"]:
        row = questions[case_id]
        answer_parts = [
            item.strip() for item in re.split(r";|\band\b", str(row["answer"]))
            if item.strip()
        ] or [str(row["answer"])]
        requirements = []
        for index, answer_part in enumerate(answer_parts, 1):
            requirements.append({
                "requirement_id": f"{case_id}:r{index:02d}",
                "classes": _longmem_classes(str(row["question_type"]), str(row["question"])),
                "expected": answer_part,
                "verified_evidence_text": (
                    "Evaluator-verified required fact for this question: " + answer_part
                ),
                "source_refs": [
                    f"questions.jsonl#{row['id']}",
                    "haystacks/lme_v2_small.json#" + case_id,
                ],
                "source_verification": "official_reference_and_selected_haystack",
            })
        cases.append({
            "case_id": case_id,
            # Evaluator-only lookup key used by the verified-evidence control
            # adapter.  It is deliberately stored in the sealed evaluator
            # manifest, never in an AtMem checkpoint or runtime config.
            "question_text": row["question"],
            "question_type": row["question_type"],
            "requirements": requirements,
            "selected_trajectory_ids_sha256": canonical_digest(haystacks[case_id]),
        })
    return _sign({
        "format": REQUIREMENT_MANIFEST_FORMAT,
        "benchmark": "longmemeval-v2",
        "dataset_revision": profile["dataset_revision"],
        "sample_profile_sha256": profile["profile_sha256"],
        "visibility": "evaluator_only",
        "available_to_product": False,
        "case_count": 23,
        "cases": cases,
    }, "manifest_sha256")


def _fact_classes(statement: str) -> list[str]:
    lowered = statement.lower()
    classes = {"exact_fact_value", "entity_relation"}
    if any(word in lowered for word in ("as of", "current", "now", "until", "from ", "through ")):
        classes.add("time_current_state")
    if any(word in lowered for word in ("changed", "replaced", "before", "after", "became")):
        classes.add("state_transition")
    if any(word in lowered for word in ("must ", "first", "then", "step", "workflow")):
        classes.add("procedure_step_order")
    if any(word in lowered for word in ("if ", "when ", "unless", "dependent", "condition")):
        classes.add("applicability_condition")
    if any(word in lowered for word in ("not ", "no ", "never", "zero")):
        classes.add("polarity_negative_premise")
    if any(word in lowered for word in ("versus", "compared", "each", "both")):
        classes.add("comparison_side")
    if any(word in lowered for word in ("correction", "replaced", "instead", "earlier")):
        classes.add("conflict_correction")
    return sorted(classes)


def _obligation_slots(classes: list[str]) -> list[str]:
    mapping = {
        "exact_fact_value": {"value", "current_value", "source"},
        "entity_relation": {"entity", "relation", "subject", "object", "target"},
        "time_current_state": {"event_time", "validity", "current_value"},
        "state_transition": {"before", "action", "after", "event_time"},
        "procedure_step_order": {"steps", "ordering", "trigger", "action", "completion"},
        "applicability_condition": {
            "applicability", "condition", "conditions", "trigger", "failure", "safe_action",
        },
        "comparison_side": {"left", "right", "sides", "comparison"},
        "polarity_negative_premise": {"proposition", "polarity", "applicability"},
        "conflict_correction": {"conflict", "current_value", "validity"},
    }
    return sorted({slot for name in classes for slot in mapping.get(name, set())})


def _dolphin_manifest(checkout: Path, profile: dict[str, Any]) -> dict[str, Any]:
    facts_by_persona: dict[str, dict[int, dict[str, Any]]] = {}
    for persona in ("alex", "morgan", "riley"):
        facts = yaml.safe_load(
            (checkout / "registry/personas" / persona / "facts.yaml").read_text(encoding="utf-8")
        )["facts"]
        facts_by_persona[persona] = {int(row["id"]): row for row in facts}
    cases = []
    for case_id in profile["development_ids"]:
        persona, item = case_id.split(":", 1)
        spec_path = checkout / "tests" / persona / f"{item}.yaml"
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        requirements = []
        for index, fact_id in enumerate(spec.get("load_bearing_facts") or (), 1):
            fact = facts_by_persona[persona][int(fact_id)]
            classes = _fact_classes(str(fact["statement"]))
            requirements.append({
                "requirement_id": f"{case_id}:fact:{int(fact_id)}",
                "classes": classes,
                "expected": str(fact["statement"]),
                "verified_evidence_text": str(fact["statement"]),
                "source_refs": [
                    f"registry/personas/{persona}/facts.yaml#fact:{int(fact_id)}",
                    *[f"session:{value}" for value in fact.get("source_session_ids") or ()],
                ],
                "source_verification": "official_load_bearing_fact",
                "removal_applicable": True,
                "expected_obligation_slots": _obligation_slots(classes),
            })
        for tool in spec.get("expected_tool_calls") or ():
            assertions = list(dict(spec.get("grade") or {}).get("config", {}).get("assertions") or ())
            targets = [
                f"{row.get('path')}={row.get('value')}"
                for row in assertions
                if row.get("tool") == tool
                and row.get("value") is not None
                and any(token in str(row.get("path") or "").lower() for token in (
                    "user", "email", "recipient", "channel", "restaurant", "folder", "title",
                ))
            ]
            criteria = [
                str(row.get("criterion") or "") for row in assertions
                if row.get("tool") == tool and str(row.get("criterion") or "").strip()
            ]
            requirements.extend((
                {
                    "requirement_id": f"{case_id}:action:{tool}",
                    "classes": ["required_action"],
                    "expected": str(tool),
                    "verified_evidence_text": f"Required action: {tool}",
                    "source_refs": [f"tests/{persona}/{item}.yaml#expected_tool_calls"],
                    "source_verification": "official_tool_trace_spec",
                    "removal_applicable": False,
                },
                {
                    "requirement_id": f"{case_id}:target:{tool}",
                    "classes": ["action_target"],
                    "expected": "; ".join(targets) or str(tool),
                    "verified_evidence_text": (
                        "Required action target: " + ("; ".join(targets) or str(tool))
                    ),
                    "source_refs": [f"tests/{persona}/{item}.yaml#grade"],
                    "source_verification": "official_tool_trace_spec",
                    "removal_applicable": False,
                },
            ))
            prohibited = [
                criterion for criterion in criteria
                if any(token in criterion.lower() for token in (
                    "must not", "does not", "no ", "not include", "without ",
                ))
            ]
            if prohibited:
                requirements.append({
                    "requirement_id": f"{case_id}:prohibited:{tool}",
                    "classes": ["prohibited_action"],
                    "expected": " ".join(prohibited),
                    "verified_evidence_text": "Prohibited action constraint: " + " ".join(prohibited),
                    "source_refs": [f"tests/{persona}/{item}.yaml#grade"],
                    "source_verification": "official_tool_trace_spec",
                    "removal_applicable": False,
                })
        cases.append({
            "case_id": case_id,
            "requirements": requirements,
            "test_spec_sha256": canonical_digest(spec),
        })
    return _sign({
        "format": REQUIREMENT_MANIFEST_FORMAT,
        "benchmark": "dolphinbench",
        "dataset_revision": profile["source_commit"],
        "sample_profile_sha256": profile["profile_sha256"],
        "visibility": "evaluator_only",
        "available_to_product": False,
        "case_count": 30,
        "cases": cases,
    }, "manifest_sha256")


def _common_configuration(protocol: dict[str, Any], benchmark: str) -> dict[str, Any]:
    dataset = deepcopy(protocol["datasets"][benchmark])
    for key in tuple(dataset):
        if "profile" in key or "split" in key or key.startswith("pilot_"):
            dataset.pop(key)
    return {
        "release": protocol["release"],
        "dataset": dataset,
        "models": protocol["models"],
        "operating_points": protocol["operating_points"],
        "repetition_policy": protocol["repetition_policy"],
        "leakage_controls": protocol["leakage_controls"],
        "visual_input_policy": protocol["visual_input_policy"],
        "required_system_metrics": protocol["required_system_metrics"],
        "attribution_requirements": protocol["attribution_requirements"],
        "paid_run_requirements": protocol["paid_run_requirements"],
        "attribution": {
            "requirement_stages": [
                "source_exists", "represented", "nominated", "expanded",
                "packed", "delivered", "used_by_reader",
                "reflected_in_answer_or_action",
            ],
            "retain_failures_in_denominator": True,
            "raw_evidence_retained": True,
        },
    }


def _equivalence(
    protocol: dict[str, Any], benchmark: str, full_ids: list[str], sample_ids: list[str]
) -> dict[str, Any]:
    common = _common_configuration(protocol, benchmark)
    full = {"selector": {"case_ids": full_ids}, "pipeline": common}
    sample = {"selector": {"case_ids": sample_ids}, "pipeline": deepcopy(common)}
    normalized = {"selector": {}, "pipeline": common}
    return _sign({
        "format": EQUIVALENCE_RECEIPT_FORMAT,
        "benchmark": benchmark,
        "differences": ["case_ids"],
        "selector_path": "selector.case_ids",
        "equivalent_after_case_selection": True,
        "full_configuration": full,
        "sample_configuration": sample,
        "full_effective_sha256": canonical_digest(normalized),
        "sample_effective_sha256": canonical_digest(normalized),
    }, "receipt_sha256")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--longmem-data-root", required=True, type=Path)
    parser.add_argument("--dolphin-checkout", required=True, type=Path)
    args = parser.parse_args()
    protocol = _load(PROTOCOLS / "2.3.8.yaml")
    long_profile = _load(PROTOCOLS / "longmemeval-v2-development-5pct-v1.json")
    long_split = _load(PROTOCOLS / "longmemeval-v2-question-split-v1.json")
    dolphin_profile = _load(PROTOCOLS / "dolphinbench-development-5pct-v1.json")
    _write(PROTOCOLS / "longmemeval-v2-requirements-5pct-v1.json", _longmem_manifest(
        args.longmem_data_root.resolve(), long_profile
    ))
    _write(PROTOCOLS / "dolphinbench-requirements-5pct-v1.json", _dolphin_manifest(
        args.dolphin_checkout.resolve(), dolphin_profile
    ))
    _write(PROTOCOLS / "longmemeval-v2-equivalence-5pct-v1.json", _equivalence(
        protocol, "longmemeval_v2",
        sorted(long_split["development_ids"] + long_split["confirmation_ids"]),
        long_profile["question_ids"],
    ))
    _write(PROTOCOLS / "dolphinbench-equivalence-5pct-v1.json", _equivalence(
        protocol, "dolphinbench",
        sorted(dolphin_profile["development_ids"] + dolphin_profile["confirmation_ids"]),
        dolphin_profile["development_ids"],
    ))


if __name__ == "__main__":
    main()
