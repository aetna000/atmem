"""Evaluator-only paired summaries. No answer key is sent to product code."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class Outcome:
    task_id: str
    cluster: str
    passed: bool
    duration_ms: float
    input_tokens: int | None
    output_tokens: int | None

    def __post_init__(self) -> None:
        if not self.task_id or not self.cluster or type(self.passed) is not bool:
            raise ValueError("task, cluster and boolean outcome required")
        if not math.isfinite(self.duration_ms) or self.duration_ms < 0:
            raise ValueError("invalid duration")
        if any(v is not None and (type(v) is not int or v < 0)
               for v in (self.input_tokens, self.output_tokens)):
            raise ValueError("usage must be nonnegative integers or explicitly unknown")


def wilson(successes: int, total: int) -> tuple[float, float]:
    """Descriptive binomial interval; not a substitute for cluster uncertainty."""
    if type(successes) is not int or type(total) is not int or not 0 <= successes <= total or total == 0:
        raise ValueError("invalid binomial denominator")
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z*z / total
    center = (p + z*z / (2*total)) / denominator
    half = z * math.sqrt((p*(1-p) + z*z/(4*total))/total) / denominator
    return max(0., center-half), min(1., center+half)


def quantile(values: list[float], q: float) -> float:
    if not values or not 0 <= q <= 1:
        raise ValueError("invalid percentile")
    ordered = sorted(values)
    offset = (len(ordered)-1)*q
    low = math.floor(offset)
    high = math.ceil(offset)
    return ordered[low] + (offset-low)*(ordered[high]-ordered[low])


def paired_summary(baseline: list[Outcome], candidate: list[Outcome], *,
                   seed: int = 2310, replicates: int = 2000) -> dict:
    base = {o.task_id: o for o in baseline}
    cand = {o.task_id: o for o in candidate}
    if not base or len(base) != len(baseline) or len(cand) != len(candidate) or base.keys() != cand.keys():
        raise ValueError("paired comparison requires identical complete unique task IDs")
    if type(replicates) is not int or replicates < 100:
        raise ValueError("insufficient bootstrap replicates")
    clusters = defaultdict(list)
    wins = losses = 0
    for key in sorted(base):
        a, b = base[key], cand[key]
        if a.cluster != b.cluster:
            raise ValueError("paired cluster identity mismatch")
        delta = int(b.passed)-int(a.passed)
        clusters[a.cluster].append(delta)
        wins += delta == 1
        losses += delta == -1
    n = len(base)
    rng = random.Random(seed)
    keys = sorted(clusters)
    interval = None
    if len(keys) >= 2:
        deltas = []
        for _ in range(replicates):
            selected = [clusters[rng.choice(keys)] for _ in keys]
            deltas.append(sum(sum(v) for v in selected)/sum(len(v) for v in selected))
        interval = [quantile(deltas, .025), quantile(deltas, .975)]
    def summarize(rows: list[Outcome]) -> dict:
        passed = sum(o.passed for o in rows)
        missing = sum(o.input_tokens is None or o.output_tokens is None for o in rows)
        return {"passed": passed, "tasks": n, "accuracy": passed/n,
                "descriptive_binomial_95_interval": wilson(passed, n),
                "p50_ms": quantile([o.duration_ms for o in rows], .5),
                "p95_ms": quantile([o.duration_ms for o in rows], .95),
                "input_tokens_known_lower_bound": sum(o.input_tokens or 0 for o in rows),
                "output_tokens_known_lower_bound": sum(o.output_tokens or 0 for o in rows),
                "tasks_with_unknown_usage": missing}
    discordant = wins+losses
    # Exact paired sign/McNemar test; descriptive where within-cluster dependence exists.
    p = min(1., 2*sum(math.comb(discordant, i) for i in range(min(wins, losses)+1))/2**discordant) if discordant else 1.
    return {"baseline": summarize(baseline), "candidate": summarize(candidate),
            "paired_wins": wins, "paired_losses": losses,
            "accuracy_delta": (wins-losses)/n, "independent_clusters": len(keys),
            "cluster_bootstrap_95_delta_interval": interval,
            "cluster_inference_warning": "Few clusters; exploratory, not powered confirmation" if len(keys) < 10 else None,
            "descriptive_exact_paired_p": p,
            "ready_for_600": False}


def readiness(summary: dict, *, pillars_accepted: int, transfer_accepted: bool,
              review_passed: bool, guardrails_passed: bool,
              matched_mem0: bool, powered_confirmation: bool) -> dict:
    """Legacy generalization/superiority qualification, not working-set dispatch.

    Preserve the stronger historical claim gate. The owner's fixed-set campaign
    uses working_set_readiness and never treats it as proof of generalization.
    """
    interval = summary.get("cluster_bootstrap_95_delta_interval")
    conditions = {
        "four_pillars": type(pillars_accepted) is int and pillars_accepted == 4,
        "transfer": transfer_accepted is True,
        "review": review_passed is True,
        "guardrails": guardrails_passed is True,
        "matched_mem0": matched_mem0 is True,
        "powered_confirmation": powered_confirmation is True,
        "at_least_90_percent": summary["candidate"]["accuracy"] >= .9,
        "positive_cluster_lower_bound": interval is not None and interval[0] > 0,
        "complete_usage": summary["candidate"]["tasks_with_unknown_usage"] == 0
                          and summary["baseline"]["tasks_with_unknown_usage"] == 0,
    }
    return {"ready_for_600": all(conditions.values()), "conditions": conditions}


PILLARS = frozenset({'hybrid-discovery', 'bounded-followup', 'applicable-state', 'complete-evidence'})


def working_set_readiness(working: dict, recurring: dict, *, pillar_decisions: dict,
                          review_passed: bool, guardrails_passed: bool,
                          artifact_qualified: bool, recording_qualified: bool,
                          budget_qualified: bool, archive_qualified: bool) -> dict:
    """Owner-approved fixed-60/18 gate, distinct from a scientific claim gate.

    Inputs are complete saved-trace comparisons from stage_report, bound to the
    dispatch review. This computes the decision; it does not create attestations,
    qualify missing components, waive failures or request another corpus.
    """
    def complete(report, count):
        if report.get('complete_paired_comparison') is not True or report.get('paired_tasks') != count:
            return False
        for arm in ('baseline','candidate'):
            row=report.get(arm,{})
            if (any(type(row.get(k)) is not int for k in ('requested','graded','passed'))
                    or row['requested'] != count or row['graded'] != count
                    or not 0 <= row['passed'] <= count or row.get('complete') is not True
                    or row.get('ungraded_or_not_executed') != 0):
                return False
        return True

    def usage_complete(report):
        return all(type(report.get(arm,{}).get(metric,{}).get('unknown_tasks')) is int
            and report[arm][metric]['unknown_tasks'] == 0
            for arm in ('baseline','candidate')
            for metric in ('reader_input_tokens','reader_output_tokens'))

    complete60,complete18=complete(working,60),complete(recurring,18)
    wins,losses=working.get('paired_wins'),working.get('paired_losses')
    conditions={
        'complete_fixed_60':complete60,
        'complete_fixed_18':complete18,
        'at_least_54_of_60':complete60 and working['candidate']['passed']>=54,
        'all_recurring_18_correct':complete18 and recurring['candidate']['passed']==18,
        'positive_observed_paired_effect':(complete60 and type(wins) is int and type(losses) is int
            and 0<=losses<wins<=60 and wins+losses<=60
            and wins-losses==working['candidate']['passed']-working['baseline']['passed']),
        'four_accepted_pillars':set(pillar_decisions)==PILLARS
            and all(v=='accepted' for v in pillar_decisions.values()),
        'complete_recorded_usage':usage_complete(working) and usage_complete(recurring),
        'review':review_passed is True,'guardrails':guardrails_passed is True,
        'installed_artifact':artifact_qualified is True,'recording':recording_qualified is True,
        'reserved_budget':budget_qualified is True,'verified_archive':archive_qualified is True,
    }
    return {'ready_for_600':all(conditions.values()),'conditions':conditions,
        'scope':'owner-approved-known-benchmark-working-set',
        'generalization_established':False,'mem0_superiority_established':False,
        'external_transfer_corpus_required':False}
