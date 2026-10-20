"""Verify the Code profile from an installed wheel outside the source tree."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import venv
import xml.etree.ElementTree as ET


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel")
    parser.add_argument("--venv", help="Reuse only an explicitly selected verification environment")
    parser.add_argument("--report")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    candidates = [Path(args.wheel).resolve()] if args.wheel else list((source / "dist").glob("atmem-*.whl"))
    if len(candidates) != 1:
        raise ValueError("select exactly one AtMem wheel")
    wheel = candidates[0]
    workspace = Path(tempfile.mkdtemp(prefix="atmem-code-wheel-")).resolve()
    environment_path = Path(args.venv).resolve() if args.venv else workspace / "venv"
    if not args.venv:
        venv.EnvBuilder(with_pip=True).create(environment_path)
    python = environment_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTEST_ADDOPTS", None)
    environment["ATMEM_CODE_SKIP_HOST_PROBES"] = "1"
    subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-deps", "--force-reinstall", str(wheel)], check=True, env=environment)
    subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", str(wheel) + "[code]", "pytest>=8,<10"], check=True, env=environment)
    test_root = workspace / "tests"
    test_root.mkdir()
    shutil.copy2(source / "tests/conftest.py", test_root / "conftest.py")
    for test in (source / "tests").glob("test_code*.py"):
        # Replay harnesses are repository research tools, not wheel contents.
        # They run in the source regression suite, not the installed product gate.
        if test.name.startswith("test_code_replay"):
            continue
        shutil.copy2(test, test_root / test.name)
    shutil.copy2(source / "tests/test_knowledge_lifecycle.py", test_root / "test_knowledge_lifecycle.py")
    shutil.copy2(source / "tests/test_knowledge_portable.py", test_root / "test_knowledge_portable.py")
    shutil.copy2(source / "tests/test_store_transactions.py", test_root / "test_store_transactions.py")
    (test_root / "integration").mkdir()
    for test in (source / "tests/integration").glob("test_code*.py"):
        shutil.copy2(test, test_root / "integration" / test.name)
    shutil.copytree(source / "tests/fixtures", test_root / "fixtures")
    # Supporting test fixtures/scripts are copied, never the atmem package.
    # All product imports must still resolve to the installed wheel below.
    (workspace / "tools").mkdir()
    shutil.copy2(source / "tools/qualify_discovery_hosts.py", workspace / "tools/qualify_discovery_hosts.py")
    shutil.copy2(source / "tools/qualify_code_curation.py", workspace / "tools/qualify_code_curation.py")
    shutil.copytree(source / "tools/code-extractor", workspace / "tools/code-extractor")
    identity = json.loads(subprocess.run([str(python), "-c", "import atmem,platform,json; print(json.dumps({'module_path':atmem.__file__,'python':platform.python_version()}))"], cwd=workspace,
                                        env=environment, text=True, capture_output=True, check=True).stdout)
    imported = identity["module_path"]
    if not Path(imported).resolve().is_relative_to(environment_path.resolve()):
        raise RuntimeError(f"verification imported {imported} outside the selected wheel environment {environment_path}")
    junit = workspace / "results.xml"
    result = subprocess.run([str(python), "-m", "pytest", "-q", "tests", "--tb=short", "--junitxml=" + str(junit)],
                            cwd=workspace, env=environment, check=False)
    suites = ET.parse(junit).getroot() if junit.exists() else None
    totals = {key: sum(int(suite.get(key, "0")) for suite in suites.iter("testsuite")) if suites is not None else 0
              for key in ("tests", "failures", "errors", "skipped")}
    report = {"format": "atmem-code-installed-wheel-verification-v1", "platform": platform.platform(),
              "python": identity["python"], "wheel": wheel.name, "wheel_sha256": sha256(wheel.read_bytes()).hexdigest(),
              "module_path": imported, "atmem_imported_from_selected_environment": True,
              "pytest_returncode": result.returncode, "totals": totals, "artifacts": str(workspace),
              "host_probes": "separately qualified; not run by the portable core gate"}
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
