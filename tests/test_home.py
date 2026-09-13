from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope, EvidenceService
from atmem.home import ArtifactVault, HomeLayout, HomeService, resolve_home
from atmem.home.service import _digest_path
from atmem.control.manager import ControlPlaneManager
from atmem.identity import LocalIdentityService


def test_home_precedence_and_safe_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    environment = tmp_path / "environment"
    explicit = tmp_path / "explicit"
    monkeypatch.setenv("ATMEM_HOME", str(environment))
    assert resolve_home() == environment
    assert resolve_home(explicit) == explicit

    layout = HomeLayout.selected(explicit)
    layout.initialize_directories()
    assert layout.artifacts.is_dir()
    with pytest.raises(ValueError, match="safe relative"):
        layout.path("../escaped")
    (explicit / "linked").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="symlink"):
        layout.path("linked/private.db")


def test_manifest_is_content_free_and_portable(tmp_path: Path) -> None:
    planted = "private-user-prompt-and-url"
    home = HomeService(tmp_path / "atmem-home")
    manifest = home.initialize()
    raw = home.layout.manifest.read_text(encoding="utf-8")
    assert manifest["format"] == "atmem-home-manifest-v1"
    assert planted not in raw
    assert home.verify()["verified"] is True

    copied = tmp_path / "copied-home"
    shutil.copytree(home.layout.root, copied)
    recovered = HomeService(copied)
    assert recovered.verify()["instance_id"] == manifest["instance_id"]


def test_global_cli_home_override_wins_over_environment(tmp_path: Path) -> None:
    environment = tmp_path / "environment-home"
    explicit = tmp_path / "explicit-home"
    result = subprocess.run(
        [sys.executable, "-m", "atmem.cli", "--home", str(explicit), "home", "init", "--json"],
        cwd=Path(__file__).parents[1],
        env={**__import__("os").environ, "ATMEM_HOME": str(environment)},
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["format"] == "atmem-home-manifest-v1"
    assert (explicit / "manifest.json").is_file()
    assert not environment.exists()


def test_non_default_home_routes_durable_component_defaults(tmp_path: Path) -> None:
    selected = tmp_path / "selected-home"
    code = """
import json
from atmem.control.manager import DEFAULT_CONTROL_ROOT, DEFAULT_STATE_PATH
from atmem.control.atbot_service import DEFAULT_ROOT as ATBOT_ROOT
from atmem.core.keys import DEFAULT_KEY_PATH
from atmem.dashboard_daemon import DEFAULT_DAEMON_STATE
from atmem.delegated.config import DEFAULT_CONFIG_PATH
from atmem.provider_adapters.lifecycle import provider_root
print(json.dumps([str(value) for value in (
    DEFAULT_CONTROL_ROOT, DEFAULT_STATE_PATH, ATBOT_ROOT, DEFAULT_KEY_PATH,
    DEFAULT_DAEMON_STATE, DEFAULT_CONFIG_PATH, provider_root(),
)]))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parents[1],
        env={**__import__("os").environ, "ATMEM_HOME": str(selected)},
        text=True,
        capture_output=True,
        check=True,
    )
    for value in json.loads(result.stdout):
        assert Path(value).is_relative_to(selected)


def test_quiescent_snapshot_is_verified_and_rejects_active_writer(tmp_path: Path) -> None:
    source = HomeService(tmp_path / "source")
    source.initialize()
    (source.layout.path("memory/example.bin")).write_bytes(b"portable-state")
    snapshot = source.snapshot(tmp_path / "snapshot")
    assert snapshot["verified"] is True
    assert (tmp_path / "snapshot" / "memory" / "example.bin").read_bytes() == b"portable-state"

    daemon = source.layout.path("runtime/dashboard-daemon.json")
    daemon.write_text(json.dumps({
        "format": "atmem-dashboard-daemon-v1",
        "pid": __import__("os").getpid(),
        "hostname": socket.gethostname(),
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="active dashboard writer"):
        source.snapshot(tmp_path / "blocked-snapshot")


def test_home_inventory_digest_reads_at_most_one_mib_per_chunk() -> None:
    requested: list[int] = []

    class Reader(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            requested.append(size)
            return super().read(size)

    class LargeLogicalFile:
        name = "large-logical-file"

        @staticmethod
        def is_file() -> bool:
            return True

        @staticmethod
        def is_symlink() -> bool:
            return False

        @staticmethod
        def open(mode: str) -> Reader:
            assert mode == "rb"
            return Reader(b"x" * (2 * 1024 * 1024 + 17))

    digest, files, byte_count = _digest_path(LargeLogicalFile())  # type: ignore[arg-type]
    assert len(digest) == 64
    assert files == 1
    assert byte_count == 2 * 1024 * 1024 + 17
    assert requested and max(requested) == 1024 * 1024


def test_encrypted_artifact_round_trip_deduplicates_and_rejects_tamper(tmp_path: Path) -> None:
    plaintext = b"\x89PNG\r\n\x1a\nprivate-image-pixels"
    vault = ArtifactVault(tmp_path / "artifacts" / "sha256", b"k" * 32)
    first = vault.put_bytes(plaintext)
    second = vault.put_bytes(plaintext)
    assert first["plaintext_sha256"] == second["plaintext_sha256"]
    assert second["replayed"] is True
    assert vault.read(str(first["plaintext_sha256"])) == plaintext

    blob = tmp_path / str(first["relative_path"])
    raw = blob.read_bytes()
    assert plaintext not in raw
    blob.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    with pytest.raises(Exception):
        vault.read(str(first["plaintext_sha256"]))


def test_evidence_externalizes_and_authorized_restore_materializes_media(tmp_path: Path) -> None:
    control = tmp_path / "home" / "migrations" / "control_fixture"
    service = EvidenceService(control, vault_id="control_fixture", home_root=tmp_path / "home")
    image = b"\x89PNG\r\n\x1a\nexact-event-943-image"
    envelope = {
        "event_id": "event-943",
        "run_id": "run-943",
        "tenant_id": "local",
        "subject_id": "local-user",
        "evidence": {
            "parts": [{
                "type": "image",
                "mime_type": "image/png",
                "data_base64": base64.b64encode(image).decode("ascii"),
            }],
        },
    }
    receipt = service.capture(envelope)
    assert receipt["captured"] is True
    raw_db = service.vault_path.read_bytes()
    assert image not in raw_db

    principal = EvidencePrincipal(
        "administrator",
        EvidenceRole.ADMINISTRATOR,
        EvidenceScope("local", "local-user"),
    )
    restored = service.events(principal, "run-943")
    part = restored[0]["envelope"]["evidence"]["parts"][0]
    assert base64.b64decode(part["data_base64"]) == image
    assert part["artifact"]["relative_path"].startswith("artifacts/sha256/")

    copied = tmp_path / "copied"
    shutil.copytree(tmp_path / "home", copied)
    source_keys = control.parent / ".evidence-keys"
    source_identity = control.parent / ".evidence-identity-keys"
    # Existing beta key locations are inside the portable home and preserve
    # copied-home login/decryption until canonical key migration is committed.
    assert source_keys.is_dir()
    assert source_identity.is_dir()
    recovered = EvidenceService(
        copied / "migrations" / "control_fixture",
        vault_id="control_fixture",
        home_root=copied,
    )
    recovered_part = recovered.events(principal, "run-943")[0]["envelope"]["evidence"]["parts"][0]
    assert base64.b64decode(recovered_part["data_base64"]) == image


def test_legacy_migration_is_copy_first_and_source_preserving(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "memories.db").write_bytes(b"legacy-db")
    (legacy / "control-plane.json").write_text("{}", encoding="utf-8")
    destination = tmp_path / "portable"
    receipt = HomeService(legacy).migrate_legacy(destination)
    assert receipt["phase"] == "verify"
    assert receipt["source_preserved"] is True
    assert (legacy / "memories.db").read_bytes() == b"legacy-db"
    assert (destination / "memory" / "memories.db").read_bytes() == b"legacy-db"
    committed = HomeService(legacy).migrate_legacy(destination, commit=True)
    assert committed["phase"] == "commit"
    assert committed["mapping"][0]["content_sha256"]
    rollback_target = tmp_path / "rollback-generation"
    HomeService(legacy).migrate_legacy(rollback_target)
    rolled_back = HomeService(legacy).migrate_legacy(rollback_target, rollback=True)
    assert rolled_back["phase"] == "rolled_back"
    assert not rollback_target.exists()
    assert (legacy / "memories.db").is_file()


@pytest.mark.parametrize("phase", ("discover", "preflight", "copy", "verify", "switch"))
def test_legacy_migration_resumes_after_every_journal_boundary(
    tmp_path: Path, phase: str
) -> None:
    legacy = tmp_path / f"legacy-{phase}"
    legacy.mkdir()
    (legacy / "memories.db").write_bytes(b"canonical-memory")
    target = tmp_path / f"target-{phase}"
    with pytest.raises(RuntimeError, match="simulated migration interruption"):
        HomeService(legacy).migrate_legacy(
            target, commit=phase == "switch", _interrupt_after=phase
        )

    resumed = HomeService(legacy).migrate_legacy(target, commit=True)
    assert resumed["phase"] == "commit"
    assert resumed["source_preserved"] is True
    assert (legacy / "memories.db").read_bytes() == b"canonical-memory"
    assert (target / "memory" / "memories.db").read_bytes() == b"canonical-memory"


def test_adoption_rejects_a_live_local_writer(tmp_path: Path) -> None:
    home = HomeService(tmp_path / "home")
    home.initialize()
    home.layout.path("runtime/dashboard-daemon.json").write_text(json.dumps({
        "format": "atmem-dashboard-daemon-v1",
        "pid": __import__("os").getpid(),
        "hostname": socket.gethostname(),
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="active writer"):
        home.adopt(administrator_confirmed=True)


def test_copied_home_rebinds_runtime_and_accepts_original_administrator(tmp_path: Path) -> None:
    source = tmp_path / "source-home"
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=source / "control-plane.json",
        control_root=source / "migrations",
        memory_db=source / "memories.db",
    )
    bootstrap = manager.identity_service().bootstrap()
    copied = tmp_path / "target-home"
    shutil.copytree(source, copied)
    shutil.rmtree(source)

    preflight = HomeService(copied).prepare_restore()
    assert preflight["read_only_restore"] is True
    assert preflight["content_disclosed"] is False
    restored_manager = ControlPlaneManager(preflight["runtime_state"])
    rebound = restored_manager.state()
    assert Path(rebound.control_dir).is_relative_to(copied)
    login = restored_manager.identity_service().login(
        bootstrap["username"], bootstrap["password"], source="restore-test"
    )
    assert login["account"]["role"] == "administrator"


def test_adoption_requires_admin_and_rotates_target_sessions(tmp_path: Path) -> None:
    source = tmp_path / "canonical-source"
    HomeService(source).initialize()
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=source / "config" / "control-plane.json",
        control_root=source / "migrations",
        memory_db=source / "memory" / "memories.db",
    )
    bootstrap = manager.identity_service().bootstrap()
    copied = tmp_path / "canonical-copy"
    shutil.copytree(source, copied)
    preflight = HomeService(copied).prepare_restore()
    restored = ControlPlaneManager(preflight["runtime_state"])
    identity = restored.identity_service()
    temporary = identity.login(bootstrap["username"], bootstrap["password"])
    changed = identity.change_password(
        temporary["session_token"], bootstrap["password"], "portable-password"
    )
    with pytest.raises(PermissionError):
        HomeService(copied).adopt(administrator_confirmed=False)
    sessions = identity.revoke_all_sessions(changed["session_token"], reason="home-adoption")
    receipt = HomeService(copied).adopt(administrator_confirmed=True)
    assert sessions["revoked_sessions"] == 1
    assert identity.authenticate_session(changed["session_token"]) is None
    assert receipt["historical_evidence_rewritten"] is False
    assert json.loads((copied / "runtime" / "home-mode.json").read_text())["mode"] == "adopted_writable"


def test_dead_agent_multimodal_home_reconstructs_without_source_dependencies(
    tmp_path: Path,
) -> None:
    source = tmp_path / "dead-agent-source"
    HomeService(source).initialize()
    control = source / "migrations" / "control_dead_agent"
    identity = LocalIdentityService(
        control, vault_id="control_dead_agent", subject_id="owner"
    )
    bootstrap = identity.bootstrap()
    temporary = identity.login(bootstrap["username"], bootstrap["password"])
    signed_in = identity.change_password(
        temporary["session_token"], "", "portable-admin"
    )
    evidence = EvidenceService(
        control, vault_id="control_dead_agent", home_root=source
    )
    binary_parts = {
        "document": b"private-file-bytes",
        "image": b"\x89PNG\r\n\x1a\nprivate-image-bytes",
        "audio": b"RIFFprivate-audio-bytes",
        "video": b"\x00\x00\x00\x18ftypprivate-video-bytes",
    }
    parts = [
        {"type": "text", "text": "private recovery prompt"},
        {"type": "link", "url": "https://private.example.test/recovery"},
    ]
    mime = {
        "document": "application/octet-stream",
        "image": "image/png",
        "audio": "audio/wav",
        "video": "video/mp4",
    }
    parts.extend(
        {
            "type": kind,
            "mime_type": mime[kind],
            "data_base64": base64.b64encode(value).decode("ascii"),
        }
        for kind, value in binary_parts.items()
    )
    evidence.capture({
        "event_id": "dead-agent-event",
        "run_id": "dead-agent-run",
        "tenant_id": "local",
        "subject_id": "owner",
        "evidence": {"parts": parts},
    })

    copied = tmp_path / "dead-agent-recovered"
    shutil.copytree(source, copied)
    shutil.rmtree(source)
    # Nothing outside the copied home is available from this point onward.
    recovered_control = copied / "migrations" / "control_dead_agent"
    recovered_identity = LocalIdentityService(
        recovered_control, vault_id="control_dead_agent", subject_id="owner"
    )
    recovered_session = recovered_identity.login("administrator", "portable-admin")
    principal = recovered_identity.evidence_principal(recovered_session)
    recovered = EvidenceService(
        recovered_control, vault_id="control_dead_agent", home_root=copied
    ).events(principal, "dead-agent-run")
    recovered_parts = recovered[0]["envelope"]["evidence"]["parts"]

    assert recovered_parts[0]["text"] == "private recovery prompt"
    assert recovered_parts[1]["url"] == "https://private.example.test/recovery"
    for part in recovered_parts[2:]:
        assert base64.b64decode(part["data_base64"]) == binary_parts[part["type"]]
        assert part.get("artifact_recovery") != "inline_encrypted_evidence"
    stolen = b"".join(
        path.read_bytes() for path in copied.rglob("*") if path.is_file()
    )
    for secret in (
        b"administrator", b"portable-admin", b"private recovery prompt",
        b"private.example.test", *binary_parts.values(),
    ):
        assert secret not in stolen
