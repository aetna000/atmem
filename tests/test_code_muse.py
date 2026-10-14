from __future__ import annotations

import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest


def test_installed_muse_prompt_hook_executes_offline(tmp_path: Path) -> None:
    binary = shutil.which("muse")
    if binary is None:
        pytest.skip("Muse Code is not installed")
    script = Path(__file__).parent / "fixtures" / "muse_canary_hook.py"
    hooks = tmp_path / ".muse" / "hooks.json"
    hooks.parent.mkdir()
    hooks.write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [{
        "type": "command",
        "command": f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}",
        "timeout": 10,
    }]}]}}), encoding="utf-8")
    result = subprocess.run(
        [binary, "exec", "--provider", "echo", "--trust-workspace", "--json", "hello"],
        cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert (tmp_path / "muse-hook-fired").exists(), result.stderr[-2000:]
    # Echo-provider output does not expose model input. This is only hook
    # execution evidence, not proof that a real model received context.
