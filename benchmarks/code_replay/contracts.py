"""Closed metadata-only replay manifests. Validation is not authorization.

Operational text belongs in AtMem's protected evidence service, not these JSON
manifests. Artifact references bind bytes but do not establish their truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any, ClassVar
from urllib.parse import urlsplit


ARMS = ("A", "B", "C", "D")
SCHEDULE = (("A", "B", "C", "D"), ("B", "C", "D", "A"), ("C", "D", "A", "B"))
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
STAGES = frozenset({"setup", "index", "update", "capture", "formation", "retrieval", "delivery", "solver", "grading"})


def closed(value: Any, fields: set[str], name: str) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise ValueError(f"{name}: fields do not match contract")
    return value


def identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name}: invalid opaque identifier")
    return value


def digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(f"{name}: expected lowercase SHA-256")
    return value


def commit(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _COMMIT.fullmatch(value):
        raise ValueError(f"{name}: expected full SHA-1 Git revision")
    return value


def integer(value: Any, name: str, *, minimum: int = 0, maximum: int = 10**15) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name}: invalid bounded integer")
    return value


def timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError(f"{name}: invalid timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name}: invalid timestamp") from exc
    if result.utcoffset() is None:
        raise ValueError(f"{name}: timezone required")
    return result


def sequence(value: Any, name: str, *, maximum: int, minimum: int = 0) -> list:
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise ValueError(f"{name}: invalid bounded list")
    return value


def ids(value: Any, name: str, *, maximum: int, minimum: int = 0) -> list:
    items = sequence(value, name, maximum=maximum, minimum=minimum)
    for item in items:
        identifier(item, name)
    if len(set(items)) != len(items):
        raise ValueError(f"{name}: duplicate identifiers")
    return items


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _not_finite(value: str) -> None:
    raise ValueError("non-finite JSON number")


def parse_json(raw: str) -> Any:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 2_000_000:
        raise ValueError("manifest exceeds byte budget")
    try:
        return json.loads(raw, object_pairs_hook=_no_duplicates, parse_constant=_not_finite)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid manifest JSON") from exc


@dataclass(frozen=True, slots=True)
class Manifest:
    """Canonical immutable bytes; callers cannot mutate the validated tree."""

    canonical_json: str
    format: ClassVar[str]

    def __post_init__(self) -> None:
        value = parse_json(self.canonical_json)
        self.validate(value)
        object.__setattr__(self, "canonical_json", json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))

    @classmethod
    def from_dict(cls, value: dict) -> Manifest:
        try:
            raw = json.dumps(value, allow_nan=False)
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("manifest is not finite JSON") from exc
        return cls(raw)

    @classmethod
    def from_json(cls, raw: str) -> Manifest:
        return cls(raw)

    def to_dict(self) -> dict:
        return json.loads(self.canonical_json)

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def envelope(cls, value: Any, fields: set[str]) -> dict:
        row = closed(value, fields | {"format"}, cls.format)
        if row["format"] != cls.format:
            raise ValueError("unsupported manifest format")
        return row

    @classmethod
    def validate(cls, value: Any) -> None:
        raise NotImplementedError


class TaskManifest(Manifest):
    format = "atmem-click-task-v1"

    @classmethod
    def validate(cls, value: Any) -> None:
        row = cls.envelope(value, {"task_id", "order", "parent_commit", "reference_commit", "issue_version_sha256",
                                  "requirements_sha256", "source_sha256", "environment_sha256", "grader_sha256",
                                  "baseline_policy_sha256", "license_ref", "requirements_at", "solution_cutoff",
                                  "parent_fails", "reference_passes"})
        identifier(row["task_id"], "task_id")
        identifier(row["license_ref"], "license_ref")
        integer(row["order"], "order", minimum=1, maximum=5)
        for name in ("parent_commit", "reference_commit"):
            commit(row[name], name)
        if row["parent_commit"] == row["reference_commit"]:
            raise ValueError("parent and reference must differ")
        for name in ("issue_version_sha256", "requirements_sha256", "source_sha256", "environment_sha256",
                     "grader_sha256", "baseline_policy_sha256"):
            digest(row[name], name)
        if timestamp(row["requirements_at"], "requirements_at") >= timestamp(row["solution_cutoff"], "solution_cutoff"):
            raise ValueError("requirements must predate solution cutoff")
        if row["parent_fails"] is not True or row["reference_passes"] is not True:
            raise ValueError("parent/reference grading qualification required")


def _budgets(value: Any, *, allow_zero_cost: bool = False) -> dict:
    row = closed(value, {"tokens", "tool_calls", "wall_seconds", "context_bytes", "cost_microusd"}, "budgets")
    for name, upper in (("tokens", 10_000_000), ("tool_calls", 10_000), ("wall_seconds", 86_400),
                        ("context_bytes", 1_000_000), ("cost_microusd", 10**12)):
        integer(row[name], name, minimum=0 if name == "cost_microusd" and allow_zero_cost else 1, maximum=upper)
    return row


class ProtocolManifest(Manifest):
    format = "atmem-click-protocol-v1"
    arms = ARMS
    repetitions = 3
    schedule = SCHEDULE
    allow_zero_cost = False

    @classmethod
    def validate(cls, value: Any) -> None:
        row = cls.envelope(value, {"protocol_id", "anchor_commit", "search_horizon", "tasks", "arms", "repetitions",
                                  "schedule", "versions", "configuration_sha256", "hardware_sha256", "budgets",
                                  "total_cost_microusd", "inference", "storage_profile", "analysis_sha256"})
        identifier(row["protocol_id"], "protocol_id")
        commit(row["anchor_commit"], "anchor_commit")
        if type(row["search_horizon"]) is not int or row["search_horizon"] != 100:
            raise ValueError("v1 search horizon must be 100")
        tasks = sequence(row["tasks"], "tasks", minimum=5, maximum=5)
        for task in tasks:
            TaskManifest.from_dict(task)
        if [t["order"] for t in tasks] != list(range(1, 6)) or len({t["task_id"] for t in tasks}) != 5:
            raise ValueError("tasks must have unique identities and chronological order")
        cutoffs = [timestamp(t["solution_cutoff"], "solution_cutoff") for t in tasks]
        # A branch may be authored earlier but merged later. V2 follows the
        # validated first-parent ledger, not overlapping branch author dates.
        if cls.format == ProtocolManifest.format and any(a >= b for a, b in zip(cutoffs, cutoffs[1:])):
            raise ValueError("task cutoffs must increase chronologically")
        if row["arms"] != list(cls.arms) or type(row["repetitions"]) is not int or row["repetitions"] != cls.repetitions:
            raise ValueError("protocol requires its frozen arms and repetitions")
        if row["schedule"] != [list(order) for order in cls.schedule]:
            raise ValueError("protocol requires its frozen schedule")
        versions = closed(row["versions"], {"atmem", "agent", "model", "extractor"}, "versions")
        for name, pin in versions.items():
            closed(pin, {"artifact_sha256", "configuration_sha256"}, name)
            digest(pin["artifact_sha256"], name)
            digest(pin["configuration_sha256"], name)
        for name in ("configuration_sha256", "hardware_sha256", "analysis_sha256"):
            digest(row[name], name)
        budget = _budgets(row["budgets"], allow_zero_cost=cls.allow_zero_cost)
        integer(row["total_cost_microusd"], "total_cost_microusd", minimum=budget["cost_microusd"], maximum=10**12)
        inference = closed(row["inference"], {"provider_id", "endpoint", "license_review_sha256", "egress_policy_sha256"}, "inference")
        identifier(inference["provider_id"], "provider_id")
        for name in ("license_review_sha256", "egress_policy_sha256"):
            digest(inference[name], name)
        endpoint = inference["endpoint"]
        if not isinstance(endpoint, str) or len(endpoint) > 2048:
            raise ValueError("inference endpoint invalid")
        try:
            parsed = urlsplit(endpoint)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("inference endpoint invalid") from exc
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or port not in (None, 443)):
            raise ValueError("inference endpoint must be credential-free HTTPS on port 443")
        profile = closed(row["storage_profile"], {"profile_id", "qualification_sha256"}, "storage_profile")
        identifier(profile["profile_id"], "profile_id")
        digest(profile["qualification_sha256"], "storage_profile")


class StructureExperienceProtocol(ProtocolManifest):
    """Distinct reduced pilot; never interprets a four-arm v1 as two-arm data."""
    format = "atmem-click-structure-experience-protocol-v2"
    arms = ("C", "D")
    repetitions = 2
    schedule = (("C", "D"), ("D", "C"))
    allow_zero_cost = True


class RunManifest(Manifest):
    format = "atmem-click-run-v1"
    arms = ARMS
    repetitions = 3
    allow_zero_cost = False

    @classmethod
    def validate(cls, value: Any) -> None:
        row = cls.envelope(value, {"run_id", "protocol_sha256", "task_id", "task_sha256", "arm", "repetition",
                                  "trajectory_id", "session_id", "lane_id", "source_sha256", "capability_sha256",
                                  "effective_configuration_sha256", "started_at", "budgets"})
        for name in ("run_id", "task_id", "trajectory_id", "session_id", "lane_id"):
            identifier(row[name], name)
        for name in ("protocol_sha256", "task_sha256", "source_sha256", "capability_sha256", "effective_configuration_sha256"):
            digest(row[name], name)
        if row["arm"] not in cls.arms:
            raise ValueError("unsupported arm")
        integer(row["repetition"], "repetition", minimum=1, maximum=cls.repetitions)
        timestamp(row["started_at"], "started_at")
        _budgets(row["budgets"], allow_zero_cost=cls.allow_zero_cost)

    def bind(self, protocol: ProtocolManifest) -> None:
        row, parent = self.to_dict(), protocol.to_dict()
        task = next((t for t in parent["tasks"] if t["task_id"] == row["task_id"]), None)
        if (row["protocol_sha256"] != protocol.sha256 or task is None
                or row["task_sha256"] != TaskManifest.from_dict(task).sha256
                or row["source_sha256"] != task["source_sha256"]):
            raise ValueError("run does not bind to protocol task/source")
        if any(row["budgets"][key] > parent["budgets"][key] for key in row["budgets"]):
            raise ValueError("run exceeds protocol budgets")
        if row["arm"] not in parent["arms"] or row["repetition"] > parent["repetitions"]:
            raise ValueError("run arm/repetition is outside protocol")


class StructureExperienceRun(RunManifest):
    format = "atmem-click-structure-experience-run-v2"
    arms = ("C", "D")
    repetitions = 2
    allow_zero_cost = True


_MEASURES = frozenset({"input_tokens", "output_tokens", "cached_tokens", "cost_microusd", "elapsed_ms",
                       "tool_calls", "file_reads", "searches", "context_bytes", "human_interventions", "peak_rss_bytes"})


class TrialResult(Manifest):
    format = "atmem-click-result-v1"

    @classmethod
    def validate(cls, value: Any) -> None:
        row = cls.envelope(value, {"run_sha256", "status", "reason_code", "ended_at", "checks_total", "checks_passed",
                                  "safety_violations", "exposure", "evidence_sha256", "context_sha256", "memory_ids",
                                  "measurements", "stage_ms", "price_source_ref"})
        for name in ("run_sha256", "evidence_sha256", "context_sha256"):
            digest(row[name], name)
        identifier(row["reason_code"], "reason_code")
        timestamp(row["ended_at"], "ended_at")
        if not isinstance(row["status"], str) or row["status"] not in {"passed", "failed", "infra_invalid", "blocked"}:
            raise ValueError("invalid terminal status")
        for name in ("checks_total", "checks_passed", "safety_violations"):
            integer(row[name], name)
        if row["checks_passed"] > row["checks_total"]:
            raise ValueError("passed check count exceeds total")
        if row["status"] == "passed" and (row["checks_total"] == 0 or row["checks_passed"] != row["checks_total"] or row["safety_violations"]):
            raise ValueError("passing result requires all checks and no safety violations")
        if not isinstance(row["exposure"], str) or row["exposure"] not in {"none", "prepared", "submitted", "host_acknowledged", "model_input_observed"}:
            raise ValueError("invalid exposure assurance")
        ids(row["memory_ids"], "memory_ids", maximum=128)
        measurements = closed(row["measurements"], set(_MEASURES), "measurements")
        for name, measure in measurements.items():
            if measure is not None:
                integer(measure, name)
        stages = row["stage_ms"]
        if type(stages) is not dict or not set(stages) <= STAGES:
            raise ValueError("unknown timing stage")
        for name, measure in stages.items():
            if measure is not None:
                integer(measure, name)
        if row["price_source_ref"] is not None:
            identifier(row["price_source_ref"], "price_source_ref")
        if measurements["cost_microusd"] is not None and row["price_source_ref"] is None:
            raise ValueError("observed cost requires price provenance")

    def bind(self, run: RunManifest) -> None:
        row, parent = self.to_dict(), run.to_dict()
        if row["run_sha256"] != run.sha256:
            raise ValueError("result does not bind to run")
        if timestamp(row["ended_at"], "ended_at") < timestamp(parent["started_at"], "started_at"):
            raise ValueError("result predates run")
