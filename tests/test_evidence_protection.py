from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from atmem.core.canonical import canonical_json

from atmem.control.manager import ControlPlaneManager
from atmem.control.store import ControlStore, ENCRYPTED_CONTROL_MAGIC
from atmem.evidence import (
    CaptureMode,
    EvidenceOperation,
    EvidencePrincipal,
    EvidenceRole,
    EvidenceScope,
)
from atmem.evidence.crypto import (
    decrypt_export,
    encrypted_export,
    generate_recipient_keypair,
    generate_signing_keypair,
    open_json,
    seal_json,
    unwrap_data_key,
    wrap_data_key,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _manager(tmp_path: Path) -> ControlPlaneManager:
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "control",
        subject_id="test-subject",
        memory_db=tmp_path / "memory.db",
    )
    manager.configure_agent_topology(
        [{"agent_id": "main", "workspace": str(tmp_path), "is_default": True}]
    )
    return manager


def _principal(role: EvidenceRole, *, subject: str = "test-subject") -> EvidencePrincipal:
    return EvidencePrincipal(
        f"test-{role.value}", role, EvidenceScope("local", subject)
    )


def _record(manager: ControlPlaneManager, run_id: str = "run-secret") -> dict:
    return manager.record_blackbox_event(
        event_type="tool.requested",
        run_id=run_id,
        execution_id=run_id,
        event_id=f"event-{run_id}",
        producer_instance_id="fixture",
        producer_epoch="epoch-1",
        producer_sequence=1,
        event_time="2026-09-13T01:02:03.000Z",
        subject_id="test-subject",
        agent_id="main",
        payload={
            "tool_name": "browser.open",
            "params_sha256": "1" * 64,
            "param_keys": ["url"],
            "_atmem_evidence": {
                "parts": [
                    {"type": "text", "text": "PLANTED-PROMPT-ALPHA"},
                    {
                        "type": "image",
                        "mime_type": "image/png",
                        "data_base64": "UE5HLVNFQ1JFVC1CWVRFUw==",
                    },
                    {
                        "type": "audio",
                        "mime_type": "audio/wav",
                        "data_base64": "V0FWLVNFQ1JFVC1CWVRFUw==",
                    },
                    {
                        "type": "video",
                        "mime_type": "video/mp4",
                        "data_base64": "TVA0LVNFQ1JFVC1CWVRFUw==",
                    },
                ],
                "params": {"url": "https://secret.example/private?q=alpha"},
            },
        },
    )


def test_role_matrix_is_closed_and_plaintext_export_is_collector_only() -> None:
    target = EvidenceScope("local", "test-subject", run_id="run-1")
    expected = {
        EvidenceRole.VIEWER: {EvidenceOperation.VIEW, EvidenceOperation.SEARCH},
        EvidenceRole.INVESTIGATOR: {
            EvidenceOperation.VIEW,
            EvidenceOperation.SEARCH,
            EvidenceOperation.RECONSTRUCT,
            EvidenceOperation.REPLAY_MANIFEST,
            EvidenceOperation.ENCRYPTED_EXPORT,
        },
        EvidenceRole.EVIDENCE_COLLECTOR: set(EvidenceOperation),
    }
    for role in EvidenceRole:
        principal = _principal(role)
        for operation in EvidenceOperation:
            if operation in expected[role]:
                principal.authorize(operation, target)
            else:
                with pytest.raises(PermissionError):
                    principal.authorize(operation, target)
    with pytest.raises(PermissionError):
        _principal(EvidenceRole.EVIDENCE_COLLECTOR, subject="other").authorize(
            EvidenceOperation.VIEW, target
        )


def test_aes_gcm_round_trip_and_tamper_rejection() -> None:
    key = bytes(range(32))
    nonce, ciphertext = seal_json(key, "obj-test", {"secret": "alpha"})
    assert open_json(key, "obj-test", nonce, ciphertext) == {"secret": "alpha"}
    damaged = bytearray(ciphertext)
    damaged[-1] ^= 1
    with pytest.raises(Exception):
        open_json(key, "obj-test", nonce, bytes(damaged))
    # NIST SP 800-38D, Test Case 13: 256-bit key, 96-bit IV, empty plaintext/AAD.
    assert AESGCM(bytes(32)).encrypt(bytes(12), b"", b"").hex() == "530f8afbc74536b9a963b4f1c4cb738b"
    wrap_nonce, wrapped = wrap_data_key(key, "slot-test", bytes(reversed(range(32))))
    assert unwrap_data_key(key, "slot-test", wrap_nonce, wrapped) == bytes(reversed(range(32)))
    with pytest.raises(Exception):
        unwrap_data_key(key, "slot-other", wrap_nonce, wrapped)
    nonce_2, _ = seal_json(key, "obj-test", {"secret": "alpha"})
    assert nonce_2 != nonce


def test_ml_kem_and_ml_dsa_export_round_trip_and_tamper_rejection() -> None:
    pytest.importorskip("pqcrypto")
    recipient_public, recipient_secret = generate_recipient_keypair()
    signing_public, signing_secret = generate_signing_keypair()
    bundle = encrypted_export(
        b"quantum-resistant evidence",
        recipient_public_key=recipient_public,
        signing_secret_key=signing_secret,
        signing_public_key=signing_public,
    )
    assert decrypt_export(bundle, recipient_secret) == b"quantum-resistant evidence"
    damaged = dict(bundle)
    damaged["ciphertext"] = ("A" if bundle["ciphertext"][0] != "A" else "B") + bundle["ciphertext"][1:]
    with pytest.raises(Exception):
        decrypt_export(damaged, recipient_secret)
    bad_signature = dict(bundle)
    bad_signature["signature"] = ("A" if bundle["signature"][0] != "A" else "B") + bundle["signature"][1:]
    with pytest.raises(Exception):
        decrypt_export(bad_signature, recipient_secret)
    downgraded = dict(bundle)
    downgraded["suite"] = "RSA+AES-256-GCM"
    with pytest.raises(ValueError, match="unsupported"):
        decrypt_export(downgraded, recipient_secret)
    unknown = dict(bundle)
    unknown["format"] = "atmem-encrypted-evidence-export-v999"
    with pytest.raises(ValueError, match="unsupported"):
        decrypt_export(unknown, recipient_secret)
    from pqcrypto.sign.ml_dsa_65 import sign
    import base64

    invalid_kem = dict(bundle)
    invalid_kem["kem_ciphertext"] = base64.b64encode(b"invalid-encapsulation").decode()
    unsigned = {key: value for key, value in invalid_kem.items() if key != "signature"}
    invalid_kem["signature"] = base64.b64encode(
        sign(signing_secret, canonical_json(unsigned).encode())
    ).decode()
    with pytest.raises(Exception):
        decrypt_export(invalid_kem, recipient_secret)


def test_post_quantum_provider_absence_fails_closed(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pqcrypto.kem.ml_kem_768", None)
    with pytest.raises(RuntimeError, match="post-quantum extra"):
        generate_recipient_keypair()


def test_default_full_capture_is_encrypted_and_byte_exact_inside_atmem(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    receipt = _record(manager)
    assert receipt["protected_evidence"]["capture_mode"] == "full"
    service = manager.evidence_service()
    events = service.events(_principal(EvidenceRole.VIEWER), "run-secret")
    exact = events[0]["envelope"]["evidence"]
    assert exact["parts"][0]["text"] == "PLANTED-PROMPT-ALPHA"
    assert exact["params"]["url"] == "https://secret.example/private?q=alpha"
    with service._store() as vault:
        assert vault.key_slot_count() >= 2

    planted = (
        b"PLANTED-PROMPT-ALPHA",
        b"https://secret.example/private?q=alpha",
        b"browser.open",
        b"run-secret",
        b"UE5HLVNFQ1JFVC1CWVRFUw==",
        b"V0FWLVNFQ1JFVC1CWVRFUw==",
        b"TVA0LVNFQ1JFVC1CWVRFUw==",
    )
    for path in Path(manager.state().control_dir).glob("**/*"):
        if path.is_file():
            raw = path.read_bytes()
            assert all(secret not in raw for secret in planted), path


def test_plaintext_control_store_migrates_atomically_to_application_encrypted_container(tmp_path: Path) -> None:
    control_root = tmp_path / "migrations"
    migration_id = "control_legacy_fixture"
    control_dir = control_root / migration_id
    path = control_dir / "evidence.db"
    plain = ControlStore(path)
    try:
        plain.create_migration(migration_id, "generic", "SECRET-SUBJECT")
        plain.append_evidence(
            migration_id,
            kind="agent_blackbox",
            body={"format": "fixture-v1", "run_id": "SECRET-RUN", "tool": "SECRET-TOOL"},
        )
    finally:
        plain.close()
    assert b"SECRET-RUN" in path.read_bytes()

    from atmem.evidence import EvidenceService

    service = EvidenceService(control_dir, vault_id=migration_id)
    migrated = ControlStore(path, encryption_key=service.storage_key())
    try:
        assert migrated.list_evidence(migration_id, kind="agent_blackbox")[0]["body"]["tool"] == "SECRET-TOOL"
    finally:
        migrated.close()
    raw = path.read_bytes()
    assert raw.startswith(ENCRYPTED_CONTROL_MAGIC)
    assert b"SQLite format 3" not in raw
    assert b"SECRET-SUBJECT" not in raw
    assert b"SECRET-RUN" not in raw
    assert b"SECRET-TOOL" not in raw
    inferred = ControlStore(path)
    try:
        assert inferred.list_evidence(migration_id, kind="agent_blackbox")[0]["body"]["run_id"] == "SECRET-RUN"
    finally:
        inferred.close()


def test_data_off_retains_encrypted_metadata_and_recorder_off_stores_nothing(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    service = manager.evidence_service()
    collector = _principal(EvidenceRole.EVIDENCE_COLLECTOR)
    service.set_capture_mode(collector, CaptureMode.METADATA)
    _record(manager, "run-metadata")
    reconstructed = service.reconstruct(
        _principal(EvidenceRole.INVESTIGATOR), "run-metadata"
    )
    assert reconstructed["reconstructable"] is False
    serialized = json.dumps(reconstructed)
    assert "PLANTED-PROMPT-ALPHA" not in serialized
    assert '"captured": false' in serialized.lower()

    before = service.protection_status()["stored_objects"]
    service.set_capture_mode(collector, CaptureMode.OFF)
    after_setting = service.protection_status()["stored_objects"]
    legacy_before = len(manager.blackbox_events())
    assert after_setting > before
    receipt = _record(manager, "run-off")
    assert receipt["recorded"] is False
    assert receipt["protected_evidence"]["captured"] is False
    assert service.protection_status()["stored_objects"] == after_setting
    assert len(manager.blackbox_events()) == legacy_before


def test_existing_vault_with_missing_key_is_locked_and_never_rekeyed(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager)
    service = manager.evidence_service()
    original = service.key_path.read_bytes()
    service.key_path.unlink()

    locked = manager.evidence_service()
    status = locked.protection_status()
    assert status["locked"] is True
    assert status["stored_objects"] is None
    assert not locked.key_path.exists()
    with pytest.raises(PermissionError, match="locked"):
        locked.capture({"run_id": "must-not-write", "subject_id": "test-subject"})
    assert not locked.key_path.exists()

    service.key_path.write_bytes(original)
    service.key_path.chmod(0o600)
    assert manager.evidence_service().protection_status()["locked"] is False


def test_collector_can_lock_and_unlock_while_viewer_cannot(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager)
    service = manager.evidence_service()
    credentials = service.create_demo_accounts(subject_id="test-subject")
    viewer = service.authenticate(credentials[0]["token"])
    collector = service.authenticate(credentials[2]["token"])
    with pytest.raises(PermissionError):
        service.lock(viewer, confirmation="LOCK EVIDENCE")
    assert service.lock(collector, confirmation="LOCK EVIDENCE")["locked"] is True
    locked = manager.evidence_service()
    collector_while_locked = locked.authenticate(credentials[2]["token"])
    with pytest.raises(PermissionError, match="locked"):
        locked.events(viewer, "run-secret")
    assert locked.unlock(collector_while_locked, confirmation="UNLOCK EVIDENCE")["locked"] is False
    assert manager.evidence_service().events(viewer, "run-secret")


def test_three_demo_accounts_and_plaintext_export_boundary(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager)
    service = manager.evidence_service()
    credentials = service.create_demo_accounts(subject_id="test-subject")
    assert [row["role"] for row in credentials] == [
        "viewer",
        "investigator",
        "evidence_collector",
    ]
    principals = {row["role"]: service.authenticate(row["token"]) for row in credentials}
    assert all(principals.values())
    assert service.events(principals["viewer"], "run-secret")
    with pytest.raises(PermissionError):
        service.reconstruct(principals["viewer"], "run-secret")
    assert service.reconstruct(principals["investigator"], "run-secret")["reconstructable"]
    for role in ("viewer", "investigator"):
        with pytest.raises(PermissionError):
            service.plaintext_export(
                principals[role], "run-secret", confirmation="EXPORT run-secret"
            )
    collector = principals["evidence_collector"]
    with pytest.raises(PermissionError):
        service.plaintext_export(collector, "run-secret", confirmation="yes")
    exported = service.plaintext_export(
        collector, "run-secret", confirmation="EXPORT run-secret"
    )
    assert b"PLANTED-PROMPT-ALPHA" in exported
    accounts_path = manager.state().control_dir
    raw_accounts = b"".join(
        path.read_bytes()
        for path in Path(accounts_path).parent.glob(".evidence-accounts/*")
    )
    assert b"atmem-viewer" not in raw_accounts
    assert credentials[0]["token"].encode() not in raw_accounts


def test_role_services_search_replay_grant_revoke_and_delete(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager)
    service = manager.evidence_service()
    credentials = service.create_demo_accounts(subject_id="test-subject")
    principals = {row["role"]: service.authenticate(row["token"]) for row in credentials}
    viewer = principals["viewer"]
    investigator = principals["investigator"]
    collector = principals["evidence_collector"]
    assert service.search(viewer, "secret.example")
    with pytest.raises(PermissionError):
        service.replay_manifest(viewer, "run-secret")
    assert service.replay_manifest(investigator, "run-secret")["executable"] is False
    granted = service.grant(
        collector,
        principal_id="case-reviewer",
        role=EvidenceRole.VIEWER,
        scope=EvidenceScope("local", "test-subject", run_id="run-secret"),
    )
    new_viewer = service.authenticate(granted["token"])
    assert service.events(new_viewer, "run-secret")
    assert service.revoke(collector, principal_id="case-reviewer") is True
    assert service.authenticate(granted["token"]) is None
    with pytest.raises(PermissionError):
        service.delete_run(investigator, "run-secret", confirmation="DELETE run-secret")
    result = service.delete_run(collector, "run-secret", confirmation="DELETE run-secret")
    assert result["deleted"]["objects"] == 1
    assert service.events(collector, "run-secret") == []


def test_collector_rotates_external_key_without_changing_evidence(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager)
    service = manager.evidence_service()
    credentials = service.create_demo_accounts(subject_id="test-subject")
    collector = service.authenticate(credentials[2]["token"])
    before_key = service.key_path.read_bytes()
    before = service.events(collector, "run-secret")
    with pytest.raises(PermissionError):
        service.rotate_key(_principal(EvidenceRole.INVESTIGATOR), confirmation="ROTATE EVIDENCE KEY")
    result = service.rotate_key(collector, confirmation="ROTATE EVIDENCE KEY")
    assert result["rotated"] is True
    assert service.key_path.read_bytes() != before_key
    reopened = manager.evidence_service()
    assert reopened.events(reopened.authenticate(credentials[2]["token"]), "run-secret")[0]["envelope"] == before[0]["envelope"]
    assert manager.blackbox_events(run_id="run-secret")


def test_interrupted_rotation_resumes_before_any_plaintext_access(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager)
    service = manager.evidence_service()
    credentials = service.create_demo_accounts(subject_id="test-subject")
    new_key = bytes(reversed(range(32)))
    service._write_rotation_journal(new_key)
    with service._store() as store:
        store.rotate_key(new_key)
    # Simulate process death before account re-encryption and key-file switch.
    resumed = manager.evidence_service()
    assert resumed.rotation_path.exists() is False
    assert resumed._key == new_key
    investigator = resumed.authenticate(credentials[1]["token"])
    assert resumed.reconstruct(investigator, "run-secret")["reconstructable"] is True


def test_dead_agent_recovery_uses_only_encrypted_store_and_authorized_key(tmp_path: Path) -> None:
    manager = _manager(tmp_path / "source")
    _record(manager)
    source = manager.evidence_service()
    credentials = source.create_demo_accounts(subject_id="test-subject")

    recovery_root = tmp_path / "recovered" / "vault"
    recovery_root.mkdir(parents=True)
    shutil.copy2(source.vault_path, recovery_root / "protected-evidence.db")
    recovery_key = recovery_root.parent / ".evidence-keys" / "recovered.key"
    recovery_key.parent.mkdir()
    shutil.copy2(source.key_path, recovery_key)
    recovery_identity_key = recovery_root.parent / ".evidence-identity-keys" / "recovered.key"
    recovery_identity_key.parent.mkdir()
    shutil.copy2(source.identity_key_path, recovery_identity_key)
    recovery_accounts = recovery_root.parent / ".evidence-accounts" / "recovered.json"
    recovery_accounts.parent.mkdir()
    shutil.copy2(source.accounts_path, recovery_accounts)

    from atmem.evidence import EvidenceService

    recovered = EvidenceService(recovery_root, vault_id="recovered")
    investigator = recovered.authenticate(credentials[1]["token"])
    story = recovered.reconstruct(investigator, "run-secret")
    assert story["reconstructable"] is True
    assert story["events"][0]["envelope"]["evidence"]["parts"][0]["text"] == "PLANTED-PROMPT-ALPHA"

    recovery_key.unlink()
    locked = EvidenceService(recovery_root, vault_id="recovered")
    assert locked.protection_status()["locked"] is True
    with pytest.raises(PermissionError, match="locked"):
        locked.reconstruct(_principal(EvidenceRole.INVESTIGATOR), "run-secret")


def test_investigator_recipient_export_uses_ml_kem_and_ml_dsa(tmp_path: Path) -> None:
    pytest.importorskip("pqcrypto")
    manager = _manager(tmp_path)
    _record(manager)
    service = manager.evidence_service()
    recipient_public, recipient_secret = generate_recipient_keypair()
    signing_public, signing_secret = generate_signing_keypair()
    bundle = service.recipient_export(
        _principal(EvidenceRole.INVESTIGATOR),
        "run-secret",
        recipient_public_key=recipient_public,
        signing_secret_key=signing_secret,
        signing_public_key=signing_public,
    )
    decoded = json.loads(decrypt_export(bundle, recipient_secret))
    assert decoded[0]["envelope"]["evidence"]["parts"][0]["text"] == "PLANTED-PROMPT-ALPHA"


def test_evidence_cli_creates_accounts_and_enforces_plaintext_export(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager)
    state = str(manager.state_path)

    def cli(*arguments: str) -> dict:
        result = subprocess.run(
            [sys.executable, "-m", "atmem.cli", "evidence", *arguments],
            cwd=Path(__file__).parents[1],
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    credentials = cli("create-test-accounts", "--state", state)
    tokens = {row["role"]: row["token"] for row in credentials["accounts"]}
    viewed = cli(
        "show", "--state", state, "--token", tokens["viewer"], "run-secret"
    )
    assert viewed["events"][0]["envelope"]["evidence"]["parts"][0]["text"] == "PLANTED-PROMPT-ALPHA"
    denied = subprocess.run(
        [
            sys.executable,
            "-m",
            "atmem.cli",
            "evidence",
            "export-plaintext",
            "--state",
            state,
            "--token",
            tokens["investigator"],
            "run-secret",
            "--confirm",
            "EXPORT run-secret",
            "--output",
            str(tmp_path / "denied.json"),
        ],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
    )
    assert denied.returncode != 0
    assert not (tmp_path / "denied.json").exists()
    exported = cli(
        "export-plaintext",
        "--state",
        state,
        "--token",
        tokens["evidence_collector"],
        "run-secret",
        "--confirm",
        "EXPORT run-secret",
        "--output",
        str(tmp_path / "collector.json"),
    )
    assert exported["exported"] is True
    assert b"PLANTED-PROMPT-ALPHA" in (tmp_path / "collector.json").read_bytes()
    assert (tmp_path / "collector.json").stat().st_mode & 0o077 == 0


def test_interrupted_plaintext_stream_records_denial_and_leaves_cleanup_to_surface(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager)
    service = manager.evidence_service()
    credentials = service.create_demo_accounts(subject_id="test-subject")
    collector = service.authenticate(credentials[2]["token"])
    stream = service.iter_plaintext_export(
        collector, "run-secret", confirmation="EXPORT run-secret"
    )
    assert next(stream) == b"[\n"
    stream.close()
    with service._store() as store:
        audits = [row for row in store.documents() if row.get("record_type") == "access"]
    assert any(
        row.get("operation") == "plaintext_export"
        and row.get("allowed") is False
        and row.get("detail", {}).get("interrupted") is True
        for row in audits
    )
