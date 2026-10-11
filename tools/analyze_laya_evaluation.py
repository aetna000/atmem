#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.laya_formation.formation_run import load_frozen_cases
from benchmarks.laya_formation.statistics import paired_cluster_interval, rate_by_class
from benchmarks.laya_formation.adapters import (
    BASE_LAYA_MODEL, BASE_LAYA_REVISION, FINETUNED_LAYA_MODEL,
    FINETUNED_LAYA_REVISION, QWEN_MODEL, QWEN_REVISION,
)
from research.laya_formation.dataset.generator import build_scenario


ARMS = (
    "deterministic-atmem", "base-laya", "finetuned-laya",
    "finetuned-laya-with-atbot-escalation", "pinned-current-qwen", "pinned-jev",
)
COMPARATORS = ("deterministic-atmem", "base-laya", "pinned-current-qwen", "pinned-jev")


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formation-packet-dir", type=Path, required=True)
    parser.add_argument("--retrieval-packet-dir", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite statistics: {args.output}")
    cases = load_frozen_cases(
        args.formation_packet_dir / "matched-packet.json",
        args.formation_packet_dir / "matched-answer-key.json",
    )
    scenario_ids = sorted({case.scenario_id for case in cases})
    scenario = {value: build_scenario(int(value.removeprefix("scenario-"))) for value in scenario_ids}
    clusters = {value: scenario[value].paraphrase_cluster_id for value in scenario_ids}
    operation = {value: scenario[value].expected_final_state["operation"] for value in scenario_ids}
    memory_class = {value: scenario[value].expected_final_state["memory_class"] for value in scenario_ids}
    formation, combined, retrieval, formation_raw = {}, {}, {}, {}
    valid = {}
    for arm in ARMS:
        formation_raw[arm] = _jsonl(args.results_dir / f"{arm}.jsonl")
        formation[arm] = {row["scenario_id"]: float(row["exact"]) for row in _jsonl(args.results_dir / f"{arm}-post-state.jsonl")}
        combined[arm] = {row["scenario_id"]: float(row["future_query_sufficient"]) for row in _jsonl(args.results_dir / f"{arm}-combined.jsonl")}
        retrieval_rows = _jsonl(args.results_dir / f"{arm}-retrieval.jsonl")
        retrieval[arm] = {}
        for row in retrieval_rows:
            if row["expected_relevance_count"] == 0:
                continue
            rank = next((index for index, value in enumerate(row["delivered_ids"][:5], 1) if value == row["scenario_id"]), None)
            retrieval[arm][row["scenario_id"]] = 0.0 if rank is None else 1.0 / rank
        valid[arm] = not any(row.get("error_code") for row in formation_raw[arm])
    retrieval_clusters = {value: clusters[value] for value in retrieval["finetuned-laya"]}
    comparisons = {}
    for comparator in COMPARATORS:
        if not valid[comparator]:
            comparisons[comparator] = {
                "status": "unavailable_error_arm", "comparator_valid": False,
                "formation_exact_state": None, "retrieval_mrr_at_5": None,
                "combined_sufficiency": None,
            }
        else:
            comparisons[comparator] = {
                "status": "valid", "comparator_valid": True,
                "formation_exact_state": paired_cluster_interval(formation["finetuned-laya"], formation[comparator], clusters),
                "retrieval_mrr_at_5": paired_cluster_interval(retrieval["finetuned-laya"], retrieval[comparator], retrieval_clusters),
                "combined_sufficiency": paired_cluster_interval(combined["finetuned-laya"], combined[comparator], clusters),
            }
    fine_classes = {
        "operation": rate_by_class(formation["finetuned-laya"], operation),
        "memory_class": rate_by_class(formation["finetuned-laya"], memory_class),
    }
    per_class = {"finetuned-laya": fine_classes}
    for arm in COMPARATORS:
        if not valid[arm]:
            continue
        per_class[arm] = {
            "operation": rate_by_class(formation[arm], operation),
            "memory_class": rate_by_class(formation[arm], memory_class),
        }
    det = comparisons["deterministic-atmem"]
    baseline_matching = {row["case_id"]: row["matching"] for row in formation_raw["deterministic-atmem"]}
    matchedness = all(
        len(rows) == len(baseline_matching)
        and {row["case_id"]: row["matching"] for row in rows} == baseline_matching
        for rows in formation_raw.values()
    )
    summaries = {
        arm: json.loads((args.results_dir / f"{arm}-summary.json").read_text()) for arm in ARMS
    }
    identities = {arm: formation_raw[arm][0]["identity"] for arm in ARMS}
    identity_valid = {
        "deterministic-atmem": identities["deterministic-atmem"]["model"] == "atmem-deterministic-formation" and identities["deterministic-atmem"]["revision"] == "2.3.9b1",
        "base-laya": (identities["base-laya"]["model"], identities["base-laya"]["revision"]) == (BASE_LAYA_MODEL, BASE_LAYA_REVISION),
        "finetuned-laya": (identities["finetuned-laya"]["model"], identities["finetuned-laya"]["revision"]) == (FINETUNED_LAYA_MODEL, FINETUNED_LAYA_REVISION),
        "finetuned-laya-with-atbot-escalation": identities["finetuned-laya-with-atbot-escalation"]["revision"] == FINETUNED_LAYA_REVISION,
        "pinned-current-qwen": (identities["pinned-current-qwen"]["model"], identities["pinned-current-qwen"]["revision"]) == (QWEN_MODEL, QWEN_REVISION),
        "pinned-jev": False,
    }
    safety = {arm: summaries[arm]["safety_violations"] for arm in ARMS}
    required_classes_noninferior = all(
        fine_classes[group][name]["rate"] >= per_class["deterministic-atmem"][group][name]["rate"]
        for group in ("operation", "memory_class") for name in fine_classes[group]
    )
    formation_claim = (
        det["formation_exact_state"]["ci95_lower"] > 0 and matchedness
        and safety["finetuned-laya"] <= safety["deterministic-atmem"]
        and required_classes_noninferior
    )
    combined_claim = det["combined_sufficiency"]["ci95_lower"] > 0 and matchedness
    report = {
        "format": "atmem-laya-statistical-analysis-v1",
        "protocol": {"unit": "scenario_cluster", "bootstrap_repetitions": 10000, "confidence_level": 0.95, "seed": 410239},
        "comparisons": comparisons,
        "per_class": per_class,
        "gates": {
            "matchedness": matchedness,
            "identity_valid": identity_valid,
            "identities": identities,
            "safety_violations": safety,
            "fine_required_classes_noninferior_to_deterministic": required_classes_noninferior,
            "jev_identity": "blocked",
            "qwen_identity": "verified_but_execution_failed",
            "latency_ratio_effect": None,
            "latency_gate": "blocked_no_successful_paired_qwen_rows",
        },
        "claim_decisions": {
            "synthetic_formation_finetuned_beats_deterministic": formation_claim,
            "synthetic_retrieval_finetuned_beats_deterministic": det["retrieval_mrr_at_5"]["ci95_lower"] > 0,
            "synthetic_retrieval_finetuned_ties_deterministic": det["retrieval_mrr_at_5"]["difference"] == 0,
            "synthetic_combined_finetuned_beats_deterministic": combined_claim,
            "qwen_comparison": "inconclusive_infrastructure_error",
            "jev_comparison": "blocked_unresolved_concrete_identity",
            "latency_gate_vs_qwen": "blocked_no_successful_paired_qwen_rows",
            "production_superiority_claim": "blocked_synthetic_only_and_public_corpora_not_run"
        },
        "source_sha256": {
            f"{arm}:{kind}": _sha(args.results_dir / f"{arm}-{kind}.jsonl")
            for arm in ARMS for kind in ("post-state", "retrieval", "combined")
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["claim_decisions"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
