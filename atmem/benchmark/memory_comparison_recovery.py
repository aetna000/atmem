"""Explicit owner recovery of settled malformed outputs; never retry a paid call.

Normal study entry remains fresh-Home-only. This one-shot repair verifies all
captured calls settled, marks the already captured malformed output incorrect,
and executes only cases/arms with no prior attempt. Unknown calls stop recovery.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import time

from atmem.benchmark.memory_comparison import (
    ARMS, GENERIC, Ledger, SCOPE, execute, file_digest, fresh_cases, grade_answer,
    load_key, Provider, worker,
)
from atmem.evidence.service import EvidenceService
from atmem.feedback.service import FeedbackService
from atmem.feedback.store import FeedbackError


def captured_failure(ledger, case_id, arm):
    with ledger.transaction() as (tx, _):
        calls = [c for c in tx.iter_kind("comparison_call") if c["trial"] == case_id + ":" + arm]
    if not calls or any(c["state"] != "complete" for c in calls):
        raise ValueError("settled captured calls required")
    last = max(calls, key=lambda c: len(c["request"]["messages"]))
    choice = last["result"]["response"]["choices"][0]
    malformed = choice.get("finish_reason") != "stop"
    try:
        action = json.loads(choice["message"]["content"])
        malformed |= type(action) is not dict or set(action) != {"action", "content"}
    except (ValueError, KeyError, TypeError):
        malformed = True
    if not malformed:
        raise ValueError("cannot replace a valid captured model response")
    observations = []
    messages = last["request"]["messages"]
    for index in range(len(messages)):
        if messages[index]["role"] != "assistant":
            continue
        action = json.loads(messages[index]["content"])
        response = json.loads(messages[index+1]["content"])
        if action["action"] != "QUERY" or "observation" not in response:
            raise ValueError("captured query sequence is not reconstructable")
        observations.append({"query": action["content"], "result": response["observation"]})
    return {"answer": None, "queries": len(observations), "observations": observations,
            "failure": "captured_malformed_model_output"}


def run(args):
    root = Path(__file__).resolve().parents[2]
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if head != args.source_sha:
        raise ValueError("exact committed recovery source required")
    committed = subprocess.check_output(["git", "-C", str(root), "show", head + ":atmem/benchmark/memory_comparison_recovery.py"])
    if sha256(committed).hexdigest() != file_digest(__file__):
        raise ValueError("uncommitted recovery implementation")
    home = args.home.resolve()
    manifest = json.loads((home / "preregistration.json").read_text())
    for relative, field in (("atmem/benchmark/memory_comparison.py", "runner_sha256"),
                            ("tools/matched_memory_worker.py", "worker_sha256"),
                            ("atmem/benchmark/memory_adaptation.py", "agent_and_grader_sha256")):
        if file_digest(root / relative) != manifest[field]:
            raise ValueError("frozen policy/tool/agent/worker implementation changed")
    ledger = object.__new__(Ledger)
    ledger.clock = time.time
    ledger.scope = type(SCOPE)("local", "public-benchmark", "memory-comparison", "spec-053")
    ledger.credential = json.loads((home / ".comparison-access.json").read_text())["credential"]
    ledger.feedback = FeedbackService(EvidenceService(home / "control", vault_id="memory-comparison", home_root=home))
    cases = fresh_cases(args.data.resolve())
    with ledger.transaction() as (tx, _):
        row = tx.get("comparison_run", "run")
        ledger.check(row)
        if row["manifest"] != manifest or manifest.get("protocol_revision") != 2:
            raise ValueError("exact protocol2 registration required")
        if tx.get("comparison_recovery", "once") is not None:
            raise ValueError("recovery already reserved; cannot retry")
        calls = list(tx.iter_kind("comparison_call"))
        if any(c["state"] != "complete" for c in calls):
            raise ValueError("unknown or pending call prevents recovery")
        completed = {(t["case_id"], t["arm"]) for t in tx.iter_kind("comparison_trial")}
        attempts = {(t["case_id"], t["arm"]) for t in tx.iter_kind("comparison_attempt")}
        unfinished = attempts - completed
        if len(unfinished) != 1:
            raise ValueError("exactly one settled malformed attempt required")
        history = tx.get("comparison_history", "history")
        tx.put("comparison_recovery", "once", {"source_sha": head,
            "source_sha256": file_digest(__file__), "reason": "settled malformed JSON; no call retry",
            "already_completed": len(completed), "failed_attempt": list(next(iter(unfinished)))}, expected_revision=0)
    shutil.copyfile(home / "summary.json", home / "interrupted-summary.json")
    provider = Provider(load_key(args.env_file))
    script = root / "tools/matched_memory_worker.py"
    status = "complete_with_explicit_settled_malformed_recovery"
    try:
        for index, case in enumerate(cases):
            offset = index % 3
            for arm in ARMS[offset:] + ARMS[:offset]:
                pair = (case["id"], arm)
                if pair in completed:
                    continue
                started = time.time()
                key = "case-" + case["id"] + "-" + arm
                if pair in unfinished:
                    output = captured_failure(ledger, *pair)
                    with ledger.transaction() as (tx, _):
                        prepared = tx.get("comparison_context", key)
                else:
                    ledger.retain("comparison_attempt", key, {"case_id": case["id"], "arm": arm, "state": "reserved"})
                    prepared, context, load = None, "", ""
                    if arm != "none":
                        path = home / arm
                        version = manifest["installed_packages"][arm]["identity"]["version"]
                        python = args.original_python if arm == "original" else args.pilot_python
                        prepared = worker(python, script, path / "home", {"command": "context", "expected_version": version,
                            "database": str(path / "memory.db"), "query": case["public"]["question"], "case_id": case["id"]})
                        expected = manifest["installed_packages"][arm]
                        if prepared["identity"] != expected["identity"] or prepared["generation"] != expected["generation"]:
                            raise ValueError("frozen installed memory changed")
                        context = prepared["package"]["context"]
                        if type(context) is not str or len(context.encode()) > 8192:
                            raise ValueError("invalid frozen-budget context")
                        load = GENERIC["load"] if arm == "original" else history["policy"]["load"]
                        ledger.retain("comparison_context", key, prepared)
                    try:
                        output = execute(ledger, provider, args.data.resolve(), {k: case[k] for k in ("id", "public")}, arm, context, load)
                    except json.JSONDecodeError:
                        output = captured_failure(ledger, case["id"], arm)
                grade = grade_answer(output, case["target"])
                record = {"case_id": case["id"], "arm": arm, "correct": grade.correct,
                    "upstream_correct": grade.evidence["upstream_correct"], "queries": output["queries"],
                    "seconds": None if pair in unfinished else time.time()-started,
                    "context_bytes": len(prepared["package"]["context"].encode()) if prepared else 0,
                    "context_status": prepared["package"]["status"] if prepared else "disabled",
                    "input": case["public"], "output": output, "grade": grade.to_dict(),
                    "recovery": pair in unfinished}
                # Preserve unknown interrupted latency explicitly. The base reporter
                # expects numeric durations, so separate that row's duration below.
                if record["seconds"] is None:
                    record["seconds"] = 0
                    record["latency_unavailable"] = True
                ledger.retain("comparison_trial", key, record)
                print(json.dumps({"event": "recovered_failed_trial" if pair in unfinished else "trial",
                    "case_id": case["id"], "arm": arm, "correct": grade.correct}), flush=True)
                completed.add(pair)
    except Exception:
        status = "recovery_stopped; never retry automatically"
        raise
    finally:
        report = ledger.report(status)
        report["latency_limitations"] = "Original119 interrupted latency unavailable; recovered row placeholder0 must be excluded from latency aggregates. Elapsed includes recovery downtime."
        for arm in ARMS:
            times = [t["seconds"] for t in report["trials"] if t["arm"] == arm and (t["case_id"], arm) not in unfinished]
            import statistics
            report["arms"][arm]["p50_seconds"] = statistics.median(times) if times else None
            report["arms"][arm]["latency_observed"] = len(times)
        for trial in report["trials"]:
            if (trial["case_id"], trial["arm"]) in unfinished:
                trial["seconds"] = None
        (home / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("home", "data", "original-python", "pilot-python", "env-file"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--continue-settled-only", action="store_true")
    args = parser.parse_args()
    if not args.continue_settled_only:
        parser.error("explicit owner continuation required; never retries a call or attempted task")
    run(args)


if __name__ == "__main__":
    main()
