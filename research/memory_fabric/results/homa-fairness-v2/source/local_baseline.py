"""Measured local AtMem baseline with synthetic data in a disposable home.

This runner exercises real Memory retrieval/writes and protected EvidenceService
capture. It does not claim OpenClaw hook delivery or revocation-race safety.
"""

from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import ExitStack
from dataclasses import asdict
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import platform
import random
import struct
import subprocess
import tempfile
from time import monotonic, perf_counter, sleep
import wave
import zlib
from threading import BoundedSemaphore, Condition, Lock, Thread

from atmem import Memory
from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope, EvidenceService

from research.memory_fabric.protocol import Observation, Provenance, Request, arrival_schedule, summarize


SUBJECT = "fabric-fixture-subject"
RUN_ID = "fabric-fixture-run"


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    content = kind + payload
    return struct.pack(">I", len(payload)) + content + struct.pack(">I", zlib.crc32(content))


def _png(seed: int, side: int = 192) -> bytes:
    rng = random.Random(seed)
    pixels = b"".join(b"\x00" + rng.randbytes(side * 3) for _ in range(side))
    return (b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", struct.pack(">2I5B", side, side, 8, 2, 0, 0, 0))
            + _png_chunk(b"IDAT", zlib.compress(pixels)) + _png_chunk(b"IEND", b""))


def _wav() -> bytes:
    stream = BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"".join(struct.pack("<h", int(6000 * math.sin(index / 16)))
                                   for index in range(8000)))
    return stream.getvalue()


def _media_fixtures(root: Path) -> dict[str, tuple[str, bytes]]:
    fixtures = {"image": ("image/png", _png(1729)), "audio": ("audio/wav", _wav())}
    target = root / "fixture.mp4"
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "color=c=blue:s=64x64:r=2:d=1", "-an", "-c:v", "mpeg4",
             "-y", str(target)], check=True, capture_output=True, timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # A missing local encoder is reported; binary data is never mislabeled video.
        pass
    else:
        fixtures["video"] = ("video/mp4", target.read_bytes())
    return fixtures


def _memory_fact(index: int) -> str:
    return f"My synthetic catalog item {index:04d} is marker {index:04d}."


def _seed(memory_path: Path, count: int) -> dict[str, int]:
    memory = Memory(memory_path)
    try:
        for index in range(count):
            result = memory.remember(
                SUBJECT, f"Store synthetic catalog entry {index:04d}.",
                interpreted_fact=_memory_fact(index),
                interpreted_fact_key=f"synthetic_catalog_{index:04d}",
                session_id="fabric-seed",
            )
            if not result["records"] or result["records"][0]["status"] != "active":
                raise RuntimeError("synthetic seed was not admitted as active memory")
        return {"active_records": count}
    finally:
        memory.close()


def _operation(index: int) -> str:
    # Fixed deterministic 80/15/5 mix across each 20-request cycle.
    bucket = index % 20
    return "recall" if bucket < 16 else "write" if bucket < 19 else "artifact"


def _fabric_pick(queue: list[tuple[Request, int, float, Future]],
                 dispatch_count: int) -> int:
    """Pick one queued task using declared deadlines, cost classes and bulk share.

    This research-only heuristic has no authority to release content. Every fifth
    dispatch reserves service for an available bulk item; other dispatches favor
    earliest-deadline interactive work, then estimated (not oracle) cost.
    """
    estimated_ms = {"artifact": 4, "recall": 12, "write": 40}
    candidates = list(enumerate(queue))
    if dispatch_count % 5 == 4:
        bulk = [(position, item) for position, item in candidates
                if item[0].lane == "bulk" or _operation(item[1]) == "write"]
        if bulk:
            candidates = bulk
    return min(candidates, key=lambda entry: (
        0 if entry[1][0].deadline_s is not None else 1,
        entry[1][0].deadline_s if entry[1][0].deadline_s is not None else math.inf,
        estimated_ms[_operation(entry[1][1])], entry[1][0].arrival_s,
    ))[0]


def run_local_baseline(*, count: int = 60, seed_records: int = 40,
                       rate_per_s: float = 20, workers: int = 2,
                       max_outstanding: int = 24, seed: int = 17,
                       generator_lag_budget_ms: float = 25,
                       distribution: str = "fixed",
                       serialize_writes: bool = False,
                       isolate_write_lane: bool = False,
                       policy: str = "fifo") -> dict:
    """Run one measured composition over a temporary synthetic AtMem home."""
    if not 0 < count <= 500 or not 1 <= seed_records <= 1000 or not 1 <= workers <= 16:
        raise ValueError("count, seed_records or workers outside bounded pilot range")
    if max_outstanding < workers or max_outstanding > 1000:
        raise ValueError("max_outstanding must be between worker count and 1000")
    if isolate_write_lane and (workers < 2 or serialize_writes):
        raise ValueError("isolated write lane requires at least two workers and no write gate")
    if policy not in ("fifo", "fabric-deadline-size"):
        raise ValueError("unknown policy")
    if policy != "fifo" and (workers != 1 or serialize_writes or isolate_write_lane):
        raise ValueError("fabric prototype requires one worker and no other controls")
    if not math.isfinite(generator_lag_budget_ms) or generator_lag_budget_ms <= 0:
        raise ValueError("generator_lag_budget_ms must be positive and finite")
    offsets = arrival_schedule(count, rate_per_s, seed=seed, distribution=distribution)
    requests = [Request(f"r{index+1}", offset,
                        lane="fast" if _operation(index) == "recall" else "bulk",
                        deadline_s=offset + 1 if _operation(index) == "recall" else None)
                for index, offset in enumerate(offsets)]

    with tempfile.TemporaryDirectory(prefix="atmem-fabric-p0b-") as directory:
        home = Path(directory)
        memory_path = home / "canonical-memory.db"
        seed_info = _seed(memory_path, seed_records)
        media = _media_fixtures(home)
        evidence = EvidenceService(home / "evidence", vault_id="fabric-fixture", home_root=home)
        protection = evidence.protection_status()
        if protection["capture_mode"] != "full" or not protection["encrypted"]:
            raise RuntimeError("full encrypted evidence is required for the baseline")

        capacity = BoundedSemaphore(max_outstanding)
        write_gate = Lock()
        observations: list[Observation] = []
        stage_rows: list[dict] = []
        pending: list[Future] = []
        origin = monotonic()

        def worker(request: Request, index: int, admitted_s: float) -> tuple[Observation, dict]:
            start = monotonic() - origin
            memory: Memory | None = None
            stages = {"request_id": request.request_id, "operation": _operation(index),
                      "memory_ms": None, "evidence_ms": None, "capture_bytes": 0}
            phase = "write_gate" if serialize_writes and _operation(index) == "write" else "memory_open"
            write_gate_held = False
            try:
                began = perf_counter()
                if serialize_writes and _operation(index) == "write":
                    write_gate.acquire()
                    write_gate_held = True
                    stages["write_gate_wait_ms"] = round((perf_counter() - began) * 1000, 3)
                phase = "memory_open"
                memory = Memory(memory_path)
                operation = _operation(index)
                phase = f"memory_{operation}"
                if operation == "recall":
                    item = index % seed_records
                    block = memory.build_recall_block(
                        SUBJECT, f"What is synthetic catalog item {item:04d}?",
                        session_id="fabric-baseline", max_records=3,
                        require_direct_support=True,
                    )
                    exact = str(block["block"])
                    parity = _memory_fact(item) in exact
                    parts = [{"type": "text", "text": f"Synthetic catalog query {item:04d}"},
                             {"type": "text", "text": exact}]
                elif operation == "write":
                    item = seed_records + index
                    record = memory.remember(
                        SUBJECT, f"Store synthetic catalog entry {item:04d}.",
                        interpreted_fact=_memory_fact(item),
                        interpreted_fact_key=f"synthetic_catalog_{item:04d}",
                        session_id="fabric-baseline",
                    )
                    parity = bool(record["records"]) and record["records"][0]["status"] == "active"
                    parts = [{"type": "text", "text": f"Stored synthetic catalog entry {item:04d}"}]
                else:
                    kind = tuple(media)[(index // 20) % len(media)]
                    mime, payload = media[kind]
                    parity = bool(payload)
                    parts = [{"type": kind, "mime_type": mime,
                              "data_base64": base64.b64encode(payload).decode("ascii")}]
                phase = "memory_close_and_vector_sync"
                closing_memory = memory
                memory = None
                closing_memory.close()
                if write_gate_held:
                    write_gate.release()
                    write_gate_held = False
                stages["memory_ms"] = round((perf_counter() - began) * 1000, 3)
                phase = "protected_evidence_capture"
                began = perf_counter()
                receipt = evidence.capture({
                    "event_id": f"fabric-{request.request_id}", "run_id": RUN_ID,
                    "tenant_id": "local", "subject_id": SUBJECT,
                    "event_type": f"fabric.synthetic.{operation}", "parts": parts,
                })
                stages["evidence_ms"] = round((perf_counter() - began) * 1000, 3)
                stages["capture_bytes"] = sum(len(part.get("data_base64", "")) * 3 // 4
                                              for part in parts)
                if not receipt["captured"] or not receipt["reconstructable"]:
                    raise RuntimeError("protected evidence capture was incomplete")
                terminal = monotonic() - origin
                return Observation(
                    request.request_id, "completed", "finished", admitted_s, start,
                    terminal, completed_bytes=sum(len(str(part)) for part in parts),
                    # P0b does not establish a revocation/disclosure linearization.
                    authorized_at_release=None, evidence_complete=True,
                    output_parity_verified=parity,
                ), stages
            except Exception as exc:
                stages["error_type"] = type(exc).__name__
                stages["error_phase"] = phase
                stages["sqlite_error_name"] = getattr(exc, "sqlite_errorname", None)
                # This workload contains synthetic identifiers only; retain the
                # concrete failure so a failed trial can be diagnosed.
                stages["error_detail"] = str(exc)[:500]
                return Observation(request.request_id, "error", "worker_error",
                                   admitted_s, start, monotonic() - origin), stages
            finally:
                try:
                    if memory is not None:
                        memory.close()
                finally:
                    if write_gate_held:
                        write_gate.release()
                    capacity.release()

        if policy == "fabric-deadline-size":
            condition = Condition()
            queue: list[tuple[Request, int, float, Future]] = []
            arrivals_done = False

            def dispatch() -> None:
                nonlocal arrivals_done
                dispatch_count = 0
                while True:
                    with condition:
                        condition.wait_for(lambda: queue or arrivals_done)
                        if not queue:
                            return
                        selected = _fabric_pick(queue, dispatch_count)
                        request, index, admitted, future = queue.pop(selected)
                    try:
                        future.set_result(worker(request, index, admitted))
                    except BaseException as exc:
                        future.set_exception(exc)
                    dispatch_count += 1

            dispatch_thread = Thread(target=dispatch, name="fabric-research-dispatch")
            dispatch_thread.start()
        with ExitStack() as stack:
            if policy == "fifo":
                read_pool = stack.enter_context(ThreadPoolExecutor(
                    max_workers=workers - 1 if isolate_write_lane else workers))
                write_pool = (stack.enter_context(ThreadPoolExecutor(max_workers=1))
                              if isolate_write_lane else read_pool)
            try:
                for index, request in enumerate(requests):
                    wait = request.arrival_s - (monotonic() - origin)
                    if wait > 0:
                        sleep(wait)
                    admitted = monotonic() - origin
                    if not capacity.acquire(blocking=False):
                        observations.append(Observation(request.request_id, "refused", "overload",
                                                        terminal_s=admitted))
                    elif policy == "fabric-deadline-size":
                        future = Future()
                        pending.append(future)
                        with condition:
                            queue.append((request, index, admitted, future))
                            condition.notify()
                    else:
                        pool = write_pool if _operation(index) == "write" else read_pool
                        pending.append(pool.submit(worker, request, index, admitted))
            finally:
                if policy == "fabric-deadline-size":
                    with condition:
                        arrivals_done = True
                        condition.notify()
                    dispatch_thread.join()
            for future in pending:
                observation, stages = future.result()
                observations.append(observation)
                stage_rows.append(stages)

        horizon = max(monotonic() - origin, offsets[-1]) + .001
        protocol = summarize(requests, observations, horizon_s=horizon)
        generator_p99_s = protocol["all"]["generator_lag"]["p99_s"]
        generator_valid = (generator_p99_s is not None and
                           generator_p99_s * 1000 <= generator_lag_budget_ms)
        principal = EvidencePrincipal("fabric-investigator", EvidenceRole.INVESTIGATOR,
                                      EvidenceScope("local", SUBJECT))
        events = evidence.events(principal, RUN_ID)
        captured_ids = {str(event["envelope"].get("event_id")) for event in events}
        completed_ids = {f"fabric-{row.request_id}" for row in observations if row.outcome == "completed"}
        if captured_ids != completed_ids:
            raise RuntimeError("protected evidence did not reconstruct every completed operation")
        media_checks = {kind: False for kind in media}
        for event in events:
            for part in event["envelope"].get("parts", []):
                kind = part.get("type")
                if kind in media:
                    media_checks[kind] = (base64.b64decode(part["data_base64"]) == media[kind][1])

        # Source identity is caller-discovered here; protocol.py itself has no I/O.
        revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                  text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                                    text=True, check=True).stdout.strip())
        return {
            "format": "atmem-memory-fabric-local-baseline-v1",
            "measurement_kind": "real_local_composed_component_measurement",
            "scope": "Memory build_recall_block/remember plus encrypted EvidenceService.capture",
            "host_delivery_measured": False,
            "scheduling_policy": (
                "research_fabric_deadline_estimated_size_reserved_bulk" if policy != "fifo" else
                "bounded_isolated_single_writer_lane" if isolate_write_lane else
                "bounded_thread_pool_fifo_submission_serialized_writes" if serialize_writes else
                "bounded_thread_pool_fifo_submission"),
            "source_digest": {
                "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                "protocol_sha256": sha256((Path(__file__).parent / "protocol.py").read_bytes()).hexdigest(),
            },
            "authority_race_verified": False,
            "generator_lag_budget_ms": generator_lag_budget_ms,
            "generator_timing_valid": generator_valid,
            "comparison_ready": False,
            "provenance": asdict(Provenance(source_revision=revision, source_dirty=dirty,
                                            cpu_count=os.cpu_count())),
            "environment": {"python": platform.python_version(), "system": platform.system(),
                            "machine": platform.machine(), "workers": workers,
                            "max_outstanding": max_outstanding, "rate_per_s": rate_per_s,
                            "seed": seed, "arrival_distribution": distribution,
                            "seed_used_for_arrivals": distribution == "poisson",
                            "seed_records": seed_records, "offered": count},
            "write_serialization": {"enabled": serialize_writes,
                                    "scope": "in_process_same_runner_only"},
            "isolated_write_lane": isolate_write_lane,
            "policy_parameters": ({"estimated_service_ms": {"artifact": 4,
                                                                "recall": 12, "write": 40},
                                   "bulk_reservation_every_n_dispatches": 5}
                                  if policy != "fifo" else None),
            "fixture": {"memory": seed_info, "media_sha256": {
                kind: sha256(data).hexdigest() for kind, (_, data) in media.items()}},
            "capture": {"mode": protection["capture_mode"],
                        "encrypted": protection["encrypted"],
                        "reconstructed_count": len(events), "media_exact": media_checks},
            "accounting": {"horizon_s": horizon, "summary": protocol["all"],
                           "lanes": protocol["lanes"],
                           "workload_sha256": protocol["workload_sha256"],
                           "record_sha256": protocol["record_sha256"]},
            "stage_samples": stage_rows,
            "unknown_stages": ["database_lock_wait", "index_lookup", "ranking",
                               "encryption_within_evidence", "host_hook_delivery"],
            "observations": protocol["observations"],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--seed-records", type=int, default=40)
    parser.add_argument("--rate", type=float, default=20)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-outstanding", type=int, default=24)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--distribution", choices=("fixed", "poisson"), default="fixed")
    parser.add_argument("--serialize-writes", action="store_true")
    parser.add_argument("--isolate-write-lane", action="store_true")
    parser.add_argument("--policy", choices=("fifo", "fabric-deadline-size"), default="fifo")
    parser.add_argument("--generator-lag-budget-ms", type=float, default=25)
    args = parser.parse_args()
    result = run_local_baseline(count=args.count, seed_records=args.seed_records,
                                rate_per_s=args.rate, workers=args.workers,
                                max_outstanding=args.max_outstanding, seed=args.seed,
                                generator_lag_budget_ms=args.generator_lag_budget_ms,
                                distribution=args.distribution,
                                serialize_writes=args.serialize_writes,
                                isolate_write_lane=args.isolate_write_lane,
                                policy=args.policy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
                           encoding="utf-8")
    summary = result["accounting"]["summary"]
    print(json.dumps({"output": str(args.output), "outcomes": summary["outcome_counts"],
                      "p95_s": summary["completed_latency"]["p95_s"],
                      "evidence_objects": result["capture"]["reconstructed_count"]}))


if __name__ == "__main__":
    main()
