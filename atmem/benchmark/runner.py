"""Isolated AtMem benchmark execution and release-gate scoring."""

from __future__ import annotations

from importlib import metadata, resources
import hashlib
import json
import math
from pathlib import Path
import platform
import tempfile
import time
from typing import Any

from atmem import Memory
from atmem.benchmark.contracts import (
    REPORT_FORMAT,
    SCORING_FORMAT,
    canonical_digest,
    load_dataset,
    metric,
    read_json,
    stable_quality_payload,
    validate_report,
)
from atmem.benchmark.profiles import resolve_profile
from atmem.contracts import AuthorityScope, ContextRequest, RecallRequest


def data_path(name: str) -> Path:
    return Path(str(resources.files("atmem.benchmark").joinpath("data", name)))


def run_benchmark(
    *,
    profile_name: str = "deterministic",
    dataset_path: str | Path | None = None,
    thresholds_path: str | Path | None = None,
) -> dict[str, Any]:
    dataset = load_dataset(dataset_path or data_path("deterministic-v1.json"))
    thresholds_doc = read_json(thresholds_path or data_path("thresholds-v1.json"))
    if thresholds_doc.get("format") != "atmem-benchmark-thresholds-v1":
        raise ValueError("unsupported benchmark threshold format")
    profile = resolve_profile(profile_name)
    dataset_identity = {
        "name": dataset["name"],
        "version": dataset["version"],
        "sha256": dataset["dataset_sha256"],
        "case_ids": [case["id"] for case in dataset["cases"]],
    }
    base: dict[str, Any] = {
        "format": REPORT_FORMAT,
        "scoring_format": SCORING_FORMAT,
        "dataset": dataset_identity,
        "profile": profile,
        "thresholds": thresholds_doc["thresholds"],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system().lower(),
            "atmem": _atmem_version(),
        },
        "limitations": list(dataset.get("limitations") or ()),
    }
    if not profile["available"]:
        metrics = _empty_metrics("profile was not executed")
        report = {
            **base,
            "status": "skipped",
            "passed": False,
            "failures": [profile["skip_reason"]],
            "metrics": metrics,
            "case_results": [],
            "observations": {"duration_ms": None},
        }
        report["quality_sha256"] = canonical_digest(stable_quality_payload(report))
        return validate_report(report)

    started = time.perf_counter()
    results = [_run_case(case, profile) for case in dataset["cases"]]
    metrics = _aggregate(results)
    failures = _apply_thresholds(metrics, thresholds_doc["thresholds"])
    report = {
        **base,
        "status": "passed" if not failures else "failed",
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "case_results": results,
        "observations": {"duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }
    report["quality_sha256"] = canonical_digest(stable_quality_payload(report))
    return validate_report(report)


def run_task_state_benchmark(
    dataset_path: str | Path | None = None,
) -> dict[str, Any]:
    """Execute Spec 007's deterministic guard/context benchmark."""
    source = read_json(dataset_path or data_path("task-state-v1.json"))
    if source.get("format") != "atmem-task-state-benchmark-v1":
        raise ValueError("unsupported task-state benchmark format")
    cases = source.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("task-state benchmark requires cases")
    results = [_run_task_state_case(dict(case)) for case in cases]
    body = {
        "format": "atmem-task-state-benchmark-report-v1",
        "dataset": {
            "name": source.get("name"),
            "version": source.get("version"),
            "sha256": canonical_digest(source),
            "case_count": len(results),
        },
        "passed": all(row["passed"] for row in results),
        "passed_cases": sum(1 for row in results if row["passed"]),
        "case_results": results,
        "limitations": [
            "Deterministic policy, guard, lifecycle, and serialization benchmark; no model or host execution is measured."
        ],
    }
    body["report_sha256"] = canonical_digest(body)
    return body


def _run_task_state_case(case: dict[str, Any]) -> dict[str, Any]:
    from atmem.contracts.task_state import ItemStatus, TaskItem, TaskLifecycle, TaskState
    from atmem.task_state import GENERAL_V1
    from atmem.task_state.context import eligibility_reason, prepare
    from atmem.task_state.guards import action_fingerprint, evaluate_completion_guard
    from atmem.task_state.models import summarize

    scope = AuthorityScope("benchmark-user", "benchmark-agent", "benchmark-workspace")
    status = ItemStatus(str(case.get("status") or "pending"))
    item = TaskItem(
        item_id="item-1",
        kind="step",
        title=str(case.get("text") or "Finish the governed step"),
        status=status,
        blocker_reason="waiting for evidence" if status is ItemStatus.BLOCKED else None,
        skip_reason="operator-approved skip" if status is ItemStatus.SKIPPED else None,
        required=True,
    )
    lifecycle = TaskLifecycle(str(case.get("lifecycle") or "open"))
    state = TaskState(
        task_id="task-benchmark",
        scope=scope,
        revision=1,
        lifecycle=lifecycle,
        phase="execute",
        goal="Complete the benchmark safely",
        profile_id="general",
        profile_version="general-v1",
        items=(item,),
    )
    kind = str(case.get("kind"))
    if kind == "status":
        summary = summarize(state, GENERAL_V1)
        observed = (
            "completed" if summary["completed_items"] else
            "skipped" if summary["skipped_items"] else
            "failed" if summary["failed_items"] else
            "blocked" if summary["blocked_items"] else "remaining"
        )
    elif kind == "repeated_action":
        first = action_fingerprint(action="write", target="item-1", arguments={"path": "x"})
        second = action_fingerprint(action="write", target="item-1", arguments={"path": "x"})
        observed = "same_fingerprint" if first == second else "different_fingerprint"
    elif kind == "premature_finish":
        guard = evaluate_completion_guard(state, GENERAL_V1)
        observed = guard.guard_type.value if guard else "allowed"
    elif kind == "terminal_context":
        observed = eligibility_reason(lifecycle, in_scope=True)
    elif kind == "overflow":
        package = prepare(
            state,
            GENERAL_V1,
            scope=scope,
            context_id="context-benchmark",
            prepared_at="2026-09-05T00:00:00Z",
            budget_chars=int(case.get("budget_chars") or 32),
        )
        observed = package.reason_codes[0] if package.reason_codes else package.disposition.value
    elif kind == "instruction":
        package = prepare(
            state,
            GENERAL_V1,
            scope=scope,
            context_id="context-instruction",
            prepared_at="2026-09-05T00:00:00Z",
        )
        observed = (
            "contained"
            if package.context.count("<<<end-atmem-governed-task-data>>>") == 1
            and "[escaped-delimiter]" in package.context
            else "escaped_boundary_failed"
        )
    else:
        raise ValueError(f"unknown task-state benchmark case kind: {kind}")
    return {
        "case_id": str(case["id"]),
        "kind": kind,
        "expected": case.get("expected"),
        "observed": observed,
        "passed": observed == case.get("expected"),
    }


def _run_case(case: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    subject = str(case.get("subject_id") or "benchmark-user")
    scope = AuthorityScope(
        subject_id=subject,
        agent_id=str(case.get("agent_id") or "benchmark-agent"),
        workspace_id=str(case.get("workspace_id") or "benchmark-workspace"),
    )
    active: list[dict[str, Any]] = []
    inactive: list[dict[str, Any]] = []
    context = ""
    context_ids: list[str] = []
    intelligence_error: str | None = None
    with tempfile.TemporaryDirectory(prefix="atmem-benchmark-") as directory:
        memory = Memory(Path(directory) / "memory.db")
        try:
            created: dict[str, str] = {}
            for index, operation in enumerate(case.get("setup") or ()):
                op_subject = str(operation.get("subject_id") or subject)
                try:
                    record_ids = _apply_setup(
                        memory, operation, op_subject, scope, profile,
                        case_id=str(case["id"]), index=index,
                    )
                    if record_ids:
                        created[str(operation.get("label") or index)] = record_ids[0]
                    if operation.get("exclude") and record_ids:
                        memory.set_retrieval_excluded(op_subject, record_ids[0], True)
                except Exception as exc:
                    intelligence_error = (
                        f"capture profile failed: {type(exc).__name__}: {exc}"
                    )

            active = memory.list(subject)
            inactive = memory.list(subject, include_inactive=True)
            query = str(case.get("query") or "").strip()
            if query:
                signals = ("lexical", "graph", "trust", "recency")
                if profile["mode"] == "local-embeddings":
                    try:
                        from atmem.semantic import SemanticIndex, create_embedder, default_index_path

                        embedder = create_embedder(
                            str(profile["provider"]),
                            str(profile["model"]),
                            endpoint=profile.get("endpoint"),
                            api_key_env=profile.get("api_key_env"),
                            model_version=str(profile.get("model_version") or "unverified"),
                        )
                        index = SemanticIndex(default_index_path(memory.store.path), policy=memory.policy)
                        try:
                            index.build(memory, subject, embedder)
                        finally:
                            index.close()
                        signals = ("lexical", "semantic", "graph", "trust", "recency")
                    except Exception as exc:  # optional provider failure is benchmark evidence
                        intelligence_error = f"local embedding setup failed: {type(exc).__name__}: {exc}"
                request = RecallRequest(
                    request_id=f"req-{case['id']}",
                    scope=scope,
                    query=query,
                    limit=int(case.get("limit") or 5),
                    candidate_limit=50,
                    signals=signals,
                    min_score=float(case.get("min_score", 0.35)),
                    egress_class=profile["egress_class"],
                )
                try:
                    candidates = memory.eligible_candidates(request)
                    selected = tuple(row.record_id for row in candidates.candidates)
                    if profile["mode"] in {"local-atbot", "hosted-atbot"}:
                        from atmem.control.atbot_companion import AtBotCompanionClient

                        ranked = AtBotCompanionClient().query(
                            query, [row.to_dict() for row in candidates.candidates]
                        )
                        if not ranked.get("companion", {}).get("available"):
                            raise RuntimeError("AtBot ranking became unavailable during the case")
                        allowed = set(selected)
                        selected = tuple(
                            record_id
                            for record_id in ranked.get("ranked_record_ids") or ()
                            if record_id in allowed
                        )
                    prepared = memory.prepare_context_v1(
                        ContextRequest(
                            context_id=f"context-{case['id']}",
                            candidate_set_id=candidates.candidate_set_id,
                            scope=scope,
                            record_ids=selected,
                        )
                    )
                    context = prepared.context
                    context_ids = list(prepared.record_ids)
                except Exception as exc:  # provider/authority failures remain visible evidence
                    intelligence_error = (
                        intelligence_error
                        or f"retrieval profile failed: {type(exc).__name__}: {exc}"
                    )
        finally:
            memory.close()

    expected = dict(case["expected"])
    active_text = [str(row["content"]) for row in active]
    inactive_text = [str(row["content"]) for row in inactive if row.get("status") != "active"]
    checks: list[tuple[str, bool]] = []
    if intelligence_error:
        checks.append((intelligence_error, False))
    checks.extend((f"active contains {text}", _contains(active_text, text)) for text in expected.get("active_contains", ()))
    checks.extend((f"active excludes {text}", not _contains(active_text, text)) for text in expected.get("active_excludes", ()))
    checks.extend((f"inactive contains {text}", _contains(inactive_text, text)) for text in expected.get("inactive_contains", ()))
    checks.extend((f"context contains {text}", text.casefold() in context.casefold()) for text in expected.get("context_contains", ()))
    checks.extend((f"context excludes {text}", text.casefold() not in context.casefold()) for text in expected.get("context_excludes", ()))
    if "withhold" in expected:
        checks.append(("withhold decision", (not context_ids) is bool(expected["withhold"])))
    passed = all(result for _, result in checks)
    return {
        "case_id": case["id"],
        "category": case["category"],
        "polarity": case.get("polarity", "positive"),
        "passed": passed,
        "expected": {
            "active_contains": expected.get("active_contains", []),
            "active_excludes": expected.get("active_excludes", []),
            "inactive_contains": expected.get("inactive_contains", []),
            "context_contains": expected.get("context_contains", []),
            "context_excludes": expected.get("context_excludes", []),
            "withhold": expected.get("withhold"),
        },
        "observed": {
            "active_record_count": len(active),
            "inactive_record_count": len(inactive_text),
            "context_record_count": len(context_ids),
            "context_was_empty": not context_ids,
        },
        "failures": [label for label, result in checks if not result],
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _contains(values: list[str], expected: str) -> bool:
    needle = str(expected).casefold()
    return any(needle in value.casefold() for value in values)


def _apply_setup(
    memory: Memory,
    operation: dict[str, Any],
    subject: str,
    scope: AuthorityScope,
    profile: dict[str, Any],
    *,
    case_id: str,
    index: int,
) -> list[str]:
    message = str(operation["message"])
    source_type = str(operation.get("source_type") or "user_message")
    session_id = f"benchmark:{case_id}"
    if profile["mode"] not in {"local-atbot", "hosted-atbot"} or subject != scope.subject_id:
        result = memory.remember(
            subject, message, source_type=source_type,
            session_id=session_id, turn_id=str(index + 1),
        )
        return [str(row["id"]) for row in result["records"]]

    from atmem.control.atbot_companion import AtBotCompanionClient
    from atmem.contracts import (
        InterpreterIdentity, MemoryProposal, SourceBinding, SourceCaptureRequest,
    )

    intelligence = AtBotCompanionClient().propose(message)
    if not intelligence.get("companion", {}).get("available"):
        raise RuntimeError("AtBot extraction became unavailable during the case")
    digest = hashlib.sha256(f"{case_id}:{index}:{message}".encode()).hexdigest()
    captured = memory.capture_source(
        SourceCaptureRequest(
            source_id=f"source_{digest[:32]}",
            idempotency_key=f"benchmark-capture:{digest}",
            scope=scope,
            message=message,
            source_type=source_type,
            session_id=session_id,
            turn_id=str(index + 1),
            binding_method="host_authenticated_turn",
            binding_assurance="host_authenticated",
        )
    )
    interpreter_value = dict(intelligence.get("interpreter") or {})
    interpreter = InterpreterIdentity(
        provider=str(interpreter_value.get("provider") or profile["provider"]),
        model=str(interpreter_value.get("model") or profile["model"]),
        prompt_version=str(interpreter_value.get("prompt_version") or "atbot-extract-v1"),
        assurance=str(interpreter_value.get("assurance") or "model_interpreted"),
        egress_class=str(interpreter_value.get("egress_class") or profile["egress_class"]),
    )
    record_ids: list[str] = []
    for proposal_index, row in enumerate(intelligence.get("proposals") or ()):
        proposal_digest = hashlib.sha256(
            f"{digest}:{proposal_index}:{canonical_digest(row)}".encode()
        ).hexdigest()
        admitted = memory.submit_proposal(
            MemoryProposal(
                proposal_id=f"proposal_{proposal_digest[:32]}",
                idempotency_key=f"benchmark-proposal:{proposal_digest}",
                scope=scope,
                fact=str(row.get("fact") or ""),
                fact_key=row.get("fact_key"),
                confidence=float(row.get("confidence", 0.0)),
                source_ids=(captured.source_id,),
                interpreter=interpreter,
                source_binding=SourceBinding(
                    method="host_authenticated_turn",
                    source_sha256=captured.source_sha256,
                    assurance="host_authenticated",
                ),
                entities=tuple(row.get("entities") or ()),
                suggested_action=str(row.get("suggested_action") or "uncertain"),
                related_record_ids=(),
                sensitivity=str(row.get("sensitivity") or "personal"),
                session_id=session_id,
                turn_id=str(index + 1),
            )
        )
        record_ids.extend(admitted.record_ids)
        record_ids.extend(admitted.candidate_ids)
    return record_ids


def _aggregate(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_category = {name: [row for row in results if row["category"] == name] for name in {
        "extraction", "contradiction", "recall", "no_answer", "incorrect_injection", "privacy", "poisoning", "fallback"
    }}
    extraction = by_category["extraction"]
    tp = sum(row["passed"] for row in extraction if row["polarity"] == "positive")
    fp = sum(not row["passed"] for row in extraction if row["polarity"] == "negative")
    fn = sum(not row["passed"] for row in extraction if row["polarity"] == "positive")
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    durations = sorted(float(row["duration_ms"]) for row in results)
    return {
        "extraction_precision": metric(round(precision, 6), unit="ratio"),
        "extraction_recall": metric(round(recall, 6), unit="ratio"),
        "extraction_f1": metric(round(f1, 6), unit="ratio"),
        "contradiction_accuracy": metric(_pass_rate(by_category["contradiction"]), unit="ratio"),
        "answerable_recall": metric(_pass_rate(by_category["recall"]), unit="ratio"),
        "no_answer_correctness": metric(_pass_rate(by_category["no_answer"]), unit="ratio"),
        "incorrect_injection_rate": metric(round(1 - _pass_rate(by_category["incorrect_injection"]), 6), unit="ratio"),
        "privacy_leak_count": metric(sum(not row["passed"] for row in by_category["privacy"]), unit="count"),
        "poisoning_success_count": metric(sum(not row["passed"] for row in by_category["poisoning"]), unit="count"),
        "fallback_completion": metric(_pass_rate(by_category["fallback"]), unit="ratio"),
        "latency_p50_ms": metric(_percentile(durations, 0.50), unit="ms"),
        "latency_p95_ms": metric(_percentile(durations, 0.95), unit="ms"),
        "token_usage": metric(None, unit="tokens", reason="deterministic AtMem path exposes no model token usage"),
        "model_cost_usd": metric(None, unit="USD", reason="no model call or explicit run-time pricing metadata"),
    }


def _empty_metrics(reason: str) -> dict[str, dict[str, Any]]:
    names = (
        "extraction_precision", "extraction_recall", "extraction_f1", "contradiction_accuracy",
        "answerable_recall", "no_answer_correctness", "incorrect_injection_rate",
        "privacy_leak_count", "poisoning_success_count", "fallback_completion",
        "latency_p50_ms", "latency_p95_ms", "token_usage", "model_cost_usd",
    )
    return {name: metric(None, unit="unknown", reason=reason) for name in names}


def _pass_rate(rows: list[dict[str, Any]]) -> float:
    return round(sum(row["passed"] for row in rows) / len(rows), 6) if rows else 0.0


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    index = max(0, math.ceil(len(values) * fraction) - 1)
    return round(values[index], 3)


def _apply_thresholds(metrics: dict[str, dict[str, Any]], thresholds: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for name, rule in thresholds.items():
        item = metrics.get(name)
        if item is None or item["value"] is None:
            failures.append(f"{name}: required metric is unavailable")
            continue
        value = float(item["value"])
        if "min" in rule and value < float(rule["min"]):
            failures.append(f"{name}: {value} is below {rule['min']}")
        if "max" in rule and value > float(rule["max"]):
            failures.append(f"{name}: {value} exceeds {rule['max']}")
    return failures


def _atmem_version() -> str:
    try:
        return metadata.version("atmem")
    except metadata.PackageNotFoundError:
        return "source-tree"
