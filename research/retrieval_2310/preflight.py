"""Fail-closed review checks; hashes authenticate inputs, not review quality."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from pathlib import Path
from typing import Mapping

from .protocol import digest


def inventory(root: Path) -> dict[str, str]:
    paths = set(root.glob("specs/**/*.md")) | set(root.glob("docs/**/*.md"))
    paths |= set(root.glob("atmem/**/*.py"))
    paths |= set(root.glob("packages/atbot/src/**/*.py"))
    paths |= set(root.glob("packages/atbot/tests/**/*.py"))
    paths |= set(root.glob("research/retrieval_2310/*.py"))
    paths |= set(root.glob("research/retrieval_2310/*.json"))
    paths |= set(root.glob("tests/**/*.py"))
    paths |= set(root.glob("benchmarks/dolphinbench/**/*.py"))
    for name in (".specify/memory/constitution.md", "pyproject.toml", "AGENTS.md"):
        if (root / name).exists():
            paths.add(root / name)
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}


@dataclass(frozen=True)
class Review:
    stage: str
    reviewer: str
    inventory_digest: str
    config_digest: str
    dispositions: Mapping[str, str]
    unresolved_high: tuple[str, ...] = ()


def validate_review(root: Path, config: dict, review: Review,
                    *, stage: str, required_specs: set[str]) -> None:
    if not review.reviewer.strip() or review.stage != stage:
        raise ValueError("missing reviewer or wrong stage")
    if review.unresolved_high:
        raise ValueError("unresolved critical/high review findings")
    current = inventory(root)
    if digest(current) != review.inventory_digest or digest(config) != review.config_digest:
        raise ValueError("stale spec/source/config review")
    if not required_specs or not required_specs.issubset(current):
        raise ValueError("missing governing specification")
    if not required_specs.issubset(review.dispositions):
        raise ValueError("incomplete requirement impact review")
    if any(not review.dispositions[p].strip() for p in required_specs):
        raise ValueError("empty impact disposition")


def validate_dispatch(config: dict) -> None:
    """Mandatory evidence about dispatch qualification, not a paid runner."""
    required = {"dataset_qualified", "split_frozen", "baseline_qualified",
                "metrics_frozen", "ledger_reconciled", "final_reserve_present",
                "archive_dependencies_present", "recording_qualified"}
    if any(config.get(key) is not True for key in required):
        raise ValueError("unqualified dispatch prerequisites")
    if config.get("primary_auth") != "subscription":
        raise ValueError("primary run requires supported subscription qualification")
    if config.get("silent_paid_fallback") is not False:
        raise ValueError("paid fallback must be explicitly disabled")
    if not isinstance(config.get("artifact_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", config["artifact_sha256"]):
        raise ValueError("missing installed artifact digest")
