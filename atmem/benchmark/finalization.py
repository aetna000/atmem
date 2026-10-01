"""Fail-closed validation for paid benchmark finalization evidence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any, Mapping

from atmem.benchmark.contracts import canonical_digest


FORMAT = "atmem-benchmark-finalization-gate-v1"
_LONGMEM_READER_CONDITIONS = {
    "short_control": 3,
    "oracle_evidence": 3,
    "product_context": 3,
    "worst_budget_multimodal": 3,
}
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def probe_artifact_identity(
    probe: Mapping[str, Any], identity: Mapping[str, Any]
) -> str:
    """Digest the retained, content-free response evidence for one paid call."""
    fields = (
        "probe_id", "role", "condition", "status", "finish_reason",
        "content_sha256", "content_bytes", "answer_parse_ok", "usage",
        "cleanup_failed", "error", "retries", "latency_ms", "cost_usd",
    )
    return canonical_digest({
        "configuration_sha256": finalization_identity(identity),
        "probe": {name: probe.get(name) for name in fields},
    })


def finalization_identity(value: Mapping[str, Any]) -> str:
    """Bind evidence to every input that can change model finalization."""
    required = (
        "gate_type", "candidate_commit", "candidate_artifact_sha256",
        "checkpoint_sha256", "provider", "model",
        "model_revision", "processor_sha256", "prompt_sha256",
        "proxy_sha256", "concurrency", "input_budget", "output_budget",
        "sampling", "judge_provider", "judge_model", "judge_revision",
        "judge_prompt_sha256",
        "probe_set_sha256", "run_config_sha256", "cost_authorization_id",
        "runner_sha256", "grader_runtime", "agent_driver_target",
        "agent_driver_sha256",
    )
    identity = dict(value)
    missing = [name for name in required if identity.get(name) in (None, "")]
    if missing:
        raise ValueError("finalization identity is missing: " + ", ".join(missing))
    return canonical_digest({name: identity[name] for name in required})


def validate_finalization_gate(
    value: Mapping[str, Any], *, expected_identity: Mapping[str, Any],
    expected_gate_type: str | None = None,
) -> dict[str, Any]:
    """Accept only complete, usable, cost-accounted probe evidence."""
    gate = dict(value)
    if gate.get("format") != FORMAT:
        raise ValueError(f"finalization gate format must be {FORMAT}")
    gate_type = str(gate.get("gate_type") or "")
    if gate_type not in {"longmemeval", "dolphinbench"}:
        raise ValueError("finalization gate_type is invalid")
    if expected_gate_type is not None and gate_type != expected_gate_type:
        raise ValueError("finalization gate_type does not authorize this runner")
    identity = dict(gate.get("identity") or {})
    if identity.get("gate_type") != gate_type:
        raise ValueError("finalization identity gate_type does not match")
    digest = finalization_identity(identity)
    if gate.get("identity_sha256") != digest:
        raise ValueError("finalization identity digest does not match")
    if digest != finalization_identity(expected_identity):
        raise ValueError("finalization evidence belongs to another configuration")
    now = datetime.now(timezone.utc)
    try:
        created = datetime.fromisoformat(str(gate["created_at"]).replace("Z", "+00:00"))
        expires = datetime.fromisoformat(str(gate["expires_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("finalization gate timestamps are invalid") from exc
    if created.tzinfo is None or expires.tzinfo is None:
        raise ValueError("finalization gate timestamps require timezones")
    if (
        created > now or expires <= now or expires <= created
        or expires - created > timedelta(hours=24)
    ):
        raise ValueError("finalization gate is stale or not yet valid")
    if gate.get("status") != "passed" or gate.get("bypassed") is not False:
        raise ValueError("finalization gate did not pass without bypass")
    probes = list(gate.get("probes") or ())
    if not probes:
        raise ValueError("finalization probes are missing")
    counts: Counter[str] = Counter()
    judge_count = 0
    probe_ids: set[str] = set()
    for index, probe in enumerate(probes):
        if not isinstance(probe, dict):
            raise ValueError(f"finalization probe {index} is malformed")
        if probe.get("status") != "completed" or probe.get("finish_reason") != "stop":
            raise ValueError(f"finalization probe {index} did not finish")
        probe_id = str(probe.get("probe_id") or "")
        if not probe_id or probe_id in probe_ids:
            raise ValueError(f"finalization probe {index} identity is invalid")
        probe_ids.add(probe_id)
        if not _DIGEST.fullmatch(str(probe.get("content_sha256") or "")) or int(
            probe.get("content_bytes") or 0
        ) <= 0 or probe.get("answer_parse_ok") is not True:
            raise ValueError(f"finalization probe {index} has no final answer")
        usage = dict(probe.get("usage") or {})
        if int(usage.get("prompt_tokens") or 0) <= 0 or int(
            usage.get("completion_tokens") or 0
        ) <= 0:
            raise ValueError(f"finalization probe {index} lacks usage evidence")
        if not {"cleanup_failed", "error", "retries"} <= set(probe):
            raise ValueError(f"finalization probe {index} lacks explicit attempt evidence")
        if probe.get("cleanup_failed") or probe.get("error"):
            raise ValueError(f"finalization probe {index} reports failure")
        if int(probe.get("retries") or 0) != 0:
            raise ValueError(f"finalization probe {index} used retries")
        if probe.get("artifact_sha256") != probe_artifact_identity(probe, identity):
            raise ValueError(f"finalization probe {index} artifact binding is invalid")
        latency = float(probe.get("latency_ms") or 0)
        cost = float(probe.get("cost_usd") if probe.get("cost_usd") is not None else -1)
        if not math.isfinite(latency) or latency <= 0 or not math.isfinite(cost) or cost < 0:
            raise ValueError(f"finalization probe {index} lacks operational evidence")
        role = str(probe.get("role") or "reader")
        condition = str(probe.get("condition") or "")
        if role == "judge":
            judge_count += 1
        elif role == "reader":
            counts[condition] += 1
        else:
            raise ValueError(f"finalization probe {index} has an invalid role")
    if gate_type == "longmemeval":
        if counts != Counter(_LONGMEM_READER_CONDITIONS):
            raise ValueError("LongMemEval finalization lacks the frozen twelve reader probes")
        if judge_count != 3:
            raise ValueError("LongMemEval finalization requires three judge probes")
    elif counts != Counter({"official_agent": 3}) or judge_count != 3:
        raise ValueError("DolphinBench finalization requires three agent and grader probes")
    observed_probe_set = canonical_digest([
        {
            "probe_id": str(probe["probe_id"]),
            "role": str(probe.get("role") or "reader"),
            "condition": str(probe.get("condition") or ""),
        }
        for probe in probes
    ])
    if identity.get("probe_set_sha256") != observed_probe_set:
        raise ValueError("finalization probe set differs from the bound identity")
    authorization = dict(gate.get("cost_authorization") or {})
    cap = float(authorization.get("cap_usd") or 0)
    reserved_value = authorization.get("reserved_usd")
    spent_value = authorization.get("spent_usd")
    reserved = float(-1 if reserved_value is None else reserved_value)
    spent = float(-1 if spent_value is None else spent_value)
    if (
        not authorization.get("authorization_id")
        or authorization.get("authorization_id") != identity.get("cost_authorization_id")
        or not all(math.isfinite(value) for value in (cap, reserved, spent))
        or cap <= 0 or reserved < 0 or spent < 0
        or reserved > cap or spent > reserved
    ):
        raise ValueError("finalization cost authorization is invalid")
    probe_cost = sum(float(probe["cost_usd"]) for probe in probes)
    if probe_cost > spent + 1e-9:
        raise ValueError("finalization probe costs exceed reconciled spend")
    return gate
