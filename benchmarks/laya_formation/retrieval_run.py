"""Freeze and execute the synthetic retrieval workflow over formation states."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any, Mapping

from atmem import Memory

from research.laya_formation.dataset.generator import build_scenario

from .contracts import canonical_bytes, digest


POOL_SIZE = 10


def _index(scenario_id: str) -> int:
    if not scenario_id.startswith("scenario-"):
        raise ValueError("invalid scenario id")
    return int(scenario_id.removeprefix("scenario-"))


def _record(state: Mapping[str, Any]) -> Mapping[str, Any] | None:
    values = [value for value in state.values() if isinstance(value, Mapping)]
    return values[0] if len(values) == 1 else None


def freeze_retrieval_packet(scenario_ids: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(scenario_ids) < POOL_SIZE or len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("retrieval freeze requires unique scenarios and a full pool")
    scenarios = {value: build_scenario(_index(value)) for value in sorted(scenario_ids)}
    descriptors = {
        key: _record(value.expected_final_state["canonical_state"])
        for key, value in scenarios.items()
    }
    cases, labels = [], []
    for scenario_id in sorted(scenarios):
        target = descriptors[scenario_id]
        query = (
            f"Recall the current {target['relation']} for {target['subject']}."
            if target is not None
            else f"Recall any supported canonical memory from fictional {scenario_id}."
        )
        # Prefer genuinely hard negatives with a shared relation or subject, then
        # use a hash tie-breaker. This is deterministic and arm-independent.
        others = [value for value in sorted(scenarios) if value != scenario_id]
        def priority(value: str) -> tuple[int, str]:
            candidate = descriptors[value]
            overlap = 0
            if target is not None and candidate is not None:
                overlap = int(candidate.get("relation") == target.get("relation")) + int(candidate.get("subject") == target.get("subject"))
            tie = hashlib.sha256(f"410239:{scenario_id}:{value}".encode()).hexdigest()
            return (-overlap, tie)
        pool = [scenario_id, *sorted(others, key=priority)[: POOL_SIZE - 1]]
        matching = {
            "query_digest": digest(query),
            "candidate_pool_digest": digest(pool),
        }
        cases.append({
            "case_id": f"{scenario_id}:retrieval", "scenario_id": scenario_id,
            "cluster_id": scenarios[scenario_id].paraphrase_cluster_id,
            "query": query, "candidate_pool": pool, "matching": matching,
        })
        labels.append({
            "case_id": f"{scenario_id}:retrieval",
            "evidence_ids": [scenario_id] if target is not None else [],
            "should_abstain": target is None,
        })
    packet = {
        "format": "atmem-laya-retrieval-packet-v1", "seed": 410239,
        "case_count": len(cases), "pool_size": POOL_SIZE, "cases": cases,
    }
    key = {
        "format": "atmem-laya-retrieval-answer-key-v1",
        "case_count": len(labels), "labels": labels,
    }
    packet["digest"] = digest(packet)
    key["digest"] = digest(key)
    return packet, key


def write_frozen_retrieval(root: Path, packet: Mapping[str, Any], key: Mapping[str, Any]) -> None:
    if root.exists():
        raise FileExistsError(f"refusing to overwrite retrieval packet: {root}")
    root.mkdir(parents=True)
    (root / "retrieval-packet.json").write_bytes(canonical_bytes(packet) + b"\n")
    (root / "retrieval-answer-key.json").write_bytes(canonical_bytes(key) + b"\n")


def _state_content(state: Mapping[str, Any], candidate_id: str) -> str:
    record = _record(state)
    if record is None:
        # Preserve fixed candidate membership through AtMem's ordinary duplicate
        # suppression without pretending the placeholder is a memory fact.
        return f"No supported canonical memory is available for candidate {candidate_id}."
    return " ".join(str(record.get(key, "")) for key in ("subject", "relation", "value"))


def execute_retrieval_arm(
    packet_path: Path, answer_key_path: Path, formation_results_path: Path,
    post_state_path: Path, output_path: Path,
) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite retrieval results: {output_path}")
    packet = json.loads(packet_path.read_text())
    key = json.loads(answer_key_path.read_text())
    labels = {row["case_id"]: row for row in key["labels"]}
    formation_rows = [json.loads(line) for line in formation_results_path.read_text().splitlines() if line]
    arm = formation_rows[0]["identity"]["arm"]
    errors: dict[str, str] = {}
    for row in formation_rows:
        if row.get("error_code") is not None:
            errors[row["case_id"].split(":", 1)[0]] = str(row["error_code"])
    post_rows = {
        row["scenario_id"]: row
        for row in (json.loads(line) for line in post_state_path.read_text().splitlines() if line)
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    rows = []
    with tmp.open("x", encoding="utf-8") as stream:
        for case in packet["cases"]:
            expected = labels[case["case_id"]]
            started = perf_counter()
            upstream_error = errors.get(case["scenario_id"])
            error = f"UPSTREAM_FORMATION_{upstream_error}" if upstream_error else None
            ranked: list[str] = []
            abstained = True
            if error is None:
                memory = Memory(":memory:", auto_vectors=False)
                try:
                    subject = f"retrieval:{case['case_id']}"
                    for candidate_id in case["candidate_pool"]:
                        state = post_rows[candidate_id]["predicted_canonical_state"]
                        content = _state_content(state, candidate_id)
                        memory.remember(
                            subject, content, interpreted_fact=content,
                            interpreted_fact_key=candidate_id, source_type="user_message",
                            actor="benchmark:laya-formation",
                        )
                    recalled = memory.recall(subject, case["query"], limit=POOL_SIZE, include_scores=True)
                    ranked = [str(item.get("fact_key") or "") for item in recalled]
                    if set(ranked) != set(case["candidate_pool"]) or len(ranked) != POOL_SIZE:
                        raise ValueError("retrieval changed frozen candidate-pool membership")
                    target_state = post_rows[case["scenario_id"]]["predicted_canonical_state"]
                    abstained = _record(target_state) is None
                except Exception as exc:
                    error = f"RETRIEVAL_{type(exc).__name__}"
                    ranked = []
                    abstained = True
                finally:
                    memory.close()
            latency = (perf_counter() - started) * 1000
            delivered = [] if abstained or error is not None else ranked
            row = {
                "format": "atmem-laya-retrieval-case-result-v1",
                "case_id": case["case_id"], "scenario_id": case["scenario_id"],
                "cluster_id": case["cluster_id"], "arm": arm,
                "matching": case["matching"], "candidate_pool": case["candidate_pool"],
                "ranked_ids": ranked, "delivered_ids": delivered,
                "abstained": abstained, "latency_ms": latency,
                "usage": {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
                "error_code": error,
                "expected_relevance_count": len(expected["evidence_ids"]),
            }
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            rows.append((row, expected))
    tmp.replace(output_path)
    positive = [(row, expected) for row, expected in rows if expected["evidence_ids"]]
    reciprocal, hits, coverage = [], {1: 0, 5: 0, 10: 0}, []
    for row, expected in positive:
        relevant = set(expected["evidence_ids"])
        ranked = row["delivered_ids"] if row["error_code"] is None else []
        rank = next((index for index, value in enumerate(ranked, 1) if value in relevant), None)
        reciprocal.append(0.0 if rank is None or rank > 5 else 1 / rank)
        for cutoff in hits:
            hits[cutoff] += int(bool(relevant.intersection(ranked[:cutoff])))
        coverage.append(len(relevant.intersection(ranked)) / len(relevant))
    negatives = [(row, expected) for row, expected in rows if not expected["evidence_ids"]]
    latencies = [row["latency_ms"] for row, _ in rows]
    return {
        "format": "atmem-laya-retrieval-arm-summary-v1", "arm": arm,
        "queries": len(rows), "positive_queries": len(positive), "negative_queries": len(negatives),
        "mrr_at_5": sum(reciprocal) / max(1, len(positive)),
        "recall_at_1": hits[1] / max(1, len(positive)),
        "recall_at_5": hits[5] / max(1, len(positive)),
        "recall_at_10": hits[10] / max(1, len(positive)),
        "evidence_coverage": sum(coverage) / max(1, len(positive)),
        "abstention_rate": sum(row["abstained"] for row, _ in rows) / len(rows),
        "negative_abstention_accuracy": sum(row["abstained"] for row, _ in negatives) / max(1, len(negatives)),
        "positive_abstention_errors": sum(row["abstained"] for row, _ in positive),
        "error_rate": sum(row["error_code"] is not None for row, _ in rows) / len(rows),
        "latency_ms": {"median": median(latencies), "sum": sum(latencies)},
        "cost_usd": sum(row["usage"]["cost_usd"] for row, _ in rows),
    }
