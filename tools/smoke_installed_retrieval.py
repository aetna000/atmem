"""Installed-artifact smoke for benchmark-independent retrieval dependencies."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from atmem import Memory
from atmem.service.household import HouseholdApplication


for forbidden in ("memory_modules", "harness", "datasets"):
    assert importlib.util.find_spec(forbidden) is None, forbidden

with tempfile.TemporaryDirectory(prefix="atmem installed retrieval ") as temporary:
    database = Path(temporary) / "path with spaces" / "memory.db"
    memory = Memory(database)
    try:
        memory.remember("installed-user", "My exact project code is AX-204.", force=True)
        recalled = memory.recall("installed-user", "AX-204")
        assert any("AX-204" in row["content"] for row in recalled)
    finally:
        memory.close()
    status = HouseholdApplication.status(database)
    assert status["state"] == "plaintext"
    assert status["sqlcipher"]["available"] in {True, False}
    completed = subprocess.run(
        [sys.executable, "-m", "atmem.cli", "household", "status", str(database), "--json"],
        check=True, capture_output=True, text=True,
    )
    assert json.loads(completed.stdout)["database_path"] == str(database.resolve())

print(json.dumps({"format": "atmem-installed-retrieval-smoke-v1", "passed": True}))
