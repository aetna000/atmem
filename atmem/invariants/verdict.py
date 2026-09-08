"""Fail-closed invariant verdict evaluation."""

from __future__ import annotations

from collections.abc import Iterable

from .models import AssertionResult, Invariant, InvariantRegistry, InvariantVerdict, VerdictStatus


def evaluate_invariant(
    invariant: Invariant, results: Iterable[AssertionResult]
) -> InvariantVerdict:
    values = tuple(result for result in results if result.assertion_id in invariant.assertions)
    present = {result.assertion_id for result in values}
    missing = tuple(sorted(set(invariant.assertions) - present))
    failed = tuple(sorted({result.assertion_id for result in values if result.executed and not result.skipped and not result.passed}))
    unrunnable = tuple(sorted({result.assertion_id for result in values if not result.executed or result.skipped}))
    evidence = tuple(sorted({result.evidence for result in values if result.evidence}))

    if missing or failed or unrunnable:
        return InvariantVerdict(
            invariant.invariant_id,
            VerdictStatus.UNPROVEN,
            invariant.guarantee,
            invariant.owning_spec,
            evidence,
            missing_assertions=tuple(sorted(set(missing + failed + unrunnable))),
            failed_assertions=failed,
        )

    covered = {result.configuration for result in values if result.passed}
    uncovered = tuple(sorted(set(invariant.configurations) - covered))
    status = VerdictStatus.PARTIALLY_PROVEN if uncovered else VerdictStatus.PROVEN
    return InvariantVerdict(
        invariant.invariant_id,
        status,
        invariant.guarantee,
        invariant.owning_spec,
        evidence,
        uncovered_configurations=uncovered,
    )


def evaluate_registry(
    registry: InvariantRegistry, results: Iterable[AssertionResult]
) -> tuple[InvariantVerdict, ...]:
    values = tuple(results)
    return tuple(evaluate_invariant(invariant, values) for invariant in registry.invariants)
