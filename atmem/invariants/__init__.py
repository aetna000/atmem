"""Executable product invariant registry and conformance reporting."""

from .models import (
    AssertionResult,
    Invariant,
    InvariantRegistry,
    InvariantVerdict,
    VerdictStatus,
)
from .registry import REGISTRY, load_registry
from .verdict import evaluate_invariant, evaluate_registry
from .report import build_report, write_report

__all__ = [
    "AssertionResult",
    "Invariant",
    "InvariantRegistry",
    "InvariantVerdict",
    "REGISTRY",
    "VerdictStatus",
    "evaluate_invariant",
    "evaluate_registry",
    "load_registry",
    "build_report",
    "write_report",
]
