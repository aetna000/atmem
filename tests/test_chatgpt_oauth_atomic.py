"""Consent survives a failed code write; successful consent remains single-use."""
import copy
import time
from types import SimpleNamespace

import pytest

pytest.importorskip('google.cloud.firestore')
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from atmem.chatgpt import repository as module


@pytest.fixture
def consent_store(monkeypatch):
    rows = {}
    state = SimpleNamespace(fail_write=False)

    class Document:
        def __init__(self, key): self.key = key
        def get(self, **kwargs):
            row = rows.get(self.key)
            return SimpleNamespace(exists=row is not None, to_dict=lambda: row)

    class Transaction:
        def __init__(self): self.changes = []
        def set(self, doc, value):
            if state.fail_write: raise RuntimeError('synthetic code storage failure')
            self.changes.append(('set', doc.key, value))
        def delete(self, doc): self.changes.append(('delete', doc.key, None))

    def transactional(function):
        def run(transaction):
            result = function(transaction)
            updated = copy.deepcopy(rows)
            for operation, key, value in transaction.changes:
                if operation == 'set': updated[key] = value
                else: updated.pop(key, None)
            rows.clear(); rows.update(updated)
            return result
        return run

    monkeypatch.setattr(module.firestore, 'transactional', transactional)
    repo = object.__new__(module.Repository)
    repo.cipher = AESGCM(b'x' * 32)
    repo.settings = SimpleNamespace(opaque_id=lambda kind, key: kind + ':' + key)
    repo.root = SimpleNamespace(document=Document)
    repo.client = SimpleNamespace(transaction=lambda **kwargs: Transaction())
    pending = {'client_id': 'test', 'params': {}, 'expires_at': time.time() + 300}
    rows['authorize:nonce'] = {'envelope': repo.seal('authorize:nonce', module.json.dumps(pending).encode())}
    payload = {'subject': 'test-account', 'expires_at': time.time() + 90}
    return repo, rows, state, pending, payload


def test_failed_code_write_preserves_consent_for_retry(consent_store):
    repo, rows, state, pending, payload = consent_store
    state.fail_write = True
    with pytest.raises(RuntimeError, match='synthetic'):
        repo.complete_authorization('nonce', pending, 'test-account', 'code', payload)
    assert repo.get_control('authorize', 'nonce') == pending
    assert 'code:code' not in rows
    state.fail_write = False
    assert repo.complete_authorization('nonce', pending, 'test-account', 'code', payload)
    assert repo.get_control('authorize', 'nonce') is None
    assert repo.get_control('code', 'code') == payload
    assert not repo.complete_authorization('nonce', pending, 'test-account', 'another-code', payload)
    assert 'code:another-code' not in rows


def test_expired_or_changed_request_cannot_issue_code(consent_store):
    repo, rows, _, pending, payload = consent_store
    assert not repo.complete_authorization('nonce', pending | {'client_id': 'other'}, 'test-account', 'code', payload)
    expired = pending | {'expires_at': time.time() - 1}
    rows['authorize:nonce']['envelope'] = repo.seal('authorize:nonce', module.json.dumps(expired).encode())
    assert not repo.complete_authorization('nonce', expired, 'test-account', 'code', payload)
    assert 'code:code' not in rows


def test_cancel_consumes_request_without_code(consent_store):
    repo, rows, _, pending, _ = consent_store
    assert repo.complete_authorization('nonce', pending, '', None, None)
    assert 'authorize:nonce' not in rows
    assert not any(key.startswith('code:') for key in rows)


def test_wrong_subject_does_not_consume_request(consent_store):
    repo, rows, _, pending, payload = consent_store
    with pytest.raises(ValueError, match='subject_mismatch'):
        repo.complete_authorization('nonce', pending, 'other-account', 'code', payload)
    assert 'authorize:nonce' in rows
    assert 'code:code' not in rows


def test_provider_retries_failed_storage_without_losing_oauth_state(consent_store):
    from urllib.parse import parse_qs, urlsplit
    from atmem.chatgpt.auth import OAuthProvider
    repo, rows, state, pending, _ = consent_store
    pending['params'] = {
        'redirect_uri': 'https://client.example/callback',
        'redirect_uri_provided_explicitly': True,
        'scopes': ['memory:read'], 'state': 'original-state',
        'code_challenge': 'a' * 43, 'resource': 'https://atmem.example/mcp',
    }
    rows['authorize:nonce']['envelope'] = repo.seal('authorize:nonce', module.json.dumps(pending).encode())
    provider = object.__new__(OAuthProvider)
    provider.repository = repo
    provider.settings = SimpleNamespace(issuer='https://atmem.example')
    state.fail_write = True
    with pytest.raises(RuntimeError, match='synthetic'):
        provider.finish_authorize('nonce', 'test-account', True)
    assert repo.get_control('authorize', 'nonce') == pending
    state.fail_write = False
    callback = provider.finish_authorize('nonce', 'test-account', True)
    query = parse_qs(urlsplit(callback).query)
    assert query['state'] == ['original-state']
    issued = repo.get_control('code', query['code'][0])
    assert issued['subject'] == 'test-account'
    assert issued['code_challenge'] == 'a' * 43
    assert issued['redirect_uri'] == 'https://client.example/callback'
    with pytest.raises(ValueError, match='expired_or_consumed'):
        provider.finish_authorize('nonce', 'test-account', True)
