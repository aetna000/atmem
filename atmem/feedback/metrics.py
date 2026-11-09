"""Explicit denominators over attributable scoped evidence; no efficacy claim.

Inputs are authoritative task schedules and retained readback receipts supplied by
the application, never an MCP caller's success totals. Pure reducers do not
authenticate arbitrary dictionaries: production access uses the service boundary.
"""
from __future__ import annotations

from collections import defaultdict
import math
import random

from atmem.contracts.feedback import FeedbackScope, OutcomeRecord, identifier
from atmem.feedback.verification import action_results


def rate(numerator: int, denominator: int) -> dict:
    if type(numerator) is not int or type(denominator) is not int or not 0 <= numerator <= denominator:
        raise ValueError("valid exact counts required")
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None,
            "status": "assessed" if denominator else "insufficient_evidence"}


def paired_episode_interval(pairs: tuple[tuple[str, bool, bool], ...], *, seed=50, resamples=2000) -> dict:
    """Resample whole episodes, with candidate-minus-baseline task weighting.

    Diagnostics only without an independently approved powered evaluation.
    Returns inconclusive when there are fewer than two independent episodes.
    """
    if type(pairs) is not tuple or not pairs or len(pairs) > 10000 or type(resamples) is not int or not 100 <= resamples <= 10000:
        raise ValueError("bounded paired episode data required")
    groups = defaultdict(list)
    for episode, before, after in pairs:
        identifier(episode)
        if type(before) is not bool or type(after) is not bool:
            raise ValueError("paired independent boolean outcomes required")
        groups[episode].append(int(after)-int(before))
    estimate = sum(sum(g) for g in groups.values()) / len(pairs)
    result = {"estimate": estimate, "confidence_level": .95, "episodes": len(groups), "tasks": len(pairs),
              "lower": None, "upper": None, "status": "inconclusive", "claim": "diagnostic_only"}
    if len(groups) < 2:
        return result
    rng = random.Random(seed)
    episodes = list(groups.values())
    draws = []
    for _ in range(resamples):
        draw = rng.choices(episodes, k=len(episodes))
        draws.append(sum(sum(g) for g in draw) / sum(len(g) for g in draw))
    draws.sort()
    result.update(lower=draws[int(.025*(resamples-1))], upper=draws[int(.975*(resamples-1))], status="diagnostic")
    return result


def summarize(scope: FeedbackScope, scheduled: list[dict], records: list[tuple[OutcomeRecord, list[dict]]], *, assessments=()) -> dict:
    """Reduce one frozen schedule, retaining unknown and missing tasks.

    Version-one action reducer intentionally does not infer answer precision,
    evidence relevance or fact causality from a successful tool call. Those
    independent assessments remain explicitly unassessed.
    """
    if type(scope) is not FeedbackScope or len(scheduled) > 10000 or len(records) > 10000:
        raise ValueError("bounded scoped input required")
    ids = set()
    for item in scheduled:
        if (type(item) is not dict or set(item) != {"outcome_id", "episode_id", "answerable"}
                or type(item["answerable"]) is not bool):
            raise ValueError("closed task schedule required")
        identifier(item["outcome_id"])
        identifier(item["episode_id"])
        if item["outcome_id"] in ids:
            raise ValueError("duplicate scheduled outcome")
        ids.add(item["outcome_id"])
    indexed = {}
    for outcome, receipts in records:
        if outcome.scope != scope or outcome.outcome_id not in ids or outcome.outcome_id in indexed:
            raise ValueError("foreign, unscheduled or duplicate outcome")
        indexed[outcome.outcome_id] = action_results(outcome, receipts)
    complete = covered = unknown = disputed = failed = missing = 0
    details = []
    for item in scheduled:
        actions = indexed.get(item["outcome_id"])
        success = bool(actions) and all(a["verified_success"] for a in actions)
        complete += success
        covered += success and item["answerable"]
        if actions is None:
            missing += 1
            unknown += 1
            status = "unknown"
        elif success:
            status = "pass"
        elif any(a["status"] == "disputed" for a in actions):
            disputed += 1
            status = "disputed"
        elif any(a["status"] == "fail" for a in actions):
            failed += 1
            status = "fail"
        else:
            unknown += 1
            status = "unknown"
        details.append({"outcome_id": item["outcome_id"], "episode_id": item["episode_id"],
                        "status": status, "actions": actions or []})
    metrics = {name: {} for name in ("wrong_answer_rate", "evidence_precision", "false_denial_rate", "required_fact_write_failure")}
    for item in assessments:
        if (type(item) is not dict or set(item) != {"outcome_id", "metric", "unit_id", "positive"}
                or item["outcome_id"] not in ids or item["metric"] not in metrics
                or item["positive"] is not None and type(item["positive"]) is not bool):
            raise ValueError("scoped independent assessment required")
        identifier(item["unit_id"])
        key = (item["outcome_id"], item["unit_id"])
        metrics[item["metric"]].setdefault(key, set()).add(item["positive"])
    metric_rates, unassessed, disputed_units = {}, {}, {}
    for name, units in metrics.items():
        settled = [next(iter(v)) for v in units.values() if len(v) == 1 and None not in v]
        metric_rates[name] = rate(sum(settled), len(settled))
        unassessed[name] = sum(v == {None} for v in units.values())
        disputed_units[name] = sum(len(v) > 1 for v in units.values())
    assessed_answer_tasks = {outcome_id for (outcome_id, _), states in metrics["wrong_answer_rate"].items()
                             if len(states) == 1 and None not in states}
    return {"format": "atmem-feedback-quality-v1", "scope": scope.to_dict(),
            "verified_full_task_success": rate(complete, len(scheduled)),
            "coverage": rate(covered, sum(i["answerable"] for i in scheduled)),
            **metric_rates, "unassessed_units": unassessed, "disputed_units": disputed_units,
            "unknown_tasks": unknown, "disputed_tasks": disputed, "failed_tasks": failed,
            "missing_tasks": missing, "unassessed_answer_tasks": len(scheduled)-len(assessed_answer_tasks), "tasks": details,
            "quality_improvement": "not_evaluated"}
