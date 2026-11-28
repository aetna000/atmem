"""A sender offers references. Only an independently authorized recipient can read them."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from atmem.evidence import CaptureMode, EvidenceRole
from atmem.memory import Memory
from .archive import RunArchive, archive_transaction, digest, now
from .pricing import reader_terms, reader_cost
from .runner import CONTEXT_BYTES, _expired, _lookup, _supporting_text

HOSTS = ("openclaw", "hermes", "mcp", "pydantic-ai", "langgraph", "chatgpt")
FIELDS = {
    "review": {"question"},
    "offer": {
        "question",
        "recipient",
        "request_id",
        "rerun_of",
        "review",
        "reader_model",
        "reader_pricing",
    },
    "receive": {"run_id"},
    "complete": {"run_id", "delivery_id", "quote", "usage"},
    "inbox": set(),
}


def host_identity(name):
    parts = name.split(":", 2) if isinstance(name, str) else []
    if (
        len(parts) != 3
        or parts[0] != "team"
        or parts[1] not in HOSTS
        or not re.fullmatch(r"[A-Za-z0-9_.-]{1,96}", parts[2])
    ):
        raise ValueError("Use team:<host>:<registered-agent> for the host identity.")
    return parts[1], parts[2]


def resolve_host(manager, principal):
    if principal is None or principal.role is not EvidenceRole.TEAM_HOST:
        raise PermissionError("An active team host grant is required.")
    host, agent = host_identity(principal.principal_id)
    state, warning = manager.effective_state()
    if warning or not state.mode.influences_agent:
        raise PermissionError("Native AtMem memory must be active.")
    access = principal.scope
    if not access.workspace_id or access.run_id:
        raise PermissionError("A workspace-bound team credential is required.")
    members = manager.authority_topology(state=state).get("workspaces", [])
    if not any(
        row["subject_id"] == access.subject_id
        and row["workspace_id"] == access.workspace_id
        and agent in row["agent_ids"]
        for row in members
    ):
        raise PermissionError("Agent has no memory grant for this workspace.")
    scope, path = manager._memory_authority_scope(state, subject_id=access.subject_id, agent_id=agent)
    if scope.workspace_id != access.workspace_id or manager.delegated_context_applies(
        agent_id=agent, user_id=scope.subject_id, workspace_id=scope.workspace_id
    ):
        raise PermissionError("Native memory authority is unavailable for this host.")
    return host, scope, path


def _usage(value):
    if value is None:
        return {}
    allowed = {"input_tokens", "output_tokens", "cost_microusd", "model_calls", "model"}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("Invalid host usage.")
    for key in set(value) - {"model"}:
        if type(value[key]) is not int or not 0 <= value[key] <= 10**10:
            raise ValueError("Usage counts must be non-negative bounded integers.")
    if "model" in value and (not isinstance(value["model"], str) or not 0 < len(value["model"]) <= 160):
        raise ValueError("Invalid model name.")
    return dict(value)


def _snapshot(memory, scope, question):
    # The tool host may use a remote model. Apply remote eligibility at both ends.
    package, count, limit = _lookup(memory, scope, question, True, egress="remote")
    reason = package.sufficiency.status
    texts = _supporting_text(package)
    if (
        count >= limit
        or _expired(package.expires_at)
        or any(unit.get("valid_until") and _expired(unit["valid_until"]) for unit in package.selected_units)
    ):
        reason = "coverage_or_validity_limit"
    refs = [row for row in package.provenance if row["record_id"] in texts]
    if reason == "sufficient" and not refs:
        reason = "missing_provenance"
    return package, texts, refs, reason


def _summary(run):
    return {key: run[key] for key in ("run_id", "outcome", "reason")}


def _step(run, identity, role, status, reason, **more):
    host, agent = host_identity(identity)
    return {
        "step_id": f"{run['run_id']}.{len(run['steps']) + 1}",
        "parent_step_id": run["steps"][-1]["step_id"] if run["steps"] else None,
        "host": host,
        "agent_id": agent,
        "role": role,
        "status": status,
        "reason": reason,
        "occurred_at": now(),
        **more,
    }


def _elapsed(run):
    return max(
        0,
        round(
            (datetime.now(timezone.utc) - datetime.fromisoformat(run["started_at"])).total_seconds() * 1000
        ),
    )


def dispatch(manager, token: str, operation: str, body: dict, *, expected_host=None):
    if operation not in FIELDS or not isinstance(body, dict) or set(body) - FIELDS[operation]:
        raise ValueError("Unknown operation or unexpected handoff field.")
    with archive_transaction(manager) as (evidence, store):
        principal = evidence.authenticate(token)
        host, scope, path = resolve_host(manager, principal)
        if expected_host is not None and expected_host != host:
            raise PermissionError("Credential belongs to another host.")
        result = _handle_host(store, principal, scope, path, operation, body)
        if resolve_host(manager, principal) != (host, scope, path):
            raise PermissionError("The host's memory authority changed during the operation.")
        return result


def _handle_host(store, principal, scope, path, operation, body):
    archive = RunArchive(store, principal.scope)
    if store.capture_mode() is not CaptureMode.FULL:
        raise PermissionError("Portable handoffs require full encrypted evidence capture.")
    if operation == "inbox":
        pending = []
        for key in reversed(archive.ids(recipient=principal.principal_id)):
            events = archive.host_events(key, principal.principal_id)
            if events and events[0]["payload"].get("recipient") == principal.principal_id:
                run = archive.project(events)
                if run["outcome"] in {"offered", "delivered"}:
                    pending.append(_summary(run))
                    if len(pending) == 50:
                        break
        return {"runs": pending}
    if operation == "review":
        question = _question(body.get("question"))
        memory = Memory(path, auto_vectors=False, retain_query_text=False)
        try:
            pack, texts, refs, status = _snapshot(memory, scope, question)
            if (
                status != "sufficient"
                or memory.store.record_generation(scope.subject_id) != pack.generation
            ):
                return {"outcome": "abstained", "reason": "Sender evidence unavailable."}
            passages = _passages(refs, texts)
            return {
                "outcome": "ready",
                "question": question,
                "generation": pack.generation,
                "evidence_sha256": digest(passages),
                "passages": passages,
            }
        finally:
            memory.close()
    if operation == "offer":
        return _offer(archive, principal, scope, path, body)
    key = body.get("run_id")
    if not isinstance(key, str) or not re.fullmatch(r"team_[a-f0-9]{32}", key):
        raise ValueError("A valid run ID is required.")
    events = archive.host_events(key, principal.principal_id)
    if not events or events[0]["payload"].get("recipient") != principal.principal_id:
        raise PermissionError("Handoff unavailable for this recipient.")
    run = archive.project(events)
    if operation == "complete" and run["outcome"] in {"answered", "abstained"}:
        if events[-1]["payload"].get("completion_digest") == digest(body):
            return _summary(run)
        # Outcome attachments can follow completion.
        if any(e["payload"].get("completion_digest") == digest(body) for e in events[1:]):
            return _summary(run)
        raise ValueError("This handoff has already closed.")
    if run["outcome"] not in {"offered", "delivered"}:
        return _summary(run)
    memory = Memory(path, auto_vectors=False, retain_query_text=False)
    try:
        return _recipient(archive, principal, memory, scope, events, run, operation, body)
    finally:
        memory.close()


def _question(question):
    if not isinstance(question, str) or not question.strip() or len(question.encode()) > 1024:
        raise ValueError("A question of 1–1024 UTF-8 bytes is required.")
    return question


def _passages(refs, texts):
    return [
        {"record_id": record, "text": texts[record]}
        for record in dict.fromkeys(r["record_id"] for r in refs)
    ]


def _offer(archive, principal, scope, path, body):
    question, request_id, recipient = body.get("question"), body.get("request_id"), body.get("recipient")
    host_identity(recipient)
    terms = reader_terms(body.get("reader_model"), body.get("reader_pricing"))
    parent_id = body.get("rerun_of")
    if parent_id is not None:
        if not isinstance(parent_id, str) or not re.fullmatch(r"team_[a-f0-9]{32}", parent_id):
            raise ValueError("Invalid parent run ID.")
        parent = archive.events(parent_id)
        if (
            not parent
            or parent[0]["payload"].get("sender") != principal.principal_id
            or parent[0]["payload"].get("recipient") != recipient
        ):
            raise PermissionError("Rerun must use its original sender, recipient and workspace.")
        previous_run = archive.project(parent)
        if question != previous_run["question"] or previous_run["outcome"] not in {
            "answered",
            "abstained",
            "withheld",
        }:
            raise ValueError("Rerun requires a closed run and the original question.")
    _question(question)
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,96}", request_id):
        raise ValueError("A stable request ID is required.")
    if recipient == principal.principal_id:
        raise ValueError("Choose a different recipient.")
    key = "team_" + digest([archive.scope.to_dict(), principal.principal_id, request_id])[:32]
    previous = archive.events(key)
    if previous:
        if previous[0]["payload"]["request_digest"] != digest(body):
            raise ValueError("Request ID already used with different arguments.")
        return _summary(archive.project(previous))
    memory = Memory(path, auto_vectors=False, retain_query_text=False)
    try:
        pack, texts, refs, status = _snapshot(memory, scope, question)
        if memory.store.record_generation(scope.subject_id) != pack.generation:
            status = "changed"
    finally:
        memory.close()
    offered = status == "sufficient"
    run = {
        "run_id": key,
        "scope": scope.to_dict(),
        "question": question,
        "started_at": now(),
        "policy": "portable",
        "rerun_of": parent_id,
        "model": "Host supplied",
        "steps": [],
        "lookups": None,
        "model_calls": None,
        "max_calls": None,
        "input_tokens": None,
        "output_tokens": None,
        "usage_complete": False,
        "elapsed_ms": 0,
        "answer": None,
        "source_ids": [],
        "outcome": "offered" if offered else "abstained",
        "reason": "Waiting for the designated recipient." if offered else f"Sender evidence is {status}.",
    }
    run.update(terms)
    run["steps"].append(
        _step(
            run,
            principal.principal_id,
            "offer",
            status,
            run["reason"],
            generation=pack.generation,
            preparation_id=pack.preparation_id,
            provenance=refs,
            source_ids=list(dict.fromkeys(r["source_id"] for r in refs)),
        )
    )
    review = body.get("review")
    if review is not None:
        if not isinstance(review, dict) or set(review) - {
            "generation",
            "evidence_sha256",
            "quote",
            "usage",
        }:
            raise ValueError("Invalid reviewer receipt.")
        passages = _passages(refs, texts)
        quote = review.get("quote")
        if (
            not offered
            or pack.generation != review.get("generation")
            or digest(passages) != review.get("evidence_sha256")
            or not isinstance(quote, str)
            or not quote
            or len(quote.encode()) > CONTEXT_BYTES
        ):
            raise ValueError("Reviewer must confirm the current delivered passages.")
        matches = {row["record_id"] for row in passages if quote in row["text"]}
        if not matches:
            raise ValueError("Reviewer quote is outside the offered evidence.")
        usage = _usage(review.get("usage"))
        run["steps"].append(
            _step(
                run,
                principal.principal_id,
                "reviewer",
                "returned",
                "Sender selected an exact source quotation.",
                quote=quote,
                generation=pack.generation,
                evidence_sha256=digest(passages),
                passages=passages,
                provenance=[row for row in refs if row["record_id"] in matches],
                usage_source="host_reported" if usage else "unreported",
                **usage,
            )
        )
    archive.start(run, recipient=recipient, sender=principal.principal_id, request_digest=digest(body))
    return _summary(run)


def _recipient(archive, principal, memory, scope, events, run, operation, body):
    delivery = next((e["payload"]["step"] for e in events if e["event_type"] == "team.delivered"), None)
    if operation == "complete" and (not delivery or body.get("delivery_id") != delivery["receipt_id"]):
        raise PermissionError("A matching recipient delivery receipt is required.")
    pack, texts, refs, status = _snapshot(memory, scope, run["question"])
    original = run["steps"][0]
    valid = (
        status == "sufficient"
        and pack.generation == original["generation"]
        and memory.store.record_generation(scope.subject_id) == pack.generation
        and {digest(r) for r in refs} == {digest(r) for r in original["provenance"]}
    )
    passages = _passages(refs, texts)
    if delivery and delivery["evidence_sha256"] != digest(passages):
        valid = False
    if not valid:
        reason = "Recipient could not confirm the offered memory revision and source spans."
        update = {"outcome": "withheld", "reason": reason, "elapsed_ms": _elapsed(run)}
        step = _step(run, principal.principal_id, "verify", "withheld", reason, generation=pack.generation)
        archive.append(run["run_id"], "team.withheld", {"step": step, "update": update})
        return _summary({**run, **update})

    sources = list(dict.fromkeys(r["source_id"] for r in refs))
    review = next((s for s in run["steps"] if s["role"] == "reviewer"), None)
    if operation == "receive":
        if not delivery:
            receipt = (
                "delivery_"
                + digest([run["run_id"], principal.principal_id, pack.generation, passages])[:32]
            )
            delivery = _step(
                run,
                principal.principal_id,
                "receive",
                "delivered",
                "Recipient independently verified the same source spans.",
                receipt_id=receipt,
                generation=pack.generation,
                preparation_id=pack.preparation_id,
                provenance=refs,
                source_ids=sources,
                passages=passages,
                evidence_sha256=digest(passages),
            )
            update = {
                "outcome": "delivered",
                "reason": "Evidence released to the recipient tool.",
                "elapsed_ms": _elapsed(run),
            }
            archive.append(run["run_id"], "team.delivered", {"step": delivery, "update": update})
        return {
            "run_id": run["run_id"],
            "outcome": "delivered",
            "delivery_id": delivery["receipt_id"],
            "question": run["question"],
            **{k: run[k] for k in ("reader_model", "reader_pricing") if k in run},
            "reviewer_quote": review["quote"] if review else None,
            "passages": delivery["passages"],
            "evidence_sha256": delivery["evidence_sha256"],
        }
    quote = body.get("quote")
    if not isinstance(quote, str) or len(quote.encode()) > CONTEXT_BYTES:
        raise ValueError("Return a short exact quotation or an empty string to abstain.")
    matches = {p["record_id"] for p in delivery["passages"] if quote and quote in p["text"]}
    if quote and review and quote not in review["quote"]:
        raise ValueError("Reader quote is outside the verified reviewer handoff.")
    if quote and not matches:
        raise ValueError("The quote does not occur in the delivered evidence.")
    usage = _usage(body.get("usage"))
    if run.get("reader_model") and (quote or usage) and usage.get("model") != run["reader_model"]:
        raise ValueError("Completion requires the selected reader model.")
    costs = reader_cost(run, usage)
    refs = [r for r in refs if r["record_id"] in matches]
    sources = list(dict.fromkeys(r["source_id"] for r in refs))
    reason = "Recipient returned a source-linked quote." if quote else "Recipient abstained."
    step = _step(
        run,
        principal.principal_id,
        "complete",
        "returned",
        reason,
        quote=quote,
        receipt_id=delivery["receipt_id"],
        provenance=refs,
        generation=pack.generation,
        source_ids=sources,
        usage_source="host_reported" if usage else "unreported",
        **costs,
        **usage,
    )
    update = {
        "outcome": "answered" if quote else "abstained",
        "reason": reason,
        "answer": quote or None,
        "source_ids": sources,
        "elapsed_ms": _elapsed(run),
        **costs,
        **usage,
        "usage_complete": {"input_tokens", "output_tokens"} <= usage.keys(),
        "usage_source": step["usage_source"],
    }
    if review:
        for key in ("input_tokens", "output_tokens", "cost_microusd", "model_calls"):
            update[key] = review[key] + usage[key] if key in review and key in usage else None
        update["usage_complete"] = all(update[key] is not None for key in ("input_tokens", "output_tokens"))
    archive.append(
        run["run_id"], "team.completed", {"step": step, "update": update, "completion_digest": digest(body)}
    )
    return _summary({**run, **update})
