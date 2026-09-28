from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

from atmem import Memory
from atmem.core.keys import (
    _read_file_key,
    initialize_encrypted_household,
    initialize_keys,
    key_status,
    migrate_plaintext_household,
    resolve_database_key,
    sqlcipher_runtime_status,
)
from atmem.core.storage import HouseholdLock, HouseholdPolicy
from atmem.evidence.crypto import load_or_create_key


def test_installed_encryption_gate_uses_the_installed_artifact() -> None:
    if os.environ.get("ATMEM_REQUIRE_INSTALLED_ARTIFACT") != "1":
        return
    import atmem

    module_path = Path(atmem.__file__).resolve()
    repository = Path(__file__).resolve().parents[1]
    assert not module_path.is_relative_to(repository), module_path
    assert "site-packages" in module_path.parts, module_path
    status = sqlcipher_runtime_status()
    assert status["available"] is True, status


@pytest.mark.skipif(os.name != "nt", reason="Windows permission semantics")
def test_evidence_key_can_be_reopened_on_windows(tmp_path: Path) -> None:
    key_path = tmp_path / "evidence.key"

    created = load_or_create_key(key_path)

    assert load_or_create_key(key_path) == created


def test_keys_init_is_inert_for_existing_plaintext_database(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "memory.db"
    memory = Memory(database)
    try:
        memory.remember("user", "I prefer TypeScript", force=True)
    finally:
        memory.close()
    before = database.read_bytes()
    key_path = tmp_path / "keys" / "db.key"
    monkeypatch.setattr("atmem.core.keys.DEFAULT_KEY_PATH", key_path)

    status = initialize_keys(database, backend="file")

    assert status["state"] == "plaintext"
    assert status["backend"] == "file"
    assert status["key_exposed"] is False
    assert database.read_bytes() == before
    if os.name != "nt":
        assert key_path.stat().st_mode & 0o777 == 0o600
    state = json.loads(Path(f"{database}.encryption.json").read_text(encoding="utf-8"))
    assert state["state"] == "plaintext"
    assert state["key_id"]
    assert state["control_kdf_salt"]
    reopened = Memory(database)
    try:
        assert reopened.recall("user", "TypeScript")
    finally:
        reopened.close()


def test_environment_key_overrides_recorded_backend(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "memory.db"
    key_path = tmp_path / "keys" / "db.key"
    monkeypatch.setattr("atmem.core.keys.DEFAULT_KEY_PATH", key_path)
    initialize_keys(database, backend="file")
    override = "ab" * 32
    monkeypatch.setenv("ATMEM_DB_KEY", override)

    policy = HouseholdPolicy.load(database)

    assert resolve_database_key(policy) == override
    assert key_status(database)["source"] == "environment"


def test_file_key_does_not_apply_posix_mode_rules_on_windows(
    tmp_path: Path, monkeypatch
) -> None:
    key_path = tmp_path / "db.key"
    key_path.write_text("ab" * 32 + "\n", encoding="utf-8")
    key_path.chmod(0o666)
    monkeypatch.setattr("atmem.core.keys.os.name", "nt")

    assert _read_file_key(key_path) == "ab" * 32


def test_runtime_refuses_in_progress_or_header_mismatch(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    memory = Memory(database)
    memory.close()
    policy = HouseholdPolicy.load(database)
    prepared = HouseholdPolicy(
        policy.database_path,
        policy.state_path,
        policy.lock_path,
        "encrypting",
        "file",
        "key_test",
        "cd" * 32,
    )
    prepared.write()
    with pytest.raises(RuntimeError, match="runtime access is fail-closed"):
        Memory(database)

    prepared.with_state("encrypted").write()
    with pytest.raises(RuntimeError, match="plaintext SQLite header"):
        Memory(database)


def test_household_lock_blocks_migration_and_new_holders(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    policy = HouseholdPolicy.load(database)
    memory = Memory(database)
    try:
        with pytest.raises(RuntimeError, match="another process"):
            HouseholdLock(policy, exclusive=True).acquire()
    finally:
        memory.close()

    migration = HouseholdLock(policy, exclusive=True).acquire()
    try:
        with pytest.raises(RuntimeError, match="another process"):
            Memory(database)
    finally:
        migration.close()


def test_sqlcipher_status_is_explicit_when_runtime_is_missing(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sqlcipher3", None)

    status = sqlcipher_runtime_status()

    assert status["available"] is False
    assert status["reason"] == "sqlcipher3_not_installed"


def test_fresh_encrypted_household_bootstrap_is_fail_closed(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fresh.db"
    key_path = tmp_path / "keys" / "db.key"
    monkeypatch.setattr("atmem.core.keys.DEFAULT_KEY_PATH", key_path)

    class FakeConnection:
        def __init__(self, path: str) -> None:
            self.path = Path(path)

        def execute(self, _sql: str, _parameters=()):
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self.path.write_bytes(b"SQLCIPHER\x00fixture")
            return SimpleNamespace(fetchone=lambda: (1,))

        def commit(self) -> None:
            return None

        def close(self) -> None:
            return None

    dbapi2 = SimpleNamespace(
        sqlite_version="fixture-sqlcipher",
        connect=lambda path: FakeConnection(path),
    )
    module = ModuleType("sqlcipher3")
    module.dbapi2 = dbapi2  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sqlcipher3", module)

    result = initialize_encrypted_household(database)

    assert result["created"] is True
    assert result["state"] == "encrypted"
    assert result["key_exposed"] is False
    assert database.read_bytes().startswith(b"SQLCIPHER")
    policy = HouseholdPolicy.load(database)
    assert policy.state == "encrypted"
    if os.name != "nt":
        assert key_path.stat().st_mode & 0o777 == 0o600


def test_encrypted_bootstrap_refuses_existing_plaintext(tmp_path: Path) -> None:
    database = tmp_path / "existing.db"
    memory = Memory(database)
    memory.close()

    with pytest.raises((RuntimeError, ValueError), match="SQLCipher|plaintext"):
        initialize_encrypted_household(database)


def test_plaintext_migration_requires_sqlcipher_without_changing_source(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "existing.db"
    memory = Memory(database)
    memory.close()
    before = database.read_bytes()
    monkeypatch.setitem(sys.modules, "sqlcipher3", None)

    with pytest.raises(RuntimeError, match="requires sqlcipher3"):
        migrate_plaintext_household(database)

    assert database.read_bytes() == before
    assert HouseholdPolicy.load(database).state == "plaintext"


def test_migration_uses_full_sqlite_and_sqlcipher_integrity_checks() -> None:
    import inspect

    source = inspect.getsource(migrate_plaintext_household)
    assert "PRAGMA integrity_check" in source
    assert "PRAGMA cipher_integrity_check" in source
    assert "PRAGMA cipher_version" in source


def test_cipher_integrity_check_requires_supported_sqlcipher_version() -> None:
    from atmem.core.keys import _require_cipher_integrity_version

    assert _require_cipher_integrity_version("4.12.0 community") == (4, 12, 0)
    with pytest.raises(RuntimeError, match="4.2.0 or later"):
        _require_cipher_integrity_version("3.4.1")
    with pytest.raises(RuntimeError, match="invalid SQLCipher version"):
        _require_cipher_integrity_version("")


def test_plaintext_migration_with_real_sqlcipher(tmp_path: Path, monkeypatch) -> None:
    if not sqlcipher_runtime_status()["available"]:
        pytest.skip("sqlcipher3 runtime is not installed")
    database = tmp_path / "existing.db"
    key_path = tmp_path / "keys" / "db.key"
    monkeypatch.setattr("atmem.core.keys.DEFAULT_KEY_PATH", key_path)
    memory = Memory(database)
    try:
        memory.remember("user", "Migration preserves this exact value", force=True)
    finally:
        memory.close()

    result = migrate_plaintext_household(database)

    assert result["migrated"] is True
    assert result["state"] == "encrypted"
    assert not database.read_bytes().startswith(b"SQLite format 3\x00")
    reopened = Memory(database)
    try:
        assert reopened.recall("user", "exact value")
    finally:
        reopened.close()


def test_plaintext_migration_removes_source_sidecars_before_cutover(
    tmp_path: Path, monkeypatch
) -> None:
    if not sqlcipher_runtime_status()["available"]:
        pytest.skip("sqlcipher3 runtime is not installed")
    database = tmp_path / "windows-sidecars.db"
    candidate = database.with_name(f".{database.name}.atmem-encrypted")
    backup = database.with_name(f".{database.name}.atmem-plaintext-backup")
    key_path = tmp_path / "keys" / "db.key"
    monkeypatch.setattr("atmem.core.keys.DEFAULT_KEY_PATH", key_path)
    memory = Memory(database)
    memory.close()
    original_replace = os.replace

    def replace_with_retained_sidecars(source: object, destination: object) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        if source_path == database and destination_path == backup:
            original_replace(source, destination)
            Path(f"{database}-wal").write_bytes(b"retained plaintext WAL")
            Path(f"{database}-shm").write_bytes(b"retained plaintext SHM")
            return
        if source_path == candidate and destination_path == database:
            assert not Path(f"{database}-wal").exists()
            assert not Path(f"{database}-shm").exists()
        original_replace(source, destination)

    monkeypatch.setattr("atmem.core.keys.os.replace", replace_with_retained_sidecars)

    result = migrate_plaintext_household(database)

    assert result["migrated"] is True
    assert result["state"] == "encrypted"


def test_plaintext_migration_resumes_before_first_rename(
    tmp_path: Path, monkeypatch
) -> None:
    if not sqlcipher_runtime_status()["available"]:
        pytest.skip("sqlcipher3 runtime is not installed")
    database = tmp_path / "interrupted.db"
    key_path = tmp_path / "keys" / "db.key"
    monkeypatch.setattr("atmem.core.keys.DEFAULT_KEY_PATH", key_path)
    memory = Memory(database)
    try:
        memory.remember("user", "Resume preserves exact value RX-41", force=True)
    finally:
        memory.close()

    original_replace = os.replace
    interrupted = {"raised": False}

    def replace_once(source, destination):
        if (
            Path(source) == database
            and Path(destination).name == f".{database.name}.atmem-plaintext-backup"
            and not interrupted["raised"]
        ):
            interrupted["raised"] = True
            raise OSError("simulated interruption before first rename")
        return original_replace(source, destination)

    monkeypatch.setattr("atmem.core.keys.os.replace", replace_once)
    with pytest.raises(OSError, match="simulated interruption"):
        migrate_plaintext_household(database)
    assert HouseholdPolicy.load(database).state == "encrypting"
    assert database.read_bytes().startswith(b"SQLite format 3\x00")

    monkeypatch.setattr("atmem.core.keys.os.replace", original_replace)
    result = migrate_plaintext_household(database)

    assert result["resumed"] is True
    reopened = Memory(database)
    try:
        assert any("RX-41" in row["content"] for row in reopened.recall("user", "RX-41"))
    finally:
        reopened.close()


def test_encrypted_migration_reconciles_retained_plaintext_backup(
    tmp_path: Path, monkeypatch
) -> None:
    if not sqlcipher_runtime_status()["available"]:
        pytest.skip("sqlcipher3 runtime is not installed")
    database = tmp_path / "cleanup.db"
    key_path = tmp_path / "keys" / "db.key"
    monkeypatch.setattr("atmem.core.keys.DEFAULT_KEY_PATH", key_path)
    memory = Memory(database)
    try:
        memory.remember("user", "Backup cleanup preserves BC-17", force=True)
    finally:
        memory.close()
    plaintext = database.read_bytes()
    migrate_plaintext_household(database)
    reopened = Memory(database)
    try:
        reopened.remember("user", "A legitimate encrypted-only update BC-18", force=True)
    finally:
        reopened.close()
    backup = database.with_name(f".{database.name}.atmem-plaintext-backup")
    backup.write_bytes(plaintext)

    result = migrate_plaintext_household(database)

    assert result["migrated"] is False
    assert not backup.exists()
    reopened = Memory(database)
    try:
        assert any("BC-17" in row["content"] for row in reopened.recall("user", "BC-17"))
        assert any("BC-18" in row["content"] for row in reopened.recall("user", "BC-18"))
    finally:
        reopened.close()


def test_encrypted_finalizing_state_fails_closed_and_resumes(
    tmp_path: Path, monkeypatch
) -> None:
    if not sqlcipher_runtime_status()["available"]:
        pytest.skip("sqlcipher3 runtime is not installed")
    database = tmp_path / "finalizing.db"
    key_path = tmp_path / "keys" / "db.key"
    monkeypatch.setattr("atmem.core.keys.DEFAULT_KEY_PATH", key_path)
    memory = Memory(database)
    try:
        memory.remember("user", "Finalization preserves EF-22", force=True)
    finally:
        memory.close()
    migrate_plaintext_household(database)
    HouseholdPolicy.load(database).with_state("encrypted-finalizing").write()

    with pytest.raises(RuntimeError, match="runtime access is fail-closed"):
        Memory(database)

    result = migrate_plaintext_household(database)

    assert result["resumed"] is True
    reopened = Memory(database)
    try:
        assert any("EF-22" in row["content"] for row in reopened.recall("user", "EF-22"))
    finally:
        reopened.close()


def test_encrypted_finalizing_resumes_with_verified_plaintext_backup(
    tmp_path: Path, monkeypatch
) -> None:
    if not sqlcipher_runtime_status()["available"]:
        pytest.skip("sqlcipher3 runtime is not installed")
    database = tmp_path / "finalizing-backup.db"
    key_path = tmp_path / "keys" / "db.key"
    monkeypatch.setattr("atmem.core.keys.DEFAULT_KEY_PATH", key_path)
    memory = Memory(database)
    try:
        memory.remember("user", "Finalizing backup preserves FB-23", force=True)
    finally:
        memory.close()
    plaintext = database.read_bytes()
    migrate_plaintext_household(database)
    backup = database.with_name(f".{database.name}.atmem-plaintext-backup")
    backup.write_bytes(plaintext)
    HouseholdPolicy.load(database).with_state("encrypted-finalizing").write()

    result = migrate_plaintext_household(database)

    assert result["resumed"] is True
    assert not backup.exists()


def test_fresh_real_encrypted_household_opens_canonical_and_vector_planes(
    tmp_path: Path, monkeypatch
) -> None:
    if not sqlcipher_runtime_status()["available"]:
        pytest.skip("sqlcipher3 runtime is not installed")
    database = tmp_path / "fresh.db"
    key_path = tmp_path / "keys" / "db.key"
    monkeypatch.setattr("atmem.core.keys.DEFAULT_KEY_PATH", key_path)

    initialize_encrypted_household(database)
    memory = Memory(database)
    try:
        memory.remember("user", "Encrypted planes preserve this record", force=True)
    finally:
        memory.close()

    assert not database.read_bytes().startswith(b"SQLite format 3\x00")
    vectors = Path(f"{database}.vectors.db")
    assert vectors.is_file()
    assert not vectors.read_bytes().startswith(b"SQLite format 3\x00")
