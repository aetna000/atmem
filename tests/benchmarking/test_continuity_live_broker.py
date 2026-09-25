import json
import socket
import struct
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler
from urllib.parse import urlsplit

import pytest

from benchmarks.agent_continuity.live_broker import model_broker
from benchmarks.agent_continuity.live_transport import LoggedTransport, MODEL
from benchmarks.agent_continuity.spend import SpendLedger


def setup(tmp_path, sender):
    ledger = SpendLedger.create(tmp_path / 'spend.db', authorization_id='unit', protocol_sha256='c'*64)
    return LoggedTransport(ledger, tmp_path, 'TEST-KEY-NOT-REAL', 'unit', sender=sender, arm='baseline')


def reply():
    return {'id': 'provider_response', 'model': MODEL, 'service_tier': 'default',
            'usage': {'prompt_tokens': 10, 'completion_tokens': 10}}


def request(url, token):
    return Request(url, data=json.dumps({'role': 'agent', 'request': {'model': MODEL, 'messages': [], 'num_retries': 0}}).encode(),
                   headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})


def test_identical_requests_are_separate_paid_attempts_and_wrong_token_cannot_spend(tmp_path):
    calls = []
    transport = setup(tmp_path, lambda body, key: (calls.append(body) or reply()))
    opener = build_opener(ProxyHandler({}))
    with model_broker(transport, tmp_path / 'broker') as (url, token):
        with pytest.raises(HTTPError) as error:
            opener.open(request(url, 'wrong'), timeout=5)
        assert error.value.code == 401 and transport.calls == 0
        for _ in range(2):
            with opener.open(request(url, token), timeout=5) as response:
                assert json.load(response)['id'] == 'provider_response'
    assert len(calls) == 2 and calls[0] == calls[1]
    assert transport.ledger.snapshot()['summary']['attempts'] == 2
    assert transport.ledger.snapshot()['summary']['unknown_attempts'] == 0


def test_provider_timeout_stays_unknown_and_does_not_retry(tmp_path):
    def fail(*unused):
        raise TimeoutError('NEVER-EXPORT-THIS')
    transport = setup(tmp_path, fail)
    opener = build_opener(ProxyHandler({}))
    with model_broker(transport, tmp_path / 'broker') as (url, token):
        for _ in range(2):
            with pytest.raises(HTTPError) as error:
                opener.open(request(url, token), timeout=5)
            assert error.value.code == 503
    assert transport.calls == 1
    assert transport.ledger.snapshot()['summary']['unresolved_reserve_micro_usd'] == 2_200_000
    assert all('NEVER-EXPORT' not in path.read_text() for path in tmp_path.rglob('*.json'))


def test_disconnected_worker_does_not_refund_or_drop_provider_usage(tmp_path):
    entered, release = threading.Event(), threading.Event()
    def delayed(*unused):
        entered.set()
        assert release.wait(5)
        return reply()
    transport = setup(tmp_path, delayed)
    with model_broker(transport, tmp_path / 'broker') as (url, token):
        parsed = urlsplit(url)
        body = request(url, token).data
        peer = socket.create_connection((parsed.hostname, parsed.port), timeout=5)
        peer.sendall((f'POST /completion HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {token}\r\nContent-Length: {len(body)}\r\n\r\n').encode() + body)
        assert entered.wait(5)
        peer.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        peer.close()
        release.set()
        deadline = time.monotonic() + 5
        while not list((tmp_path / 'broker').glob('*.delivery.json')) and time.monotonic() < deadline:
            time.sleep(.02)
        files = list((tmp_path / 'broker').glob('*.delivery.json'))
        assert len(files) == 1
        assert json.loads(files[0].read_text())['state'] in {'orphaned_response', 'socket_write_completed_not_proof_of_worker_consumption'}
    assert transport.calls == 1
    assert transport.ledger.snapshot()['summary']['estimated_micro_usd'] == 100
    assert transport.ledger.snapshot()['summary']['unknown_attempts'] == 0


def test_exit_waits_for_inflight_charge_before_transport_reuse(tmp_path):
    entered, release, leaving, exited = (threading.Event() for _ in range(4))
    def delayed(*unused):
        entered.set()
        assert release.wait(10)
        return reply()
    transport = setup(tmp_path, delayed)
    clients = []
    def owner():
        with model_broker(transport, tmp_path / 'broker') as (url, token):
            def client():
                with build_opener(ProxyHandler({})).open(request(url, token), timeout=10) as response:
                    json.load(response)
            clients.append(threading.Thread(target=client))
            clients[0].start()
            assert entered.wait(5)
            leaving.set()
        exited.set()
    thread = threading.Thread(target=owner)
    thread.start()
    try:
        assert leaving.wait(5)
        assert not exited.wait(.7)
    finally:
        release.set()
        thread.join(10)
        for client in clients:
            client.join(10)
    assert exited.is_set()
    assert transport.ledger.snapshot()['summary']['unknown_attempts'] == 0
    assert transport.ledger.snapshot()['summary']['estimated_micro_usd'] == 100
