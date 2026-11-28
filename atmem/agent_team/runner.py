"""Run a bounded evidence lookup and up to two independent local model roles."""

from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic
from typing import Callable
from uuid import uuid4
from xml.etree import ElementTree

from atmem.contracts import AuthorityScope, ContextRequestV2, ExposureConfirmation, RecallRequest, RetrievalBudget
from atmem.memory import Memory

from .local import LocalAgents, LocalModelError

POLICIES = ("adaptive", "fixed", "single")
CONTEXT_BYTES = 4096


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expired(timestamp: str) -> bool:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")) <= _now()


def _lookup(memory, scope, question, broad):
    limit = 16 if broad else 4
    candidates = memory.eligible_candidates(RecallRequest(
        request_id="recall_" + uuid4().hex, scope=scope, query=question, limit=limit,
        candidate_limit=64 if broad else 24, signals=("lexical", "graph"),
        retrieval_strategy="core-rrf-v1", egress_class="local",
    ))
    package = memory.prepare_context_v2(ContextRequestV2(
        context_id="ctx_" + uuid4().hex, scope=scope, query=question,
        candidate_set_id=candidates.candidate_set_id,
        budget=RetrievalBudget(context_bytes=CONTEXT_BYTES, graph_visits=64 if broad else 16,
                               neighbor_depth=2 if broad else 1),
    ))
    return package, len(candidates.candidates), limit


def _supporting_text(package) -> dict[str, str]:
    if not package.context or package.sufficiency.status != "sufficient":
        return {}
    supporting = set(package.sufficiency.evidence_ids)
    # Only content inside a packed memory entry can support a quotation.
    # Instructions, source IDs, XML attributes and status text cannot.
    try:
        root = ElementTree.fromstring(package.context)
    except ElementTree.ParseError:
        return {}
    return {
        node.attrib["id"]: (node.text or "").rsplit("\nSources: ", 1)[0].strip()
        for node in root.findall("memory") if node.attrib.get("id") in supporting
    }


def run_agent_team(memory: Memory, scope: AuthorityScope, question: str, *,
                   policy: str = "adaptive", max_calls: int = 2,
                   agents: LocalAgents | None = None,
                   check_authority: Callable[[], None] | None = None) -> dict:
    """Answer an extractive question. The caller owns the local memory authority.

    A single reader is the native comparison. Fixed requests review on every
    eligible run. Adaptive reserves a reader call and reviews on weak evidence
    or a full nomination window. All policies use the same answer constraint.
    """
    if not isinstance(question, str) or not question.strip() or len(question.encode()) > 1024:
        raise ValueError("Enter a question between 1 and 1024 UTF-8 bytes.")
    if policy not in POLICIES or type(max_calls) is not int or max_calls not in (1, 2):
        raise ValueError("Choose a supported policy and a limit of one or two model calls.")
    question = question.strip()
    agents = agents or LocalAgents()
    run_id = "team_" + uuid4().hex
    started = monotonic()
    steps = []
    package = None
    report = {
        "run_id": run_id, "started_at": _now().isoformat(), "question": question,
        "scope": scope.to_dict(), "policy": policy, "model": agents.model, "max_calls": max_calls,
        "context_byte_limit": CONTEXT_BYTES, "steps": steps, "model_calls": 0,
        "input_tokens": 0, "output_tokens": 0, "usage_complete": True,
        "lookups": 0, "answer": None, "source_ids": [],
    }

    def step(role, start, **fields):
        row = {"role": role, "elapsed_ms": round((monotonic() - start) * 1000), **fields}
        steps.append(row)
        return row

    def finish(outcome, reason):
        if package is not None and any("evidence" in row for row in steps) and not current(package):
            for row in steps:
                for key in ("evidence", "quote", "source_ids"):
                    row.pop(key, None)
            report.update(answer=None, source_ids=[])
            outcome, reason = "abstained", "Evidence expired or changed during the run."
        report.update(outcome=outcome, reason=reason, elapsed_ms=round((monotonic() - started) * 1000))
        return report

    def authorize():
        if check_authority:
            check_authority()

    def current(package):
        authorize()
        if _expired(package.expires_at) or memory.store.record_generation(scope.subject_id) != package.generation:
            return False
        historical = package.need.temporal_target not in (None, "current")
        return historical or all(not unit.get("valid_until") or not _expired(unit["valid_until"])
                                 for unit in package.selected_units)

    def lookup(broad):
        authorize()
        clock = monotonic()
        report["lookups"] += 1
        role = "expanded_lookup" if broad else "lookup"
        try:
            package, count, limit = _lookup(memory, scope, question, broad)
        except (ValueError, RuntimeError, OSError):
            step(role, clock, status="failed", reason="The scoped memory lookup could not complete.")
            return None, False
        step(role, clock, status=package.sufficiency.status,
             reason="Expanded search in the same workspace." if broad else "Scoped memory lookup.",
             candidates=count, limit=limit, context_bytes=len(package.context.encode()),
             source_ids=list(package.source_ids), missing=list(package.sufficiency.missing_slots),
             reason_codes=list(package.sufficiency.reason_codes), preparation_id=package.preparation_id)
        return package, count >= limit

    def ask(role, payload, reason):
        clock = monotonic()
        report["model_calls"] += 1
        row = step(role, clock, reason=reason, evidence=payload, context_bytes=len(payload.encode()))
        try:
            reply = agents.invoke(role, question, payload)
        except LocalModelError as exc:
            row.update(status="failed", error=str(exc))
            report["usage_complete"] = False
            return None
        finally:
            row["elapsed_ms"] = round((monotonic() - clock) * 1000)
        row.update(input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
                   status="returned", quote=reply.quote)
        report["input_tokens"] += reply.input_tokens
        report["output_tokens"] += reply.output_tokens
        if reply.quote is None:
            row.update(status="invalid", error="The local model did not return a structured quote.")
        return reply.quote

    package, saturated = lookup(False)
    if package is None:
        return finish("failed", "The scoped memory lookup failed.")
    weak = package.sufficiency.status != "sufficient" or saturated
    review = policy == "fixed" or (policy == "adaptive" and weak)
    if review and max_calls < 2 and weak:
        return finish("abstained", "Review needs a second call. One call is reserved for the reader.")
    review = review and max_calls == 2
    if review:
        package, saturated = lookup(True)
        if package is None:
            return finish("failed", "The expanded memory lookup failed.")
    if package.sufficiency.status != "sufficient":
        return finish("abstained", f"Scoped evidence is {package.sufficiency.status}.")
    if saturated and policy != "single":
        return finish("abstained", "The candidate window filled before the search could establish coverage.")
    if not current(package):
        return finish("abstained", "Prepared evidence expired or changed.")
    entries = _supporting_text(package)
    if not entries or not package.source_ids:
        return finish("abstained", "No source-linked passage supports an extractive answer.")
    try:
        agents.ensure_available()
    except LocalModelError as exc:
        return finish("unavailable", str(exc))

    payload = package.context
    for index, role in enumerate(("reviewer", "reader") if review else ("reader",)):
        if not current(package):
            return finish("abstained", "Prepared evidence expired or changed before handoff.")
        reason = ("Select a supporting quote from the expanded evidence." if role == "reviewer"
                  else "Read the reviewed quote." if review else "Read the scoped evidence directly.")
        quote = ask(role, payload, reason)
        if index == 0 and steps[-1]["status"] != "failed":
            # A successful local response establishes that exact prepared bytes
            # reached the first role. The next handoff contains only a quotation.
            try:
                receipt = memory.confirm_exposure_v1(ExposureConfirmation(
                    confirmation_id="confirm_" + uuid4().hex, preparation_id=package.preparation_id, scope=scope,
                    context_sha256=package.context_sha256, host_run_id=run_id,
                ))
            except ValueError:
                return finish("abstained", "Evidence changed before delivery could be confirmed.")
            steps[-1]["receipt_id"] = receipt.receipt_id
        if quote is None:
            return finish("failed", steps[-1]["error"])
        matches = {key: value for key, value in entries.items() if quote and quote in value}
        if not matches or (index > 0 and quote not in payload):
            steps[-1]["status"] = "withheld"
            return finish("abstained", "The agent returned no matching quote from a supporting memory.")
        entries, payload = matches, quote
        steps[-1]["source_ids"] = list(dict.fromkeys(
            row["source_id"] for row in package.provenance if row["record_id"] in entries
        ))
        if not steps[-1]["source_ids"]:
            return finish("abstained", "The selected quote has no source reference.")
    if not current(package):
        return finish("abstained", "Evidence changed before the answer could be returned.")
    report.update(answer=payload, source_ids=steps[-1]["source_ids"])
    return finish("answered", "The answer is an exact quote from scoped supporting evidence.")
