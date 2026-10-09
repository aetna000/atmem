"""Qualify Context Engine V3 on an encrypted CPU-only 50k/100k workload.

The workload uses shipped V3 formation, persistent FTS, planner and retriever.
Heavy evidence belongs outside the repository (normally on ``/Volumes/MEM``).
Each of ten agent scopes commits independently, making builds resumable.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import platform
import resource
from statistics import median
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from atmem.context_engine.coverage import storage_report
from atmem.context_engine.formation import FormationManager, SourceEpisode, SourcePart
from atmem.context_engine.planner import DeterministicPlanner
from atmem.context_engine.retrieval import DeterministicRetriever
from atmem.contracts.models import AuthorityScope
from atmem.core import keys
from atmem.core.keys import initialize_encrypted_household, sqlcipher_runtime_status
from atmem.store.sqlite import SQLiteStore


MILESTONES = (50_000, 100_000)
AGENT_COUNT = 10
QUERY_REPEATS = 10
SHADOW_SAMPLE_EVERY = 10


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]


def _scope(agent: int) -> AuthorityScope:
    return AuthorityScope(
        subject_id="performance-fixture",
        agent_id=f"agent-{agent:02d}",
        workspace_id="context-performance",
    )


def _target_for_agent(total: int, agent: int) -> int:
    quotient, remainder = divmod(total, AGENT_COUNT)
    return quotient + int(agent < remainder)


def _parts(agent: int, target_units: int) -> tuple[SourcePart, ...]:
    """Produce exactly target_units under deterministic V3 formation."""
    # A text source deterministically forms four typed units: exact fact,
    # entity/relation, applicability/premise and immutable source evidence.
    # Opaque file parts contribute one unit each.
    text_parts, remainder = divmod(target_units, 4)
    values: list[SourcePart] = []
    for index in range(text_parts):
        item = agent * 1_000_000 + index
        body = (
            f"Synthetic preference item {item:07d} has exact value value-{item:07d}. "
            "This retained source sentence pads the workload to a realistic compact "
            "evidence size without adding another fact or benchmark answer."
        ).encode()
        values.append(SourcePart(f"text-{index:06d}", len(values), "text", "text/plain", body))
    for offset in range(remainder):
        body = f"Opaque fixture attachment for agent {agent}, remainder {offset}.".encode()
        values.append(SourcePart(
            f"file-{offset}", len(values), "file", "application/octet-stream", body,
        ))
    return tuple(values)


def _generation_for(store: SQLiteStore, scope: AuthorityScope) -> str | None:
    row = store._conn.execute(
        """SELECT generation_id FROM context_view_generations
           WHERE subject_id=? AND agent_id=? AND workspace_id=?
             AND state IN ('building','verified','active')
           ORDER BY created_at DESC LIMIT 1""",
        (scope.subject_id, scope.agent_id, scope.workspace_id),
    ).fetchone()
    return str(row["generation_id"]) if row else None


def _build_agent(store: SQLiteStore, agent: int, target_units: int) -> dict[str, Any]:
    manager = FormationManager(store)
    scope = _scope(agent)
    generation = _generation_for(store, scope)
    if generation is not None:
        row = store._conn.execute(
            "SELECT state FROM context_view_generations WHERE generation_id=?", (generation,),
        ).fetchone()
        count = int(store._conn.execute(
            "SELECT COUNT(*) FROM context_evidence_units WHERE generation_id=?", (generation,),
        ).fetchone()[0])
        if row and row["state"] == "active" and count == target_units:
            return {"agent": agent, "generation_id": generation, "units": count, "resumed": True}
        if row and row["state"] != "building":
            raise RuntimeError(f"agent {agent} has incompatible {row['state']} generation")
    parts = _parts(agent, target_units)
    episode = SourceEpisode(f"performance-agent-{agent:02d}", scope, parts)
    source_id = manager.retain_source(episode)
    generation = generation or manager.begin_generation(
        scope, profile_id="context-fast", configuration={"workload": "performance-v3"},
    )
    with store.transaction():
        manager.form_source(source_id, generation)
    count = int(store._conn.execute(
        "SELECT COUNT(*) FROM context_evidence_units WHERE generation_id=?", (generation,),
    ).fetchone()[0])
    if count != target_units:
        raise RuntimeError(f"agent {agent} formed {count} units; expected {target_units}")
    manager.verify_generation(generation)
    manager.activate_generation(generation)
    return {"agent": agent, "generation_id": generation, "units": count, "resumed": False}


def _query(database: Path, agent: int, generation: str, item: int) -> dict[str, Any]:
    store = SQLiteStore(database)
    try:
        planner = DeterministicPlanner()
        retriever = DeterministicRetriever(store)
        query = f"What is the exact value for synthetic preference item {item:07d}?"
        plan = planner.plan(query)
        cold_latency: float | None = None
        warm_latencies: list[float] = []
        failures = 0
        for _ in range(QUERY_REPEATS):
            started = time.perf_counter()
            result = retriever.retrieve(
                generation_id=generation, query=query, plan=plan, max_sources=4,
            )
            latency = (time.perf_counter() - started) * 1_000
            if cold_latency is None:
                cold_latency = latency
            else:
                warm_latencies.append(latency)
            if not any(f"value-{item:07d}" in candidate.text for candidate in result.candidates):
                failures += 1
        return {
            "agent": agent, "cold_latency_ms": cold_latency,
            "warm_latencies_ms": warm_latencies, "failures": failures,
            "cache_hits": retriever.cache_hits,
        }
    finally:
        store.close()


def _measure(database: Path, builds: list[dict[str, Any]]) -> dict[str, Any]:
    jobs = []
    for row in builds:
        agent = int(row["agent"])
        text_parts = int(row["units"]) // 4
        for local_index in (17, max(17, text_parts // 2), max(17, text_parts - 1)):
            jobs.append((database, agent, str(row["generation_id"]), agent * 1_000_000 + local_index))
    wall_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=AGENT_COUNT) as executor:
        rows = list(executor.map(lambda value: _query(*value), jobs))
    wall_seconds = time.perf_counter() - wall_started
    cold_latencies = [float(row["cold_latency_ms"]) for row in rows]
    warm_latencies = [
        value for row in rows for value in row["warm_latencies_ms"]
    ]
    total_queries = len(cold_latencies) + len(warm_latencies)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = int(rss if platform.system() == "Darwin" else rss * 1024)
    return {
        "queries": total_queries, "cold_queries": len(cold_latencies),
        "warm_queries": len(warm_latencies), "concurrent_agents": AGENT_COUNT,
        "wall_seconds": wall_seconds,
        "throughput_queries_per_second": total_queries / wall_seconds,
        "cold_p50_ms": median(cold_latencies),
        "cold_p95_ms": percentile(cold_latencies, 0.95),
        "warm_p50_ms": median(warm_latencies),
        "warm_p95_ms": percentile(warm_latencies, 0.95),
        "max_ms": max((*cold_latencies, *warm_latencies)),
        "retrieval_failures": sum(row["failures"] for row in rows),
        "cache_hits": sum(row["cache_hits"] for row in rows), "peak_rss_bytes": rss_bytes,
    }


def _query_plan(store: SQLiteStore, generation: str) -> list[str]:
    rows = store._conn.execute(
        """EXPLAIN QUERY PLAN
           SELECT m.unit_id FROM context_units_fts
           JOIN context_units_fts_map m ON m.fts_rowid=context_units_fts.rowid
           JOIN context_evidence_units u
             ON u.generation_id=m.generation_id AND u.unit_id=m.unit_id
           WHERE context_units_fts MATCH ? AND m.generation_id=?
             AND u.kind='fact' AND u.lifecycle='active' LIMIT 8""",
        ('"synthetic" AND "preference"', generation),
    ).fetchall()
    return [str(row[3]) for row in rows]


def _shadow_overhead(store: SQLiteStore, generation: str) -> dict[str, Any]:
    planner = DeterministicPlanner()
    queries = [f"synthetic preference item {index:07d}" for index in range(100)]

    def run(shadow: bool) -> tuple[float, float]:
        active = DeterministicRetriever(store)
        shadow_retriever = DeterministicRetriever(store)
        wall_start, cpu_start = time.perf_counter(), time.process_time()
        for index, query in enumerate(queries):
            plan = planner.plan(query)
            active.retrieve(generation_id=generation, query=query, plan=plan, max_sources=4)
            if shadow and index % SHADOW_SAMPLE_EVERY == 0:
                shadow_retriever.retrieve(
                    generation_id=generation, query=query, plan=plan, max_sources=4,
                )
        return time.perf_counter() - wall_start, time.process_time() - cpu_start

    baseline_wall, baseline_cpu = run(False)
    shadow_wall, shadow_cpu = run(True)
    wall_ratio = shadow_wall / baseline_wall if baseline_wall else math.inf
    cpu_ratio = shadow_cpu / baseline_cpu if baseline_cpu else math.inf
    return {
        "sample_rate": 1 / SHADOW_SAMPLE_EVERY,
        "baseline_wall_seconds": baseline_wall, "shadow_wall_seconds": shadow_wall,
        "wall_overhead_ratio": wall_ratio - 1,
        "baseline_cpu_seconds": baseline_cpu, "shadow_cpu_seconds": shadow_cpu,
        "cpu_overhead_ratio": cpu_ratio - 1,
    }


def _qualify(output: Path, target: int) -> dict[str, Any]:
    database = output / f"context-performance-{target}.db"
    keys.DEFAULT_KEY_PATH = output.parent / ".atmem-context-performance-db.key"
    if not database.exists():
        initialize_encrypted_household(database)
    store = SQLiteStore(database)
    started = time.perf_counter()
    try:
        builds = [
            _build_agent(store, agent, _target_for_agent(target, agent))
            for agent in range(AGENT_COUNT)
        ]
        formation_seconds = time.perf_counter() - started
        # Also applies to a resumed fixture created before activation-time FTS
        # maintenance was introduced.
        store.optimize_context_fts()
        measurement = _measure(database, builds)
        storage = storage_report(store)
        plan = _query_plan(store, str(builds[0]["generation_id"]))
        shadow = _shadow_overhead(store, str(builds[0]["generation_id"]))
    finally:
        store.close()
    receipt: dict[str, Any] = {
        "format": "atmem-context-performance-milestone-v2", "target_units": target,
        "database": str(database), "database_bytes": database.stat().st_size,
        "formation_seconds": formation_seconds, "agents": builds,
        "retrieval": measurement, "storage": storage, "query_plan": plan,
        "shadow": shadow,
    }
    receipt["gates"] = {
        "encrypted_v3_storage": bool(storage["storage_ready"]["encrypted"]),
        "exact_unit_count": sum(int(row["units"]) for row in builds) == target,
        "ten_isolated_agents": len({row["generation_id"] for row in builds}) == AGENT_COUNT,
        "warm_p50_lte_500ms": measurement["warm_p50_ms"] <= 500,
        "warm_p95_lte_2s_at_50k": target != 50_000 or measurement["warm_p95_ms"] <= 2_000,
        "warm_p95_lte_3s_at_100k": target != 100_000 or measurement["warm_p95_ms"] <= 3_000,
        "rss_lte_512mib": measurement["peak_rss_bytes"] <= 512 * 1024 * 1024,
        "retrieval_complete": measurement["retrieval_failures"] == 0,
        "derived_to_source_lte_1_5": storage["derived_to_source_ratio"] <= 1.5,
        "source_not_duplicated": bool(storage["source_duplication"]["passed"]),
        "fts_index_used": any("VIRTUAL TABLE INDEX" in row for row in plan),
        "shadow_wall_overhead_lte_20pct": shadow["wall_overhead_ratio"] <= 0.20,
        "shadow_cpu_overhead_lte_20pct": shadow["cpu_overhead_ratio"] <= 0.20,
    }
    receipt["passed"] = all(receipt["gates"].values())
    (output / f"performance-{target}.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--target", type=int, choices=MILESTONES, default=100_000)
    args = parser.parse_args()
    output = Path(args.output_root).expanduser().resolve()
    repository = Path(__file__).resolve().parents[2]
    if output == repository or repository in output.parents:
        raise SystemExit("performance evidence must be outside the repository")
    runtime = sqlcipher_runtime_status()
    if not runtime["available"]:
        raise SystemExit("SQLCipher is required for persistent Context Engine qualification")
    output.mkdir(parents=True, exist_ok=True)
    receipts = [_qualify(output, target) for target in MILESTONES if target <= args.target]
    report = {
        "format": "atmem-context-performance-qualification-v2",
        "hardware": {
            "system": platform.system(), "release": platform.release(),
            "machine": platform.machine(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "sqlcipher": runtime, "milestones": receipts,
        "passed": bool(receipts) and all(row["passed"] for row in receipts),
    }
    (output / "performance-summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
