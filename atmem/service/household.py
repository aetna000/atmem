"""Public application boundary for household storage protection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atmem.core.keys import (
    initialize_encrypted_household,
    key_status,
    migrate_plaintext_household,
    sqlcipher_runtime_status,
)
from atmem.core.storage import HouseholdPolicy, SQLITE_HEADER


class HouseholdApplication:
    """Create and inspect storage without exposing key material."""

    @staticmethod
    def status(database_path: str | Path) -> dict[str, Any]:
        target = Path(database_path).expanduser().resolve(strict=False)
        policy = HouseholdPolicy.load(target)
        header = b""
        if target.is_file() and target.stat().st_size:
            with target.open("rb") as handle:
                header = handle.read(len(SQLITE_HEADER))
        backup = target.with_name(f".{target.name}.atmem-plaintext-backup")
        candidate = target.with_name(f".{target.name}.atmem-encrypted")
        return {
            "format": "atmem-household-status-v1",
            "database_path": str(target),
            "exists": target.is_file(),
            "state": policy.state,
            "encrypted_header": bool(header and header != SQLITE_HEADER),
            "key": key_status(target),
            "sqlcipher": sqlcipher_runtime_status(),
            "migration_artifacts": {
                "plaintext_backup_retained": backup.is_file(),
                "encrypted_candidate_retained": candidate.is_file(),
            },
        }

    @staticmethod
    def initialize(
        database_path: str | Path, *, encrypted: bool, backend: str = "file"
    ) -> dict[str, Any]:
        if not encrypted:
            raise ValueError(
                "household initialization currently requires encrypted=True; "
                "ordinary Memory(path) remains the explicit plaintext development path"
            )
        result = initialize_encrypted_household(database_path, backend=backend)
        return {
            **result,
            "status": HouseholdApplication.status(database_path),
            "insecure_development_override": False,
        }

    @staticmethod
    def migrate(
        database_path: str | Path, *, backend: str = "file"
    ) -> dict[str, Any]:
        result = migrate_plaintext_household(database_path, backend=backend)
        return {
            **result,
            "status": HouseholdApplication.status(database_path),
            "plaintext_backup_retained": HouseholdApplication.status(database_path)[
                "migration_artifacts"
            ]["plaintext_backup_retained"],
        }
