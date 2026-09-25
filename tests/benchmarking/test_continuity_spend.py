from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sqlite3

import pytest

from benchmarks.agent_continuity.spend import BudgetStop, SpendLedger, encoded


CONFIG = dict(authorization_id="pilot", protocol_sha256="a" * 64, cap_micro_usd=20_000_000)


@pytest.fixture
def ledger(tmp_path):
    return SpendLedger.create(tmp_path / "spend.db", **CONFIG)


def reserve(ledger, attempt="one", amount=10_000_000, **kwargs):
    ledger.reserve(attempt, upper_micro_usd=amount, trial_id="trial", arm="baseline", role="agent", **kwargs)


def test_restart_does_not_reset_or_repeat(ledger):
    reserve(ledger)
    reopened = SpendLedger(ledger.path, **CONFIG)
    with pytest.raises(BudgetStop, match="already reserved"):
        reserve(reopened)
    reserve(reopened, "two")
    with pytest.raises(BudgetStop, match="insufficient"):
        reserve(reopened, "three", 1)
    assert reopened.snapshot()["summary"]["unknown_attempts"] == 2


def test_unknown_charge_never_becomes_zero(ledger):
    reserve(ledger)
    ledger.settle("one", estimated_micro_usd=None, reason="timeout")
    summary = ledger.snapshot()["summary"]
    assert summary["estimated_micro_usd"] == 0
    assert summary["unresolved_reserve_micro_usd"] == 10_000_000
    assert not summary["usage_estimate_complete"]


def test_known_cost_and_duplicate_settlement(ledger):
    reserve(ledger)
    for _ in range(2):
        ledger.settle("one", estimated_micro_usd=500, input_tokens=100, output_tokens=25)
    reserve(ledger, "two", 19_999_500, retry_of="one", recovery=True)
    assert len(ledger.snapshot()["events"]) == 3
    with pytest.raises(ValueError, match="conflicting"):
        ledger.settle("one", estimated_micro_usd=501, input_tokens=100, output_tokens=25)


def test_overrun_is_retained_and_halts(ledger):
    reserve(ledger, amount=10)
    ledger.settle("one", estimated_micro_usd=11, input_tokens=1, output_tokens=1)
    assert ledger.snapshot()["summary"]["estimated_micro_usd"] == 11
    with pytest.raises(BudgetStop, match="underestimated"):
        reserve(ledger, "two", 1)


def test_concurrent_reservations_are_serialized(ledger):
    def call(i):
        try:
            reserve(SpendLedger(ledger.path, **CONFIG), str(i), 11_000_000)
            return True
        except BudgetStop:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(call, range(8))) == 1


@pytest.mark.parametrize("value", [-1, 0, True, 1.5, "100", 1_000_000_001])
def test_invalid_reservations(ledger, value):
    with pytest.raises(ValueError):
        reserve(ledger, amount=value)
    assert not ledger.snapshot()["events"]


def test_missing_ledger_and_changed_cap_fail_closed(ledger, tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        SpendLedger(tmp_path / "missing.db", **CONFIG)
    with pytest.raises(ValueError, match="mismatch"):
        SpendLedger(ledger.path, **{**CONFIG, "cap_micro_usd": 21_000_000})
    with pytest.raises(FileExistsError):
        SpendLedger.create(ledger.path, **CONFIG)


def test_unknown_retry_and_unreserved_settlement(ledger):
    with pytest.raises(ValueError, match="retry"):
        reserve(ledger, retry_of="missing")
    with pytest.raises(ValueError, match="unreserved"):
        ledger.settle("one", estimated_micro_usd=None, reason="timeout")


def test_export_preserves_raw_events_and_checksum(ledger, tmp_path):
    reserve(ledger)
    path = tmp_path / "accounting.json"
    ledger.export(path)
    snapshot = json.loads(path.read_text())
    checksum = snapshot.pop("payload_sha256")
    assert checksum == hashlib.sha256(encoded(snapshot).encode()).hexdigest()
    assert snapshot["events"][0]["attempt_id"] == "one"
    assert snapshot["summary"]["provider_invoice_verified"] is False
    with pytest.raises(FileExistsError):
        ledger.export(path)


def test_roles_share_one_allowance(ledger):
    reserve(ledger, amount=19_000_000)
    ledger.reserve("user", upper_micro_usd=1_000_000, trial_id="trial", arm="baseline", role="simulator")
    with pytest.raises(BudgetStop):
        ledger.reserve("judge", upper_micro_usd=1, trial_id="trial", arm="baseline", role="grader")
    assert set(ledger.snapshot()["summary"]["by_role"]) == {"agent", "simulator"}
