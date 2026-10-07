"""Fail-closed identity checks for benchmarked AtMem artifacts."""

from __future__ import annotations

import hashlib
from importlib.metadata import distribution, version
import json
from pathlib import Path
from typing import Any


def installed_atmem_identity(expected_version: str | None = None) -> dict[str, Any]:
    """Return a content identity only when imports resolve to the distribution.

    Benchmark launchers live in the source repository, so merely finding an
    installed distribution is insufficient: Python may still import ``atmem``
    from the checkout.  Evidence produced in that state is not attributable to
    the wheel under test and must fail before any provider call.
    """
    import atmem

    installed_version = version("atmem")
    if expected_version is not None and installed_version != expected_version:
        raise RuntimeError(
            f"benchmark requires AtMem {expected_version}; found {installed_version}"
        )
    dist = distribution("atmem")
    distribution_module = Path(dist.locate_file("atmem/__init__.py")).resolve()
    imported_module = Path(atmem.__file__).resolve()
    if imported_module != distribution_module:
        raise RuntimeError(
            "benchmark imported AtMem from the checkout instead of the installed "
            f"artifact: imported={imported_module}; installed={distribution_module}. "
            "Run the launcher outside the repository with the qualification venv."
        )

    installed_files: dict[str, str] = {}
    for entry in sorted(dist.files or (), key=str):
        relative = str(entry)
        if not (
            relative.startswith("atmem/")
            or relative.endswith(("METADATA", "entry_points.txt"))
        ):
            continue
        path = Path(dist.locate_file(entry)).resolve()
        if path.is_file():
            installed_files[relative] = "sha256:" + hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    if not installed_files:
        raise RuntimeError("installed AtMem artifact has no hashable package files")
    encoded = json.dumps(
        installed_files, sort_keys=True, separators=(",", ":")
    ).encode()
    return {
        "version": installed_version,
        "module": str(imported_module),
        "artifact_sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
    }
