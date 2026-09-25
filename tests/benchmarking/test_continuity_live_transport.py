import json
import io
import urllib.request

import pytest

from benchmarks.agent_continuity.live_transport import LoggedTransport, MODEL, ProviderFailure, estimate_usage, post_openai
from benchmarks.agent_continuity.spend import BudgetStop, SpendLedger


def reply():
    return {"model": MODEL, "service_tier": "default", "usage": {"prompt_tokens": 100, "completion_tokens": 10,
            "prompt_tokens_details": {"cached_tokens": 20}}}


@pytest.fixture
def transport(tmp_path):
    ledger = SpendLedger.create(tmp_path / "spend.db", authorization_id="test", protocol_sha256="a"*64)
    item = LoggedTransport(ledger, tmp_path, "TEST-KEY-NOT-REAL", "trial", sender=lambda body, key: reply())
    item.role = "agent"
    return item


def test_logged_before_dispatch_and_key_excluded(transport):
    def sender(body, key):
        assert transport.ledger.snapshot()["summary"]["unknown_attempts"] == 1
        assert len(list(transport.output.glob("*.request.json"))) == 1
        assert body["store"] is False and body["n"] == 1
        return reply()
    transport.sender = sender
    transport.complete(model=MODEL, messages=[], num_retries=0)
    assert transport.ledger.snapshot()["summary"]["estimated_micro_usd"] == 250
    for path in transport.output.glob("*.json"):
        assert "TEST-KEY" not in path.read_text()


def test_arm_is_accounting_only_and_identical_requests_are_not_deduplicated(tmp_path):
    ledger = SpendLedger.create(tmp_path / 'spend.db', authorization_id='test', protocol_sha256='b'*64)
    bodies = []
    for arm in ['native-no-fault', 'baseline', 'atmem', 'atflows', 'both']:
        directory = tmp_path / arm
        directory.mkdir()
        item = LoggedTransport(ledger, directory, 'TEST-KEY-NOT-REAL', arm, arm=arm,
            sender=lambda body, key: (bodies.append(body) or reply()))
        item.role = 'agent'
        item.complete(model=MODEL, messages=[])
        item.complete(model=MODEL, messages=[])
    assert len(bodies) == 10
    assert all(body == bodies[0] for body in bodies)
    assert 'arm' not in bodies[0]


def test_timeout_keeps_reservation(transport):
    def sender(*_):
        raise TimeoutError("secret-key-that-must-not-be-logged")
    transport.sender = sender
    with pytest.raises(TimeoutError):
        transport.complete(model=MODEL, messages=[])
    snapshot = transport.ledger.snapshot()
    assert snapshot["summary"]["unresolved_reserve_micro_usd"] == 2_200_000
    assert "secret-key" not in json.dumps(snapshot)


def test_missing_usage_is_unknown(transport):
    transport.sender = lambda *_: {"model": MODEL, "service_tier": "default"}
    with pytest.raises(KeyError):
        transport.complete(model=MODEL, messages=[])
    assert not transport.ledger.snapshot()["summary"]["usage_estimate_complete"]


@pytest.mark.parametrize('tier', [None, 'priority'])
def test_unpriced_tier_retains_full_reservation(transport, tier):
    transport.sender = lambda *_: {**reply(), 'service_tier': tier}
    with pytest.raises(ValueError):
        transport.complete(model=MODEL, messages=[])
    assert transport.ledger.snapshot()['summary']['unresolved_reserve_micro_usd'] == 2_200_000


@pytest.mark.parametrize("extra", [{"model": "other"}, {"num_retries": 1}, {"n": 2}, {"max_tokens": 4096}, {"temperature": 1}])
def test_unapproved_options_never_dispatch(transport, extra):
    with pytest.raises(ValueError):
        transport.complete(**{"model": MODEL, "messages": [], **extra})
    assert transport.calls == 0


def test_no_dispatch_over_budget(transport):
    transport.ledger.reserve("previous", upper_micro_usd=18_000_001, trial_id="old", arm="baseline", role="simulator")
    with pytest.raises(BudgetStop):
        transport.complete(model=MODEL, messages=[])
    assert transport.calls == 0


def test_invalid_usage():
    data = reply()
    data["usage"]["prompt_tokens_details"]["cached_tokens"] = 101
    with pytest.raises(ValueError):
        estimate_usage(data)


def test_error_latches_and_prevents_grader_dispatch(transport):
    def fail(*_):
        raise TimeoutError()
    transport.sender = fail
    with pytest.raises(TimeoutError):
        transport.complete(model=MODEL, messages=[])
    transport.role = "grader"
    with pytest.raises(BudgetStop, match="halted"):
        transport.complete(model=MODEL, messages=[])
    assert transport.calls == 1


@pytest.mark.parametrize("status,body", [(401, b'{"error":{"type":"authentication_error","code":"invalid_api_key","message":"secret"}}'),
                                        (200, b'not-json-secret')])
def test_http_errors_sanitized_but_correlatable(monkeypatch, status, body):
    class Response(io.BytesIO):
        pass
    response = Response(body)
    response.status = status
    response.headers = {"x-request-id": "req-fixture"}
    class Opener:
        def open(self, *_args, **_kwargs):
            return response
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises(ProviderFailure) as caught:
        post_openai({}, "fake-test-key")
    evidence = caught.value.evidence
    assert evidence["http_status"] == status and evidence["request_id"] == "req-fixture"
    assert "secret" not in json.dumps(evidence)
    assert evidence["raw_body_omitted"]
