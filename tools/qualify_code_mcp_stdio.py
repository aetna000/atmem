"""Independent installed stdio check against an existing qualification DB.

No indexing, repository mutation, host trust changes or model calls.
"""
import json
from pathlib import Path
import subprocess
import sys

from atmem.code.application import CodeApplication
from atmem.code.identity import CodeIdentity
from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from atmem.memory import Memory
from atmem.knowledge.projections import CodeKnowledge
from atmem.knowledge.code.mcp import CodeKnowledgeMCP
from benchmarks.code_replay.atmem_bridge import ReplayEvidence


def main():
    state = Path(sys.argv[1]).resolve(strict=True)
    root = Path(sys.argv[2]).resolve(strict=True)
    database = state / "knowledge.db"
    memory = Memory(database, auto_vectors=False)
    try:
        scope = CodeIdentity(memory.store).resolve(root, subject_id="qualification", profile_id="shared", agent_id="codex")
        app = CodeApplication(memory, subject_id="qualification")
        knowledge = CodeKnowledge(app, scope)
        generation = knowledge.current(str(root))
        relation = next(row for row in generation["relations"] if row["target_id"] and row["kind"] == "calls")
        operations = {"query_facts": {"limit": 3}, "explore": {"id": relation["source_id"]},
            "traverse": {"start_ids": [relation["source_id"]], "max_depth": 20, "max_nodes": 15},
            "find_path": {"source_id": relation["source_id"], "target_id": relation["target_id"]},
            "impact_analysis": {"target_ids": [relation["target_id"]], "max_nodes": 15},
            "architecture": {"max_nodes": 15}, "insights": {"limit": 2}, "delta": {}}
        requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
        requests += [{"jsonrpc": "2.0", "id": n, "method": "tools/call", "params": {"name": "code_search",
            "arguments": {"operation": operation, "arguments": options, "budget": 131072}}}
            for n, (operation, options) in enumerate(operations.items(), 3)]
        server = CodeKnowledgeMCP(app, scope, str(root))
        expected = [server.query("code_search", request["params"]["arguments"]) for request in requests[2:]]
        dependencies = "/private/tmp/atmem-click-installed-product-20261017/lib/python3.12/site-packages"
        bootstrap = "import sys,runpy;sys.path.append(" + repr(dependencies) + ");runpy.run_module('atmem.knowledge.code.mcp',run_name='__main__')"
        command = [sys.executable, "-I", "-u", "-c", bootstrap, "--db", str(database), "--root", str(root),
            "--subject", scope.subject_id, "--project-id", scope.project_id, "--agent", scope.agent_id]
        result = subprocess.run(command, input=("\n".join(map(json.dumps, requests)) + "\n").encode(), capture_output=True,
            env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}, timeout=90)
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        assert [row["id"] for row in replies] == list(range(1, 11))
        assert {tool["name"] for tool in replies[1]["result"]["tools"]} == {"code_search", "code_explore", "code_context", "code_source"}
        for reply, wanted in zip(replies[2:], expected):
            assert reply["result"]["isError"] is False
            assert json.loads(reply["result"]["content"][0]["text"]) == wanted
        evidence_scope = EvidenceScope("benchmark", "local-operator", "code-index-parity-20261018")
        principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, evidence_scope)
        run = "code-index-parity-20261018-v1"
        vault = ReplayEvidence(state / "vault", vault_id=run, scope=evidence_scope)
        vault.capture(run_id=run, kind="qualification.independent_stdio", principal=principal,
            payload={"requests": requests, "replies": replies, "command": command, "exit_code": result.returncode,
                     "stderr": result.stderr.decode(errors="replace"), "driver_source": Path(__file__).read_text(),
                     "operations": list(operations), "exact_service_results_matched": True, "model_calls": 0})
        print(json.dumps({"independent_stdio_operations": len(operations), "protocol_replies": len(replies),
            "exact_service_results_matched": True, "model_calls": 0}), flush=True)
    finally:
        memory.close()


if __name__ == "__main__":
    main()
