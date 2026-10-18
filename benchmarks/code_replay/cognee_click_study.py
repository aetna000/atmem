"""One fixed Click task, three actual providers, protected evidence, no retries."""
import base64
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from atmem.code.receipts import CodeReceipts
from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from atmem.memory import Memory
from atmem.service.household import HouseholdApplication
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.cognee_click import worker_environment, runner
from benchmarks.code_replay.control import prompt_for
from benchmarks.code_replay.freeze import digest
from benchmarks.code_replay.frozen import digest_files, grader_tree, solution_tree
from benchmarks.code_replay.grade import tree_files, grade_files
from benchmarks.code_replay.history import ProductLane
from benchmarks.code_replay.pilot import installed_matches, stage_workspace, collect_patch, usage, summary_counts
from benchmarks.code_replay.progressive import configuration
from benchmarks.code_replay.runner import allocate_session
from benchmarks.code_replay.sandbox import shell_probe

ROOT = Path("/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/click-20261017/cognee-short-20261018")
RAM = Path("/Volumes/AtMemReplayRAM-20261017-Localization")
CHECKOUT = Path("/Volumes/MEM/AtMem-Code-Replay-20261017/upstream/click")
PACKAGE = Path("/Volumes/MEM/AtMem-Code-Replay-20261017/efficiency-p11c1-frozen.json")
WHEEL = Path("/private/tmp/atmem-click-cognee-comparator-wheel-20261018/atmem-2.3.8-py3-none-any.whl")
COGNEE = Path("/private/tmp/atmem-click-cognee-upstream-20261018/bin/python")
OLD_DEPS = "/private/tmp/atmem-click-installed-product-20261017/lib/python3.12/site-packages"
RUN = "click-cognee-short-20261018-v1"


def main():
    if ROOT.exists():
        raise ValueError("study already attempted; inspect evidence, never silently repeat")
    ROOT.mkdir(mode=0o700)
    os.environ["ATMEM_HOME"] = str(ROOT / "atmem-home")
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / "vault", vault_id=RUN, scope=scope)
    def save(kind, payload):
        vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    package = json.loads(PACKAGE.read_bytes())
    task = package["tasks"][0]
    assert task["short"] == "b67832c"
    python = Path(package["environment"]["python"])
    interpreter = Path(package["environment"]["interpreter"])
    original = tree_files(CHECKOUT, task["parent_commit"])
    grader = grader_tree(CHECKOUT, task)
    assert digest_files(original) == task["manifest"]["source_sha256"]
    assert digest_files(grader) == task["manifest"]["grader_sha256"]
    wheel_hash = sha256(WHEEL.read_bytes()).hexdigest()
    installed_matches(WHEEL, wheel_hash)
    execute, runner_source = runner()
    worker_source = Path(__file__).with_name("cognee_click.py").read_text()
    auth = Path.home() / ".codex/auth.json"
    save("comparison.preparation_started", {"task": task, "order": ["native", "cognee", "atmem"],
        "wheel_sha256": wheel_hash, "runner_source": runner_source,
        "driver_source": Path(__file__).read_text(), "worker_source": worker_source,
        "protocol_source": Path(__file__).parents[2].joinpath("specs/043-click-historical-replay/cognee-short-comparison.md").read_text(),
        "model_calls": 0, "owner_install_changed": False})
    memory = None
    attempts = []
    try:
        cases = []
        for arm in ("native", "cognee", "atmem"):
            print(json.dumps({"arm": arm, "state": "preparing"}), flush=True)
            started = time.monotonic()
            session = allocate_session(RAM, auth)
            session = stage_workspace(session, session.workspace, original, python)
            probe = shell_probe(session.workspace, denied_paths=(PACKAGE, CHECKOUT / ".git/config", auth),
                                runtime_roots=(python.parent.parent, interpreter))
            if not probe["passed"]:
                raise PermissionError("source/evaluator/auth isolation failed")
            case = {"arm": arm, "session": session, "config": None, "context": "", "probe": probe,
                    "setup_ms": int((time.monotonic() - started) * 1000), "index_ms": 0, "context_ms": 0}
            if arm == "cognee":
                state = ROOT / "cognee-state"
                state.mkdir(mode=0o700)
                environment = worker_environment(state, COGNEE)
                bootstrap = "import sys;sys.argv=['cognee-click-worker',*sys.argv[1:]];exec(compile(" + repr(worker_source) + ",'<cognee-click-worker>','exec'))"
                command = [str(COGNEE), "-I", "-u", "-c", bootstrap, "index", "--root", str(session.workspace)]
                tick = time.monotonic()
                indexed = subprocess.run(command, cwd=state, env=environment, capture_output=True, timeout=300)
                case["index_ms"] = int((time.monotonic() - tick) * 1000)
                save("cognee.index_observed", {"command": command, "environment": environment,
                    "exit_code": indexed.returncode, "stdout": indexed.stdout.decode(errors="replace"),
                    "stderr": indexed.stderr.decode(errors="replace"), "index_ms": case["index_ms"]})
                if indexed.returncode or b"get_help_option" not in indexed.stdout:
                    raise RuntimeError("upstream Cognee real indexed-symbol qualification failed")
                server = "import os,sys;os.environ.clear();os.environ.update(" + repr(environment) + ");sys.argv=['cognee-click-worker','serve'];exec(compile(" + repr(worker_source) + ",'<cognee-click-worker>','exec'))"
                # A fresh process must recover the persisted graph and expose it over MCP.
                messages = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "qualification", "version": "1"}}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "code_search", "arguments": {"operation": "query_facts", "arguments": {"name": "get_help_option", "kinds": ["symbol"], "limit": 10}}}}]
                checked = subprocess.run([str(COGNEE), "-I", "-u", "-c", server], cwd=state, env=environment,
                    input=("\n".join(map(json.dumps, messages)) + "\n").encode(), capture_output=True, timeout=90)
                replies = [json.loads(line) for line in checked.stdout.splitlines()]
                save("cognee.mcp_qualification", {"exit_code": checked.returncode, "requests": messages,
                    "replies": replies, "stderr": checked.stderr.decode(errors="replace")})
                if checked.returncode or len(replies) != 3 or any("error" in reply for reply in replies) or "get_help_option" not in json.dumps(replies[-1]):
                    raise RuntimeError("persisted upstream graph MCP qualification failed")
                case["config"] = {"command": str(COGNEE), "args": ["-I", "-u", "-c", server],
                    "enabled_tools": ["code_search"], "required": True, "startup_timeout_sec": 30,
                    "tool_timeout_sec": 30, "default_tools_approval_mode": "approve"}
                case["context"] = "Cognee's indexed pre-change repository structure is available through code_structure.code_search. Use arguments.name for a symbol substring when using query_facts with filters. Use explore/traverse for relevant relationships. Current native source takes precedence. No conversational experience is supplied."
            elif arm == "atmem":
                database = ROOT / "atmem-structure.db"
                HouseholdApplication.initialize(database, encrypted=True)
                memory = Memory(database, auto_vectors=False)
                lane = ProductLane(memory, session.workspace, environment_sha256=digest(package["environment"]), experience=False)
                prepared = lane.prepare(run_id=RUN, task=task["requirements"], image_id=package["image_id"], max_context_bytes=4096)
                if prepared["package"].memory_ids or prepared["previous_candidates"]:
                    raise ValueError("structure-only invariant failed")
                case.update(lane=lane, prepared=prepared, context=prepared["package"].content,
                            index_ms=prepared["index_ms"], context_ms=prepared["context_ms"])
                case["config"] = configuration(sys.executable, [OLD_DEPS], database=database,
                    root=session.workspace, scope=lane.scope, focused=True)
            case["prompt"] = prompt_for(task, python, case["context"]) + (
                "Use the configured workspace-local TMPDIR. If a code-graph tool is available, inspect relevant structural evidence before editing; use native source and tests to verify it.\n")
            cases.append(case)
        save("comparison.frozen", {"wheel_sha256": wheel_hash, "upstream_revision": "f154b32a9e544dac73e7ddf2010327cf9988edcd",
            "source_sha256": digest_files(original), "grader_sha256": digest_files(grader),
            "harness_sha256": {name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ("cognee_click.py", "cognee_click_study.py", "runner.py", "sandbox.py", "grade.py", "frozen.py", "history.py", "pilot.py", "control.py", "progressive.py")},
            "model": "gpt-6-luna", "effort": "low", "caps": {"seconds": 180, "tools": 24, "audited_tokens": 500000},
            "cases": [{k: str(v) if k == "session" else v for k, v in c.items() if k not in ("lane", "prepared")} for c in cases],
            "runtime": {"agent_sha256": sha256(cases[0]["session"].executable.read_bytes()).hexdigest(),
                "atmem_dependencies": sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())}})
        for case in cases:
            arm, session = case["arm"], case["session"]
            print(json.dumps({"arm": arm, "state": "solver_started"}), flush=True)
            save("trial.started", {"arm": arm, "prompt": case["prompt"], "config": case["config"]})
            def submitted():
                if arm == "atmem":
                    prepared = case["prepared"]
                    CodeReceipts(memory.store).submitted(prepared["request"], prepared["package"], host="codex")
            observed = execute(session, case["prompt"], runtime_roots=(python.parent.parent, interpreter),
                max_seconds=180, max_tool_calls=24, mcp_config=case["config"], on_submitted=submitted)
            paths, sources, changes, violations = collect_patch(session.workspace, original)
            graph_calls = [e["item"] for e in observed["events"] if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "mcp_tool_call"]
            save("agent.attempt", {"arm": arm, "command": observed["command"],
                "stdout_base64": base64.b64encode(observed["stdout"]).decode(), "stderr_base64": base64.b64encode(observed["stderr"]).decode(),
                "patch_source_bytes": changes, "changed_paths": paths, "stop_reason": observed["stop_reason"],
                "exit_code": observed["exit_code"], "graph_calls": graph_calls})
            attempts.append((case, observed, sources, violations, graph_calls))
            print(json.dumps({"arm": arm, "state": "solver_terminal", "solver_ms": observed["elapsed_ms"], "stop": observed["stop_reason"]}), flush=True)
        rows = []
        for case, observed, sources, violations, graph_calls in attempts:
            graded = grade_files(solution_tree(grader, sources), python=python, interpreter_root=interpreter, test_paths=("tests/",))
            tokens = usage(observed["events"])
            receipt_complete = observed["exit_code"] == 0 and observed["stop_reason"] is None and tokens["input_tokens"] is not None
            functional = graded.exit_code == 0 and not graded.environment_error and not violations
            within_tokens = tokens["input_tokens"] is not None and tokens["input_tokens"] + tokens["output_tokens"] <= 500000
            row = {"arm": case["arm"], "task": task["short"], "functional_pass": functional,
                "budget_pass": functional and receipt_complete and within_tokens, "receipt_complete": receipt_complete,
                "tokens": tokens, "solver_ms": observed["elapsed_ms"], "setup_ms": case["setup_ms"],
                "index_ms": case["index_ms"], "context_ms": case["context_ms"], "graph_tool_calls": len(graph_calls),
                "tool_calls": observed["tool_calls"], "grade": graded.summary(), "grade_counts": summary_counts(graded.output),
                "patch_violations": violations, "stop_reason": observed["stop_reason"]}
            save("trial.completed", {"result": row, "grade_output_base64": base64.b64encode(graded.output).decode()})
            rows.append(row)
        save("comparison.completed", {"rows": rows, "classification": "one_reused_task_integration_diagnostic_not_confirmation"})
        print(json.dumps({"state": "completed", "rows": rows}), flush=True)
    except BaseException as exc:
        save("comparison.interrupted", {"error_type": type(exc).__name__, "error": str(exc), "terminal_models": len(attempts)})
        raise
    finally:
        if memory is not None:
            memory.close()


if __name__ == "__main__":
    main()
