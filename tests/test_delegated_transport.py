from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from email.message import Message
import hashlib
import http.client
import json
from pathlib import Path
import sqlite3
import threading
import time
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from atmem.delegated.client import authentication_headers, request_context, request_health
from atmem.delegated.config import DelegatedConfigStore, DelegatedRegistration
from atmem.delegated.contracts import DelegatedBinding, DelegatedContextRequest
from atmem.delegated.service import DelegatedContextService
from atmem.delegated.transport import (
    AuthenticationError, FIELDS, PREFIX, PROFILE, ReplayLedger, RequestAuthenticator,
    configure_keyring, load_keyring, load_secret, revoke_key, sign_headers, signing_input,
)
from atmem.delegated.validation import parse_and_verify_envelope
from atmem.provider_adapters.models import ContextItem, ProviderProposal, ProviderRuntimeIdentity
from atmem.provider_adapters.runtime import ProviderRuntime
from atmem.provider_adapters.server import create_server
from atmem.provider_adapters.signing import generate_keypair, load_private_key

VECTOR_PATH = Path(__file__).parents[1] / "docs/contracts/delegated-request-auth-v1.json"
VECTOR = json.loads(VECTOR_PATH.read_text())
BINDING = DelegatedBinding("run", "turn", "session", "agent", "user", "workspace")


def message(headers: dict[str, str]) -> Message:
    result = Message()
    for key, value in headers.items():
        result[key] = value
    return result


@pytest.fixture
def vector_auth(tmp_path, monkeypatch):
    monkeypatch.setattr("atmem.delegated.transport.time.time", lambda: VECTOR["issued"])
    secret = tmp_path / "fixture.key"
    secret.write_text(VECTOR["secret_base64"])
    secret.chmod(0o600)
    ring = tmp_path / "auth.json"
    ring.write_text(json.dumps({"profile": PROFILE, "provider_id": VECTOR["provider_id"],
        "instance_id": VECTOR["instance_id"], "active_key_id": VECTOR["key_id"],
        "keys": [{"key_id": VECTOR["key_id"], "secret_file": str(secret), "valid_until": None}]}))
    ring.chmod(0o600)
    auth = RequestAuthenticator(ring, tmp_path / "nonces.db")
    headers = sign_headers(secret=load_secret(secret), provider_id=VECTOR["provider_id"],
        instance_id=VECTOR["instance_id"], key_id=VECTOR["key_id"], method=VECTOR["method"],
        authority=VECTOR["authority"], target=VECTOR["target"], body=VECTOR["body_utf8"].encode(),
        now=VECTOR["issued"], nonce=VECTOR["nonce"])
    return auth, message({"Host": VECTOR["authority"], **headers})


def test_shared_known_answer_vector(vector_auth):
    auth, headers = vector_auth
    assert headers[PREFIX + "Signature"] == VECTOR["signature"]
    body = VECTOR["body_utf8"].encode()
    assert hashlib.sha256(body).hexdigest() == VECTOR["body_sha256"]
    auth.verify(method="POST", target=VECTOR["target"], headers=headers, body=body)


@pytest.mark.parametrize("vector", VECTOR["negative_vectors"], ids=lambda row: row["id"])
def test_shared_negative_vectors(vector_auth, monkeypatch, vector):
    auth, headers = vector_auth
    method, target, body = "POST", VECTOR["target"], VECTOR["body_utf8"].encode()
    change = vector["mutation"]
    if change == "remove_all_auth_headers":
        headers = message({"Host": VECTOR["authority"]})
    elif change == "duplicate_signature":
        headers[PREFIX + "Signature"] = headers[PREFIX + "Signature"]
    elif change == "append_body_space":
        body += b" "
    elif change == "change_method":
        method = "GET"
    elif change == "change_target":
        target += "?changed=1"
    elif change == "clock_at_expiry":
        monkeypatch.setattr("atmem.delegated.transport.time.time", lambda: VECTOR["expires"])
    elif change == "clock_before_issue_skew":
        monkeypatch.setattr("atmem.delegated.transport.time.time", lambda: VECTOR["issued"] - 6)
    else:
        field, value = {
            "change_host": ("Host", "127.0.0.1:9999"),
            "change_provider": (PREFIX + "Provider", "other"),
            "change_instance": (PREFIX + "Instance", "other"),
            "change_key": (PREFIX + "Key-Id", "other"),
            "change_nonce": (PREFIX + "Nonce", "02" * 32),
            "change_expiry": (PREFIX + "Expires", str(VECTOR["expires"] + 1)),
            "change_signature": (PREFIX + "Signature", "00" * 32),
        }[change]
        headers.replace_header(field, value)
    with pytest.raises(AuthenticationError):
        auth.verify(method=method, target=target, headers=headers, body=body)
    with sqlite3.connect(auth.ledger.path) as db:
        assert db.execute("SELECT COUNT(*) FROM nonces").fetchone()[0] == 0


def test_atomic_replay_restart_and_concurrency(vector_auth):
    auth, headers = vector_auth
    def attempt(_):
        try:
            auth.verify(method="POST", target=VECTOR["target"], headers=headers, body=VECTOR["body_utf8"].encode())
            return True
        except AuthenticationError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(16))) == 1
    restarted = RequestAuthenticator(auth.keyring, auth.ledger.path)
    with pytest.raises(AuthenticationError):
        restarted.verify(method="POST", target=VECTOR["target"], headers=headers, body=VECTOR["body_utf8"].encode())


@pytest.fixture
def live(tmp_path):
    auth_path = tmp_path / "request-auth.json"
    key = configure_keyring(auth_path, provider_id="synthetic", instance_id="local")
    public = generate_keypair(tmp_path / "private.key", tmp_path / "public.key")
    calls, statuses = [], []
    class Provider:
        def decide(self, request):
            calls.append(request.query)
            if request.query == "withhold":
                return ProviderProposal.withhold()
            return ProviderProposal(decision="inject", items=(ContextItem("Trip 🧠\r\nBooked", "ref:1"),), source_refs=("ref:1",))
    runtime = ProviderRuntime(provider=Provider(), identity=ProviderRuntimeIdentity("synthetic", "test", "local", "primary"),
        private_key=load_private_key(tmp_path / "private.key"), adapter_kind="test")
    runtime.request_authenticator = RequestAuthenticator(auth_path, tmp_path / "nonces.db")
    original_status = runtime.status
    def status():
        statuses.append(True)
        return original_status()
    runtime.status = status
    server = create_server(runtime, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    registration = DelegatedRegistration(provider_id="synthetic", provider_version="test", provider_instance_id="local",
        key_id="primary", public_key_base64=public, endpoint=f"http://127.0.0.1:{server.server_port}/v1/delegated-context",
        workspace_ids=("workspace",), agent_ids=("agent",), user_ids=("user",),
        request_key_id=key["request_key_id"], request_secret_file=key["request_secret_file"])
    try:
        yield SimpleNamespace(registration=registration, server=server, runtime=runtime, auth_path=auth_path,
            calls=calls, statuses=statuses, root=tmp_path)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def wire_request(live, query="trip"):
    body = json.dumps(DelegatedContextRequest.create(binding=BINDING, query=query,
        max_context_bytes=4096, timeout_ms=3000).to_dict()).encode()
    return Request(live.registration.endpoint, data=body, headers={"Content-Type": "application/json",
        **authentication_headers(live.registration, "POST", live.registration.endpoint, body)}, method="POST")


def test_http_unsigned_health_and_context_never_access_provider(live):
    for request in (Request(live.registration.endpoint, data=b"{}", headers={"Content-Type": "application/json"}),
                    Request(live.registration.endpoint.replace("/v1/delegated-context", "/health"))):
        with pytest.raises(HTTPError) as error:
            urlopen(request, timeout=2)
        assert error.value.code == 401
        assert json.loads(error.value.read()) == {"error": "request_authentication_rejected"}
    assert live.calls == live.statuses == []


def test_http_authenticated_inject_withhold_health_and_replay(live):
    for query in ("trip", "withhold"):
        raw = request_context(live.registration, binding=BINDING, query=query)
        verified = parse_and_verify_envelope(raw, expected_binding=BINDING, trust=live.registration)
        assert verified.decision == ("withhold" if query == "withhold" else "inject")
        if query == "trip":
            assert verified.context_bytes == "Memory: Trip 🧠\r\nBooked\n".encode()
    assert request_health(live.registration)["transport_profile"] == PROFILE
    request = wire_request(live)
    with urlopen(request, timeout=2) as response:
        assert response.status == 200
    live.runtime.request_authenticator = RequestAuthenticator(live.auth_path, live.root / "nonces.db")
    with pytest.raises(HTTPError) as error:
        urlopen(request, timeout=2)
    assert error.value.code == 401
    assert live.calls == ["trip", "withhold", "trip"]
    assert len(live.statuses) == 1
    assert b"Trip" not in (live.root / "nonces.db").read_bytes()


def test_http_concurrent_replay_invokes_provider_once(live):
    request = wire_request(live)
    def attempt(_):
        try:
            with urlopen(request, timeout=3) as response:
                return response.status
        except HTTPError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(12)))
    assert results.count(200) == 1
    assert results.count(401) == 11
    assert live.calls == ["trip"]


@pytest.mark.parametrize("kind", ["duplicate_signature", "duplicate_host", "duplicate_length", "transfer_encoding", "tampered_body", "expired_body"])
def test_http_adversarial_requests_never_call_provider(live, kind):
    request = wire_request(live)
    body = request.data
    headers = dict(request.header_items())
    if kind == "tampered_body":
        body += b" "
    if kind == "expired_body":
        value = json.loads(body)
        value["deadline"] = "2000-01-01T00:00:00Z"
        body = json.dumps(value).encode()
        headers = {"Content-Type": "application/json", **authentication_headers(live.registration, "POST", live.registration.endpoint, body)}
    connection = http.client.HTTPConnection("127.0.0.1", live.server.server_port, timeout=2)
    connection.putrequest("POST", "/v1/delegated-context")
    for key, value in headers.items():
        connection.putheader(key, value)
    connection.putheader("Content-Length", str(len(body)))
    if kind == "duplicate_signature":
        connection.putheader(PREFIX + "Signature", "00" * 32)
    if kind == "duplicate_host":
        connection.putheader("Host", f"127.0.0.1:{live.server.server_port}")
    if kind == "duplicate_length":
        connection.putheader("Content-Length", str(len(body)))
    if kind == "transfer_encoding":
        connection.putheader("Transfer-Encoding", "chunked")
    connection.endheaders(body)
    response = connection.getresponse()
    assert response.status in (400, 401, 504)
    response.read()
    connection.close()
    assert live.calls == []


def test_rotation_overlap_revocation_and_expiry(live, monkeypatch):
    now = int(time.time())
    monkeypatch.setattr("atmem.delegated.transport.time.time", lambda: now)
    old = live.registration
    result = configure_keyring(live.auth_path, provider_id="synthetic", instance_id="local", rotate=True, overlap_seconds=10)
    new = replace(old, request_key_id=result["request_key_id"], request_secret_file=result["request_secret_file"])
    request_health(old)
    request_health(new)
    now += 10
    with pytest.raises(HTTPError):
        request_health(old)
    request_health(new)
    next_key = configure_keyring(live.auth_path, provider_id="synthetic", instance_id="local", rotate=True, overlap_seconds=10)
    revoke_key(live.auth_path, new.request_key_id)
    with pytest.raises(HTTPError):
        request_health(new)
    request_health(replace(new, request_key_id=next_key["request_key_id"], request_secret_file=next_key["request_secret_file"]))
    assert len(live.statuses) == 4


def test_legacy_migration_preserves_block_and_explicit_activation(live):
    config = DelegatedConfigStore(live.root / "delegated.json")
    legacy = replace(live.registration, request_key_id=None, request_secret_file=None)
    config.register(legacy)
    with pytest.raises(AuthenticationError):
        config.set_enabled(legacy.registration_id, True)
    # Actual beta persisted shape, including previously enabled fallback.
    value = json.loads(config.path.read_text())
    row = value["registrations"][0]
    row.pop("request_key_id")
    row.pop("request_secret_file")
    row["enabled"] = row["native_fallback_on_failure"] = True
    config.path.write_text(json.dumps(value))
    service = DelegatedContextService(config)
    assert service.doctor()["state"] == "migration_required"
    with pytest.raises(AuthenticationError):
        config.match(workspace_id="workspace", agent_id="agent", user_id="user")
    assert live.calls == live.statuses == []
    configured = config.set_request_auth(legacy.registration_id, live.registration.request_key_id, live.registration.request_secret_file)
    assert configured["enabled"] is False
    config.set_enabled(legacy.registration_id, True)
    assert service.doctor()["ready"] is True
    assert "migration" not in config.status()["next_action"]


def test_missing_credential_prevents_any_network(live, monkeypatch):
    legacy = replace(live.registration, request_key_id=None, request_secret_file=None)
    monkeypatch.setattr("atmem.delegated.client.build_opener", lambda *a: pytest.fail("network attempted"))
    with pytest.raises(AuthenticationError):
        request_context(legacy, binding=BINDING, query="private query")


def test_replay_storage_capacity_clock_and_corruption(tmp_path):
    ledger = ReplayLedger(tmp_path / "nonces.db", capacity=1)
    ledger.reserve("scope", "a", 110, 100)
    with pytest.raises(AuthenticationError, match="capacity"):
        ledger.reserve("scope", "b", 110, 100)
    with pytest.raises(AuthenticationError, match="backwards"):
        ledger.reserve("scope", "b", 110, 99)
    ledger.reserve("scope", "b", 120, 110)
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TABLE nonces")
    with pytest.raises(AuthenticationError, match="storage"):
        ledger.reserve("scope", "c", 130, 120)
    with pytest.raises(AuthenticationError, match="storage"):
        ReplayLedger(ledger.path)


def test_replay_storage_loss_never_reinitializes(tmp_path):
    ledger = ReplayLedger(tmp_path / "nonces.db")
    ledger.reserve("scope", "a", 110, 100)
    ledger.path.unlink()
    with pytest.raises(AuthenticationError, match="storage"):
        ledger.reserve("scope", "a", 110, 100)
    with pytest.raises(AuthenticationError, match="storage"):
        ReplayLedger(ledger.path)
    assert not ledger.path.exists()


def test_existing_empty_replay_storage_is_not_reset(tmp_path):
    path = tmp_path / "nonces.db"
    path.touch(mode=0o600)
    with pytest.raises(AuthenticationError, match="storage"):
        ReplayLedger(path)


def test_secret_permissions_symlinks_and_key_separation(tmp_path):
    first = configure_keyring(tmp_path / "auth.json", provider_id="provider", instance_id="one")
    second = configure_keyring(tmp_path / "auth2.json", provider_id="provider", instance_id="two")
    assert load_secret(first["request_secret_file"]) != load_secret(second["request_secret_file"])
    path = Path(first["request_secret_file"])
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(AuthenticationError):
        load_secret(link)
    path.chmod(0o644)
    with pytest.raises(AuthenticationError):
        load_secret(path)


def test_server_requires_authenticator():
    with pytest.raises(ValueError, match="authentication"):
        create_server(object(), "127.0.0.1", 0)


@pytest.mark.parametrize("field", (*FIELDS, "Signature", "Host"))
@pytest.mark.parametrize("mutation", ("missing", "duplicate"))
def test_each_header_requires_exactly_one_occurrence(vector_auth, field, mutation):
    auth, headers = vector_auth
    name = field if field == "Host" else PREFIX + field
    if mutation == "missing":
        del headers[name]
    else:
        headers[name] = headers[name]
    with pytest.raises(AuthenticationError):
        auth.verify(method="POST", target=VECTOR["target"], headers=headers, body=VECTOR["body_utf8"].encode())


@pytest.mark.parametrize("issued,expires", [(1800000000, 1800000031), (1800000000, 1800000000),
    (1800000006, 1800000030), (1799999990, 1800000000)])
def test_even_valid_mac_cannot_override_time_policy(vector_auth, issued, expires):
    import hmac
    auth, headers = vector_auth
    fields = {field: headers[PREFIX + field] for field in FIELDS}
    fields.update(Issued=str(issued), Expires=str(expires))
    body = VECTOR["body_utf8"].encode()
    signature = hmac.new(base64.b64decode(VECTOR["secret_base64"]),
        signing_input("POST", VECTOR["authority"], VECTOR["target"], body, fields), hashlib.sha256).hexdigest()
    headers.replace_header(PREFIX + "Issued", str(issued))
    headers.replace_header(PREFIX + "Expires", str(expires))
    headers.replace_header(PREFIX + "Signature", signature)
    with pytest.raises(AuthenticationError):
        auth.verify(method="POST", target=VECTOR["target"], headers=headers, body=body)


def test_health_replay_does_not_disclose_identity_again(live):
    endpoint = live.registration.endpoint.replace("/v1/delegated-context", "/health")
    request = Request(endpoint, headers=authentication_headers(live.registration, "GET", endpoint))
    with urlopen(request, timeout=2) as response:
        assert json.loads(response.read())["provider_id"] == "synthetic"
    with pytest.raises(HTTPError) as error:
        urlopen(request, timeout=2)
    assert error.value.code == 401 and b"synthetic" not in error.value.read()
    assert live.statuses == [True]


def test_legacy_enabled_fallback_never_calls_native_or_provider(live, monkeypatch):
    from atmem.control.store import ControlStore
    config = DelegatedConfigStore(live.root / "legacy.json")
    config.register(replace(live.registration, request_key_id=None, request_secret_file=None))
    data = json.loads(config.path.read_text())
    data["registrations"][0].update(enabled=True, native_fallback_on_failure=True)
    config.path.write_text(json.dumps(data))
    def forbidden(*args, **kwargs):
        pytest.fail("legacy credentials reached transport")
    service = DelegatedContextService(config, transport=forbidden)
    store = ControlStore(live.root / "control.db")
    try:
        store.create_migration("migration", "generic", "user")
        result = service.prepare(query="secret query", binding=BINDING, migration_id="migration", store=store)
        assert result["authority"] == "delegated"
        assert result["native_fallback"] is False
        assert result["inject"] is False
    finally:
        store.close()


def test_blackbox_accepts_exact_delegated_byte_length():
    from atmem.control.blackbox import normalize_event
    event = normalize_event(migration_id="m", host="generic", event_type="context.injected", run_id="r",
        session_id="s", tool_call_id=None, payload={"context_byte_length": 43, "context_sha256": "ab" * 32})
    assert event["payload"]["context_byte_length"] == 43
