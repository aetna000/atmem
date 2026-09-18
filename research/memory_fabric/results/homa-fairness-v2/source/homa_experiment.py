"""Controlled real AtMem queue experiment; no production or host integration.

All policies share one dispatcher, one worker, bounded admission, warm read
fixtures, synchronous writes to an independent subject, and full encrypted
evidence. A stable read oracle checks full context bytes outside timed work.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import tempfile
from threading import Condition, Thread
from time import monotonic, sleep

from atmem import Memory
from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope, EvidenceService
from research.memory_fabric.local_baseline import SUBJECT, _seed, _media_fixtures, _png, _memory_fact
from research.memory_fabric.protocol import arrival_schedule
from research.memory_fabric.scheduling import Scheduler, Work

WRITE_SUBJECT = "fabric-independent-writes"
MIXES = {"mixed": (80, 15, 5), "write-heavy": (50, 40, 10), "interactive": (90, 5, 5)}
DEFAULT_ESTIMATES = {"recall": .020, "write": .045, "artifact": .015}


def digest(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def percentile(values, p):
    return sorted(values)[max(0, math.ceil(p * len(values)) - 1)] if values else None


def source_identity():
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], check=True,
                                  capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], check=True,
                                    capture_output=True, text=True).stdout.strip())
        return {"revision": revision, "source_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"revision": None, "source_dirty": None}


def workload(seed: int, count: int, rate: float, profile: str, media) -> list[Work]:
    if profile not in MIXES or count < 20 or count > 2000:
        raise ValueError("unknown profile or count outside 20..2000")
    rng = random.Random(seed)
    recall, write, _ = MIXES[profile]
    nr, nw = round(count * recall / 100), round(count * write / 100)
    kinds = ["recall"] * nr + ["write"] * nw + ["artifact"] * (count - nr - nw)
    rng.shuffle(kinds)
    offsets = arrival_schedule(count, rate, seed=seed, distribution="poisson")
    result = []
    for i, (kind, arrival) in enumerate(zip(kinds, offsets)):
        size = (len(media[i % len(media)][1]) if kind == "artifact" else
                rng.choice((64, 256, 1024)) if kind == "write" else 48)
        # Trusted synthetic deadlines vary independently; only observations,
        # not actual external releases, occur in this runner.
        deadline = arrival + rng.choice((.15, .4, 1.0)) if kind == "recall" else None
        result.append(Work(i, arrival, kind, size, deadline))
    return result


def run_trial(*, policy="fifo", profile="mixed", seed=101, count=160,
              rate=40., estimates=None, max_outstanding=32, max_bytes=4 * 1024 * 1024):
    wall_started = datetime.now(timezone.utc).isoformat()
    if SUBJECT == WRITE_SUBJECT:
        raise ValueError("read corpus must be independent of write targets")
    if max_outstanding < 1 or max_bytes < 1:
        raise ValueError("admission bounds must be positive")
    scheduler = Scheduler(policy, estimates or DEFAULT_ESTIMATES)
    with tempfile.TemporaryDirectory(prefix="atmem-fabric-homa-") as directory:
        home = Path(directory)
        database = home / "memory.db"
        _seed(database, 40)
        media_map = _media_fixtures(home)
        media = list(media_map.values()) + [("image/png", _png(991, side=512))]
        jobs = workload(seed, count, rate, profile, media)
        evidence = EvidenceService(home / "evidence", vault_id="fabric-homa", home_root=home)
        protection = evidence.protection_status()
        if not protection["encrypted"] or protection["capture_mode"] != "full":
            raise RuntimeError("full encrypted evidence is required")
        oracle = {}
        memory = Memory(database)
        try:
            for item in range(8):
                block = memory.build_recall_block(
                    SUBJECT, f"What is synthetic catalog item {item:04d}?",
                    session_id="fabric-oracle", max_records=3, require_direct_support=True)["block"]
                if _memory_fact(item) not in block:
                    raise RuntimeError("oracle does not contain the expected synthetic fact")
                oracle[item] = sha256(block.encode()).hexdigest()
            read_generation = memory.store.record_generation(SUBJECT)
        finally:
            memory.close()

        def perform(job):
            opened = monotonic()
            row = {"ordinal": job.ordinal, "kind": job.kind, "size": job.size,
                   "arrival": job.arrival, "deadline": job.deadline, "outcome": "completed",
                   "output_digest_match": None, "error": None}
            parts = []
            handle = None
            phase = "open"
            try:
                if job.kind != "artifact":
                    handle = Memory(database)
                row["open_s"] = monotonic() - opened
                began = monotonic()
                phase = "operation"
                if job.kind == "recall":
                    item = job.ordinal % 8
                    query = f"What is synthetic catalog item {item:04d}?"
                    block = handle.build_recall_block(SUBJECT, query, session_id="fabric-run",
                                                       max_records=3, require_direct_support=True)["block"]
                    row["output_sha256"] = sha256(block.encode()).hexdigest()
                    row["output_digest_match"] = row["output_sha256"] == oracle[item]
                    parts = [{"type": "text", "text": query}, {"type": "text", "text": block}]
                elif job.kind == "write":
                    text = f"Synthetic write {job.ordinal}: " + "x" * job.size
                    result = handle.remember(WRITE_SUBJECT, text, interpreted_fact=text,
                                             interpreted_fact_key=f"fixture_{job.ordinal}",
                                             session_id="fabric-write")
                    if not result["records"] or result["records"][0]["status"] != "active":
                        raise RuntimeError("write not admitted as active")
                    parts = [{"type": "text", "text": text}]
                else:
                    mime, data = media[job.ordinal % len(media)]
                    row["artifact_sha256"] = sha256(data).hexdigest()
                    parts = [{"type": mime.split("/")[0], "mime_type": mime,
                              "data_base64": base64.b64encode(data).decode("ascii")}]
                row["operation_s"] = monotonic() - began
                began = monotonic()
                phase = "close_sync"
                if handle is not None:
                    closing, handle = handle, None
                    closing.close()
                row["close_sync_s"] = monotonic() - began
            except Exception as exc:
                row.update(outcome="error", error=f"{phase}:{type(exc).__name__}:{str(exc)[:300]}")
                parts.append({"type": "text", "text": row["error"]})
            finally:
                if handle is not None:
                    try:
                        handle.close()
                    except Exception as exc:
                        row.update(outcome="error", error=f"cleanup:{type(exc).__name__}:{str(exc)[:300]}")
            began = monotonic()
            row["text_parts_sha256"] = digest([part["text"] for part in parts if part["type"] == "text"])
            try:
                receipt = evidence.capture({"event_id": f"r{job.ordinal}", "run_id": "fabric-homa",
                    "tenant_id": "local", "subject_id": SUBJECT,
                    "event_type": f"fabric.{job.kind}.{row['outcome']}", "parts": parts})
                if not receipt["captured"] or not receipt["reconstructable"]:
                    raise RuntimeError("capture incomplete")
                row["evidence_complete"] = True
            except Exception as exc:
                row.update(outcome="error", evidence_complete=False,
                           error=f"evidence:{type(exc).__name__}:{str(exc)[:300]}")
            row["evidence_s"] = monotonic() - began
            return row

        condition = Condition()
        queue = []
        rows = []
        outstanding = active_bytes = 0
        arrivals_done = False
        fatal = []
        origin = monotonic()

        def consume():
            nonlocal outstanding, active_bytes
            try:
                while True:
                    with condition:
                        condition.wait_for(lambda: queue or arrivals_done)
                        if not queue:
                            return
                        selected, reason = scheduler.pick([entry[0] for entry in queue], monotonic() - origin)
                        job, admitted = queue.pop(selected)
                    start = monotonic() - origin
                    row = perform(job)
                    end = monotonic() - origin
                    scheduler.finish(job, end - start)
                    row.update(admitted=admitted, start=start, end=end,
                               service_s=end - start, latency_s=end - job.arrival,
                               queue_s=start - admitted, selection=reason)
                    stages = sum(row.get(key, 0) for key in ("open_s", "operation_s", "close_sync_s", "evidence_s"))
                    row["unattributed_service_s"] = end - start - stages
                    if row["outcome"] == "completed" and row["unattributed_service_s"] < -.000001:
                        raise RuntimeError("stage durations exceed measured service")
                    with condition:
                        rows.append(row)
                        outstanding -= 1
                        active_bytes -= job.size
            except BaseException as exc:
                with condition:
                    fatal.append(f"{type(exc).__name__}:{exc}")
                    condition.notify_all()

        thread = Thread(target=consume, name="fabric-common-dispatcher")
        thread.start()
        try:
            for job in jobs:
                delay = job.arrival - (monotonic() - origin)
                if delay > 0:
                    sleep(delay)
                with condition:
                    now = monotonic() - origin
                    if fatal:
                        raise RuntimeError(fatal[0])
                    if outstanding >= max_outstanding or active_bytes + job.size > max_bytes:
                        rows.append({"ordinal": job.ordinal, "kind": job.kind, "size": job.size,
                                     "arrival": job.arrival, "deadline": job.deadline,
                                     "admitted": None, "end": now, "outcome": "refused"})
                    else:
                        queue.append((job, now))
                        outstanding += 1
                        active_bytes += job.size
                        condition.notify()
        finally:
            with condition:
                arrivals_done = True
                condition.notify_all()
            thread.join()
        if fatal:
            raise RuntimeError(fatal[0])
        horizon = monotonic() - origin
        if len(rows) != len(jobs) or len({r["ordinal"] for r in rows}) != len(jobs) or outstanding != 0:
            raise RuntimeError("accounting did not reconcile")
        memory = Memory(database)
        try:
            if memory.store.record_generation(SUBJECT) != read_generation:
                raise RuntimeError("read corpus changed")
        finally:
            memory.close()
        principal = EvidencePrincipal("fixture-investigator", EvidenceRole.INVESTIGATOR,
                                      EvidenceScope("local", SUBJECT))
        events = evidence.events(principal, "fabric-homa")
        expected = {f"r{r['ordinal']}" for r in rows if r.get("evidence_complete")}
        if {e["envelope"]["event_id"] for e in events} != expected:
            raise RuntimeError("reconstructed evidence IDs differ from capture receipts")
        by_id = {f"r{r['ordinal']}": r for r in rows}
        recovered = 0
        for event in events:
            row = by_id[event["envelope"]["event_id"]]
            texts = [part["text"] for part in event["envelope"]["parts"] if part["type"] == "text"]
            if digest(texts) != row["text_parts_sha256"]:
                raise RuntimeError("reconstructed text differs from original captured text")
            if "artifact_sha256" in row:
                payloads = [p for p in event["envelope"]["parts"] if "data_base64" in p]
                if len(payloads) != 1 or sha256(base64.b64decode(payloads[0]["data_base64"])).hexdigest() != row["artifact_sha256"]:
                    raise RuntimeError("artifact recovery differs from captured original bytes")
                recovered += 1
        lags = [(r["admitted"] if r["admitted"] is not None else r["end"]) - r["arrival"] for r in rows]
        summaries = {}
        for lane, selected in (("all", rows), ("recall", [r for r in rows if r["kind"] == "recall"]),
                               ("bulk", [r for r in rows if r["kind"] != "recall"]),
                               ("write", [r for r in rows if r["kind"] == "write"]),
                               ("artifact", [r for r in rows if r["kind"] == "artifact"])):
            done = [r for r in selected if r["outcome"] == "completed"]
            latencies = [r["latency_s"] for r in done]
            summaries[lane] = {"offered": len(selected), "completed": len(done),
                "error": sum(r["outcome"] == "error" for r in selected),
                "refused": sum(r["outcome"] == "refused" for r in selected),
                "p95_s": percentile(latencies, .95), "p90_s": percentile(latencies, .90),
                "mean_s": statistics.mean(latencies) if latencies else None,
                "max_queue_s": max((r["queue_s"] for r in done), default=None),
                "completed_per_s": len(done) / horizon,
                "completed_before_arrivals_end": sum(r["end"] <= jobs[-1].arrival for r in done),
                "observed_on_time": sum(r["deadline"] is not None and r["end"] < r["deadline"] for r in done)}
            rank = math.ceil(.95 * len(selected))
            summaries[lane]["all_offered_p95_completion_bound_s"] = (
                sorted(latencies)[rank - 1] if rank > 0 and len(latencies) >= rank else None)
            summaries[lane]["all_offered_p95_attainable"] = rank > 0 and len(latencies) >= rank
        return {"format": "fabric-service-fairness-v1", "measurement": "real_local_atomic_operations",
                "policy": policy, "profile": profile, "seed": seed, "count": count, "rate": rate,
                "horizon_s": horizon, "estimates_initial": estimates or DEFAULT_ESTIMATES,
                "parameters": {"fifo_fraction": scheduler.fifo_fraction,
                               "bulk_fraction": scheduler.bulk_fraction, "credit_cap_s": scheduler.credit_cap,
                               "workers": 1, "max_outstanding": max_outstanding, "max_bytes": max_bytes},
                "workload_digest": digest([asdict(j) for j in jobs]),
                "media_digest": digest([(mime, sha256(data).hexdigest()) for mime, data in media]),
                "source_digest": {name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                  for name in ("homa_experiment.py", "scheduling.py", "local_baseline.py",
                                               "run_fairness_suite.py", "analyze_fairness.py")},
                "environment": {"python": platform.python_version(), "machine": platform.machine(),
                                "system": platform.system(), "warm_read_oracle": True,
                                "cpu_count": os.cpu_count(), "started_utc": wall_started,
                                **source_identity()},
                "generator_p99_s": percentile(lags, .99), "generator_valid": percentile(lags, .99) <= .025,
                "quality": {"exact_read_digest_matches": sum(r.get("output_digest_match") is True for r in rows),
                            "exact_read_digest_failures": sum(r.get("output_digest_match") is False for r in rows),
                            "encrypted": True, "reconstructed_events": len(events), "recovered_artifacts": recovered},
                "host_delivery_measured": False, "release_authority_verified": False,
                "summary": summaries, "rows": sorted(rows, key=lambda r: r["ordinal"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=Scheduler.POLICIES, default="fifo")
    parser.add_argument("--profile", choices=MIXES, default="mixed")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--count", type=int, default=160)
    parser.add_argument("--rate", type=float, default=40)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_trial(policy=args.policy, profile=args.profile, seed=args.seed,
                       count=args.count, rate=args.rate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "summary": report["summary"]}))


if __name__ == "__main__":
    main()
