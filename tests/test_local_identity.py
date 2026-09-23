from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

import pytest

from atmem.identity import LocalIdentityService, normalize_username, validate_password
from atmem.identity.store import EncryptedIdentityDocument


def test_bootstrap_dashboard_url_keeps_secret_out_of_http_request() -> None:
    from atmem.cli import _bootstrap_dashboard_url

    value = _bootstrap_dashboard_url(
        "http://127.0.0.1:8766/",
        {"username": "administrator", "password": "temporary secret + value"},
    )

    request_url, fragment = value.split("#", 1)
    assert request_url == "http://127.0.0.1:8766/"
    assert "password" not in request_url
    assert "bootstrap=1" in fragment
    assert "password=temporary+secret+%2B+value" in fragment


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 13, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value


def service(tmp_path: Path, clock: Clock | None = None) -> LocalIdentityService:
    root = tmp_path / "control"
    root.mkdir()
    return LocalIdentityService(root, vault_id="test-vault", subject_id="owner", clock=clock or Clock())


def bootstrap_login(identity: LocalIdentityService):
    bootstrap = identity.bootstrap()
    return bootstrap, identity.login(bootstrap["username"], bootstrap["password"])


def test_username_and_password_policy_is_simple_and_explicit() -> None:
    assert normalize_username(" Audit.Team-1 ") == "audit.team-1"
    for invalid in ("ab", "space name", "ümlaut", "-prefix"):
        with pytest.raises(ValueError):
            normalize_username(invalid)
    validate_password("a", "owner")
    validate_password("owner", "owner")
    validate_password("password", "owner")
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_password("", "owner")


def test_bootstrap_is_one_time_encrypted_and_forces_change(tmp_path: Path) -> None:
    identity = service(tmp_path)
    created = identity.bootstrap()
    assert created["created"] is True
    assert created["username"] == "administrator"
    assert len(created["password"]) >= 32
    assert identity.bootstrap() == {"created": False, "username": "administrator", "password": None}
    session = identity.login("administrator", created["password"])
    assert session["account"]["role"] == "administrator"
    assert session["account"]["password_change_required"] is True
    stolen = identity.accounts.path.read_bytes() + identity.sessions.path.read_bytes()
    for planted in (b"administrator", created["password"].encode(), b"login", b"role"):
        assert planted not in stolen


def test_password_change_rotates_session_and_expiry_is_enforced(tmp_path: Path) -> None:
    clock = Clock()
    identity = service(tmp_path, clock)
    bootstrap, first = bootstrap_login(identity)
    changed = identity.change_password(first["session_token"], "", "A much better local password 42!")
    assert changed["session_token"] != first["session_token"]
    assert identity.authenticate_session(first["session_token"]) is None
    assert changed["account"]["password_change_required"] is False
    clock.value += timedelta(minutes=31)
    assert identity.authenticate_session(changed["session_token"]) is None


def test_administrator_creates_roles_and_last_admin_is_protected(tmp_path: Path) -> None:
    identity = service(tmp_path)
    bootstrap, first = bootstrap_login(identity)
    admin = identity.change_password(first["session_token"], bootstrap["password"], "A much better local password 42!")
    viewer = identity.create_user(admin["session_token"], "viewer.one", "viewer", display_name="Evidence Viewer")
    investigator = identity.create_user(admin["session_token"], "investigator.one", "investigator")
    collector = identity.create_user(admin["session_token"], "collector.one", "evidence_collector")
    assert {viewer["role"], investigator["role"], collector["role"]} == {"viewer", "investigator", "evidence_collector"}
    with pytest.raises(ValueError, match="final enabled Administrator"):
        identity.update_user(admin["session_token"], "administrator", enabled=False)
    reset = identity.reset_password(admin["session_token"], "viewer.one")
    assert reset["password_change_required"] is True
    assert identity.login("viewer.one", reset["temporary_password"])["account"]["role"] == "viewer"


def test_login_throttles_and_recovery_revokes_sessions(tmp_path: Path) -> None:
    identity = service(tmp_path)
    bootstrap, session = bootstrap_login(identity)
    for _ in range(4):
        with pytest.raises(PermissionError, match="incorrect"):
            identity.login("administrator", "not the password")
    with pytest.raises(PermissionError, match="incorrect"):
        identity.login("administrator", "not the password")
    with pytest.raises(PermissionError, match="temporarily"):
        identity.login("administrator", bootstrap["password"])
    recovered = identity.recover_administrator("RECOVER LOCAL ADMINISTRATOR")
    assert identity.authenticate_session(session["session_token"]) is None
    assert identity.login(recovered["username"], recovered["temporary_password"])["account"]["password_change_required"] is True


@pytest.mark.skipif(os.name != "nt", reason="Windows replace semantics")
def test_identity_document_retries_transient_windows_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = EncryptedIdentityDocument(
        tmp_path / "identity.json", bytes(range(32)), "identity", {"users": []}
    )
    real_replace = os.replace
    attempts = 0

    def transient_replace(source: str | Path, destination: str | Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("file is temporarily busy")
        real_replace(source, destination)

    monkeypatch.setattr("atmem.identity.store.os.replace", transient_replace)
    monkeypatch.setattr("atmem.identity.store.time.sleep", lambda _seconds: None)

    document.write({"users": [{"id": "owner"}]})

    assert attempts == 3
    assert document.load() == {"users": [{"id": "owner"}]}
