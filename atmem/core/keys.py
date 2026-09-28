from __future__ import annotations

import os
from pathlib import Path
import re
import sqlite3

from atmem.home.layout import compatible_home_path
import secrets
import stat
import uuid
from typing import Any

from atmem.core.storage import HouseholdPolicy


KEY_ENV = "ATMEM_DB_KEY"
DEFAULT_KEY_PATH = compatible_home_path("identity/keys/db.key", "keys/db.key")
KEYRING_SERVICE = "atmem"
MINIMUM_CIPHER_INTEGRITY_VERSION = (4, 2, 0)


def _require_cipher_integrity_version(value: object) -> tuple[int, int, int]:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", str(value or "").strip())
    if match is None:
        raise RuntimeError("encrypted candidate reported an invalid SQLCipher version")
    version = tuple(int(part) for part in match.groups())
    if version < MINIMUM_CIPHER_INTEGRITY_VERSION:
        required = ".".join(str(part) for part in MINIMUM_CIPHER_INTEGRITY_VERSION)
        raise RuntimeError(
            f"SQLCipher {required} or later is required for cipher_integrity_check"
        )
    return version


def _validate_key(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise ValueError("AtMem database key must be exactly 64 hexadecimal characters")
    return normalized


def _write_file_key(value: str, path: Path | None = None) -> None:
    path = path or DEFAULT_KEY_PATH
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        raise ValueError(f"database key already exists: {path}")
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(value + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    if os.name != "nt":
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def _read_file_key(path: Path | None = None) -> str:
    path = path or DEFAULT_KEY_PATH
    if os.name != "nt":
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise RuntimeError(
                f"database key permissions are unsafe ({oct(mode)}); require 0600"
            )
    return _validate_key(path.read_text(encoding="utf-8"))


def initialize_keys(database_path: str | Path, *, backend: str = "file") -> dict[str, Any]:
    if backend not in {"file", "keyring"}:
        raise ValueError("key backend must be file or keyring")
    policy = HouseholdPolicy.load(database_path)
    if policy.state_path is None:
        raise ValueError("persistent keys cannot be initialized for :memory:")
    if policy.state_path.exists():
        return key_status(database_path)
    environment_key = os.environ.get(KEY_ENV)
    key = _validate_key(environment_key) if environment_key else secrets.token_hex(32)
    key_id = f"key_{uuid.uuid4().hex}"
    if backend == "file":
        if DEFAULT_KEY_PATH.exists():
            stored_key = _read_file_key()
            if environment_key and stored_key != key:
                raise RuntimeError(
                    f"{KEY_ENV} differs from the durable household key file"
                )
            key = stored_key
        else:
            _write_file_key(key)
    else:
        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError("keyring backend requires the keyring package") from exc
        keyring.set_password(KEYRING_SERVICE, key_id, key)
    created = HouseholdPolicy(
        database_path=str(Path(database_path).expanduser().resolve(strict=False)),
        state_path=policy.state_path,
        lock_path=policy.lock_path,
        state="plaintext",
        backend=backend,
        key_id=key_id,
        control_kdf_salt=secrets.token_hex(32),
    )
    created.write()
    return key_status(database_path)


def resolve_database_key(policy: HouseholdPolicy) -> str:
    override = os.environ.get(KEY_ENV)
    if override:
        return _validate_key(override)
    if policy.backend == "file":
        try:
            return _read_file_key()
        except FileNotFoundError as exc:
            raise RuntimeError(f"database key file is missing: {DEFAULT_KEY_PATH}") from exc
    if policy.backend == "keyring":
        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError("keyring backend requires the keyring package") from exc
        value = keyring.get_password(KEYRING_SERVICE, str(policy.key_id))
        if value is None:
            raise RuntimeError(f"database key {policy.key_id} is missing from keyring")
        return _validate_key(value)
    raise RuntimeError("household has no initialized key backend")


def key_status(database_path: str | Path) -> dict[str, Any]:
    policy = HouseholdPolicy.load(database_path)
    source = None
    available = False
    if os.environ.get(KEY_ENV):
        _validate_key(os.environ[KEY_ENV])
        source, available = "environment", True
    elif policy.backend == "file":
        source = "file"
        try:
            _read_file_key()
            available = True
        except (FileNotFoundError, RuntimeError, ValueError):
            available = False
    elif policy.backend == "keyring":
        source = "keyring"
        try:
            import keyring

            available = keyring.get_password(KEYRING_SERVICE, str(policy.key_id)) is not None
        except ImportError:
            available = False
    return {
        "format": "atmem-key-status-v1",
        "database_path": policy.database_path,
        "state": policy.state,
        "backend": policy.backend,
        "key_id": policy.key_id,
        "source": source,
        "available": available,
        "key_exposed": False,
    }


def sqlcipher_runtime_status() -> dict[str, Any]:
    """Report whether the separately provisioned SQLCipher runtime is usable.

    Importing the module is intentionally the only check performed here.  It
    does not create a database, read a key, or silently install a dependency.
    """

    try:
        from sqlcipher3 import dbapi2 as sqlcipher  # type: ignore[import-not-found]
    except ImportError:
        return {
            "format": "atmem-sqlcipher-runtime-status-v1",
            "available": False,
            "module": "sqlcipher3",
            "version": None,
            "reason": "sqlcipher3_not_installed",
        }
    return {
        "format": "atmem-sqlcipher-runtime-status-v1",
        "available": True,
        "module": "sqlcipher3",
        "version": str(getattr(sqlcipher, "sqlite_version", "unknown")),
        "reason": None,
    }


def initialize_encrypted_household(
    database_path: str | Path, *, backend: str = "file"
) -> dict[str, Any]:
    """Create or safely resume one *new* SQLCipher-backed household.

    This operation never converts an existing plaintext database.  The
    ``migration-prepared`` policy state is written before the first encrypted
    page so interruption fails closed.  A later invocation may resume that
    exact fresh bootstrap using the already provisioned key.
    """

    from atmem.core.storage import HouseholdLock, SQLITE_HEADER

    target = Path(database_path).expanduser().resolve(strict=False)
    if str(database_path) == ":memory:":
        raise ValueError("encrypted households require a persistent database path")
    runtime = sqlcipher_runtime_status()
    if not runtime["available"]:
        raise RuntimeError(
            "encrypted household requires sqlcipher3; install the documented "
            "SQLCipher runtime before retrying"
        )
    from sqlcipher3 import dbapi2 as sqlcipher  # type: ignore[import-not-found]

    def database_header() -> bytes:
        if not target.is_file() or target.stat().st_size == 0:
            return b""
        with target.open("rb") as handle:
            return handle.read(len(SQLITE_HEADER))

    policy = HouseholdPolicy.load(target)
    with HouseholdLock(policy, exclusive=True):
        policy = HouseholdPolicy.load(target)
        if target.exists() and target.stat().st_size:
            header = database_header()
            if header == SQLITE_HEADER:
                raise ValueError(
                    "refusing to convert an existing plaintext database; use the "
                    "separate verified migration workflow"
                )
            if policy.state == "encrypted":
                return {
                    **key_status(target),
                    "format": "atmem-encrypted-household-bootstrap-v1",
                    "created": False,
                    "resumed": False,
                    "sqlcipher": runtime,
                }
            if policy.state != "migration-prepared":
                raise RuntimeError(
                    "a non-plaintext database exists without a resumable encrypted bootstrap"
                )
        elif policy.state == "encrypted":
            raise RuntimeError("encrypted household policy exists but its database is missing")

        if policy.backend is None:
            initialize_keys(target, backend=backend)
            policy = HouseholdPolicy.load(target)
        elif policy.backend != backend:
            raise ValueError(
                f"household key backend is already {policy.backend}; requested {backend}"
            )
        if policy.state not in {"plaintext", "migration-prepared"}:
            raise RuntimeError(f"household state {policy.state!r} cannot be bootstrapped")
        prepared = policy.with_state("migration-prepared")
        prepared.write()
        key = resolve_database_key(prepared)
        target.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlcipher.connect(str(target))
        try:
            connection.execute(f"PRAGMA key = \"x'{key}'\"")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS atmem_encrypted_bootstrap "
                "(format TEXT NOT NULL PRIMARY KEY)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO atmem_encrypted_bootstrap(format) VALUES (?)",
                ("atmem-encrypted-household-bootstrap-v1",),
            )
            connection.commit()
            connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
        finally:
            connection.close()
        if database_header() == SQLITE_HEADER:
            raise RuntimeError("SQLCipher bootstrap unexpectedly produced plaintext SQLite")
        encrypted = prepared.with_state("encrypted")
        encrypted.write()
        return {
            **key_status(target),
            "format": "atmem-encrypted-household-bootstrap-v1",
            "created": True,
            "resumed": policy.state == "migration-prepared",
            "sqlcipher": runtime,
        }


def migrate_plaintext_household(
    database_path: str | Path, *, backend: str = "file"
) -> dict[str, Any]:
    """Atomically replace one plaintext SQLite household with SQLCipher.

    SQLCipher's own ``sqlcipher_export`` copies the complete SQLite schema and
    data.  AtMem verifies table row counts and both databases' integrity before
    the first rename.  The source, encrypted candidate, and short-lived backup
    stay in the same directory so each rename is atomic on Windows, macOS and
    Linux.  A crash leaves a fail-closed policy plus enough local state for the
    same command to resume; runtime opens never guess which file is current.
    """

    from atmem.core.storage import HouseholdLock, SQLITE_HEADER

    target = Path(database_path).expanduser().resolve(strict=False)
    if str(database_path) == ":memory:":
        raise ValueError("encrypted household migration requires a persistent path")
    runtime = sqlcipher_runtime_status()
    if not runtime["available"]:
        raise RuntimeError(
            "encrypted household migration requires sqlcipher3; install the "
            "documented SQLCipher runtime before retrying"
        )
    from sqlcipher3 import dbapi2 as sqlcipher  # type: ignore[import-not-found]

    candidate = target.with_name(f".{target.name}.atmem-encrypted")
    backup = target.with_name(f".{target.name}.atmem-plaintext-backup")
    policy = HouseholdPolicy.load(target)

    def header(path: Path) -> bytes:
        if not path.is_file() or path.stat().st_size == 0:
            return b""
        with path.open("rb") as handle:
            return handle.read(len(SQLITE_HEADER))

    def plaintext_inventory(path: Path) -> dict[str, int]:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            check = connection.execute("PRAGMA integrity_check").fetchone()
            if check is None or check[0] != "ok":
                raise RuntimeError("plaintext source failed SQLite integrity_check")
            rows = connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            return {
                str(name): int(
                    connection.execute(
                        f'SELECT count(*) FROM "{str(name).replace(chr(34), chr(34) * 2)}"'
                    ).fetchone()[0]
                )
                for (name,) in rows
            }
        finally:
            connection.close()

    def encrypted_inventory(path: Path, key: str) -> dict[str, int]:
        connection = sqlcipher.connect(str(path))
        try:
            connection.execute(f"PRAGMA key = \"x'{key}'\"")
            version = connection.execute("PRAGMA cipher_version").fetchone()
            if version is None or not str(version[0] or "").strip():
                raise RuntimeError("encrypted candidate did not report a SQLCipher runtime")
            _require_cipher_integrity_version(version[0])
            check = connection.execute("PRAGMA integrity_check").fetchone()
            if check is None or check[0] != "ok":
                raise RuntimeError("encrypted candidate failed SQLCipher integrity_check")
            cipher_errors = connection.execute(
                "PRAGMA cipher_integrity_check"
            ).fetchall()
            if any(str(row[0]).strip().casefold() != "ok" for row in cipher_errors):
                raise RuntimeError(
                    "encrypted candidate failed SQLCipher cipher_integrity_check"
                )
            rows = connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            return {
                str(name): int(
                    connection.execute(
                        f'SELECT count(*) FROM "{str(name).replace(chr(34), chr(34) * 2)}"'
                    ).fetchone()[0]
                )
                for (name,) in rows
            }
        finally:
            connection.close()

    def sync_file(path: Path) -> None:
        descriptor = os.open(path, os.O_RDWR if os.name == "nt" else os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def sync_directory(path: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def purge_rebuildable_plaintext_derivatives() -> None:
        vector = Path(f"{target}.vectors.db")
        for path in (
            vector, Path(f"{vector}-wal"), Path(f"{vector}-shm"),
            Path(f"{target}-wal"), Path(f"{target}-shm"),
        ):
            path.unlink(missing_ok=True)

    with HouseholdLock(policy, exclusive=True):
        policy = HouseholdPolicy.load(target)
        if policy.state == "encrypted-finalizing":
            key = resolve_database_key(policy)
            if (
                not target.exists()
                or header(target) == SQLITE_HEADER
            ):
                raise RuntimeError(
                    "encrypted migration cleanup is incomplete; retained files require review"
                )
            target_inventory = encrypted_inventory(target, key)
            if backup.exists():
                if header(backup) != SQLITE_HEADER:
                    raise RuntimeError("retained migration backup is not plaintext SQLite")
                if target_inventory != plaintext_inventory(backup):
                    raise RuntimeError(
                        "finalizing encrypted database differs from its retained source"
                    )
                backup.unlink()
            candidate.unlink(missing_ok=True)
            purge_rebuildable_plaintext_derivatives()
            sync_directory(target.parent)
            policy.with_state("encrypted").write()
            return {
                **key_status(target),
                "format": "atmem-household-migration-v1",
                "migrated": True,
                "resumed": True,
                "sqlcipher": runtime,
            }
        # Finish a rename interrupted after the verified candidate was built.
        if policy.state == "encrypting":
            key = resolve_database_key(policy)
            # Interruption before the first rename: re-verify both complete
            # files, then continue the same atomic cutover.
            if (
                target.exists()
                and header(target) == SQLITE_HEADER
                and candidate.exists()
                and not backup.exists()
            ):
                source_inventory = plaintext_inventory(target)
                if encrypted_inventory(candidate, key) != source_inventory:
                    raise RuntimeError(
                        "interrupted encrypted candidate differs from the plaintext source"
                    )
                os.replace(target, backup)
                os.replace(candidate, target)
                sync_directory(target.parent)
            # Interruption between the two renames.
            if not target.exists() and backup.exists() and candidate.exists():
                os.replace(candidate, target)
                sync_directory(target.parent)
            # Interruption after the second rename: the retained plaintext
            # source remains the authority for the final row-count check.
            if (
                target.exists()
                and header(target) != SQLITE_HEADER
                and backup.exists()
                and header(backup) == SQLITE_HEADER
            ):
                if encrypted_inventory(target, key) != plaintext_inventory(backup):
                    raise RuntimeError(
                        "interrupted encrypted database differs from its plaintext source"
                    )
                policy.with_state("encrypted-finalizing").write()
                backup.unlink(missing_ok=True)
                candidate.unlink(missing_ok=True)
                purge_rebuildable_plaintext_derivatives()
                sync_directory(target.parent)
                policy.with_state("encrypted").write()
                return {
                    **key_status(target),
                    "format": "atmem-household-migration-v1",
                    "migrated": True,
                    "resumed": True,
                    "sqlcipher": runtime,
                }
            raise RuntimeError(
                "interrupted encryption cannot be reconciled automatically; "
                "the source and candidate files were retained"
            )
        if policy.state == "encrypted":
            if backup.exists():
                if (
                    not target.exists()
                    or header(target) == SQLITE_HEADER
                    or header(backup) != SQLITE_HEADER
                ):
                    raise RuntimeError(
                        "encrypted policy has an unreconciled migration backup"
                    )
                # Compatibility cleanup for the earlier state machine.  That
                # implementation wrote ``encrypted`` only after it had already
                # verified exact source/candidate inventories.  Requiring
                # equality again is unsafe because the runtime may since have
                # appended legitimate encrypted rows.  Validate both stores,
                # trust the durable completed-state attestation, then remove
                # the stale plaintext copy while runtime remains fail-closed.
                key = resolve_database_key(policy)
                encrypted_inventory(target, key)
                plaintext_inventory(backup)
                backup.unlink()
                sync_directory(target.parent)
            return {
                **key_status(target),
                "format": "atmem-household-migration-v1",
                "migrated": False,
                "resumed": False,
                "sqlcipher": runtime,
            }
        if policy.state not in {"plaintext", "migration-prepared"}:
            raise RuntimeError(f"household state {policy.state!r} cannot be migrated")
        if not target.is_file() or header(target) != SQLITE_HEADER:
            raise ValueError("migration source must be an existing plaintext SQLite database")
        if backup.exists():
            raise RuntimeError(f"migration backup already exists and requires review: {backup}")

        checkpoint = sqlite3.connect(str(target))
        try:
            checkpoint.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        finally:
            checkpoint.close()
        source_inventory = plaintext_inventory(target)
        if policy.backend is None:
            initialize_keys(target, backend=backend)
            policy = HouseholdPolicy.load(target)
        elif policy.backend != backend:
            raise ValueError(
                f"household key backend is already {policy.backend}; requested {backend}"
            )
        prepared = policy.with_state("migration-prepared")
        prepared.write()
        key = resolve_database_key(prepared)
        candidate.unlink(missing_ok=True)

        # Open the source without a key and export into a keyed attached DB.
        connection = sqlcipher.connect(str(target))
        try:
            escaped = str(candidate).replace("'", "''")
            connection.execute(
                f"ATTACH DATABASE '{escaped}' AS atmem_encrypted KEY \"x'{key}'\""
            )
            connection.execute("SELECT sqlcipher_export('atmem_encrypted')")
            connection.execute(
                "PRAGMA atmem_encrypted.user_version = "
                + str(int(connection.execute("PRAGMA main.user_version").fetchone()[0]))
            )
            connection.commit()
            connection.execute("DETACH DATABASE atmem_encrypted")
        finally:
            connection.close()
        if header(candidate) in {b"", SQLITE_HEADER}:
            raise RuntimeError("SQLCipher migration did not create an encrypted candidate")
        if encrypted_inventory(candidate, key) != source_inventory:
            raise RuntimeError("encrypted candidate row counts differ from plaintext source")
        sync_file(candidate)

        prepared.with_state("encrypting").write()
        os.replace(target, backup)
        os.replace(candidate, target)
        sync_directory(target.parent)
        sync_file(target)
        if encrypted_inventory(target, key) != source_inventory:
            # Restore the known-good plaintext source before exposing runtime.
            os.replace(target, candidate)
            os.replace(backup, target)
            sync_directory(target.parent)
            prepared.write()
            raise RuntimeError("post-rename encrypted verification failed; plaintext restored")
        prepared.with_state("encrypted-finalizing").write()
        backup.unlink(missing_ok=True)
        sync_directory(target.parent)
        purge_rebuildable_plaintext_derivatives()
        sync_directory(target.parent)
        prepared.with_state("encrypted").write()
        return {
            **key_status(target),
            "format": "atmem-household-migration-v1",
            "migrated": True,
            "resumed": policy.state == "migration-prepared",
            "tables_verified": len(source_inventory),
            "sqlcipher": runtime,
        }
