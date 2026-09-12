#!/usr/bin/env python3
"""Isolated real OpenClaw/Claude CLI journey with a real local Mem0 provider.

Requires mem0ai, ollama, local nomic-embed-text and qwen3 models, and Claude CLI
login. No shared-channel messages are sent. Uses only generated dummy data.
"""
from __future__ import annotations
import argparse
import hashlib
import sqlite3
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--scenario", choices=["default", "inject", "withhold", "tools", "tools-missing", "tool-error"], default="default")
    parser.add_argument("--openclaw", default="openclaw")
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(mode=0o700, parents=True)
    repo = Path(__file__).resolve().parents[1]
    provider_root = root / "provider"
    provider_root.mkdir(mode=0o700)
    env = dict(os.environ, PYTHONPATH=str(repo), MEM0_TELEMETRY="false")
    provider_log = (root / "provider.log").open("w")
    provider = subprocess.Popen([sys.executable, str(repo / "tools/smoke_mem0_roleplay.py"), "--serve", str(provider_root)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=provider_log, text=True, env=env)
    try:
        line = provider.stdout.readline()
        if not line: raise RuntimeError("provider failed to start; see provider.log")
        details = json.loads(line)
        bridge = root / "bridge"
        bridge.mkdir()
        shutil.copytree(repo / "integrations/openclaw/dist", bridge / "dist")
        shutil.copyfile(repo / "integrations/openclaw/openclaw.plugin.json", bridge / "openclaw.plugin.json")
        package = json.loads((repo / "integrations/openclaw/package.json").read_text())
        package["openclaw"]["extensions"] = ["./index.js"]
        (bridge / "package.json").write_text(json.dumps(package))
        # Observe actual host metadata without supplying or changing it.
        (bridge / "index.js").write_text('''import plugin from "./dist/index.js";
import { appendFileSync } from "node:fs";
export default { ...plugin, register(api) {
  const events = api.agent?.events;
  const subscribe = events?.registerAgentEventSubscription?.bind(events) || api.registerAgentEventSubscription?.bind(api);
  subscribe?.({id: "atmem-live-observer", streams: ["tool"], handle(event) {
    const d = event.data || {};
    appendFileSync(process.env.ATMEM_LIVE_HOOK_LOG, JSON.stringify({name: "agent_tool_event", runId: event.runId, sessionKey: event.sessionKey,
      data: { phase: d.phase, name: d.name, toolCallId: d.toolCallId, isError: d.isError, incomplete: d.incomplete,
      hasResult: Object.hasOwn(d, "result"), resultKeys: d.result && typeof d.result === "object" ? Object.keys(d.result) : [] }}) + "\\n");
  }});
  const original = api.runContext;
  const traced = original ? { ...original,
    setRunContext(patch) { const ok = original.setRunContext(patch); appendFileSync(process.env.ATMEM_LIVE_HOOK_LOG, JSON.stringify({name: "run_context_set", key: patch.namespace, ok}) + "\\n"); return ok; },
    getRunContext(key) { const value = original.getRunContext(key); appendFileSync(process.env.ATMEM_LIVE_HOOK_LOG, JSON.stringify({name: "run_context_get", key: key.namespace, found: value !== undefined}) + "\\n"); return value; },
  } : undefined;
  const filteredEvents = events ? { ...events, registerAgentEventSubscription(subscription) {
    events.registerAgentEventSubscription({ ...subscription, handle(event, context) {
      if (process.env.ATMEM_DROP_TOOL_RESULTS === "1" && event.stream === "tool" && event.data.phase === "result") return;
      return subscription.handle(event, context);
    }});
  }} : undefined;
  plugin.register({ ...api, agent: filteredEvents ? { ...api.agent, events: filteredEvents } : api.agent,
    runContext: traced, on(name, handler) {
    api.on(name, (event, ctx) => {
      const fields = ["agentId", "sessionKey", "sessionId", "runId", "workspaceDir", "messageProvider", "channel", "channelId", "senderIsOwner", "senderId", "toolCallId"];
      const safe = Object.fromEntries(fields.filter(k => ctx[k] !== undefined).map(k => [k, ctx[k]]));
      appendFileSync(process.env.ATMEM_LIVE_HOOK_LOG, JSON.stringify({name, ctx: safe, eventKeys: Object.keys(event), toolName: event.toolName, toolCallId: event.toolCallId}) + "\\n");
      if (process.env.ATMEM_DROP_TOOL_RESULTS === "1" && name === "after_tool_call") return;
      return handler(event, ctx);
    });
  }});
}};
''')
        session = str(uuid.uuid4())
        session_key = "agent:main:atmem-mem0-roleplay-" + session
        (root / "state").mkdir(mode=0o700)
        local = {"isolated": True, "stateDir": str(root / "state"), "agentId": "main", "workspaceDir": details["workspace"],
                 "sessionKey": session_key, "sessionId": session}
        config = {
            "gateway": {"mode": "local"},
            "agents": {"defaults": {"workspace": details["workspace"], "model": {"primary": "claude-cli/sonnet"}}},
            "skills": {"allowBundled": []},
            "plugins": {"allow": ["memory-atmem", "anthropic"], "load": {"paths": [str(bridge)]}, "entries": {
                "anthropic": {"enabled": True},
                "memory-atmem": {"enabled": True, "hooks": {"allowConversationAccess": True, "allowPromptInjection": True}, "config": {
                    "command": str(repo / ".venv/bin/atmem"),
                    "subject": details["subject"], "dbPath": details["memory_db"],
                    "agentWorkspaces": {"main": details["workspace"]},
                    "controlPlane": {"enabled": True, "statePath": details["state_path"]},
                    "delegatedContext": {"userId": "owner", "requireOwner": args.scenario == "default", "localOperator": local},
                    "recall": {"timeoutMs": 15000}, "capture": {"enabled": False},
                    "persona": {"enabled": False}, "tools": {"enabled": False},
                }},
            }},
        }
        config_path = root / "openclaw.json"
        config_path.write_text(json.dumps(config, indent=2)); config_path.chmod(0o600)
        (Path(details["workspace"]) / "dummy.txt").write_text("ATMEM_DUMMY_FILE_OK\n")
        env.update(OPENCLAW_STATE_DIR=str(root / "state"), OPENCLAW_CONFIG_PATH=str(config_path),
                   ATMEM_DELEGATED_CONFIG=details["config_path"], ATMEM_LIVE_HOOK_LOG=str(root / "hooks.jsonl"),
                   ATMEM_DROP_TOOL_RESULTS="1" if args.scenario == "tools-missing" else "0")
        prompts = {
            "default": "The fictional travel club codeword is ORCHID-731. Do not call tools. Reply exactly DEFAULT_GATE_OK.",
            "inject": "The fictional travel club codeword is ORCHID-731. Do not call tools. Reply with the codeword in supplied memory.",
            "withhold": "Calculate 87423 times 63782. Do not call tools. Reply with only the number.",
            "tools": "The fictional travel club codeword is ORCHID-731. Read dummy.txt in this workspace using the read tool, then use exec to run printf ATMEM_EXEC_OK. Do not access any other files or run any other commands. Report the two tool outputs and the memory codeword.",
        }
        prompts["tools-missing"] = prompts["tools"]
        prompts["tool-error"] = "The fictional travel club codeword is ORCHID-731. Use the read tool once to read missing-fixture.txt in the current workspace. This file intentionally does not exist. Report the observed error; do not create the file, search for it, or retry."
        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        command = [args.openclaw, "agent", "--local", "--agent", "main", "--session-id", session,
                   "--session-key", session_key, "--message", prompts[args.scenario], "--timeout", "90", "--json"]
        (root / "invocation.json").write_text(json.dumps({"command": command, "session": session, "scenario": args.scenario},indent=2))
        with (root / "host.stdout").open("w") as stdout, (root / "host.stderr").open("w") as stderr:
            result = subprocess.run(command, env=env, cwd=details["workspace"], stdout=stdout, stderr=stderr, timeout=120)
        print(json.dumps({"root": str(root), "host_exit": result.returncode, "scenario": args.scenario}), flush=True)
        # Persist content-minimized flight reports through the real control service.
        from atmem.control.manager import ControlPlaneManager
        manager = ControlPlaneManager(details["state_path"])
        reports = [manager.verify_blackbox_flight(row["run_id"]) for row in manager.blackbox_runs(limit=20).get("runs", [])]
        (root / "flights.json").write_text(json.dumps(reports, indent=2))
        print(json.dumps([{"run_id":r["run_id"],"verdict":r["verdict"],"tools":r["tools"]} for r in reports]),flush=True)
        assert result.returncode == 0, "host command failed"
        assert len(reports) == 1, "expected exactly one observed flight"
        report = reports[0]
        expected = "incomplete_evidence" if args.scenario == "tools-missing" else "completed_with_tool_errors" if args.scenario == "tool-error" else "completed_successfully"
        assert report["verdict"] == expected, (expected, report["verdict"])
        assert report["timeline_chain_valid"]
        with sqlite3.connect(next(provider_root.rglob("evidence.db"))) as db:
            db.row_factory = sqlite3.Row
            accepted = [dict(row) for row in db.execute("SELECT run_id,decision,receipt_id,receipt_sha256,context_sha256,context_byte_length FROM delegated_context_acceptances")]
            deliveries = [dict(row) for row in db.execute("SELECT context_sha256,shown FROM delegated_context_deliveries")]
        injected = [e for e in report["timeline"] if e["event_type"] == "context.injected" and e["payload"].get("success")]
        if args.scenario == "default":
            assert not accepted and not injected
            assert "delegated_owner_metadata_missing" in (root / "host.stderr").read_text()
        else:
            assert len(accepted) == 1 and accepted[0]["run_id"] == report["run_id"]
            authorization = [e for e in report["timeline"] if e["event_type"] == "context.provider_authorization"]
            assert len(authorization) == 1
            assert authorization[0]["payload"]["context_receipt_sha256"] == accepted[0]["receipt_sha256"]
            if args.scenario == "withhold":
                assert accepted[0]["decision"] == "withhold" and not injected and not deliveries
            else:
                digest = hashlib.sha256(details["exact"].encode()).hexdigest()
                assert accepted[0]["decision"] == "inject" and accepted[0]["context_sha256"] == digest
                assert len(injected) == 1 and injected[0]["payload"]["context_sha256"] == digest
                assert len(deliveries) == 1 and deliveries[0]["shown"] == 1
        if args.scenario.startswith("tools"):
            names = {e["payload"]["tool_name"] for e in report["timeline"] if e["event_type"] == "tool.requested"}
            assert {"read", "exec"} <= names
            assert report["tools"]["requested"] >= 2
            assert report["tools"]["completed"] == (0 if args.scenario == "tools-missing" else report["tools"]["requested"])
        summary = {"scenario": args.scenario, "started_at": started_at,
            "ended_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "host": subprocess.check_output([args.openclaw, "--version"],text=True).strip(),
            "run_id": report["run_id"], "verdict": report["verdict"], "accepted": accepted,
            "deliveries": deliveries, "tools": report["tools"], "assertions_passed": True}
        (root / "summary.json").write_text(json.dumps(summary,indent=2))
        print("LIVE ACCEPTANCE ASSERTIONS PASSED", flush=True)
    finally:
        provider.stdin.close()
        try: provider.wait(timeout=10)
        except subprocess.TimeoutExpired: provider.terminate(); provider.wait(timeout=5)
        provider_log.close()

if __name__ == "__main__":
    main()
