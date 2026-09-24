"""Descriptive smoke reporting, not confirmatory significance or a leaderboard."""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import math
import random


def charge_totals(charges: list[dict]) -> dict:
    unique = {}
    for charge in charges:
        key = charge["charge_id"]
        if key in unique and unique[key] != charge:
            raise ValueError("conflicting charge_id")
        unique[key] = charge
    known: dict[str, Decimal] = {}
    unknown = 0
    for charge in unique.values():
        amount = charge.get("amount")
        if amount is None:
            unknown += 1
            continue
        if not charge.get("currency") or not charge.get("price_source"):
            raise ValueError("known amount needs currency and price provenance")
        try:
            number = Decimal(str(amount))
        except InvalidOperation as exc:
            raise ValueError("invalid amount") from exc
        if not number.is_finite() or number < 0:
            raise ValueError("invalid amount")
        currency = charge["currency"]
        known[currency] = known.get(currency, Decimal(0)) + number
    return {"known_subtotals": {k: str(v) for k, v in known.items()},
            "unknown_charge_count": unknown, "unique_charges": len(unique),
            "complete": unknown == 0}


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    if not 0 <= fraction <= 1 or any(not math.isfinite(v) for v in values):
        raise ValueError("invalid percentile input")
    return sorted(values)[max(0, math.ceil(len(values)*fraction)-1)]


def paired_cluster_interval(pairs: list[dict], *, seed: int = 20260925,
                            samples: int = 2000) -> dict:
    """Mean paired difference with cluster bootstrap; no hypothesis-test claim."""
    if samples < 100:
        raise ValueError("at least 100 bootstrap resamples")
    clusters: dict[str, list[float]] = {}
    seen = set()
    for pair in pairs:
        if pair["pair_id"] in seen:
            raise ValueError("duplicate pair_id")
        seen.add(pair["pair_id"])
        try:
            delta = pair["candidate"] - pair["baseline"]
        except TypeError as exc:
            raise ValueError("missing/nonfinite pair") from exc
        if not math.isfinite(delta):
            raise ValueError("missing/nonfinite pair")
        clusters.setdefault(pair["cluster_id"], []).append(delta)
    if len(clusters) < 2:
        return {"interval": None, "reason": "fewer_than_two_task_clusters"}
    means = [sum(values)/len(values) for values in clusters.values()]
    rng = random.Random(seed)
    draws = [sum(rng.choices(means, k=len(means)))/len(means) for _ in range(samples)]
    return {"mean_delta": sum(means)/len(means), "interval": [percentile(draws, .025), percentile(draws, .975)],
            "estimand": "equally weighted task-cluster mean paired difference",
            "clusters": len(means), "seed": seed, "resamples": samples}


def summarize(rows: list[dict]) -> dict:
    cells: dict[str, list[dict]] = {}
    for row in rows:
        key = "/".join([row["arm"], row["capability"], str(row["fault"]),
                        str(row["negative_control"]), "drop=" + str(row.get("drop_request", False))])
        cells.setdefault(key, []).append(row)
    result = {}
    for key, trials in cells.items():
        measured = [r for r in trials if "oracle" in r]
        times = [r["elapsed_ms"] for r in measured if r.get("elapsed_ms") is not None
                 and r["disposition"] == "completed"]
        blocked_times = [r["elapsed_ms"] for r in measured if r.get("elapsed_ms") is not None
                         and r["disposition"] == "blocked"]
        intended = sum(r["oracle"]["intended_operations"] for r in measured)
        result[key] = {
            "scheduled_trials": len(trials), "scored_trials": len(measured),
            "dispositions": dict(Counter(r["disposition"] for r in trials)),
            "fault_reached": sum(r["fault_reached"] for r in trials),
            "valid_completion_count": sum(r["oracle"]["valid_completion"] and r["disposition"] == "completed" for r in measured),
            "duplicate_effects": sum(r["oracle"]["duplicate_effects"] for r in measured),
            "wrong_effects": sum(r["oracle"]["wrong_effects"] for r in measured),
            "forgotten_operations": sum(len(r["oracle"]["forgotten_operations"]) for r in measured),
            "pending_blocked_operations": sum(len(r["oracle"]["pending_blocked_operations"]) for r in measured),
            "intended_operations_scored": intended,
            "elapsed_p50_ms": percentile(times, .5), "elapsed_p95_ms": percentile(times, .95),
            "latency_population": "completed scored trials only; excludes fixture setup and teardown",
            "blocked_elapsed_p50_ms": percentile(blocked_times, .5),
            "blocked_elapsed_p95_ms": percentile(blocked_times, .95),
            "incomplete_denominator": len(measured) != len(trials),
        }
    return {"evidence_level": "smoke", "production_claims_allowed": False,
            "cells": result,
            "unavailable_metrics": ["live model cost/tokens", "context integrity in agent execution",
                                    "full-fidelity evidence continuity", "CPU and peak RSS",
                                    "held-out significance and multiplicity-controlled comparison"],
            "warning": "Generic one-operation crash fixtures; not a public-corpus agent evaluation."}
