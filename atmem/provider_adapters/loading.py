"""Explicit Python factory loading for operator-owned provider code."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def load_factory(reference: str) -> Any:
    if not isinstance(reference, str) or reference.count(":") != 1:
        raise ValueError("factory must use module:attribute syntax")
    module_name, attribute = reference.split(":", 1)
    if not module_name or not attribute or any(part.startswith("_") for part in attribute.split(".")):
        raise ValueError("invalid provider factory reference")
    value: Any = import_module(module_name)
    for part in attribute.split("."):
        value = getattr(value, part)
    return value


def create_from_factory(reference: str) -> Any:
    factory = load_factory(reference)
    return factory() if callable(factory) else factory
