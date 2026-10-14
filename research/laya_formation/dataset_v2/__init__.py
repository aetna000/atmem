"""Leakage-resistant, live-schema training data for Laya formation v2."""

from .generator import GENERATOR_VERSION, generate_examples
from .validation import validate_examples

__all__ = ["GENERATOR_VERSION", "generate_examples", "validate_examples"]
