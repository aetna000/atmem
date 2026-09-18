"""Synthetic measurement protocol, not a scheduler or authority implementation.

Validates supplied observations only. No I/O, environment reads, runtime imports,
or proof of permission enforcement. All provenance is caller supplied.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from hashlib import sha256
import json
import math
import random
import re


OUTCOMES = ("completed", "refused", "expired", "cancelled", "error", "censored")
LANES = ("fast", "bulk")
REASONS = {
    "completed": {"finished"},
    "refused": {"overload", "revoked", "policy"},
    "expired": {"deadline"},
    "cancelled": {"caller_cancel", "revoked"},
    "error": {"worker_error", "evidence_failure"},
    "censored": {"observation_ended"},
}


def _number(value: float, name: str, *, positive: bool = False) -> None:
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be finite numeric")
    try:
        finite = math.isfinite(value)
    except OverflowError as exc:
        raise ValueError(f"{name} is too large") from exc
    if not finite:
        raise ValueError(f"{name} must be finite numeric")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{name} out of range")


def _integer(value: int, name: str) -> None:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValueError(f"{name} must be a nonnegative signed-64-bit integer")


@dataclass(frozen=True, slots=True)
class Request:
    request_id: str
    arrival_s: float
    lane: str = "fast"
    deadline_s: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not re.fullmatch(r"r[0-9]{1,12}", self.request_id):
            raise ValueError("request_id must be a synthetic r<number> identifier")
        _number(self.arrival_s, "arrival_s")
        if self.lane not in LANES:
            raise ValueError("unknown lane")
        if self.deadline_s is not None:
            _number(self.deadline_s, "deadline_s")
            if self.deadline_s < self.arrival_s:
                raise ValueError("deadline precedes arrival")


@dataclass(frozen=True, slots=True)
class Observation:
    request_id: str
    outcome: str
    reason: str
    admitted_s: float | None = None
    started_s: float | None = None
    terminal_s: float | None = None
    completed_bytes: int = 0
    authorized_at_release: bool | None = None
    evidence_complete: bool | None = None
    output_parity_verified: bool | None = None
    authority_generation: int | None = None
    revocation_ack_s: float | None = None

    def __post_init__(self) -> None:
        Request(self.request_id, 0)
        if self.outcome not in OUTCOMES or self.reason not in REASONS[self.outcome]:
            raise ValueError("invalid outcome/reason")
        for name in ("admitted_s", "started_s", "terminal_s", "revocation_ack_s"):
            value = getattr(self, name)
            if value is not None:
                _number(value, name)
        _integer(self.completed_bytes, "completed_bytes")
        if self.authority_generation is not None:
            _integer(self.authority_generation, "authority_generation")
        for flag in self.verification:
            if flag is not None and type(flag) is not bool:
                raise ValueError("verification fields must be bool or None")
        if (self.outcome == "censored") != (self.terminal_s is None):
            raise ValueError("only censored observations have no terminal time")
        if self.started_s is not None and self.admitted_s is None:
            raise ValueError("start requires admission")
        if self.outcome == "completed" and self.started_s is None:
            raise ValueError("completion requires start")
        if self.outcome != "completed" and (
            self.completed_bytes or any(flag is not None for flag in self.verification)
        ):
            raise ValueError("only completion carries bytes/verification")

    @property
    def verification(self) -> tuple[bool | None, ...]:
        return (self.authorized_at_release, self.evidence_complete, self.output_parity_verified)


@dataclass(frozen=True, slots=True)
class Provenance:
    """Unknowns are explicit; this module never discovers machine/user state."""

    source_revision: str | None = None
    source_dirty: bool | None = None
    dependency_sha256: str | None = None
    cpu_count: int | None = None

    def __post_init__(self) -> None:
        for name, length in (("source_revision", 40), ("dependency_sha256", 64)):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str) or not re.fullmatch(rf"[0-9a-f]{{{length}}}", value)
            ):
                raise ValueError(f"invalid {name}")
        if self.source_dirty is not None and type(self.source_dirty) is not bool:
            raise ValueError("source_dirty must be bool or None")
        if self.cpu_count is not None:
            _integer(self.cpu_count, "cpu_count")
            if self.cpu_count == 0:
                raise ValueError("cpu_count must be positive")


def arrival_schedule(count: int, rate_per_s: float, *, seed: int = 0,
                     distribution: str = "fixed") -> tuple[float, ...]:
    """Open-loop offsets independent of completions; does not dispatch or sleep."""
    _integer(count, "count")
    _integer(seed, "seed")
    _number(rate_per_s, "rate_per_s", positive=True)
    if distribution not in ("fixed", "poisson"):
        raise ValueError("unknown arrival distribution")
    rng = random.Random(seed)
    offsets = []
    elapsed = 0.0
    for index in range(count):
        elapsed = index / rate_per_s if distribution == "fixed" else elapsed + rng.expovariate(rate_per_s)
        _number(elapsed, "arrival offset")
        offsets.append(elapsed)
    return tuple(offsets)


def _rank(probability: float, count: int) -> int:
    _number(probability, "probability", positive=True)
    if probability > 1:
        raise ValueError("probability must be <= 1")
    fraction = Fraction(str(probability))
    return -(-(fraction.numerator * count) // fraction.denominator)


def percentile(values: list[float], probability: float) -> float | None:
    rank = _rank(probability, len(values))
    for value in values:
        _number(value, "sample")
    return sorted(values)[rank - 1] if values else None


def _timings(values: list[float]) -> dict:
    return {"n": len(values), "max_s": max(values, default=None), **{
        name: percentile(values, p) for name, p in (("p50_s", .5), ("p95_s", .95), ("p99_s", .99))
    }}


def _summary(pairs: list[tuple[Request, Observation]], horizon_s: float) -> dict:
    offered = len(pairs)
    counts = {outcome: sum(o.outcome == outcome for _, o in pairs) for outcome in OUTCOMES}
    completed = [(r, o) for r, o in pairs if o.outcome == "completed"]
    unknown = sum(not any(flag is False for flag in o.verification)
                  and any(flag is None for flag in o.verification) for _, o in completed)
    failed = sum(any(flag is False for flag in o.verification) for _, o in completed)
    verified = [(r, o) for r, o in completed if all(flag is True for flag in o.verification)
                and (r.deadline_s is None or o.terminal_s < r.deadline_s)]
    success_latencies = sorted(o.terminal_s - r.arrival_s for r, o in verified)
    bounds = {}
    for label, p in (("p50", .5), ("p95", .95), ("p99", .99)):
        rank = _rank(p, offered)
        status = "empty" if not offered else "unknown_verification" if unknown else (
            "finite" if rank <= len(success_latencies) else "unattainable"
        )
        bounds[label] = {"status": status, "seconds": success_latencies[rank - 1] if status == "finite" else None}
    deadline_pairs = [(r, o) for r, o in pairs if r.lane == "fast" and r.deadline_s is not None]
    deadline_successes = sum(r.lane == "fast" and r.deadline_s is not None for r, _ in verified)
    verified_late = sum(all(flag is True for flag in o.verification)
                        and r.deadline_s is not None and o.terminal_s >= r.deadline_s
                        for r, o in completed)
    return {
        "offered": offered, "outcome_counts": counts,
        "outcome_rates": {k: v / offered if offered else None for k, v in counts.items()},
        "completed_latency": _timings([o.terminal_s - r.arrival_s for r, o in completed]),
        "admitted_completed_latency": _timings([o.terminal_s - o.admitted_s for _, o in completed]),
        "generator_lag": _timings([
            (o.admitted_s if o.admitted_s is not None else o.terminal_s) - r.arrival_s
            for r, o in pairs if o.admitted_s is not None or o.outcome == "refused"
        ]),
        "queue_wait": _timings([o.started_s - o.admitted_s for _, o in pairs if o.started_s is not None]),
        "service_until_terminal": _timings([o.terminal_s - o.started_s for _, o in pairs
                                            if o.started_s is not None and o.terminal_s is not None]),
        "oldest_censored_age_s": max((horizon_s - r.arrival_s for r, o in pairs if o.outcome == "censored"), default=None),
        "completed_per_s": len(completed) / horizon_s,
        "completed_bytes_per_s": sum(o.completed_bytes for _, o in completed) / horizon_s,
        "known_verified_ontime_count": len(verified), "unknown_verification_count": unknown,
        "failed_verification_count": failed,
        "verification_counts": {"failed": failed, "unknown": unknown,
                                "verified_late": verified_late, "verified_ontime": len(verified)},
        "late_completion_count": sum(r.deadline_s is not None and o.terminal_s >= r.deadline_s for r, o in completed),
        "known_deadline_miss_count": sum(r.deadline_s is not None and r.deadline_s <= horizon_s
                                         and (o.outcome != "completed" or o.terminal_s >= r.deadline_s)
                                         for r, o in pairs),
        "authorized_ontime_goodput_per_s": None if unknown else len(verified) / horizon_s,
        "known_goodput_lower_bound_per_s": len(verified) / horizon_s,
        "interactive_deadline_offered": len(deadline_pairs),
        "interactive_deadline_success_lower_bound": deadline_successes / len(deadline_pairs) if deadline_pairs else None,
        "all_offered_verified_completion_bound": bounds,
    }


def summarize(requests: list[Request], observations: list[Observation], *,
              horizon_s: float, provenance: Provenance | None = None) -> dict:
    """Closed synthetic observations only; not a real benchmark or safety proof."""
    _number(horizon_s, "horizon_s", positive=True)
    if any(type(r) is not Request for r in requests) or any(type(o) is not Observation for o in observations):
        raise ValueError("only closed protocol records are supported")
    provenance = provenance if provenance is not None else Provenance()
    if type(provenance) is not Provenance:
        raise ValueError("invalid provenance record")
    reqs = {r.request_id: r for r in requests}
    obs = {o.request_id: o for o in observations}
    if len(reqs) != len(requests) or len(obs) != len(observations):
        raise ValueError("duplicate request or observation")
    if reqs.keys() != obs.keys():
        raise ValueError("every offered request needs exactly one observation")
    pairs = [(reqs[key], obs[key]) for key in sorted(reqs)]
    raw = []
    for r, o in pairs:
        if r.arrival_s >= horizon_s:
            raise ValueError("arrival must precede horizon")
        previous = r.arrival_s
        for value in (o.admitted_s, o.started_s, o.terminal_s):
            if value is not None:
                if value < previous or value > horizon_s:
                    raise ValueError("observation times out of order or beyond horizon")
                previous = value
        if o.revocation_ack_s is not None and o.revocation_ack_s > horizon_s:
            raise ValueError("revocation ACK beyond horizon")
        if o.outcome == "expired" and (r.deadline_s is None or o.terminal_s < r.deadline_s):
            raise ValueError("expiry requires an elapsed deadline")
        raw.append({"request": asdict(r), "observation": asdict(o),
                    "censored_deadline_missed": o.outcome == "censored" and r.deadline_s is not None and r.deadline_s <= horizon_s})
    workload = [asdict(r) for r, _ in pairs]
    record = {"horizon_s": horizon_s, "observations": raw}
    report = {
        "format": "atmem-memory-fabric-protocol-report", "schema_version": 1,
        "measurement_kind": "synthetic_protocol_observations",
        "claim": "Validates supplied observations only; no runtime or authority proof.",
        "comparative_performance_valid": False,
        "goodput_scope": "observed completions within [0, horizon_s], not eventual outcomes",
        "deadline_convention": "completion strictly before deadline",
        "provenance": asdict(provenance), "horizon_s": horizon_s,
        "workload_sha256": sha256(json.dumps(workload, sort_keys=True, allow_nan=False).encode()).hexdigest(),
        "record_sha256": sha256(json.dumps(record, sort_keys=True, allow_nan=False).encode()).hexdigest(),
        "percentile_method": "nearest_rank", "all": _summary(pairs, horizon_s),
        "lanes": {lane: _summary([(r, o) for r, o in pairs if r.lane == lane], horizon_s) for lane in LANES},
        "observations": raw,
    }
    # Reject overflow in derived metrics, rather than emitting non-standard JSON.
    json.dumps(report, allow_nan=False)
    return report
