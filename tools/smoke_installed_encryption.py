"""Exercise real SQLCipher bootstrap and migration from an installed wheel."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from atmem import Memory
from atmem.core import keys
from atmem.core.storage import HouseholdPolicy
from atmem.service.household import HouseholdApplication


with tempfile.TemporaryDirectory(prefix="atmem installed encryption ") as temporary:
    root = Path(temporary)
    keys.DEFAULT_KEY_PATH = root / "keys" / "db.key"
    fresh = root / "fresh path" / "memory.db"
    created = HouseholdApplication.initialize(fresh, encrypted=True)
    assert created["status"]["state"] == "encrypted"
    memory = Memory(fresh)
    try:
        memory.remember("user", "Fresh encryption works", force=True)
    finally:
        memory.close()
    assert not fresh.read_bytes().startswith(b"SQLite format 3\x00")
    assert not Path(f"{fresh}.vectors.db").read_bytes().startswith(b"SQLite format 3\x00")

    plaintext = root / "migration path" / "memory.db"
    memory = Memory(plaintext)
    try:
        memory.remember("user", "Migration keeps exact value MX-91", force=True)
    finally:
        memory.close()
    migrated = HouseholdApplication.migrate(plaintext)
    assert migrated["status"]["state"] == "encrypted"
    reopened = Memory(plaintext)
    try:
        assert any("MX-91" in row["content"] for row in reopened.recall("user", "MX-91"))
    finally:
        reopened.close()

    interrupted = root / "interrupted migration" / "memory.db"
    memory = Memory(interrupted)
    try:
        memory.remember("user", "Interrupted migration preserves IR-22", force=True)
    finally:
        memory.close()
    original_replace = os.replace
    raised = False
    interruption = {"raised": False}

    def replace_once(source, destination):
        if (
            Path(source).resolve() == interrupted.resolve()
            and not interruption["raised"]
        ):
            interruption["raised"] = True
            raise OSError("installed smoke interruption")
        return original_replace(source, destination)

    os.replace = replace_once
    try:
        try:
            HouseholdApplication.migrate(interrupted)
        except OSError as exc:
            assert str(exc) == "installed smoke interruption"
            raised = True
    finally:
        os.replace = original_replace
    assert raised
    resumed = HouseholdApplication.migrate(interrupted)
    assert resumed["resumed"] is True
    reopened = Memory(interrupted)
    try:
        assert any("IR-22" in row["content"] for row in reopened.recall("user", "IR-22"))
    finally:
        reopened.close()

    finalizing = root / "finalizing migration" / "memory.db"
    memory = Memory(finalizing)
    try:
        memory.remember("user", "Finalizing migration preserves FI-23", force=True)
    finally:
        memory.close()
    plaintext = finalizing.read_bytes()
    HouseholdApplication.migrate(finalizing)
    backup = finalizing.with_name(f".{finalizing.name}.atmem-plaintext-backup")
    backup.write_bytes(plaintext)
    HouseholdPolicy.load(finalizing).with_state("encrypted-finalizing").write()
    try:
        Memory(finalizing)
    except RuntimeError as exc:
        assert "fail-closed" in str(exc)
    else:
        raise AssertionError("runtime opened during encrypted finalization")
    resumed = HouseholdApplication.migrate(finalizing)
    assert resumed["resumed"] is True
    assert not backup.exists()

print(json.dumps({"format": "atmem-installed-encryption-smoke-v1", "passed": True}))
