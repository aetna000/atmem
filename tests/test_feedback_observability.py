from dataclasses import replace
import json

import pytest

from atmem.feedback.observability import FeedbackObservability
from atmem.feedback.store import FeedbackError
from atmem.knowledge.rag.contracts import RagQuery
from rag_fixtures import setup_rag
from test_feedback_actions import actions_fixture


def test_actual_authorized_operations_have_scoped_content_free_runtime_metrics(tmp_path):
    f = setup_rag(tmp_path)
    reply = f.rag.search(f.session, RagQuery("law", "filing deadline"), idempotency_key="actual-search")
    report = f.feedback.operational_metrics(f.session)
    metric = report["operations"]["rag.search"]
    assert metric["calls"] == 1 and metric["reasons"] == {"ok":1}
    assert metric["latency_ms"]["samples"] == 1 and metric["latency_ms"]["p95"] > 0
    raw = json.dumps(report)
    for content in ("filing deadline", "ten days", f.user["token"], reply["receipt_id"]):
        assert content not in raw
    other = replace(f.scope, workspace_id="other")
    assert f.feedback.observability.snapshot(other)["operations"] == {}
    f.feedback.revoke_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"])
    with pytest.raises(FeedbackError, match="denied"):
        f.feedback.operational_metrics(f.session)


def test_bounded_window_percentiles_and_exception_redaction(tmp_path):
    f, _ = actions_fixture(tmp_path)
    values = iter(float(n) for n in range(1200))
    metrics = FeedbackObservability(timer=lambda:next(values))
    for _ in range(300):
        with metrics.measure(f.scope, "rule.evaluate"):
            pass
    with pytest.raises(RuntimeError, match="PRIVATE"):
        with metrics.measure(f.scope, "verification.readback"):
            raise RuntimeError("PRIVATE tokens and memory cannot become metric labels")
    report = metrics.snapshot(f.scope)
    assert report["operations"]["rule.evaluate"]["calls"] == 300
    assert report["operations"]["rule.evaluate"]["latency_ms"] == {"p50":1000, "p95":1000, "samples":256}
    assert report["operations"]["verification.readback"]["reasons"] == {"error":1}
    assert "PRIVATE" not in json.dumps(report)
    assert FeedbackObservability().snapshot(f.scope)["operations"] == {}  # restart is explicit


def test_reported_usage_is_idempotent_scoped_partial_and_not_verified_billing(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    f.feedback.schedule(f.owner["token"], f.scope, schedule_id="schedule", tasks=(
        {"outcome_id":outcome.outcome_id, "episode_id":"episode", "answerable":True},))
    f.feedback.report_outcome(f.session, outcome, idempotency_key="reported")
    usage = f.feedback.quality(f.session, schedule_id="schedule")["usage"]
    assert usage["status"] == "not_captured" and usage["usd_micros"] is None
    options = dict(receipt_id="provider-receipt", run_id=outcome.run_id, usd_micros=12345,
                   input_tokens=20, output_tokens=10, model_calls=1)
    with pytest.raises(FeedbackError, match="denied"):
        f.feedback.record_usage(f.user["token"], f.scope, **options)
    first = f.feedback.record_usage(f.owner["token"], f.scope, **options)
    assert f.feedback.record_usage(f.owner["token"], f.scope, **options) == first
    with pytest.raises(FeedbackError, match="conflicting_retry"):
        f.feedback.record_usage(f.owner["token"], f.scope, **{**options, "run_id":"other"})
    f.feedback.record_usage(f.owner["token"], f.scope, **{**options, "receipt_id":"foreign-run", "run_id":"other", "usd_micros":999})
    usage = f.feedback.quality(f.session, schedule_id="schedule")["usage"]
    assert usage["usd_micros"] == 12345 and usage["receipt_count"] == 1
    assert usage["assurance"] == "host_report" and usage["status"] == "partial"
    assert not usage["complete_billing_verified"]
    # A subscription/provider may report tokens but no attributable invoice.
    # Keep known subtotals without inventing a zero total for the missing cost.
    f.feedback.record_usage(f.owner["token"], f.scope, receipt_id="unknown-billing", run_id=outcome.run_id,
        model_calls=1, input_tokens=30)
    usage = f.feedback.quality(f.session, schedule_id="schedule")["usage"]
    assert usage["usd_micros"] is None and usage["reported_subtotals"]["usd_micros"] == 12345
    assert usage["unknown_receipts"]["usd_micros"] == 1 and usage["model_calls"] == 2
    assert usage["input_tokens"] == 50 and usage["output_tokens"] is None
