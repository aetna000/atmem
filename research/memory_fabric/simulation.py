"""Deterministic mechanism checks, explicitly not AtMem performance results."""
from __future__ import annotations

import json
import argparse
from pathlib import Path

from research.memory_fabric.scheduling import Scheduler, Work


def simulate(jobs, durations, policy):
    scheduler = Scheduler(policy, {"write": .05, "artifact": .001, "recall": .002})
    future = sorted(jobs, key=lambda j: (j.arrival, j.ordinal))
    queue, completed = [], []
    now = 0.
    while queue or future:
        if not queue:
            now = max(now, future[0].arrival)
        while future and future[0].arrival <= now:
            queue.append(future.pop(0))
        selected, reason = scheduler.pick(queue, now)
        job = queue.pop(selected)
        # Duration is hidden from pick(); revealed only after service completes.
        duration = durations[job.ordinal]
        start, now = now, now + duration
        scheduler.finish(job, duration)
        completed.append({"ordinal": job.ordinal, "kind": job.kind, "arrival": job.arrival,
                          "start": start, "end": now, "reason": reason})
    return completed


def adversarial_report():
    # One oldest expensive write and continuing cheap BULK artifacts. Legacy
    # "every fifth bulk" can select the cheap bulk repeatedly instead of oldest.
    jobs = [Work(0, 0, "write", 100)] + [Work(i, (i - 1) * .0005, "artifact", 10)
                                                    for i in range(1, 501)]
    durations = {job.ordinal: (.05 if job.kind == "write" else .001) for job in jobs}
    results = {}
    for policy in Scheduler.POLICIES:
        rows = simulate(jobs, durations, policy)
        oldest = next(r for r in rows if r["ordinal"] == 0)
        results[policy] = {"oldest_write_start_s": oldest["start"],
                           "oldest_write_end_s": oldest["end"],
                           "completed": len(rows), "makespan_s": max(r["end"] for r in rows)}
    return {"measurement": "deterministic_simulation_not_product_performance",
            "scenario": "oldest_write_under_continuous_small_bulk_arrivals",
            "tasks": len(jobs), "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(adversarial_report(), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
    print(report)
