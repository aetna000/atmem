"""One disjoint subscription-only turn; interruption evidence, not scored usage."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import time

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.appserver_probe import ConfigRPC, configuration_command
from benchmarks.code_replay.grade import write_new_tree
from benchmarks.code_replay.runner import allocate_session


class UsageRPC(ConfigRPC):
    ALLOWED = ConfigRPC.ALLOWED | {"turn/start", "turn/interrupt"}

    def send(self, message):
        if message.get("method") == "turn/start" and any(m.get("method") == "turn/start" for m in self.sent):
            raise ValueError("one model turn maximum; no hidden retries")
        super().send(message)


def usage_evidence(messages, thread_id, turn_id):
    updates, terminals = [], []
    for index, message in enumerate(messages):
        params = message.get("params", {})
        method = message.get("method")
        if method not in {"thread/tokenUsage/updated", "turn/completed"}:
            continue
        if params.get("threadId") != thread_id:
            raise ValueError("cross-thread accounting event")
        if method == "turn/completed":
            if params["turn"]["id"] != turn_id:
                raise ValueError("cross-turn terminal")
            terminals.append({"index": index, "status": params["turn"]["status"]})
            continue
        if params.get("turnId") != turn_id:
            raise ValueError("cross-turn accounting event")
        usage = params["tokenUsage"]
        for name in ("last", "total"):
            for key in ("inputTokens", "cachedInputTokens", "outputTokens", "reasoningOutputTokens", "totalTokens"):
                value = usage[name][key]
                if type(value) is not int or value < 0:
                    raise ValueError("invalid host token counter")
        updates.append({"index": index, "usage": usage})
    return {"updates": updates, "terminals": terminals,
        "counter_semantics": "host_cumulative_snapshots_not_summed",
        "full_usage_verified": False, "historical_usage_backfilled": False,
        "assurance": "diagnostic_partial_counters_only_until_completeness_proven"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ram-root", "auth-file", "state-root", "evidence-root", "interpreter"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--subscription-only", action="store_true")
    args = parser.parse_args()
    if not args.subscription_only:
        parser.error("subscription-only required")
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    run_id = "usage-rpc-interrupt-p1-20261017"
    if vault.inspect(principal, run_id):
        raise ValueError("retained diagnostic must not be overwritten")
    qualified = vault.inspect(principal, "usage-rpc-config-p1-20261017")
    if not any(e["envelope"]["payload"].get("proof", {}).get("passed") for e in qualified):
        raise PermissionError("actual zero-inference sandbox control required first")
    args.state_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    session = allocate_session(args.ram_root, args.auth_file)
    library = args.interpreter / "lib/python3.12"
    files = {name: (library / name).read_bytes() for name in ("logging/__init__.py", "logging/handlers.py", "LICENSE.txt")}
    write_new_tree(session.workspace, files)
    command = configuration_command(session, args.interpreter)
    rpc = UsageRPC(command, cwd=session.workspace, env={"PATH": "/usr/bin:/bin",
        "CODEX_HOME": str(session.cli_home), "TMPDIR": str(session.temporary), "LANG": "en_US.UTF-8"})
    proof, failure, thread_id, turn_id = {}, None, None, None
    try:
        rpc.call("initialize", {"clientInfo": {"name": "atmem-code-benchmark", "version": "1.0.0"}})
        rpc.send({"method": "initialized"})
        thread = rpc.call("thread/start", {"model": "gpt-6-luna", "ephemeral": True,
            "cwd": str(session.workspace), "approvalPolicy": "never"})
        if thread["model"] != "gpt-6-luna" or thread["approvalPolicy"] != "never" or thread["cwd"] != str(session.workspace):
            raise PermissionError("thread binding changed")
        thread_id = thread["thread"]["id"]
        prompt = ("Read-only public-source diagnostic. Do not modify any files or use the network. "
            "Run exactly three separate shell tool calls in sequence, not combined: "
            "first head -n 2 LICENSE.txt; second head -n 2 logging/__init__.py; "
            "third head -n 2 logging/handlers.py. Then report which files you read.")
        vault.capture(run_id=run_id, kind="appserver.usage_probe_started", principal=principal,
            payload={"prompt": prompt, "maximum_model_turns": 1, "interrupt_after": "first_command_completed",
                "wall_limit_seconds": 80, "tool_hard_limit": 3, "command": command,
                "probe_sha256": sha256(Path(__file__).read_bytes()).hexdigest()})
        turn = rpc.call("turn/start", {"threadId": thread_id, "model": "gpt-6-luna", "effort": "low",
            "input": [{"type": "text", "text": prompt}]})
        turn_id = turn["turn"]["id"]
        deadline, interrupted, terminal_at = time.monotonic() + 80, False, None
        while time.monotonic() < deadline:
            matching = [m for m in rpc.messages if m.get("params", {}).get("threadId") == thread_id]
            ended = any(m.get("method") == "turn/completed" and
                m["params"]["turn"]["id"] == turn_id for m in matching)
            commands = [m for m in matching if m.get("method") == "item/completed" and
                m["params"].get("item", {}).get("type") == "commandExecution"]
            started = [m for m in matching if m.get("method") == "item/started" and
                m["params"].get("item", {}).get("type") == "commandExecution"]
            if not interrupted and not ended and (commands or len(started) >= 3):
                rpc.call("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
                interrupted = True
            if ended:
                terminal_at = terminal_at or time.monotonic()
                if time.monotonic() - terminal_at >= 2:
                    break
            rpc.pump(.1)
        else:
            raise TimeoutError("bounded usage diagnostic wall limit")
        proof = usage_evidence(rpc.messages, thread_id, turn_id)
        proof.update({"model_turns": 1, "interrupt_requested": interrupted,
            "command_started_events": len(started), "command_completed_events": len(commands)})
    except BaseException as exc:
        failure = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        cleanup_failure = None
        try:
            rpc.close()
        except Exception as exc:
            cleanup_failure = type(exc).__name__ + ": " + str(exc)
        vault.capture(run_id=run_id, kind="appserver.usage_probe_completed", principal=principal,
            payload={"proof": proof, "failure": failure, "cleanup_failure": cleanup_failure,
                "thread_id": thread_id, "turn_id": turn_id, "requests": rpc.sent,
                "messages": rpc.messages, "stdout_base64": base64.b64encode(rpc.raw["stdout"]).decode(),
                "stderr_base64": base64.b64encode(rpc.raw["stderr"]).decode(),
                "cli_sha256": sha256(session.executable.read_bytes()).hexdigest(),
                "probe_sha256": sha256(Path(__file__).read_bytes()).hexdigest()})
        if cleanup_failure is not None and failure is None:
            raise RuntimeError(cleanup_failure)
    print(json.dumps({**proof, "updates": len(proof["updates"])}))


if __name__ == "__main__":
    main()
