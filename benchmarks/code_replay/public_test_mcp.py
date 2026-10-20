"""Common benchmark-only test tool on AtMem transport and protected evidence."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
from uuid import uuid4

from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from atmem.mcp.server import MCPServer, _error, _result
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
import atmem_public_test_helpers as helpers


def options(arguments):
    if not isinstance(arguments, dict) or set(arguments) - {"patch", "paths", "keyword", "max_failures"}:
        raise ValueError("only public patch and test selectors allowed")
    patch = arguments.get("patch", "")
    if not isinstance(patch, str) or len(patch.encode()) > 262144 or "\0" in patch:
        raise ValueError("bounded UTF-8 text patch required")
    pytest = {"paths": arguments.get("paths", list(getattr(helpers, "PINNED_DEFAULT_TEST_PATHS", ("tests",)))), "keyword": arguments.get("keyword"),
        "max_failures": arguments.get("max_failures", 0)}
    # The same validator is also enforced in the container; host rejects bad
    # selectors before launching a worker. Supplied by the operator bootstrap.
    helpers.pytest_arguments(pytest)
    return patch, pytest


class PublicTestMCP(MCPServer):
    def __init__(self, preset):
        if set(preset) != {"image", "worker_source", "worker_sha256", "source", "run_id", "evidence_root"}:
            raise ValueError("exact operator public-test preset required")
        if sha256(preset["worker_source"].encode()).hexdigest() != preset["worker_sha256"]:
            raise ValueError("public worker source changed")
        # Validate image before creating evidence or serving tools.
        helpers.worker_command(preset["image"], "atmem-reference-control-" + "0" * 32, preset["worker_source"])
        super().__init__(None, default_subject="benchmark-operator")
        self.preset, self.calls = preset, 0
        scope = EvidenceScope("benchmark", "local-operator", preset["run_id"])
        self.principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
        self.evidence = ReplayEvidence(Path(preset["evidence_root"]), vault_id=preset["run_id"], scope=scope)
        self.record("public_tests.started", preset)

    def record(self, kind, payload):
        return self.evidence.capture(run_id=self.preset["run_id"], kind=kind, payload=payload, principal=self.principal)

    def handle(self, message):
        if message.get("method") != "tools/call" or "id" not in message:
            return super().handle(message)
        try:
            self.record("public_tests.mcp_request", {"message": message})
            response = super().handle(message)
            self.record("public_tests.mcp_response", {"message": response})
            return response
        except Exception:
            return _error(message.get("id"), -32603, "public tests unavailable; protected result not released")

    def _tool_definitions(self):
        return [{"name": "run_public_tests", "description":
            "Run public tests in the pinned environment against a supplied unified diff from the public base. "
            "Empty patch tests the unchanged base, NOT your current workspace. Obtain a diff against your initial "
            "snapshot; include new files explicitly. No hidden tests or private evaluator feedback. "
            "Final scoring uses the actual stopped workspace, not this submitted patch.",
            "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
                "patch": {"type": "string", "maxLength": 262144},
                "paths": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "string"}},
                "keyword": {"type": ["string", "null"], "maxLength": 256},
                "max_failures": {"type": "integer", "minimum": 0, "maximum": 10}}}}]

    def run_tests(self, arguments):
        patch, pytest = options(arguments)
        if self.calls >= 20:
            raise ValueError("public-test call budget exhausted")
        self.calls += 1
        source = self.preset["source"]
        payload = {"format": "atmem-public-patch-tests-v1", "base_commit": source["base_commit"],
            "public_base_files_base64": source["files_base64"], "public_base_modes": source["modes"],
            "patch": patch, "pytest": pytest}
        name = "atmem-reference-control-" + uuid4().hex
        command = helpers.worker_command(self.preset["image"], name, self.preset["worker_source"])
        command[command.index("--label") + 1] = "atmem.benchmark=common-public-tests-v1"
        self.record("public_tests.request", {"call": self.calls, "arguments": arguments, "command": command})
        result = helpers.execute_worker(command, payload, name)
        receipt = self.record("public_tests.completed", {"call": self.calls, "result": result})
        worker = result.get("worker", {})
        raw = base64.b64decode(worker.get("output_base64", ""), validate=True)
        succeeded = (result.get("exit_code") == 0 and not result.get("reason") and not worker.get("reason")
            and worker.get("original_git_object_store_removed") is True and worker.get("evaluator_material_received") is False
            and worker.get("output_truncated") is False and worker.get("patch_sha256") == sha256(patch.encode()).hexdigest()
            and isinstance(worker.get("candidate_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", worker["candidate_sha256"])
            and isinstance(worker.get("tested_candidate_files_base64"), dict))
        return {"status": "executed" if succeeded else "unavailable", "test_exit_code": worker.get("exit_code"),
            "reason": result.get("reason") or worker.get("reason") or (None if succeeded else "public_worker_contract"),
            "patch_sha256": sha256(patch.encode()).hexdigest(),
            "tested_candidate_sha256": worker.get("candidate_sha256"), "output_tail": raw[-12000:].decode(errors="replace"),
            "output_bytes": worker.get("output_bytes", len(raw)), "display_truncated": len(raw) > 12000,
            "worker_output_truncated": worker.get("output_truncated"), "evidence_object_id": receipt["object_id"],
            "assurance": "public_tests_of_supplied_patch_not_current_agent_worktree_or_hidden_grading"}

    def _call_tool(self, request_id, name, arguments):
        if name != "run_public_tests":
            return _error(request_id, -32602, "unknown public-test tool")
        try:
            answer = self.run_tests(arguments)
        except ValueError:
            return _error(request_id, -32602, "invalid public-test request or exhausted budget")
        except Exception:
            # No plaintext fallback or reflection of private runtime paths.
            return _error(request_id, -32603, "public tests unavailable; protected result not released")
        return _result(request_id, {"content": [{"type": "text", "text": json.dumps(answer)}], "isError": False})
