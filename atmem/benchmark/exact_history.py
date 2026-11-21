"""Offline exact-history evidence diagnostic. Run with python -m atmem.benchmark.exact_history."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
import platform
import random
from pathlib import Path
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns

from atmem import Memory
from atmem.context_engine import service as context_service
from atmem.context_engine.contracts import ContextRequestV3
from atmem.contracts import AuthorityScope, EpisodeIngestRequest, EpisodePart
from atmem.contracts.models import RetrievalBudget
from atmem.service.household import HouseholdApplication


SPLIT_SEEDS = {"development": 55201, "holdout": 55202}
SCOPE = AuthorityScope("benchmark-owner", "benchmark-agent", "benchmark-workspace")
FOREIGN_SCOPE = AuthorityScope("other-owner", SCOPE.agent_id, SCOPE.workspace_id)
PRINCIPALS = {SCOPE: "synthetic-history-import", FOREIGN_SCOPE: "foreign-history-import"}
OUTPUT_BYTES = 4096
SUMMARY = "The work session reviewed dispatch tickets, account changes, and queue settings."


@dataclass(frozen=True)
class HistoryLine:
    text: str
    foreign: bool = False


@dataclass(frozen=True)
class RecallCase:
    id: str
    cohort: str
    question: str
    literal: str
    expected: str | None = None
    outdated: str | None = None
    forbidden: str | None = None


def make_fixture(split: str) -> tuple[list[HistoryLine], list[RecallCase]]:
    """Derive source text and grading data from a pinned split seed."""
    rng = random.Random(SPLIT_SEEDS[split])

    def value() -> str:
        return f"{rng.getrandbits(64):016x}"

    history = []
    cases = []
    for index in range(4):
        key = f"slot[{value()[:8]}]/A+B"
        log_ref = f"worker:{value()[:8]}/scan"
        account = f"queue-{value()[:8]}"
        job = f"job-{value()[:8]}"
        foreign_key = f"private-{value()[:8]}"
        missing = f"unseen-{value()[:8]}"
        exact, log, outdated, current, paraphrase, forbidden = (value() for _ in range(6))
        history.extend([
            HistoryLine(f"Dispatch KV {key} = {exact}."),
            HistoryLine(f"ERROR {log_ref} trace_id={log}."),
            HistoryLine(f"At 09:00 {account} active routing code was {outdated}."),
            HistoryLine(f"For {job}, the build artifact was moved to storage locker {paraphrase}."),
            HistoryLine(f"Private entry {foreign_key} = {forbidden}.", foreign=True),
        ])
        for _ in range(12):
            history.append(HistoryLine(f"Dispatch scan worker:{value()[:8]} completed successfully."))
        history.append(HistoryLine(f"At 10:00 {account} active routing code changed to {current}."))
        cases.extend([
            RecallCase(f"kv-{index}", "kv", f"What exact value was stored for {key}?", key, exact),
            RecallCase(f"log-{index}", "log", f"What trace_id appeared on the ERROR line for {log_ref}?", log_ref, log),
            RecallCase(f"latest-{index}", "latest", f"What is the current active routing code for {account}?", account,
                       current, outdated=outdated),
            RecallCase(f"paraphrase-{index}", "paraphrase", f"Where is the deliverable for {job} kept?", job, paraphrase),
            RecallCase(f"foreign-{index}", "scope", f"What exact value was stored for {foreign_key}?", foreign_key,
                       forbidden=forbidden),
            RecallCase(f"missing-{index}", "missing", f"What exact value was stored for {missing}?", missing),
        ])
    # Later observations occupy the working history. The questions arrive afterward.
    history.extend(
        HistoryLine(f"Unrelated maintenance worker:{value()[:8]} finished its scheduled check.")
        for _ in range(96)
    )
    return history, cases


def fixture_digest(history: list[HistoryLine], cases: list[RecallCase]) -> str:
    document = {"history": [asdict(line) for line in history], "cases": [asdict(case) for case in cases],
                "working_summary": SUMMARY}
    return sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()


def _import_history(memory: Memory, history: list[HistoryLine]) -> None:
    for index, line in enumerate(history):
        scope = FOREIGN_SCOPE if line.foreign else SCOPE
        episode = f"history-{index}"
        memory.form_context_episode(EpisodeIngestRequest(
            episode_id=episode, idempotency_key=episode, scope=scope,
            parts=(EpisodePart(
                part_id="line", ordinal=0, kind="tool", source_type="tool_output",
                content=line.text, content_sha256="sha256:" + sha256(line.text.encode()).hexdigest(),
            ),),
            binding_method="host_asserted", binding_assurance="host_asserted",
            source_observation_granularity="sentence",
        ), history_import_principal=PRINCIPALS[scope])
    memory.freeze_context_engine(SCOPE)
    memory.freeze_context_engine(FOREIGN_SCOPE)


def literal_history(history: list[HistoryLine], literal: str, *, budget: int = OUTPUT_BYTES) -> str:
    """Fixed-query comparator. The literal is visible in the question."""
    lines = []
    remaining = budget
    for line in reversed(history):
        if line.foreign or literal not in line.text:
            continue
        size = len(line.text.encode()) + bool(lines)
        if size > remaining:
            break
        lines.append(line.text)
        remaining -= size
    return "\n".join(lines)


def score(case: RecallCase, text: str, *, source_available: bool, status: str, elapsed_ns: int,
          calls: int = 1, error: str | None = None) -> dict:
    hit = case.expected is not None and case.expected in text
    stale = case.outdated is not None and case.outdated in text
    forbidden = case.forbidden is not None and case.forbidden in text
    return {
        "id": case.id, "cohort": case.cohort, "source_available": source_available,
        "target_delivered": hit, "stale_delivered": stale, "forbidden_delivered": forbidden,
        "passed": error is None and (hit if case.expected is not None else not text.strip()),
        "status": status, "calls": calls, "bytes": len(text.encode()),
        "elapsed_ns": elapsed_ns, "error": error,
    }


def summarize(rows: list[dict]) -> dict:
    latencies = sorted(row["elapsed_ns"] for row in rows)
    return {
        "cases": len(rows), "passed": sum(row["passed"] for row in rows),
        "recoverable_misses": sum(row["source_available"] and not row["target_delivered"] for row in rows),
        "stale_deliveries": sum(row["stale_delivered"] for row in rows),
        "forbidden_deliveries": sum(row["forbidden_delivered"] for row in rows),
        "errors": sum(row["error"] is not None for row in rows),
        "total_calls": sum(row["calls"] for row in rows),
        "total_context_bytes": sum(row["bytes"] for row in rows),
        "p50_ms": round(median(latencies) / 1_000_000, 3),
        "p95_ms": round(latencies[(95 * len(latencies) + 99) // 100 - 1] / 1_000_000, 3),
        "by_cohort": {
            cohort: {"passed": sum(row["passed"] for row in rows if row["cohort"] == cohort),
                     "cases": sum(row["cohort"] == cohort for row in rows)}
            for cohort in sorted({row["cohort"] for row in rows})
        },
    }


def _run_benchmark(split: str, *, output_bytes: int) -> dict:
    history, cases = make_fixture(split)
    arms = {"atmem_v3": [], "summary_plus_literal": []}
    budget = RetrievalBudget(context_bytes=output_bytes, optional_model_calls=0)
    authority = tuple({"principal_id": principal, **scope.to_dict(), "scopes": ["history_import:review"]}
                      for scope, principal in PRINCIPALS.items())
    with TemporaryDirectory(prefix="atmem-exact-history-") as directory:
        database = Path(directory) / "state.db"
        HouseholdApplication.initialize(database, encrypted=True, backend="file")
        memory = Memory(database, auto_vectors=False, review_authorities=authority)
        try:
            if memory.policy.state != "encrypted":
                raise RuntimeError("the diagnostic requires an encrypted store")
            _import_history(memory, history)
            generation = memory.context_generation(SCOPE)["canonical_generation"]
            for case in cases:
                available = case.expected is not None and any(
                    not line.foreign and case.expected in line.text for line in history
                )
                request = ContextRequestV3(
                    context_id=f"context-{case.id}", request_id=f"request-{case.id}", scope=SCOPE,
                    query=case.question, profile_id="context-fast", generation=generation,
                    turn_id=f"turn-{case.id}", mode="active", budget=budget,
                )
                started = perf_counter_ns()
                try:
                    package = memory.prepare_context_v3(request)
                except context_service.GovernanceViolation as error:
                    row = score(case, "", source_available=available, status="governance_error",
                                elapsed_ns=perf_counter_ns() - started, error=str(error))
                else:
                    row = score(case, package.context, source_available=available,
                                status=package.status, elapsed_ns=perf_counter_ns() - started)
                arms["atmem_v3"].append(row)
                started = perf_counter_ns()
                snippet = literal_history(history, case.literal, budget=output_bytes)
                arms["summary_plus_literal"].append(score(case, snippet, source_available=available,
                    status="matched" if snippet else "no_match", elapsed_ns=perf_counter_ns() - started))
        finally:
            memory.close()
    return {
        "format": "atmem-exact-history-diagnostic-v1", "classification": "synthetic_evidence_delivery",
        "split": split, "seed": SPLIT_SEEDS[split], "fixture_sha256": fixture_digest(history, cases),
        "history_lines": len(history), "output_budget_bytes": output_bytes, "model_calls": 0,
        "native_context_service_sha256": sha256(Path(context_service.__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(), "platform": platform.platform(),
        "arms": {name: {"summary": summarize(rows), "cases": rows} for name, rows in arms.items()},
    }


def run_benchmark(split: str, *, output_bytes: int = OUTPUT_BYTES) -> dict:
    # Key locations are resolved at import time. Start the evaluator with its
    # own home before importing AtMem, separate from any operator key or DB.
    with TemporaryDirectory(prefix="atmem-exact-history-home-") as home:
        environment = {key: value for key, value in os.environ.items()
                       if key not in {"ATMEM_HOME", "ATMEM_DB_KEY", "ATMEM_DB"}}
        environment.update(ATMEM_HOME=home, PYTHONPATH=str(Path(__file__).resolve().parents[2]))
        result = subprocess.run(
            [sys.executable, "-m", "atmem.benchmark.exact_history",
             "--split", split, "--output-bytes", str(output_bytes), "--worker"],
            cwd=home, env=environment, capture_output=True, text=True,
        )
        if result.returncode:
            raise RuntimeError(f"Exact-history evaluator failed:\n{result.stderr.strip()}")
        return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=tuple(SPLIT_SEEDS), default="development")
    parser.add_argument("--output-bytes", type=int, choices=(512, OUTPUT_BYTES), default=OUTPUT_BYTES)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    benchmark = _run_benchmark if args.worker else run_benchmark
    result = json.dumps(benchmark(args.split, output_bytes=args.output_bytes), indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as output:
            output.write(result)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
