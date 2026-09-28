"""Install exactly one locally built AtBot and AtMem wheel cross-platform."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def one(pattern: str) -> Path:
    matches = sorted(Path().glob(pattern))
    if len(matches) != 1:
        raise SystemExit(f"expected one {pattern}, found {len(matches)}")
    return matches[0]


atbot = one("atbot-dist/atmem_atbot-*.whl")
atmem = one("dist/atmem-*.whl")
subprocess.run(
    [sys.executable, "-m", "pip", "install", str(atbot), f"{atmem}[atflows]"],
    check=True,
)
