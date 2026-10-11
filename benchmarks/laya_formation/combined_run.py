"""Attribute synthetic store-to-retrieve outcomes to fixed pipeline stages."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from .contracts import canonical_bytes
from .formation_run import load_frozen_cases


STAGES = ("source", "formation", "mutation", "nomination", "ranking", "packing", "delivery")


def execute_combined_arm(
    formation_packet: Path, formation_key: Path, retrieval_packet: Path,
    retrieval_key: Path, formation_results: Path, post_state: Path,
    retrieval_results: Path, output_path: Path,
) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite combined results: {output_path}")
    cases = load_frozen_cases(formation_packet, formation_key)
    expected_by_scenario: dict[str, dict[str, tuple[str, ...]]] = {}
    for case in cases:
        expected_by_scenario.setdefault(case.scenario_id, {})[case.question_id] = case.expected
    formation_rows = [json.loads(line) for line in formation_results.read_text().splitlines() if line]
    arm = formation_rows[0]["identity"]["arm"]
    actual_by_scenario: dict[str, dict[str, dict[str, Any]]] = {}
    for row in formation_rows:
        scenario_id, question_id = row["case_id"].split(":", 1)
        actual_by_scenario.setdefault(scenario_id, {})[question_id] = row
    post = {
        row["scenario_id"]: row
        for row in (json.loads(line) for line in post_state.read_text().splitlines() if line)
    }
    retrieval_cases = {row["case_id"]: row for row in json.loads(retrieval_packet.read_text())["cases"]}
    retrieval_labels = {row["case_id"]: row for row in json.loads(retrieval_key.read_text())["labels"]}
    retrieval = {
        row["case_id"]: row
        for row in (json.loads(line) for line in retrieval_results.read_text().splitlines() if line)
    }
    rows, failures = [], Counter()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    with tmp.open("x", encoding="utf-8") as stream:
        for case_id in sorted(retrieval_cases):
            rcase, label, rrow = retrieval_cases[case_id], retrieval_labels[case_id], retrieval[case_id]
            scenario_id = rcase["scenario_id"]
            frows = actual_by_scenario[scenario_id]
            source_ok = all(row["matching"]["authorized_input_digest"] for row in frows.values())
            formation_ok = all(
                row.get("error_code") is None
                and tuple(row.get("selected") or ()) == expected_by_scenario[scenario_id][question_id]
                for question_id, row in frows.items()
            ) and len(frows) == len(expected_by_scenario[scenario_id])
            mutation_ok = bool(post[scenario_id]["exact"])
            relevant = set(label["evidence_ids"])
            negative = not relevant
            nomination_ok = (
                rrow["error_code"] is None
                and (rrow["abstained"] if negative else relevant <= set(rcase["candidate_pool"]))
            )
            ranking_ok = nomination_ok and (
                negative or bool(relevant.intersection(rrow["ranked_ids"][:5]))
            )
            predicted_state = post[scenario_id]["predicted_canonical_state"]
            packing_ok = json.loads(canonical_bytes(predicted_state)) == predicted_state
            delivery_ok = (
                rrow["error_code"] is None
                and ((rrow["abstained"] and not rrow["delivered_ids"]) if negative else bool(relevant.intersection(rrow["delivered_ids"][:5])))
            )
            stage_values = {
                "source": source_ok, "formation": formation_ok, "mutation": mutation_ok,
                "nomination": nomination_ok, "ranking": ranking_ok,
                "packing": packing_ok, "delivery": delivery_ok,
            }
            success = rrow["error_code"] is None and all(stage_values.values())
            first_failure = next((stage for stage in STAGES if not stage_values[stage]), None)
            if first_failure is not None:
                failures[first_failure] += 1
            row = {
                "format": "atmem-laya-combined-case-result-v1", "arm": arm,
                "case_id": case_id, "scenario_id": scenario_id,
                "cluster_id": rcase["cluster_id"], "stages": stage_values,
                "future_query_sufficient": success, "first_failure_stage": first_failure,
                "negative_query": negative, "formation_error": any(value.get("error_code") for value in frows.values()),
                "retrieval_error": rrow["error_code"],
            }
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            rows.append(row)
    tmp.replace(output_path)
    return {
        "format": "atmem-laya-combined-arm-summary-v1", "arm": arm,
        "cases": len(rows),
        "future_query_sufficiency": sum(row["future_query_sufficient"] for row in rows) / len(rows),
        "stage_pass_rate": {
            stage: sum(row["stages"][stage] for row in rows) / len(rows) for stage in STAGES
        },
        "first_failure_counts": {stage: failures.get(stage, 0) for stage in STAGES},
        "error_cases": sum(bool(row["formation_error"] or row["retrieval_error"]) for row in rows),
        "unknown_or_error_credited_as_success": any(
            row["future_query_sufficient"] and (row["formation_error"] or row["retrieval_error"])
            for row in rows
        ),
    }
