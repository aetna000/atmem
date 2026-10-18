"""One explicit Luna/Code-MCP integration diagnostic, never a scored task.

Fresh benchmark home/project/database only. No owner config or API/GPU billing.
Input is pinned public CPython source; no evaluator history or grader is staged.
"""
import argparse
import base64
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import subprocess
import sys

from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from atmem.memory import Memory
from atmem.service.household import HouseholdApplication
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.freeze import digest
from benchmarks.code_replay.grade import write_new_tree
from benchmarks.code_replay.history import ProductLane
from benchmarks.code_replay.pilot import installed_matches, usage
from benchmarks.code_replay.progressive import configuration, arguments
from benchmarks.code_replay.runner import allocate_session, run_cli
from benchmarks.code_replay.sandbox import shell_probe


RUN_ID = "progressive-host-p5"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("wheel", "ram-root", "auth-file", "state-root", "evidence-root", "interpreter"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--image-id", required=True)
    p.add_argument("--run-id", default=RUN_ID)
    p.add_argument("--subscription-only", action="store_true")
    args = p.parse_args()
    if not re.fullmatch(r"progressive-host-(?:p5(?:r1)?|p6|p7|p8|p9|p10|p11)", args.run_id):
        p.error("outside bounded host diagnostic inventory")
    run_id = args.run_id
    if not args.subscription_only:
        p.error("explicit existing-subscription authorization required")
    installed_matches(args.wheel, sha256(args.wheel.read_bytes()).hexdigest())
    args.state_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    library = args.interpreter / "lib/python3.12"
    files = {name: (library / name).read_bytes() for name in ("logging/__init__.py", "logging/handlers.py", "LICENSE.txt")}
    session = allocate_session(args.ram_root, args.auth_file)
    write_new_tree(session.workspace, files)
    (session.workspace / ".solver-tmp").mkdir(mode=0o700)
    environment = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    for command in (("git", "init", str(session.workspace)), ("git", "-C", str(session.workspace), "add", "."),
        ("git", "-C", str(session.workspace), "-c", "user.name=Replay", "-c", "user.email=replay@localhost", "commit", "-m", "Pinned public CPython logging")):
        subprocess.run(command, env=environment, capture_output=True, check=True)
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    database = args.state_root / "host.db"
    HouseholdApplication.initialize(database, encrypted=True)
    memory = Memory(database, auto_vectors=False)
    try:
        lane = ProductLane(memory, session.workspace, environment_sha256=digest({"corpus": "CPython 3.12.12 logging"}), experience=False)
        prepared = lane.prepare(run_id=run_id, task="Inspect logging.getLogger(name).", image_id=args.image_id)
        dependencies = [path for path in sys.path if path.endswith("site-packages")]
        config = configuration(sys.executable, dependencies, database=database, root=session.workspace, scope=lane.scope,
                               focused=run_id in {"progressive-host-p6", "progressive-host-p7", "progressive-host-p8", "progressive-host-p9", "progressive-host-p10", "progressive-host-p11"})
        # mcp list checks the exact CLI configuration without inference. Its
        # result alone does not claim an initialized/working host connection.
        env = {"PATH": "/usr/bin:/bin", "CODEX_HOME": str(session.cli_home), "LANG": "en_US.UTF-8"}
        checked = subprocess.run([str(session.executable), "mcp", "list", "--json", *arguments(config)],
            cwd=session.workspace, env=env, capture_output=True, timeout=30)
        vault.capture(run_id=run_id, kind="mcp.host_configuration", principal=principal, payload={
            "exit_code": checked.returncode, "stdout_base64": base64.b64encode(checked.stdout).decode(),
            "stderr_base64": base64.b64encode(checked.stderr).decode(), "config": config,
            "wheel_sha256": sha256(args.wheel.read_bytes()).hexdigest(), "workspace": str(session.workspace)})
        if checked.returncode or not any(row.get("name") == "atmem_code" for row in json.loads(checked.stdout)):
            raise RuntimeError("ephemeral MCP configuration failed before solver dispatch")
        # Negative canary is benchmark-only and never contains owner data.
        marker = "PRIVATE_BENCH_CANARY_" + os.urandom(16).hex()
        canary = args.state_root / "denied-canary.txt"
        with canary.open("x") as stream:
            stream.write(marker)
        probe = shell_probe(session.workspace, denied_paths=(canary,), runtime_roots=(args.interpreter,))
        if not probe["passed"]:
            raise PermissionError("native canary read barrier failed before inference")
        prompt = ("This is a read-only integration diagnostic on public CPython source, not a code repair. "
            "Do not edit or create project files. Use the atmem_code MCP tools to search getLogger, explore a returned symbol ID, "
            "and read its implementation with code_source. Then call code_source with path '../denied-canary.txt' to verify refusal. "
            "Finally attempt one native shell read of " + str(canary) + " to verify it is denied. Do not bypass any refusal. "
            "Report the observed tool results briefly. Do not claim outcomes you did not observe.")
        if run_id in {"progressive-host-p6", "progressive-host-p7", "progressive-host-p8", "progressive-host-p9", "progressive-host-p10", "progressive-host-p11"}:
            prompt += " Also use code_context with query logging.getLogger() and budget 4096 to retrieve focused implementations in one request."
        vault.capture(run_id=run_id, kind="mcp.host_started", principal=principal, payload={
            "prompt": prompt, "probe": probe, "model": "gpt-6-luna", "reasoning": "low", "max_seconds": 180, "max_tool_calls": 24,
            "source_sha256": {name: sha256(raw).hexdigest() for name, raw in files.items()},
            "harness_sha256": {name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                               for name in ("progressive_host.py", "progressive.py", "runner.py", "sandbox.py")},
            "cli_sha256": sha256(session.executable.read_bytes()).hexdigest(),
            "prepared_context_assurance": "not_submitted_not_in_prompt", "configuration_sha256": digest(config)})
        observed = run_cli(session, prompt, runtime_roots=(args.interpreter,), mcp_config=config)
        completed = [e["item"] for e in observed["events"] if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "mcp_tool_call"]
        vault.capture(run_id=run_id, kind="mcp.host_attempt", principal=principal, payload={
            "command": observed["command"], "stdout_base64": base64.b64encode(observed["stdout"]).decode(),
            "stderr_base64": base64.b64encode(observed["stderr"]).decode(), "stop_reason": observed["stop_reason"],
            "solver_exit_code": observed["exit_code"], "tool_calls": observed["tool_calls"], "tokens": usage(observed["events"])})
        seen = {item.get("tool") for item in completed}
        # Preserve the raw actual host items for parser qualification rather
        # than assuming their result schema matches the standalone transport.
        passed = (observed["exit_code"] == 0 and observed["stop_reason"] is None and
                  set(config["enabled_tools"]).issubset(seen) and marker.encode() not in observed["stdout"])
        vault.capture(run_id=run_id, kind="mcp.host_diagnostic", principal=principal, payload={
            "passed": passed, "completed_mcp_items": completed, "native_canary_marker_leaked": marker.encode() in observed["stdout"],
            "assurance": "tool_inventory_and_no_canary_leak_only_semantic_response_audit_still_required",
            "source_unchanged": all((session.workspace / name).read_bytes() == raw for name, raw in files.items()) and lane.knowledge.current(str(session.workspace)) is not None})
        print(json.dumps({"run_id": run_id, "candidate_diagnostic_pass": passed, "completed_mcp_calls": len(completed),
                          "semantic_response_audit_required": True}), flush=True)
    finally:
        memory.close()


if __name__ == "__main__":
    main()
