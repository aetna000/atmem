"""Run encryption tests from a temporary root against the installed wheel."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main() -> int:
    source = Path(__file__).resolve().parents[1] / "tests" / "test_encryption.py"
    with tempfile.TemporaryDirectory(prefix="atmem-installed-encryption-tests-") as value:
        root = Path(value)
        test = root / "test_encryption.py"
        shutil.copy2(source, test)
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment["ATMEM_REQUIRE_INSTALLED_ARTIFACT"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-m",
                "pytest",
                "--rootdir",
                str(root),
                "--import-mode=importlib",
                "-q",
                str(test),
            ],
            cwd=root,
            env=environment,
            check=False,
        )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
