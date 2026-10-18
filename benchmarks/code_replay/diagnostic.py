"""Disjoint real-agent product diagnostic on AtMem's own new code, not Click.

Source-only RAM staging; a genuine bounded coding attempt, not performance data.
"""
import argparse
import base64
from pathlib import Path
import json
import shutil

from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.runner import allocate_session, run_cli


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ram-root", type=Path, required=True)
    parser.add_argument("--auth-file", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    session = allocate_session(args.ram_root, args.auth_file)
    root = args.source_root.resolve(strict=True)
    for source in sorted((root / "atmem").rglob("*.py")):
        if source.is_symlink():
            raise ValueError("source-only diagnostic does not follow links")
        target = session.workspace / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (session.workspace / "tests").mkdir()
    shutil.copyfile(root / "tests/test_knowledge_contracts.py", session.workspace / "tests/test_knowledge_contracts.py")
    shutil.copyfile(root / "LICENSE", session.workspace / "LICENSE")
    runtime = Path("/private/tmp/atmem-click-diagnostic-runtime-20261017")
    interpreter = Path("/private/tmp/atmem-click-interpreters-20261017/cpython-3.12.12-macos-aarch64-none")
    prompt = f'''Fix a real path-validation gap in this AtMem Code implementation. Repository-relative source paths can currently contain control characters, which makes displayed source locations ambiguous. Reject C0 controls and DEL in source_path while keeping valid Chinese, Arabic and other Unicode filenames usable. Add regression tests and run the relevant tests. Keep the change narrow; do not weaken secret screening or path traversal checks.

Use {runtime}/bin/python for Python and pytest. It has the required cryptography and pytest dependencies. Set PYTHONPATH to this working directory if needed; temporary files must stay inside this workspace. Work only on this source copy. Do not use network or inspect any other repository.

End with a JSON object containing summary (what you actually changed/observed) and paths (changed repository-relative paths). Do not claim any tests passed unless you ran them. This is a development qualification attempt, not a Click benchmark task.'''
    observed = run_cli(session, prompt, runtime_roots=(runtime, interpreter), max_seconds=150, max_tool_calls=20)
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    retained = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope).capture(
        run_id=session.root.name, kind="agent.disjoint_diagnostic", principal=principal,
        payload={"prompt": prompt, "workspace": str(session.workspace), "integration": observed["integration"],
                 "model": observed["model"], "exit_code": observed["exit_code"], "stop_reason": observed["stop_reason"],
                 "elapsed_ms": observed["elapsed_ms"], "tool_calls": observed["tool_calls"],
                 "stdout_base64": base64.b64encode(observed["stdout"]).decode(),
                 "stderr_base64": base64.b64encode(observed["stderr"]).decode(), "Click_target_trial": False})
    summaries = [e.get("item", {}).get("text", "") for e in observed["events"]
                 if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"]
    print(json.dumps({"session": session.root.name, "workspace": str(session.workspace), "exit_code": observed["exit_code"],
                      "tool_calls": observed["tool_calls"], "stop_reason": observed["stop_reason"],
                      "summary": summaries[-1] if summaries else None, "evidence": retained, "Click_target_trial": False}))


if __name__ == "__main__":
    main()
