#!/usr/bin/env python3
"""Exercise the installed AtMem wheel outside the source checkout."""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, capture_output=True, text=True)


def json_run(*args: str) -> object:
    return json.loads(run(*args).stdout)


def main() -> None:
    distribution = importlib.metadata.distribution("atmem")
    assert distribution.version == "2.2.3"
    scripts = {
        entry.name: entry.value
        for entry in distribution.entry_points
        if entry.group == "console_scripts"
    }
    assert scripts == {"atmem": "atmem.cli:main"}, scripts

    executable = Path(sys.executable).with_name("atmem")
    assert executable.is_file()
    assert "2.2.3" in run(str(executable), "--version").stdout

    with tempfile.TemporaryDirectory(prefix="atmem-wheel-smoke-") as temp:
        database = Path(temp) / "memory.db"
        json_run(
            str(executable), "remember", str(database), "release-smoke",
            "My preferred editor is Vim.", "--session", "wheel-test",
        )
        recalled = json_run(
            str(executable), "recall", str(database), "release-smoke",
            "preferred editor",
        )
        assert isinstance(recalled, list) and "Vim" in recalled[0]["content"]
        verification = json_run(str(executable), "verify", str(database), "--incremental")
        assert verification["valid"] is True

    print("installed wheel smoke test passed")


if __name__ == "__main__":
    main()
