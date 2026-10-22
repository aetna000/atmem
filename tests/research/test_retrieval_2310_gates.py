"""Plumbing fixtures only; these tests establish no retrieval-quality score."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from research.retrieval_2310.preflight import Review, inventory, validate_dispatch, validate_review
from research.retrieval_2310.protocol import CampaignLedger, Task, digest, microdollars, stratified_sample, validate_splits


def task(identity="a", role="development", cluster="person-a", exposed=False):
    return Task(identity, "corpus", role, "temporal", (cluster,), exposed)


def test_duplicate_task_and_shared_evidence_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        validate_splits([task(), task()])
    with pytest.raises(ValueError, match="cluster crosses"):
        validate_splits([task(), task("b", "confirmation")])


def test_inspected_questions_cannot_be_confirmation():
    with pytest.raises(ValueError, match="development-only"):
        task(role="confirmation", exposed=True)


def test_stratified_sample_stable_under_input_order_and_never_undersamples():
    rows = [task(str(i)) for i in range(10)]
    assert stratified_sample(rows, role="development", per_stratum=3, seed=17) == stratified_sample(reversed(rows), role="development", per_stratum=3, seed=17)
    with pytest.raises(ValueError, match="undersample"):
        stratified_sample(rows, role="development", per_stratum=11, seed=17)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0.0000001", "bad"])
def test_invalid_cost(value):
    with pytest.raises(ValueError):
        microdollars(value)


def test_reserved_final_run_and_unknown_cost_cannot_be_spent(tmp_path):
    ledger = CampaignLedger(tmp_path / "cost.db")
    try:
        ledger.reserve("final", "200")
        ledger.reserve("tuning", "50")
        with pytest.raises(ValueError, match="budget exhausted"):
            ledger.reserve("another", "0.01")
        with pytest.raises(ValueError, match="unknown usage"):
            ledger.settle("tuning", None)
        assert ledger.snapshot()["reserved_micro_usd"] == 250_000_000
        ledger.settle("tuning", "20")
        ledger.settle("tuning", "20")
        assert ledger.snapshot()["spent_micro_usd"] == 20_000_000
        with pytest.raises(ValueError, match="exceeds reservation"):
            ledger.settle("final", "201")
        assert ledger.snapshot()["spent_micro_usd"] == 221_000_000
        with pytest.raises(ValueError, match="overrun requires reconciliation"):
            ledger.reserve("must-stop", "0.01")
    finally:
        ledger.close()


def test_concurrent_process_connections_cannot_over_reserve(tmp_path):
    path = tmp_path / "cost.db"
    CampaignLedger(path).close()
    def reserve(i):
        ledger = CampaignLedger(path)
        try:
            ledger.reserve(str(i), "150")
            return True
        except ValueError:
            return False
        finally:
            ledger.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(reserve, range(2))) == 1


def test_review_detects_added_spec_code_and_config_changes(tmp_path):
    # Test-owned file creation is fixture setup, not benchmark data generation.
    p = tmp_path / "specs/one/spec.md"
    p.parent.mkdir(parents=True)
    p.write_text("source authority remains mandatory")
    config = {"seed": 1}
    review = Review("qualification", "maintainer", digest(inventory(tmp_path)), digest(config), {"specs/one/spec.md": "retained"})
    validate_review(tmp_path, config, review, stage="qualification", required_specs={"specs/one/spec.md"})
    with pytest.raises(ValueError, match="stale"):
        validate_review(tmp_path, {"seed": 2}, review, stage="qualification", required_specs={"specs/one/spec.md"})
    p.write_text("changed source authority")
    with pytest.raises(ValueError, match="stale"):
        validate_review(tmp_path, config, review, stage="qualification", required_specs={"specs/one/spec.md"})


def test_review_high_findings_and_missing_dispositions_block(tmp_path):
    p = tmp_path / "specs/one/spec.md"
    p.parent.mkdir(parents=True)
    p.write_text("spec")
    review = Review("test", "reviewer", digest(inventory(tmp_path)), digest({}), {})
    with pytest.raises(ValueError, match="incomplete"):
        validate_review(tmp_path, {}, review, stage="test", required_specs={"specs/one/spec.md"})
    with pytest.raises(ValueError, match="critical/high"):
        validate_review(tmp_path, {}, replace(review, unresolved_high=("scope conflict",)), stage="test", required_specs={"specs/one/spec.md"})


def test_review_inventory_includes_optional_companion(tmp_path):
    source=tmp_path/'packages/atbot/src/atbot/state_assessment.py'
    source.parent.mkdir(parents=True)
    source.write_text('first version')
    before=digest(inventory(tmp_path))
    source.write_text('different classification behavior')
    assert digest(inventory(tmp_path))!=before


def test_paid_dispatch_refuses_missing_gates():
    with pytest.raises(ValueError, match="unqualified"):
        validate_dispatch({})
