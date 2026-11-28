"""Authenticated execution, replay and engineering evidence in the local dashboard."""

import re

from atmem.agent_team import run_agent_team
from atmem.agent_team.archive import RunArchive, archive_transaction
from atmem.agent_team.outcomes import compare, outcome
from atmem.evidence import CaptureMode, EvidenceScope
from atmem.core.canonical import sha256_hex
from atmem.memory import Memory


def _binding(manager, identity_session, *, live=False):
    account = identity_session()["account"]
    access = account["scope"]
    if (
        account["role"] not in {"administrator", "investigator", "evidence_collector"}
        or account.get("password_change_required")
        or access.get("run_id")
    ):
        raise PermissionError("Signed-in workspace memory access is required.")
    state, warning = manager.effective_state()
    if warning or (live and not state.mode.influences_agent):
        raise PermissionError("Live team runs require an active AtMem memory provider.")
    scope, path = manager._memory_authority_scope(state, subject_id=access["subject_id"], agent_id=None)
    if access.get("workspace_id") and access["workspace_id"] != scope.workspace_id:
        raise PermissionError("Workspace is outside the signed-in account scope.")
    if live and manager.delegated_context_applies(
        agent_id=scope.agent_id, user_id=scope.subject_id, workspace_id=scope.workspace_id
    ):
        raise PermissionError("This workspace uses a delegated context provider.")
    return (
        account["username"],
        scope,
        path,
        EvidenceScope(access["tenant_id"], scope.subject_id, scope.workspace_id),
        account["role"],
    )


def _get(archive, key):
    if not isinstance(key, str) or not re.fullmatch(r"team_[a-f0-9]{32}", key):
        raise ValueError("A valid run ID is required.")
    return archive.project(archive.events(key))


def execute(manager, identity_session, body):
    if set(body) - {"question", "policy", "max_calls", "rerun_of"}:
        raise ValueError("Unexpected run field.")
    original = _binding(manager, identity_session, live=True)
    _, scope, path, access, _ = original

    def check_authority():
        if _binding(manager, identity_session, live=True) != original:
            raise PermissionError("The signed-in workspace changed during the run.")

    question, previous = body.get("question"), body.get("rerun_of")
    if previous is not None and question is not None:
        raise ValueError("A rerun inherits its original question.")
    try:
        with archive_transaction(manager) as (_, store):
            capture_setting = store.capture_setting()
            if previous is not None:
                check_authority()
                question = _get(RunArchive(store, access), previous)["question"]
    except PermissionError:
        if previous is not None:
            raise
        capture_setting = None
    memory = Memory(path, auto_vectors=False, retain_query_text=False)
    try:
        report = run_agent_team(
            memory,
            scope,
            question,
            policy=body.get("policy", "single"),
            max_calls=body.get("max_calls", 2),
            check_authority=check_authority,
        )
    finally:
        memory.close()
    check_authority()
    # A user's capture setting governs persistence, including when it changes mid-run.
    report.update(archived=False, rerun_of=previous, usage_source="local_provider")
    if capture_setting and capture_setting[0] is CaptureMode.FULL:
        with archive_transaction(manager) as (_, store):
            check_authority()
            if store.capture_setting() == capture_setting:
                archive = RunArchive(store, access)
                if previous:
                    _get(archive, previous)
                report["archived"] = True
                archive.start(report)
    return report


def _source_excerpt(path, scope, run, body):
    step = next((s for s in run["steps"] if s.get("step_id") == body.get("step_id")), None)
    index = body.get("source_index")
    if not step or type(index) is not int or not 0 <= index < len(step.get("provenance", [])):
        raise ValueError("Select a recorded source span on this step.")
    ref = step["provenance"][index]
    unavailable = {"status": "unavailable", "source_id": ref["source_id"]}
    memory = Memory(path, auto_vectors=False, retain_query_text=False)
    try:
        record = memory.store.get_record(scope.subject_id, ref["record_id"])
        if not record or record["status"] not in {"active", "superseded"}:
            return unavailable
        source = memory.store.get_protocol_source_by_id(ref["source_id"])
        if (
            not source
            or source["workspace_id"] != scope.workspace_id
            or source["subject_id"] != scope.subject_id
            or not (source.get("result") or {}).get("retained")
        ):
            return unavailable
        episode = memory.store.get_episode(scope.subject_id, source["episode_id"])
        text = episode.get("message") if episode else None
        if not isinstance(text, str) or source["source_sha256"] != "sha256:" + sha256_hex(text):
            return unavailable
        start, end = ref["start_offset"], ref["end_offset"]
        if not 0 <= start < end <= len(text) or end - start > 65536:
            return unavailable
        excerpt = text[start:end]
        if ref["excerpt_sha256"] != "sha256:" + sha256_hex(excerpt):
            return unavailable
        return {"status": "verified", "excerpt": excerpt, **ref}
    finally:
        memory.close()


def history(manager, identity_session, body):
    op = body.get("action")
    fields = {
        "list": {"outcome_ref", "before"},
        "get": {"run_id"},
        "source": {"run_id", "step_id", "source_index"},
        "attach": {"run_id", "outcome"},
    }
    if op not in fields or set(body) - (fields[op] | {"action"}):
        raise ValueError("Invalid project history request.")
    with archive_transaction(manager) as (_, store):
        binding = _binding(manager, identity_session, live=op == "source")
        username, scope, path, access, role = binding
        archive = RunArchive(store, access)
        if op == "list":
            query, before = body.get("outcome_ref", ""), body.get("before", "")
            if not isinstance(query, str) or len(query) > 300 or not isinstance(before, str):
                raise ValueError("Invalid history filter.")
            return archive.list_runs(outcome_ref=query, before=before)
        run = _get(archive, body.get("run_id"))
        if op == "source":
            value = _source_excerpt(path, scope, run, body)
            if _binding(manager, identity_session, live=True) != binding:
                raise PermissionError("Workspace authority changed during inspection.")
            return value
        if op == "attach":
            if role not in {"administrator", "evidence_collector"}:
                raise PermissionError("An evidence collector is required to attach an outcome.")
            item = outcome(body.get("outcome"), run, username)
            if not any(old["outcome_id"] == item["outcome_id"] for old in run["outcomes"]):
                archive.append(run["run_id"], "team.outcome", item)
                run["outcomes"].append(item)
        if run.get("rerun_of"):
            events = archive.events(run["rerun_of"])
            if events:
                parent = archive.project(events)
                run["comparison"] = compare(parent, run)
                run["previous_outcomes"] = parent["outcomes"]
        return run
