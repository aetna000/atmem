import pytest

from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from benchmarks.code_replay.atmem_bridge import ReplayEvidence


def test_replay_evidence_is_protected_audited_and_survives_fresh_service_instance(tmp_path):
    scope = EvidenceScope("benchmark", "operator", "click")
    principal = EvidencePrincipal("operator", EvidenceRole.ADMINISTRATOR, scope)
    payload = {"stdout": "PLANTED-CLICK-GRADING-EVIDENCE-20261017", "command": ["python", "-m", "pytest"], "exit_code": 1}
    root = tmp_path / "vault"
    evidence = ReplayEvidence(root, vault_id="click", scope=scope)
    receipt = evidence.capture(run_id="qualification", kind="grader.parent", payload=payload, principal=principal)
    assert receipt["encrypted"]
    for path in root.rglob("*"):
        if path.is_file():
            assert payload["stdout"].encode() not in path.read_bytes()
    restored = ReplayEvidence(root, vault_id="click", scope=scope)
    values = restored.inspect(principal, "qualification")
    assert values[0]["envelope"]["payload"] == payload
    assert not values[0]["envelope"].get("model_input_observed", False)
    viewer = EvidencePrincipal("viewer", EvidenceRole.VIEWER, scope)
    with pytest.raises(PermissionError):
        restored.inspect(viewer, "qualification")
    foreign = EvidencePrincipal("other", EvidenceRole.ADMINISTRATOR, EvidenceScope("benchmark", "other"))
    with pytest.raises(PermissionError):
        restored.inspect(foreign, "qualification")


def test_dead_solver_event_recovery_from_protected_backup_in_new_process(tmp_path):
    """Exact declared-event recovery, not complete unobserved model input."""
    import base64
    import json
    import os
    from pathlib import Path
    import shutil
    import subprocess
    import sys
    scope = EvidenceScope("benchmark", "operator", "click")
    principal = EvidencePrincipal("operator", EvidenceRole.ADMINISTRATOR, scope)
    home = tmp_path / "original-evidence"
    source = tmp_path / "fixture-agent-workspace"
    source.mkdir()
    (source / "log").write_text("fixture-agent-log-must-not-be-needed")
    payload = {"prompt": "PLANTED_DEAD_AGENT_PROMPT_20261017", "tool": {"arguments": ["pytest", "-q"],
               "result_base64": base64.b64encode(b"exact result\x00\xff").decode()}, "error": "original failure"}
    evidence = ReplayEvidence(home / "vault", vault_id="click", scope=scope)
    evidence.capture(run_id="dead-agent", kind="agent.fixture", payload=payload, principal=principal)
    backup = tmp_path / "supported-backup"
    shutil.copytree(home, backup)
    # Remove access by moving these exact test-owned directories, recoverably.
    source.rename(tmp_path / "retired-agent-workspace")
    home.rename(tmp_path / "retired-original-evidence")
    script = '''import json,sys
from pathlib import Path
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from atmem.evidence import EvidenceScope,EvidenceRole,EvidencePrincipal
s=EvidenceScope("benchmark","operator","click")
v=ReplayEvidence(Path(sys.argv[1])/"vault",vault_id="click",scope=s)
p=EvidencePrincipal("operator",EvidenceRole.ADMINISTRATOR,s)
print(json.dumps(v.inspect(p,"dead-agent")[0]["envelope"]["payload"]))
'''
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-c", script, str(backup)], cwd=root,
        env={"PATH": os.defpath, "PYTHONPATH": str(root)}, capture_output=True, check=True, timeout=30)
    assert json.loads(result.stdout) == payload
    for path in backup.rglob("*"):
        if path.is_file():
            assert payload["prompt"].encode() not in path.read_bytes()


def test_protected_export_and_scoped_delete_preserve_adjacent_run(tmp_path):
    from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair, decrypt_export
    scope = EvidenceScope("benchmark", "operator", "click")
    principal = EvidencePrincipal("operator", EvidenceRole.ADMINISTRATOR, scope)
    evidence = ReplayEvidence(tmp_path / "vault", vault_id="click", scope=scope)
    for run in ("delete-me", "keep-me"):
        evidence.capture(run_id=run, kind="agent.fixture", payload={"exact": "ORIGINAL_EVENT_BYTES"}, principal=principal)
    public, secret = generate_recipient_keypair()
    sign_public, sign_secret = generate_signing_keypair()
    bundle = evidence.service.recipient_export(principal, "delete-me", recipient_public_key=public,
        signing_public_key=sign_public, signing_secret_key=sign_secret)
    assert bundle["signing_public_key"] == __import__("base64").b64encode(sign_public).decode()
    raw = decrypt_export(bundle, recipient_secret_key=secret)
    assert b"ORIGINAL_EVENT_BYTES" in raw
    evidence.delete(principal, "delete-me", "DELETE delete-me")
    assert evidence.inspect(principal, "delete-me") == []
    assert evidence.inspect(principal, "keep-me")[0]["envelope"]["payload"] == {"exact": "ORIGINAL_EVENT_BYTES"}
