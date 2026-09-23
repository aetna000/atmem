from __future__ import annotations

import os
import platform
import statistics
import sys
from typing import Any, Iterable


def _max_rss_kb() -> int:
    """Return peak resident memory in KiB on POSIX and Windows."""

    if os.name != "nt":
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    try:
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(
            process, ctypes.byref(counters), counters.cb
        ):
            return int(counters.PeakWorkingSetSize // 1024)
    except (AttributeError, OSError):
        pass
    return 0


def percentile(values: Iterable[float], p: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, int(round((p / 100) * (len(ordered) - 1)))))
    return round(ordered[index], 3)


def ranking_metrics(rows: list[dict[str, Any]], *, full_corpus: bool, manifest: dict[str, Any], digest: str, baseline: str, started_at: float, ended_at: float, errors: int) -> dict[str, Any]:
    reciprocal: list[float] = []
    hits = {1: 0, 5: 0, 10: 0}
    latencies = []
    evidence_coverage = []
    for row in rows:
        expected = set(row["evidence_ids"])
        ranked = row["ranked_ids"]
        rank = next((index for index, candidate in enumerate(ranked, 1) if candidate in expected), None)
        reciprocal.append(0.0 if rank is None or rank > 5 else 1.0 / rank)
        for cutoff in hits:
            hits[cutoff] += bool(expected.intersection(ranked[:cutoff]))
        evidence_coverage.append(len(expected.intersection(ranked)) / max(1, len(expected)))
        latencies.append(row["latency_ms"])
    count = len(rows)
    elapsed = max(ended_at - started_at, 1e-9)
    metrics: dict[str, Any] = {
        "questions": count,
        "mrr_at_5": round(sum(reciprocal) / max(1, count), 4),
        "recall_at_1": round(hits[1] / max(1, count), 4),
        "recall_at_5": round(hits[5] / max(1, count), 4),
        "recall_at_10": round(hits[10] / max(1, count), 4),
        "evidence_coverage": round(sum(evidence_coverage) / max(1, count), 4),
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
        "throughput_records_per_second": round(len(rows) / elapsed, 3),
        "errors": errors,
        "full_corpus": full_corpus,
        "baseline": baseline,
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "pid": os.getpid(), "max_rss_kb": _max_rss_kb()},
        "manifest": manifest,
        "dataset_sha256": digest,
    }
    return metrics
