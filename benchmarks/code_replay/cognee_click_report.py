"""Read-only result audit plus explicit recipient-encrypted benchmark backup."""
from datetime import datetime
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.cognee_click_study import ROOT, RUN, WHEEL, COGNEE


def artifact_audit(frozen, attempt):
    """Do not change original grades; attribute pre-dispatch indexer files."""
    case, = [c for c in frozen["envelope"]["payload"]["cases"] if c["arm"] == "cognee"]
    match = re.search(r"workspace=PosixPath\('([^']+)'\)", case["session"])
    if not match:
        raise ValueError("explicit frozen solver workspace required")
    root = Path(match[1])
    freeze_time = datetime.fromisoformat(frozen["envelope"]["event_time"]).timestamp()
    changed = attempt["changed_paths"]
    artifacts = [name for name in changed if name.startswith(".enola/")]
    expected = {"extractor_cache.json", "facts.jsonl", "insights.json", "llm_context.md",
                "receipt.json", "run.json", "snapshot.meta.json"}
    facts = []
    for name in artifacts:
        path = root / name
        stat = path.stat()
        facts.append({"path": name, "sha256": sha256(path.read_bytes()).hexdigest(),
            "bytes": stat.st_size, "ctime": stat.st_ctime, "mtime": stat.st_mtime,
            "ctime_before_freeze": stat.st_ctime < freeze_time, "mtime_before_freeze": stat.st_mtime < freeze_time})
    unexpected = [name for name in changed if not name.startswith((".enola/", "src/click/", "tests/"))]
    verified = ({Path(x["path"]).name for x in facts} == expected and not unexpected
        and all(x["ctime_before_freeze"] and x["mtime_before_freeze"] for x in facts))
    return {"verified_unchanged_pre_dispatch_indexer_artifacts": verified, "artifacts": facts,
            "unexpected_paths": unexpected, "freeze_timestamp": freeze_time,
            "raw_policy_flag_preserved": True, "model_or_grade_retries": 0}


def main():
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / "vault", vault_id=RUN, scope=scope)
    rows = vault.inspect(principal, RUN)
    done, = [r["envelope"]["payload"] for r in rows if r["envelope"]["event_type"] == "comparison.completed"]
    frozen, = [r for r in rows if r["envelope"]["event_type"] == "comparison.frozen"]
    attempts = {r["envelope"]["payload"]["arm"]: r["envelope"]["payload"] for r in rows if r["envelope"]["event_type"] == "agent.attempt"}
    audit = artifact_audit(frozen, attempts["cognee"])
    cg = subprocess.run([str(COGNEE), "-I", "-c",
        "import importlib.metadata as m,json;print(json.dumps(sorted((d.metadata['Name'],d.version) for d in m.distributions())))"], capture_output=True, check=True)
    identity = subprocess.check_output(["git", "-C", "/tmp/atmem-code-research.yKNuul/cognee", "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "-C", "/tmp/atmem-code-research.yKNuul/cognee", "status", "--porcelain"], text=True)
    source_check = subprocess.run([str(COGNEE), "-I", "-c", """
import importlib.metadata as m,json
from hashlib import sha256
from pathlib import Path
source=Path('/tmp/atmem-code-research.yKNuul/cognee/cognee')
installed=Path(m.distribution('cognee').locate_file('cognee'))
files={str(p.relative_to(source)):sha256(p.read_bytes()).hexdigest() for p in source.rglob('*.py')}
mismatches=[name for name,digest in files.items() if not (installed/name).is_file() or sha256((installed/name).read_bytes()).hexdigest()!=digest]
print(json.dumps({'python_source_files':len(files),'mismatches':mismatches,'manifest_sha256':sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()}))
"""], capture_output=True, check=True)
    installed_identity = json.loads(source_check.stdout)
    if installed_identity["mismatches"]:
        raise RuntimeError("installed Cognee differs from pinned upstream Python source")
    calls = {arm: [{"tool": c.get("tool"), "status": c.get("status"), "arguments": c.get("arguments"),
                       "error": c.get("error"), "result": c.get("result")} for c in a["graph_calls"]] for arm, a in attempts.items()}
    vault.capture(run_id=RUN, kind="comparison.artifact_policy_audit", principal=principal,
        payload={"audit": audit, "upstream_revision": identity, "upstream_worktree_clean": not status,
                 "cognee_dependencies": json.loads(cg.stdout), "installed_cognee_identity": installed_identity, "tool_calls": calls,
                 "timing": "identity_and_artifact_audit_after_all_attempts_not_prefreeze_measurement"})
    print(json.dumps({"audit": audit, "installed_cognee_identity": installed_identity, "calls": calls, "rows": done["rows"]}), flush=True)
    if not audit["verified_unchanged_pre_dispatch_indexer_artifacts"]:
        raise RuntimeError("cannot attribute Cognee's policy flag solely to unmodified setup artifacts")
    if "--archive" in sys.argv:
        from benchmarks.code_replay.control_report import archive_all
        destination = Path("/Volumes/MEM/AtMem-Code-Replay-20261017/protected-cognee-short-20261018")
        keys = ROOT.parent / "keys-cognee-short-20261018"
        if not Path("/Volumes/MEM").is_mount() or destination.exists() or keys.exists():
            raise ValueError("mounted MEM and fresh, separate archive/key destinations required")
        archive_all(vault, principal, {}, {"wheel_path": str(WHEEL)}, destination, keys,
                    protocol_id=RUN, run_ids=[])


if __name__ == "__main__":
    main()
