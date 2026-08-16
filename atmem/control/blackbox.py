"""Tamper-evident, content-minimizing flight records for agent runs.

The black box records host-observable boundaries.  It deliberately stores
digests and bounded metadata rather than prompts, responses, tool parameters,
or tool results.  A verified flight proves that the retained timeline was not
rewritten and that observed tool requests reached terminal hook events; it does
not prove an external business outcome unless a system-of-record verifier is
also present.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import json
import re
from typing import Any, Mapping

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.store.sqlite import utc_now


EVENT_FORMAT = "atmem-agent-blackbox-event-v2"
REPORT_FORMAT = "atmem-agent-blackbox-report-v2"
EVIDENCE_KIND = "agent_blackbox"

_EVENT_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
_DIGEST_KEYS = {
    "prompt_sha256",
    "system_sha256",
    "history_sha256",
    "context_sha256",
    "params_sha256",
    "result_sha256",
    "response_sha256",
    "messages_sha256",
    "assistant_visible_text_sha256",
    "model_output_bundle_sha256",
    "turn_messages_sha256",
    "context_block_sha256",
    "context_envelope_sha256",
    "context_receipt_sha256",
    "query_sha256",
}
_TEXT_KEYS = {
    "provider",
    "model",
    "resolved_ref",
    "harness_id",
    "reasoning_effort",
    "mode",
    "exposure_id",
    "tool_name",
    "tool_kind",
    "outcome",
    "error_category",
    "failure_kind",
    "reason",
    "disposition",
    "digest_profile",
    "response_digest_profile",
    "context_location",
    "tool_canonical_name",
}
_COUNT_KEYS = {
    "prompt_chars",
    "system_chars",
    "history_count",
    "images_count",
    "tools_count",
    "context_chars",
    "response_chars",
    "response_count",
    "messages_count",
    "duration_ms",
    "request_payload_bytes",
    "response_stream_bytes",
    "time_to_first_byte_ms",
}
_BOOL_KEYS = {"fast_mode", "cancelled", "success"}
_LIST_KEYS = {
    "candidate_ids",
    "param_keys",
    "derived_path_sha256",
    "context_component_event_ids",
}

_CORRELATION_KEYS = (
    "turn_id",
    "retrieval_id",
    "context_event_id",
    "context_receipt_id",
    "outcome_id",
)


def normalize_event(
    *,
    migration_id: str,
    host: str,
    event_type: str,
    run_id: str,
    session_id: str | None,
    tool_call_id: str | None,
    payload: Mapping[str, Any] | None,
    turn_id: str | None = None,
    retrieval_id: str | None = None,
    context_event_id: str | None = None,
    context_receipt_id: str | None = None,
    outcome_id: str | None = None,
) -> dict[str, Any]:
    """Validate a host event and return the canonical stored envelope."""

    event_name = event_type.strip()
    if not _EVENT_TYPE.fullmatch(event_name):
        raise ValueError("blackbox event_type is invalid")
    run = run_id.strip()
    if not run or len(run) > 512:
        raise ValueError("blackbox run_id is required and must be at most 512 characters")
    return {
        "format": EVENT_FORMAT,
        "migration_id": migration_id,
        "host": host,
        "event_type": event_name,
        "run_id": run,
        "session_id": _bounded_optional(session_id, 512),
        "tool_call_id": _bounded_optional(tool_call_id, 512),
        "turn_id": _bounded_optional(turn_id, 512),
        "retrieval_id": _bounded_optional(retrieval_id, 512),
        "context_event_id": _bounded_optional(context_event_id, 512),
        "context_receipt_id": _bounded_optional(context_receipt_id, 512),
        "outcome_id": _bounded_optional(outcome_id, 512),
        "recorded_at": utc_now(),
        "payload": _normalize_payload(payload or {}),
        "content_storage": "digests-and-bounded-metadata-only",
    }


def flight_runs(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        body = entry.get("body") or {}
        run_id = str(body.get("run_id") or "")
        if run_id:
            grouped[run_id].append(entry)
    rows: list[dict[str, Any]] = []
    for run_id, values in grouped.items():
        values.sort(key=lambda item: int(item.get("sequence") or 0))
        bodies = [item["body"] for item in values]
        event_types = [str(body.get("event_type") or "") for body in bodies]
        terminal_body = next(
            (body for body in reversed(bodies) if body.get("event_type") == "turn.ended"),
            None,
        )
        context_body = next(
            (
                body
                for body in reversed(bodies)
                if body.get("event_type")
                in {"context.disposition", "context.injected", "context.prepared"}
            ),
            None,
        )
        model_body = next(
            (body for body in reversed(bodies) if body.get("event_type") == "model.output"),
            None,
        )
        rows.append(
            {
                "run_id": run_id,
                "session_id": next(
                    (body.get("session_id") for body in bodies if body.get("session_id")),
                    None,
                ),
                "started_at": bodies[0].get("recorded_at"),
                "ended_at": bodies[-1].get("recorded_at"),
                "events": len(values),
                "tool_requests": event_types.count("tool.requested"),
                "tool_completions": event_types.count("tool.completed"),
                "terminal": "turn.ended" in event_types,
                "success": (terminal_body or {}).get("payload", {}).get("success"),
                "cancelled": (terminal_body or {}).get("payload", {}).get("cancelled"),
                "context_disposition": _context_disposition(context_body),
                "provider": (model_body or {}).get("payload", {}).get("provider"),
                "model": (model_body or {}).get("payload", {}).get("model"),
                "last_sequence": int(values[-1].get("sequence") or 0),
            }
        )
    rows.sort(key=lambda row: (str(row["ended_at"] or ""), row["run_id"]), reverse=True)
    return rows


def verify_flight(
    *,
    run_id: str,
    entries: list[dict[str, Any]],
    chain: Mapping[str, Any],
    model_baseline: tuple[str, str] | None = None,
) -> dict[str, Any]:
    selected = [
        entry
        for entry in entries
        if str((entry.get("body") or {}).get("run_id") or "") == run_id
    ]
    selected.sort(key=lambda item: int(item.get("sequence") or 0))
    if not selected:
        raise ValueError(f"no blackbox flight found for run {run_id}")

    requested: dict[str, list[dict[str, Any]]] = defaultdict(list)
    completed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    uncorrelated_requests = 0
    uncorrelated_completions = 0
    tool_errors: list[dict[str, Any]] = []
    for entry in selected:
        body = entry["body"]
        event_type = str(body.get("event_type") or "")
        call_id = str(body.get("tool_call_id") or "")
        if event_type == "tool.requested":
            if call_id:
                requested[call_id].append(entry)
            else:
                uncorrelated_requests += 1
        elif event_type == "tool.completed":
            if call_id:
                completed[call_id].append(entry)
            else:
                uncorrelated_completions += 1
            payload = body.get("payload") or {}
            if payload.get("outcome") == "error":
                tool_errors.append(
                    {
                        "tool_call_id": call_id or None,
                        "tool_name": payload.get("tool_name"),
                        "error_category": payload.get("error_category"),
                    }
                )

    missing_completions = sorted(set(requested) - set(completed))
    orphan_completions = sorted(set(completed) - set(requested))
    duplicate_requests, conflicting_requests = _duplicate_tool_events(
        requested, request=True
    )
    duplicate_completions, conflicting_completions = _duplicate_tool_events(
        completed, request=False
    )
    coalesced_wrapper_calls = _coalesced_wrapper_calls(requested, completed)
    coalesced_call_ids = {
        str(item["tool_call_id"]) for item in coalesced_wrapper_calls
    }
    # OpenClaw can expose both its namespaced wrapper and the canonical tool
    # hook for one logical call. Preserve both raw observations in the
    # timeline, but do not treat their different wrapper result envelopes as
    # conflicting tool executions.
    conflicting_requests = [
        call_id for call_id in conflicting_requests if call_id not in coalesced_call_ids
    ]
    conflicting_completions = [
        call_id
        for call_id in conflicting_completions
        if call_id not in coalesced_call_ids
    ]
    event_types = [str(entry["body"].get("event_type") or "") for entry in selected]
    turn_input = "turn.input" in event_types
    terminal = "turn.ended" in event_types
    model_input = "model.input" in event_types
    model_output = "model.output" in event_types
    context_entry = next(
        (
            entry
            for entry in reversed(selected)
            if entry["body"].get("event_type")
            in {"context.disposition", "context.injected", "context.prepared"}
        ),
        None,
    )
    context_disposition = _context_disposition(
        context_entry["body"] if context_entry else None
    )
    valid_dispositions = {
        "injected",
        "no_relevant_memory",
        "withheld_by_policy",
        "recall_failed",
        "not_applicable",
    }
    context_observed = context_disposition in valid_dispositions
    context_payload = (context_entry or {}).get("body", {}).get("payload", {})
    context_digest_bound = bool(
        context_payload.get("context_envelope_sha256")
        or context_payload.get("context_block_sha256")
        or context_payload.get("context_sha256")
    )
    context_receipt_bound = bool(
        (context_entry or {}).get("body", {}).get("context_receipt_id")
        or context_payload.get("context_receipt_sha256")
    )
    model_output_entries = [
        entry for entry in selected if entry["body"].get("event_type") == "model.output"
    ]
    response_bound = any(
        (entry["body"].get("payload") or {}).get("assistant_visible_text_sha256")
        or (entry["body"].get("payload") or {}).get("response_sha256")
        for entry in model_output_entries
    )
    response_digest_consistent = all(
        not payload.get("assistant_visible_text_sha256")
        or not payload.get("response_sha256")
        or payload["assistant_visible_text_sha256"] == payload["response_sha256"]
        for payload in [
            entry["body"].get("payload") or {} for entry in model_output_entries
        ]
    )
    terminal_entry = next(
        (
            entry
            for entry in reversed(selected)
            if entry["body"].get("event_type") == "turn.ended"
        ),
        None,
    )
    terminal_payload = (terminal_entry or {}).get("body", {}).get("payload", {})
    current_model_payload = (
        model_output_entries[-1]["body"].get("payload") or {}
        if model_output_entries
        else {}
    )
    baseline_model = model_baseline or recent_model_baseline(entries)
    current_model = (
        str(current_model_payload.get("provider") or ""),
        str(current_model_payload.get("model") or ""),
    )
    model_changed = bool(
        baseline_model and any(current_model) and current_model != baseline_model
    )
    cancelled = bool(terminal_payload.get("cancelled"))
    succeeded = terminal_payload.get("success") is True and not cancelled
    failed = terminal and not succeeded and not cancelled
    tool_closure = not any(
        (
            missing_completions,
            orphan_completions,
            uncorrelated_requests,
            uncorrelated_completions,
            conflicting_requests,
            conflicting_completions,
        )
    )
    required_evidence = bool(
        turn_input
        and context_observed
        and model_input
        and model_output
        and response_bound
        and response_digest_consistent
        and terminal
        and tool_closure
    )
    structurally_complete = bool(chain.get("valid") and required_evidence)

    component_status = {
        "integrity": "covered" if chain.get("valid") else "failed",
        "lifecycle": (
            "cancelled"
            if cancelled
            else "failed"
            if failed
            else "covered"
            if turn_input and terminal
            else "missing"
        ),
        "context": (
            "missing"
            if not context_observed
            else "warning"
            if context_disposition in {"recall_failed", "withheld_by_policy"}
            or (context_disposition == "injected" and not context_digest_bound)
            else "covered"
        ),
        "model": "covered" if model_input and model_output else "missing",
        "tools": "covered" if tool_closure else "failed",
        "response": (
            "failed"
            if not response_digest_consistent
            else "covered"
            if response_bound
            else "missing"
        ),
    }
    overall_status = (
        "cancelled"
        if cancelled
        else "failed"
        if any(value == "failed" for value in component_status.values())
        else "incomplete"
        if any(value == "missing" for value in component_status.values())
        else "warning"
        if any(value == "warning" for value in component_status.values())
        else "covered"
    )
    if not chain.get("valid"):
        verdict = "tampered_or_invalid_chain"
    elif cancelled:
        verdict = "cancelled"
    elif failed:
        verdict = "failed"
    elif not structurally_complete:
        verdict = "incomplete_evidence"
    elif tool_errors:
        verdict = "completed_with_tool_errors"
    else:
        verdict = "completed_successfully"

    timeline = [
        {
            "sequence": int(entry.get("sequence") or 0),
            "entry_sha256": entry.get("entry_sha256"),
            **deepcopy(entry["body"]),
        }
        for entry in selected
    ]
    event_formats = sorted(
        {
            str(entry["body"].get("format") or "unknown")
            for entry in selected
        }
    )
    current_contract_observed = any(
        entry["body"].get("event_type") == "context.disposition"
        or (
            entry["body"].get("event_type") == "model.output"
            and (entry["body"].get("payload") or {}).get(
                "assistant_visible_text_sha256"
            )
        )
        for entry in selected
    )
    legacy_flight = not current_contract_observed
    report_body = {
        "format": REPORT_FORMAT,
        "generated_at": utc_now(),
        "run_id": run_id,
        "session_id": next(
            (
                entry["body"].get("session_id")
                for entry in selected
                if entry["body"].get("session_id")
            ),
            None,
        ),
        "verdict": verdict,
        "timeline_chain_valid": bool(chain.get("valid")),
        "structurally_complete": structurally_complete,
        "coverage": {
            "turn_input_observed": turn_input,
            "context_disposition_observed": context_observed,
            "context_digest_bound": context_digest_bound,
            "context_receipt_bound": context_receipt_bound,
            "model_input_observed": model_input,
            "model_output_observed": model_output,
            "response_digest_bound": bool(response_bound),
            "response_digest_consistent": response_digest_consistent,
            "terminal_event_observed": terminal,
        },
        "coverage_matrix": {
            "overall_status": overall_status,
            "components": component_status,
        },
        "lifecycle": {
            "success": succeeded,
            "failed": failed,
            "cancelled": cancelled,
            "failure_kind": terminal_payload.get("failure_kind"),
            "reason": terminal_payload.get("reason"),
        },
        "context": {
            "disposition": context_disposition,
            "digest_bound": context_digest_bound,
            "receipt_bound": context_receipt_bound,
        },
        "model": {
            "provider": current_model[0] or None,
            "model": current_model[1] or None,
            "baseline_provider": baseline_model[0] if baseline_model else None,
            "baseline_model": baseline_model[1] if baseline_model else None,
            "changed_from_recent_baseline": model_changed,
        },
        "correlation": _correlation_summary(selected),
        "tools": {
            "requested": len(requested) + uncorrelated_requests,
            "completed": len(completed) + uncorrelated_completions,
            "request_observations": sum(map(len, requested.values()))
            + uncorrelated_requests,
            "completion_observations": sum(map(len, completed.values()))
            + uncorrelated_completions,
            "errors": tool_errors,
            "missing_completions": missing_completions,
            "orphan_completions": orphan_completions,
            "uncorrelated_requests": uncorrelated_requests,
            "uncorrelated_completions": uncorrelated_completions,
            "duplicate_requests": duplicate_requests,
            "duplicate_completions": duplicate_completions,
            "conflicting_requests": conflicting_requests,
            "conflicting_completions": conflicting_completions,
            "coalesced_wrapper_calls": coalesced_wrapper_calls,
        },
        "events": len(selected),
        "first_sequence": int(selected[0].get("sequence") or 0),
        "last_sequence": int(selected[-1].get("sequence") or 0),
        "timeline": timeline,
        "compatibility": {
            "event_formats": event_formats,
            "current_event_format": EVENT_FORMAT,
            "current_contract_observed": current_contract_observed,
            "legacy_flight": legacy_flight,
        },
        "claim_boundary": (
            "This report verifies retained timeline integrity and observed hook closure. "
            "It does not prove that an external real-world outcome occurred, and it does "
            "not semantically validate claims in the agent response."
        ),
        "raw_content_stored": False,
    }
    report_body["attention_points"] = flight_attention(report_body)
    return {
        **report_body,
        "report_sha256": sha256_hex(canonical_json(report_body)),
    }


def format_flight_report(report: Mapping[str, Any]) -> str:
    coverage = report.get("coverage") or {}
    matrix = report.get("coverage_matrix") or {}
    tools = report.get("tools") or {}
    lines = [
        "AtMem Agent Black Box",
        "",
        f"Run: {report.get('run_id')}",
        f"Verdict: {str(report.get('verdict') or '').replace('_', ' ')}",
        f"Evidence chain: {'VALID' if report.get('timeline_chain_valid') else 'INVALID'}",
        f"Coverage: {str(matrix.get('overall_status') or 'unknown').upper()}",
        f"Events: {report.get('events', 0)}",
        f"Tool requests: {tools.get('requested', 0)}",
        f"Tool completions: {tools.get('completed', 0)}",
        f"Tool errors: {len(tools.get('errors') or [])}",
        f"Context disposition: {(report.get('context') or {}).get('disposition') or 'missing'}",
        f"Model input observed: {'yes' if coverage.get('model_input_observed') else 'no'}",
        f"Model output observed: {'yes' if coverage.get('model_output_observed') else 'no'}",
        f"Final response digest bound: {'yes' if coverage.get('response_digest_bound') else 'no'}",
        "",
        "Timeline",
    ]
    for event in report.get("timeline") or []:
        payload = event.get("payload") or {}
        detail = payload.get("tool_name") or payload.get("model") or ""
        outcome = payload.get("outcome") or ""
        suffix = " · ".join(value for value in (str(detail), str(outcome)) if value)
        lines.append(
            f"{event.get('sequence'):>5}  {event.get('recorded_at')}  "
            f"{event.get('event_type')}" + (f"  {suffix}" if suffix else "")
        )
    lines.extend(["", str(report.get("claim_boundary") or "")])
    return "\n".join(lines) + "\n"


def flight_attention(report: Mapping[str, Any]) -> list[dict[str, str]]:
    """Turn a verified flight into a small, operator-facing attention queue."""

    points: list[dict[str, str]] = []

    def add(
        check: str,
        severity: str,
        code: str,
        title: str,
        detail: str,
        action: str,
    ) -> None:
        points.append(
            {
                "check": check,
                "severity": severity,
                "code": code,
                "title": title,
                "detail": detail,
                "action": action,
            }
        )

    if not report.get("timeline_chain_valid"):
        add(
            "completion",
            "critical",
            "evidence_chain_invalid",
            "Flight evidence failed integrity verification",
            "The retained timeline may be incomplete or modified.",
            "Inspect the evidence store before trusting this run.",
        )

    legacy_flight = bool((report.get("compatibility") or {}).get("legacy_flight"))
    if legacy_flight:
        add(
            "completion",
            "medium",
            "legacy_evidence_contract",
            "Older flights need a bridge refresh",
            "These flights predate the current evidence contract, so their apparent context and tool gaps are not reliable incidents.",
            "Upgrade AtMem and its OpenClaw bridge, restart the gateway, then run one fresh test flight.",
        )

    verdict = str(report.get("verdict") or "")
    components = (report.get("coverage_matrix") or {}).get("components") or {}
    if verdict == "failed":
        lifecycle = report.get("lifecycle") or {}
        reason = lifecycle.get("reason") or lifecycle.get("failure_kind")
        add(
            "completion",
            "high",
            "flight_failed",
            "Agent flight failed",
            str(reason or "The turn ended without a successful result."),
            "Inspect the last reliable event and retry only when the cause is understood.",
        )
    elif verdict == "incomplete_evidence" and not legacy_flight:
        missing = [
            name for name, status in components.items() if status in {"missing", "failed"}
        ]
        # A tool-only closure problem gets one precise tool card below. A
        # second generic "flight incomplete" card adds noise without another
        # action for the operator.
        if missing != ["tools"]:
            add(
                "completion",
                "high",
                "flight_incomplete",
                "Flight evidence is incomplete",
                "AtMem could not verify: "
                + ", ".join(missing or ["an unknown runtime boundary"])
                + ".",
                "Open the timeline and inspect the first missing boundary named above.",
            )

    tools = report.get("tools") or {}
    tool_gaps = sum(
        len(tools.get(name) or [])
        for name in (
            "missing_completions",
            "orphan_completions",
            "conflicting_requests",
            "conflicting_completions",
        )
    ) + int(tools.get("uncorrelated_requests") or 0) + int(
        tools.get("uncorrelated_completions") or 0
    )
    if tool_gaps and not legacy_flight:
        add(
            "tools",
            "high",
            "tool_lifecycle_mismatch",
            "AtMem could not prove one or more tool calls closed correctly",
            _tool_lifecycle_detail(report),
            "Open the named call below and compare its request with its completion. Acknowledge it only after deciding whether this was an agent failure or an observation gap.",
        )
    tool_errors = tools.get("errors") or []
    if tool_errors:
        names = sorted(
            {
                str(item.get("tool_name") or "unknown tool")
                for item in tool_errors
                if isinstance(item, Mapping)
            }
        )
        add(
            "tools",
            "medium",
            "tool_errors",
            "A tool returned an error",
            f"{len(tool_errors)} error(s): " + ", ".join(names[:3]),
            "Inspect the tool error category, credentials, and input assumptions.",
        )

    coverage = report.get("coverage") or {}
    context = report.get("context") or {}
    disposition = str(context.get("disposition") or "")
    if disposition == "recall_failed":
        add(
            "context_model",
            "medium",
            "memory_recall_failed",
            "Memory recall failed",
            "The model continued without the memory context AtMem attempted to prepare.",
            "Check AtMem availability and the context-disposition event.",
        )
    elif not coverage.get("context_disposition_observed") and not legacy_flight:
        add(
            "context_model",
            "high",
            "context_unknown",
            "Memory context is unknown",
            "No event explains what memory reached the model.",
            "Inspect the prompt hook and require one context disposition per turn.",
        )
    elif disposition == "injected" and not context.get("receipt_bound"):
        add(
            "context_model",
            "medium",
            "context_receipt_missing",
            "Injected memory has no receipt correlation",
            "The context digest exists, but it is not linked to a context receipt.",
            "Inspect the memory hook correlation envelope.",
        )
    if coverage.get("response_digest_bound") and not coverage.get(
        "response_digest_consistent", True
    ):
        add(
            "context_model",
            "high",
            "response_digest_mismatch",
            "Response fingerprints disagree",
            "The model output contains inconsistent visible-response digests.",
            "Inspect response transformation and hook ordering.",
        )
    model = report.get("model") or {}
    if model.get("changed_from_recent_baseline"):
        actual = " / ".join(
            str(value) for value in (model.get("provider"), model.get("model")) if value
        )
        expected = " / ".join(
            str(value)
            for value in (model.get("baseline_provider"), model.get("baseline_model"))
            if value
        )
        add(
            "context_model",
            "medium",
            "model_provider_changed",
            "Model or provider changed",
            f"Observed {actual}; recent baseline is {expected}.",
            "Confirm that this routing change was intentional.",
        )
    return points


def recent_model_baseline(
    entries: list[dict[str, Any]],
) -> tuple[str, str] | None:
    signatures = [
        (
            str((entry["body"].get("payload") or {}).get("provider") or ""),
            str((entry["body"].get("payload") or {}).get("model") or ""),
        )
        for entry in entries
        if entry.get("body", {}).get("event_type") == "model.output"
    ]
    counts = Counter(signature for signature in signatures if any(signature))
    ranked = counts.most_common(2)
    if (
        ranked
        and ranked[0][1] >= 2
        and (len(ranked) == 1 or ranked[0][1] > ranked[1][1])
    ):
        return ranked[0][0]
    return None


def _context_disposition(body: Mapping[str, Any] | None) -> str | None:
    if not body:
        return None
    payload = body.get("payload") or {}
    explicit = str(payload.get("disposition") or "").strip()
    if explicit:
        return explicit
    event_type = body.get("event_type")
    if event_type == "context.injected":
        return "injected"
    if event_type == "context.prepared":
        return (
            "withheld_by_policy"
            if payload.get("mode") == "shadow"
            else "no_relevant_memory"
        )
    return None


def _duplicate_tool_events(
    grouped: Mapping[str, list[dict[str, Any]]], *, request: bool
) -> tuple[list[str], list[str]]:
    duplicates: list[str] = []
    conflicts: list[str] = []
    for call_id, entries in grouped.items():
        if len(entries) < 2:
            continue
        duplicates.append(call_id)
        signatures = set()
        for entry in entries:
            payload = entry["body"].get("payload") or {}
            tool_name = payload.get("tool_canonical_name") or payload.get("tool_name")
            signatures.add(
                (tool_name, payload.get("params_sha256"))
                if request
                else (tool_name, payload.get("result_sha256"), payload.get("outcome"))
            )
        if len(signatures) > 1:
            conflicts.append(call_id)
    return sorted(duplicates), sorted(conflicts)


def _coalesced_wrapper_calls(
    requested: Mapping[str, list[dict[str, Any]]],
    completed: Mapping[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Recognize one logical call observed at wrapper and canonical hooks.

    Result envelopes may legitimately differ between those hook layers, so a
    digest mismatch alone is not a conflicting completion. This exception is
    intentionally narrow: both sides must expose the same canonical tool,
    include the canonical name among multiple raw names, agree on request
    parameters, and agree on the terminal outcome.
    """

    coalesced: list[dict[str, Any]] = []
    for call_id in sorted(set(requested) & set(completed)):
        request_entries = requested[call_id]
        completion_entries = completed[call_id]
        if len(request_entries) < 2 or len(completion_entries) < 2:
            continue

        request_payloads = [entry["body"].get("payload") or {} for entry in request_entries]
        completion_payloads = [
            entry["body"].get("payload") or {} for entry in completion_entries
        ]
        canonical_names = {
            str(payload.get("tool_canonical_name") or "")
            for payload in [*request_payloads, *completion_payloads]
            if payload.get("tool_canonical_name")
        }
        if len(canonical_names) != 1:
            continue
        canonical_name = next(iter(canonical_names))
        request_names = {
            str(payload.get("tool_name") or canonical_name)
            for payload in request_payloads
        }
        completion_names = {
            str(payload.get("tool_name") or canonical_name)
            for payload in completion_payloads
        }
        if (
            len(request_names) < 2
            or len(completion_names) < 2
            or canonical_name not in request_names
            or canonical_name not in completion_names
        ):
            continue
        if len({payload.get("params_sha256") for payload in request_payloads}) > 1:
            continue
        outcomes = {
            str(payload.get("outcome") or "") for payload in completion_payloads
        }
        if len(outcomes) > 1:
            continue
        coalesced.append(
            {
                "tool_call_id": call_id,
                "tool_name": canonical_name,
                "observed_names": sorted(request_names | completion_names),
                "request_observations": len(request_entries),
                "completion_observations": len(completion_entries),
                "outcome": next(iter(outcomes)) or None,
            }
        )
    return coalesced


def _tool_lifecycle_detail(report: Mapping[str, Any]) -> str:
    tools = report.get("tools") or {}
    timeline = report.get("timeline") or []
    by_call: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in timeline:
        call_id = str(event.get("tool_call_id") or "")
        if call_id:
            by_call[call_id].append(event)

    details: list[str] = []
    for call_id in tools.get("missing_completions") or []:
        events = by_call.get(str(call_id), [])
        request = next(
            (event for event in events if event.get("event_type") == "tool.requested"),
            {},
        )
        payload = request.get("payload") or {}
        name = payload.get("tool_canonical_name") or payload.get("tool_name") or "Unknown tool"
        details.append(
            f"{name} (call {call_id}) was requested at event "
            f"{request.get('sequence') or 'unknown'}, but no completion was observed before the turn ended."
        )
    for call_id in tools.get("orphan_completions") or []:
        events = by_call.get(str(call_id), [])
        completion = next(
            (event for event in events if event.get("event_type") == "tool.completed"),
            {},
        )
        payload = completion.get("payload") or {}
        name = payload.get("tool_canonical_name") or payload.get("tool_name") or "Unknown tool"
        details.append(
            f"{name} (call {call_id}) completed at event "
            f"{completion.get('sequence') or 'unknown'}, but AtMem never observed its request."
        )
    conflicting = list(
        dict.fromkeys(
            [
                *(tools.get("conflicting_requests") or []),
                *(tools.get("conflicting_completions") or []),
            ]
        )
    )
    for call_id in conflicting:
        events = by_call.get(str(call_id), [])
        names = sorted(
            {
                str(
                    (event.get("payload") or {}).get("tool_canonical_name")
                    or (event.get("payload") or {}).get("tool_name")
                    or "Unknown tool"
                )
                for event in events
            }
        )
        sequences = [str(event.get("sequence")) for event in events if event.get("sequence")]
        details.append(
            f"{' / '.join(names)} (call {call_id}) has incompatible duplicate observations"
            + (f" at events {', '.join(sequences)}." if sequences else ".")
        )
    if tools.get("uncorrelated_requests"):
        details.append(
            f"{tools['uncorrelated_requests']} tool request observation(s) had no call ID."
        )
    if tools.get("uncorrelated_completions"):
        details.append(
            f"{tools['uncorrelated_completions']} tool completion observation(s) had no call ID."
        )
    return " ".join(details[:4]) or "The retained tool events do not form a complete request/completion pair."


def _correlation_summary(entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    names = {
        "session_ids": "session_id",
        "turn_ids": "turn_id",
        "retrieval_ids": "retrieval_id",
        "context_event_ids": "context_event_id",
        "context_receipt_ids": "context_receipt_id",
        "outcome_ids": "outcome_id",
    }
    return {
        plural: sorted(
            {
                str(entry["body"].get(singular))
                for entry in entries
                if entry["body"].get(singular)
            }
        )
        for plural, singular in names.items()
    }


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    unknown = sorted(
        set(payload)
        - _DIGEST_KEYS
        - _TEXT_KEYS
        - _COUNT_KEYS
        - _BOOL_KEYS
        - _LIST_KEYS
        - {"usage"}
    )
    if unknown:
        raise ValueError(f"unsupported blackbox payload field(s): {', '.join(unknown)}")
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if key in _DIGEST_KEYS:
            text = str(value).lower()
            if not re.fullmatch(r"[0-9a-f]{64}", text):
                raise ValueError(f"{key} must be a SHA-256 digest")
            normalized[key] = text
        elif key in _TEXT_KEYS:
            normalized[key] = str(value)[:512]
        elif key in _COUNT_KEYS:
            normalized[key] = max(0, int(value))
        elif key in _BOOL_KEYS:
            normalized[key] = bool(value)
        elif key in _LIST_KEYS:
            if not isinstance(value, list):
                raise ValueError(f"{key} must be an array")
            normalized[key] = [str(item)[:1024] for item in value[:100]]
        elif key == "usage":
            if not isinstance(value, Mapping):
                raise ValueError("usage must be an object")
            normalized[key] = {
                name: max(0, int(amount))
                for name, amount in value.items()
                if name in {"input", "output", "cacheRead", "cacheWrite", "total"}
                and amount is not None
            }
    return normalized


def _bounded_optional(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None
