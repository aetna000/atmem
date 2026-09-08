from __future__ import annotations

import json
from pathlib import Path

import pytest

from atmem.invariants.models import AssertionResult, Invariant
from atmem.invariants.registry import REGISTRY
from atmem.invariants.verdict import evaluate_invariant


def test_registry_has_all_stable_ids_and_executable_owners() -> None:
    assert [item.invariant_id for item in REGISTRY.invariants] == [
        f"INV-{number:03d}" for number in range(1, 12)
    ]
    assert all(item.assertions for item in REGISTRY.invariants)
    schema = json.loads(
        (Path(__file__).parents[2] / "atmem/schemas/v1/invariant-registry.json").read_text()
    )
    assert schema["properties"]["format"]["const"] == REGISTRY.format


def test_invariant_without_assertion_is_rejected() -> None:
    with pytest.raises(ValueError, match="no owning assertion"):
        Invariant("INV-999", "guarantee", "I", "spec", ())


def test_verdicts_fail_closed_and_name_gaps() -> None:
    invariant = Invariant(
        "INV-999", "guarantee", "I", "spec", ("a",), ("base", "postgres")
    )
    partial = evaluate_invariant(
        invariant, (AssertionResult("a", "base", True, True, "tests/a.py"),)
    )
    assert partial.status.value == "partially_proven"
    assert partial.uncovered_configurations == ("postgres",)

    unproven = evaluate_invariant(
        invariant,
        (AssertionResult("a", "base", False, False, "tests/a.py", skipped=True),),
    )
    assert unproven.status.value == "unproven"
    assert unproven.missing_assertions == ("a",)


def test_passing_all_configurations_is_proven() -> None:
    invariant = Invariant(
        "INV-999", "guarantee", "I", "spec", ("a",), ("base", "postgres")
    )
    verdict = evaluate_invariant(
        invariant,
        (
            AssertionResult("a", "base", True, True, "tests/a.py"),
            AssertionResult("a", "postgres", True, True, "tests/a.py"),
        ),
    )
    assert verdict.status.value == "proven"
