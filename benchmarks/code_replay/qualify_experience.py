"""Qualify the existing product on a retained disjoint real coding attempt.

Never creates oracle lessons: the observation comes from that agent's retained
final report, while a new supervisor-run test receipt binds the source state.
"""
import argparse
import ast
import base64
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from atmem.code.application import CodeApplication
from atmem.code.contracts import CodeContextRequest
from atmem.code.context import build_context
from atmem.code.experience import CodeExperience
from atmem.code.identity import CodeIdentity
from atmem.core.canonical import canonical_json
from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from atmem.knowledge.contracts import ExecutionReceipt, ExperienceProposal, SourceAnchor
from atmem.memory import Memory
from atmem.service.household import HouseholdApplication
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.sandbox import permission_arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.resolve(strict=True)
    if root.parent.name != args.session_id or not str(root).startswith("/Volumes/AtMemReplayRAM-20261017"):
        raise ValueError("retained disjoint RAM session required")
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    retained = vault.inspect(principal, args.session_id)[-1]["envelope"]["payload"]
    if retained["workspace"] != str(root) or retained["Click_target_trial"] is not False or retained["exit_code"] != 0:
        raise ValueError("not a valid retained disjoint coding session")
    final = None
    for line in base64.b64decode(retained["stdout_base64"]).splitlines():
        event = json.loads(line)
        if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message":
            try:
                candidate = json.loads(event["item"]["text"])
            except ValueError:
                continue
            if set(candidate) == {"summary", "paths"}:
                final = candidate
    if not final or not final["paths"]:
        raise ValueError("agent produced no eligible attributed observation")
    environment = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "LANG": "en_US.UTF-8", "PYTHONPATH": str(root),
                   "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1",
                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}
    for command in (["git", "init", str(root)], ["git", "-C", str(root), "add", "atmem", "tests", "LICENSE"]):
        subprocess.run(command, env=environment, check=True, capture_output=True)
    if subprocess.run(["git", "-C", str(root), "diff", "--cached", "--quiet"], env=environment).returncode:
        subprocess.run(["git", "-C", str(root), "-c", "user.name=AtMem qualification", "-c", "user.email=benchmark@localhost", "commit", "-m", "Disjoint agent source state"],
                       env=environment, check=True, capture_output=True)
    runtime = Path("/private/tmp/atmem-click-diagnostic-runtime-20261017")
    interpreter = Path("/private/tmp/atmem-click-interpreters-20261017/cpython-3.12.12-macos-aarch64-none")
    identity_command = [str(runtime / "bin/python"), "-I", "-c",
                        'import sys,platform,json,hashlib,importlib.metadata as m; v={"python":platform.python_version(),"system":platform.system(),"machine":platform.machine(),"packages":sorted((str(d.metadata.get("Name","")).lower(),d.version) for d in m.distributions())}; print(hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest())']
    environment_id = subprocess.check_output(identity_command, env=environment, text=True).strip()
    if args.database.exists():
        raise ValueError("choose a fresh diagnostic database; never overwrite a run")
    args.database.parent.mkdir(parents=True, exist_ok=True)
    HouseholdApplication.initialize(args.database, encrypted=True)
    memory = Memory(args.database, auto_vectors=False)
    try:
        lane = CodeIdentity(memory.store).resolve(root, subject_id="local-operator", profile_id="shared", agent_id="codex")
        app = CodeApplication(memory, subject_id="local-operator")
        key = os.urandom(32)
        service = CodeExperience(app, lane, producer_keys={"supervisor": key}, environment_sha256=environment_id)
        before, _, exclusions = service.capture_snapshot(str(root))
        temporary = root / "verification-tmp"
        temporary.mkdir(exist_ok=True)
        bootstrap = 'import os,runpy; os.environ["TMPDIR"]=' + repr(str(temporary)) + '; runpy.run_module("pytest",run_name="__main__")'
        actual_command = [shutil.which("codex"), "sandbox", "-C", str(root), "-P", "click-replay",
                          *permission_arguments((runtime, interpreter)), str(runtime / "bin/python"), "-c", bootstrap,
                          "-q", "-p", "no:cacheprovider", "--basetemp", str(temporary / "pytest"), "tests/test_knowledge_contracts.py"]
        executed = subprocess.run(actual_command, env=environment, capture_output=True, timeout=60)
        after, _, _ = service.capture_snapshot(str(root))
        if before != after:
            raise ValueError("source changed during supervisor verification")
        output = canonical_json({"stdout_base64": base64.b64encode(executed.stdout).decode(),
                                 "stderr_base64": base64.b64encode(executed.stderr).decode(), "exit_code": executed.returncode}).encode()
        receipt = ExecutionReceipt("disjoint-execution", lane, "supervisor", args.session_id, before.snapshot_id,
                                   environment_id, tuple(actual_command), executed.returncode, sha256(output).hexdigest(), "disjoint-verification")
        signature = hmac.new(key, canonical_json(receipt.to_dict()).encode(), sha256).hexdigest()
        service.receipt(receipt, before, output, signature)
        path = "atmem/knowledge/contracts.py"
        source = (root / path).read_bytes()
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "source_path")
        proposal = ExperienceProposal("disjoint-attempt", lane, before.snapshot_id,
                                      "Validate source paths without making Unicode filenames unusable.", final["summary"],
                                      "observed_pass" if executed.returncode == 0 else "observed_failure",
                                      (SourceAnchor(path, sha256(source).hexdigest(), node.lineno, node.end_lineno),), (receipt.receipt_id,))
        formed = service.form(proposal, before, producer_id="supervisor",
                              signature=hmac.new(key, canonical_json(proposal.to_dict()).encode(), sha256).hexdigest())
        request = CodeContextRequest("disjoint-recall", "later-session", "later-turn", "source paths control characters Unicode", 4096, lane)
        recalled = build_context(memory, request, repository_root=str(root), timeout_ms=30000)
        unrelated = root / ("unrelated_diagnostic_" + uuid4().hex + ".py")
        unrelated.write_text("# unrelated diagnostic change\n")
        later = build_context(memory, request, repository_root=str(root), timeout_ms=30000)
        (root / path).write_bytes(source + b"\n")
        withheld = build_context(memory, request, repository_root=str(root), timeout_ms=30000)
        (root / path).write_bytes(source)
        result = {"real_agent_session": args.session_id, "verification_exit_code": executed.returncode,
                  "formed": formed, "candidate_count": 1, "admitted_count": len(formed.get("record_ids", [])),
                  "initial_recalled": len(recalled.memory_ids), "unrelated_change_recalled": len(later.memory_ids),
                  "changed_anchor_recalled": len(withheld.memory_ids), "excluded_counts": exclusions,
                  "graph_enabled": app.settings(lane.project_id)["graph_enabled"], "Click_target_trial": False}
        evidence = vault.capture(run_id="disjoint-product-" + args.session_id, kind="product.experience_qualification", principal=principal,
                                 payload={**result, "proposal": proposal.to_dict(), "receipt": receipt.to_dict(),
                                          "execution_result_base64": base64.b64encode(output).decode(),
                                          "contexts": {"initial": recalled.to_dict(), "later": later.to_dict(), "withheld": withheld.to_dict()}})
        print(json.dumps({**result, "evidence": evidence}))
    finally:
        memory.close()


if __name__ == "__main__":
    main()
