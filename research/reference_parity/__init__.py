"""Evaluator-only reference parity utilities.

Nothing in this package is imported by the AtMem runtime.  It exists to keep
benchmark provenance, result normalization, and comparison policy outside the
product implementation.
"""

from .contracts import BaselineResult, compare_candidate

__all__ = ["BaselineResult", "compare_candidate"]
