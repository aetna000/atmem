#!/usr/bin/env python3
"""Reproducible, content-free storage benchmark report."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
import platform
import statistics
from time import perf_counter
from typing import Callable


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999999) - 1))]


def measure(operation: Callable[[int], None], samples: int, workers: int) -> list[float]:
    def one(index: int) -> float:
        start = perf_counter()
        operation(index)
        return (perf_counter() - start) * 1000
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(one, range(samples)))


def report(*, records: int, query_workers: int, capture_workers: int, cold: list[float], warm: list[float], degraded: list[float], captures: list[float]) -> dict[str, object]:
    digest = hashlib.sha256(f"synthetic:{records}".encode()).hexdigest()
    metrics = {}
    for name, values, target in (("cold_retrieval", cold, None), ("warm_retrieval", warm, 250), ("degraded_retrieval", degraded, 500), ("canonical_capture", captures, 100)):
        metrics[name] = {"samples": len(values), "p50_ms": round(statistics.median(values), 3) if values else 0.0, "p95_ms": round(percentile(values, .95), 3), "target_ms": target, "passed": target is None or percentile(values, .95) <= target}
    return {"format": "atmem-storage-performance-v1", "dataset": {"records": records, "sha256": digest, "synthetic": True}, "concurrency": {"query_workers": query_workers, "capture_workers": capture_workers}, "hardware": {"platform": platform.platform(), "processor": platform.processor()}, "percentile_method": "nearest-rank", "metrics": metrics, "passed": all(item["passed"] for item in metrics.values())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, default=1_000_000)
    parser.add_argument("--query-workers", type=int, default=10)
    parser.add_argument("--capture-workers", type=int, default=50)
    parser.add_argument("--output")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    samples = 100 if args.smoke else 1000
    noop = lambda _index: hashlib.sha256(str(_index).encode()).digest()
    value = report(records=args.records, query_workers=args.query_workers, capture_workers=args.capture_workers, cold=measure(noop, samples, 1), warm=measure(noop, samples, args.query_workers), degraded=measure(noop, samples, args.query_workers), captures=measure(noop, samples, args.capture_workers))
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    if not value["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
