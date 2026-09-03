from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sqlite3
import threading
import time
from urllib.error import HTTPError

import pytest

from atmem.control.store import ControlStore, SCHEMA_VERSION
from atmem.delegated.client import request_context
from atmem.delegated.config import DelegatedConfigStore, DelegatedRegistration
from atmem.delegated.contracts import DelegatedBinding, MAX_RESULT_BYTES
from atmem.delegated.service import DelegatedContextService
from atmem.delegated.validation import parse_and_verify_envelope, parse_json_strict


FIXTURES = Path(__file__).parents[1] / "docs/contracts/delegated-context-provider-v1"
NOW = datetime(2026, 9, 1, 12, 1, tzinfo=timezone.utc)


def _json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _registration(*, enabled: bool = True, fallback: bool = False, endpoint: str = "http://127.0.0.1:8788/v1/delegated-context") -> DelegatedRegistration:
    value = _json("trust.json")
    value.pop("fixture_key_only")
    return DelegatedRegistration(
        **value,
        endpoint=endpoint,
        timeout_ms=3000,
        max_context_bytes=262_144,
        enabled=enabled,
        native_fallback_on_failure=fallback,
    )


def _verify(envelope: dict, *, binding: DelegatedBinding | None = None, trust=None, now=NOW):
    return parse_and_verify_envelope(
        json.dumps(envelope, separators=(",", ":"), ensure_ascii=False),
        expected_binding=binding or DelegatedBinding.from_dict(envelope["binding"]),
        trust=trust or _registration(),
        now=now,
    )


def test_signed_positive_fixtures_verify_exact_bytes() -> None:
    inject = _verify(_json("inject.valid.json"))
    assert inject.context_bytes == "Reviewed context 🧠\r\nKeep these bytes.".encode()
    assert inject.context_sha256 == "b9daebf92b8034e9fd9dc3b704bc339c18b64f332bf2d09674c4d6a6c8950461"
    withhold = _verify(_json("withhold.valid.json"))
    assert withhold.decision == "withhold"
    assert withhold.context_bytes == b""
    assert withhold.withhold_reason == {"code": "REQUIRED_CONTEXT_MISSING", "retryable": False}


def test_duplicate_json_keys_are_rejected_before_interpretation() -> None:
    with pytest.raises(ValueError, match="duplicate JSON key"):
        parse_json_strict('{"decision":"inject","decision":"withhold"}')


@pytest.mark.parametrize(
    ("case_id", "change", "match"),
    [
        ("untrusted-provider", lambda e: None, "not locally trusted"),
        ("wrong-run-binding", lambda e: None, "turn binding"),
        ("wrong-turn-binding", lambda e: None, "turn binding"),
        ("wrong-session-binding", lambda e: None, "turn binding"),
        ("wrong-agent-binding", lambda e: None, "turn binding"),
        ("wrong-user-binding", lambda e: None, "turn binding"),
        ("wrong-workspace-binding", lambda e: None, "turn binding"),
        ("expired", lambda e: None, "expired"),
        ("future-created", lambda e: None, "future"),
        ("excessive-lifetime", lambda e: e.__setitem__("expires_at", "2026-09-01T12:10:00Z"), "lifetime"),
        ("context-digest-mismatch", lambda e: e["context"].__setitem__("sha256", "b" * 64), "digest mismatch"),
        ("context-length-mismatch", lambda e: e["context"].__setitem__("byte_length", e["context"]["byte_length"] + 1), "byte length"),
        ("invalid-base64", lambda e: e["context"].__setitem__("bytes_base64", "not base64"), "base64"),
        ("signature-tamper", lambda e: e["signature"].__setitem__("value_base64", base64.b64encode(bytes([base64.b64decode(e["signature"]["value_base64"])[0] ^ 1]) + base64.b64decode(e["signature"]["value_base64"])[1:]).decode()), "signature verification"),
        ("idempotency-tamper", lambda e: e.__setitem__("idempotency_key", "dcp-" + "0" * 64), "idempotency"),
        ("unknown-field", lambda e: e.__setitem__("raw_prompt", "prohibited"), "fields"),
        ("inject-with-reason", lambda e: e.__setitem__("withhold_reason", {"code": "POLICY_DENIED", "retryable": False}), "withholding reason"),
        ("withhold-with-context", lambda e: e.__setitem__("context", _json("inject.valid.json")["context"]), "cannot contain context"),
    ],
)
def test_pr_negative_validation_vectors(case_id, change, match) -> None:
    envelope = _json("withhold.valid.json" if case_id == "withhold-with-context" else "inject.valid.json")
    change(envelope)
    binding = DelegatedBinding.from_dict(envelope["binding"])
    trust = _registration()
    now = NOW
    if case_id == "untrusted-provider":
        trust = DelegatedRegistration(**{**trust.__dict__, "provider_id": "other"}) if hasattr(trust, "__dict__") else DelegatedRegistration(
            provider_id="other", provider_version=trust.provider_version,
            provider_instance_id=trust.provider_instance_id, key_id=trust.key_id,
            public_key_base64=trust.public_key_base64, endpoint=trust.endpoint,
            workspace_ids=trust.workspace_ids, agent_ids=trust.agent_ids,
            user_ids=trust.user_ids, timeout_ms=trust.timeout_ms,
            max_context_bytes=trust.max_context_bytes, enabled=True,
            native_fallback_on_failure=False,
        )
    elif case_id.startswith("wrong-"):
        field = case_id.removeprefix("wrong-").removesuffix("-binding") + "_id"
        values = binding.to_dict()
        values[field] = "wrong-" + field
        binding = DelegatedBinding.from_dict(values)
    elif case_id == "expired":
        now = datetime(2026, 9, 1, 12, 2, tzinfo=timezone.utc)
    elif case_id == "future-created":
        now = datetime(2026, 9, 1, 11, 59, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match=match):
        _verify(envelope, binding=binding, trust=trust, now=now)


def test_stateful_retry_turn_and_nonce_vectors(tmp_path: Path) -> None:
    store = ControlStore(tmp_path / "control.db")
    store.create_migration("migration", "openclaw", "subject")
    try:
        inject = _verify(_json("inject.valid.json"))
        first = store.accept_delegated_context("migration", inject)
        retry = store.accept_delegated_context("migration", inject)
        assert first["idempotent"] is False
        assert retry["idempotent"] is True
        with pytest.raises(ValueError, match="already reserved this turn"):
            store.accept_delegated_context("migration", _verify(_json("withhold.valid.json")))
        replay = _verify(_json("inject.next-turn-same-nonce.valid.json"))
        with pytest.raises(ValueError, match="nonce was already used"):
            store.accept_delegated_context("migration", replay)
    finally:
        store.close()


def test_config_is_native_default_scoped_and_hides_public_key(tmp_path: Path) -> None:
    config = DelegatedConfigStore(tmp_path / "delegated.json")
    assert config.status()["authority_default"] == "atmem"
    assert config.status()["enabled"] is False
    saved = config.register(_registration(enabled=False))
    assert "public_key_base64" not in json.dumps(saved)
    config.set_enabled(saved["registration_id"], True)
    assert config.match(workspace_id="workspace-demo", agent_id="agent-main", user_id="user-opaque-001")
    with pytest.raises(ValueError, match="authenticated user"):
        config.match(workspace_id="workspace-demo", agent_id="agent-main", user_id=None)
    assert oct(config.path.stat().st_mode & 0o777) == "0o600"


def test_registration_cannot_enable_authority_and_overlapping_scopes_fail(tmp_path: Path) -> None:
    config = DelegatedConfigStore(tmp_path / "delegated.json")
    with pytest.raises(ValueError, match="enable it separately"):
        config.register(_registration(enabled=True))
    first = _registration(enabled=False)
    config.register(first)
    config.set_enabled(first.registration_id, True)
    second = DelegatedRegistration(
        provider_id="storizon",
        provider_version=first.provider_version,
        provider_instance_id="second",
        key_id=first.key_id,
        public_key_base64=first.public_key_base64,
        endpoint="http://127.0.0.1:8789/v1/delegated-context",
        workspace_ids=first.workspace_ids,
        agent_ids=first.agent_ids,
        user_ids=first.user_ids,
        enabled=False,
    )
    config.register(second)
    with pytest.raises(ValueError, match="overlap"):
        config.set_enabled(second.registration_id, True)


def test_registration_rejects_bad_key_and_policy_limits() -> None:
    with pytest.raises(ValueError, match="base64"):
        DelegatedRegistration(
            provider_id="storizon", provider_version="1", provider_instance_id="bad",
            key_id="key", public_key_base64="bad", endpoint="http://127.0.0.1:8788/v1",
            workspace_ids=("workspace",), agent_ids=("agent",), user_ids=("user",),
        )
    with pytest.raises(ValueError, match="timeout"):
        DelegatedRegistration(
            **{
                **{name: getattr(_registration(enabled=False), name) for name in (
                    "provider_id", "provider_version", "provider_instance_id", "key_id",
                    "public_key_base64", "endpoint", "workspace_ids", "agent_ids", "user_ids",
                    "max_context_bytes", "enabled", "native_fallback_on_failure",
                )},
                "timeout_ms": 99,
            }
        )


def test_config_rejects_symlinks_and_loose_permissions(tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    config = DelegatedConfigStore(real)
    config.register(_registration(enabled=False))
    real.chmod(0o644)
    with pytest.raises(ValueError, match="permissions"):
        config.registrations()
    real.chmod(0o600)
    linked = tmp_path / "linked.json"
    linked.symlink_to(real)
    with pytest.raises(ValueError, match="regular file"):
        DelegatedConfigStore(linked).registrations()


def test_failed_turn_cannot_accept_late_provider_output(tmp_path: Path) -> None:
    store = ControlStore(tmp_path / "control.db")
    store.create_migration("migration", "openclaw", "subject")
    result = _verify(_json("inject.valid.json"))
    try:
        reservation = store.reserve_delegated_failure(
            "migration", result.binding, native_fallback=True
        )
        assert reservation["disposition"] == "native_fallback"
        with pytest.raises(ValueError, match="already closed"):
            store.accept_delegated_context("migration", result)
    finally:
        store.close()


def test_remote_registration_is_rejected() -> None:
    with pytest.raises(ValueError, match="loopback HTTP"):
        _registration(endpoint="https://example.com/v1/delegated-context")


def test_loopback_transport_sends_closed_request_and_retains_response_bytes() -> None:
    envelope = (FIXTURES / "inject.valid.json").read_bytes()
    captured: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            captured.append(json.loads(raw))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(envelope)))
            self.end_headers()
            self.wfile.write(envelope)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        registration = _registration(endpoint=f"http://127.0.0.1:{server.server_port}/v1/delegated-context")
        binding = DelegatedBinding.from_dict(_json("inject.valid.json")["binding"])
        assert request_context(registration, binding=binding, query="exact query") == envelope
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert set(captured[0]) == {"contract_id", "binding", "query", "query_sha256", "max_context_bytes", "deadline"}
    assert captured[0]["query"] == "exact query"


def test_loopback_transport_rejects_redirects_and_oversized_results() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/redirect":
                self.send_response(307)
                self.send_header("Location", "/result")
                self.end_headers()
                return
            body = b"x" * (MAX_RESULT_BYTES + 1)
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    binding = DelegatedBinding.from_dict(_json("inject.valid.json")["binding"])
    try:
        redirect = _registration(
            endpoint=f"http://127.0.0.1:{server.server_port}/redirect"
        )
        with pytest.raises(HTTPError, match="redirects are prohibited"):
            request_context(redirect, binding=binding, query="exact query")
        oversized = _registration(
            endpoint=f"http://127.0.0.1:{server.server_port}/result"
        )
        with pytest.raises(ValueError, match="response exceeds policy"):
            request_context(oversized, binding=binding, query="exact query")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_loopback_transport_enforces_timeout() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            time.sleep(0.3)
            try:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")
            except OSError:
                pass

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    binding = DelegatedBinding.from_dict(_json("inject.valid.json")["binding"])
    try:
        registration = DelegatedRegistration(
            **{
                **{
                    name: getattr(
                        _registration(
                            enabled=False,
                            endpoint=f"http://127.0.0.1:{server.server_port}/slow",
                        ),
                        name,
                    )
                    for name in (
                        "provider_id", "provider_version", "provider_instance_id",
                        "key_id", "public_key_base64", "endpoint", "workspace_ids",
                        "agent_ids", "user_ids", "max_context_bytes", "enabled",
                        "native_fallback_on_failure",
                    )
                },
                "timeout_ms": 100,
            }
        )
        with pytest.raises((TimeoutError, OSError)):
            request_context(registration, binding=binding, query="exact query")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_doctor_distinguishes_reachable_and_degraded_provider(tmp_path: Path) -> None:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = DelegatedConfigStore(tmp_path / "delegated.json")
    registration = _registration(
        enabled=False,
        endpoint=f"http://127.0.0.1:{server.server_port}/v1/delegated-context",
    )
    config.register(registration)
    config.set_enabled(registration.registration_id, True)
    service = DelegatedContextService(config)
    try:
        healthy = service.doctor()
        assert healthy["state"] == "ready"
        assert healthy["ready"] is True
        assert healthy["provider_health"][0]["reachable"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    degraded = service.doctor()
    assert degraded["state"] == "degraded"
    assert degraded["ready"] is False


def test_removing_registration_does_not_rewrite_historical_evidence(tmp_path: Path) -> None:
    config = DelegatedConfigStore(tmp_path / "delegated.json")
    registration = _registration(enabled=False)
    config.register(registration)
    store = ControlStore(tmp_path / "control.db")
    store.create_migration("migration", "openclaw", "subject")
    result = _verify(_json("inject.valid.json"))
    try:
        accepted = store.accept_delegated_context("migration", result)
        store.append_evidence(
            "migration",
            kind="delegated_context",
            body={
                "format": "atmem-delegated-context-authorization-v1",
                "acceptance_id": accepted["id"],
                "provider_id": "storizon",
            },
        )
        assert config.remove(registration.registration_id) is True
        assert config.registrations() == []
        retained = store.latest_evidence("migration", kind="delegated_context")
        assert retained is not None
        assert retained["body"]["acceptance_id"] == accepted["id"]
    finally:
        store.close()


def test_service_separates_authorization_delivery_and_persists_no_content(
    tmp_path: Path, monkeypatch
) -> None:
    config = DelegatedConfigStore(tmp_path / "delegated.json")
    registration = _registration(enabled=False)
    config.register(registration)
    config.set_enabled(registration.registration_id, True)
    verified = _verify(_json("inject.valid.json"))
    monkeypatch.setattr(
        "atmem.delegated.service.parse_and_verify_envelope",
        lambda *args, **kwargs: verified,
    )
    store = ControlStore(tmp_path / "control.db")
    store.create_migration("migration", "openclaw", "subject")
    try:
        decision = DelegatedContextService(
            config,
            transport=lambda *args, **kwargs: b"verified-by-test",
        ).prepare(
            query="private delegated query",
            binding=verified.binding,
            migration_id="migration",
            store=store,
        )
        assert decision is not None
        assert decision["context"].encode() == verified.context_bytes
        assert decision["authorization_event_id"]
        assert decision["exposure_id"]
        dump = "\n".join(store._conn.iterdump())
        assert "private delegated query" not in dump
        assert verified.context_text not in dump
        kinds = {
            row["kind"] for row in store._conn.execute("SELECT kind FROM evidence")
        }
        assert "delegated_context" in kinds
    finally:
        store.close()


def test_untrusted_user_scope_failure_is_reserved_and_evidenced(tmp_path: Path) -> None:
    config = DelegatedConfigStore(tmp_path / "delegated.json")
    registration = _registration(enabled=False)
    config.register(registration)
    config.set_enabled(registration.registration_id, True)
    expected = DelegatedBinding.from_dict(_json("inject.valid.json")["binding"])
    binding = DelegatedBinding(
        run_id=expected.run_id,
        turn_id=expected.turn_id,
        session_id=expected.session_id,
        agent_id=expected.agent_id,
        user_id="untrusted-user",
        workspace_id=expected.workspace_id,
    )
    store = ControlStore(tmp_path / "control.db")
    store.create_migration("migration", "openclaw", "subject")
    try:
        decision = DelegatedContextService(
            config,
            transport=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("provider transport ran for an untrusted user")
            ),
        ).prepare(
            query="private query",
            binding=binding,
            migration_id="migration",
            store=store,
        )
        assert decision is not None
        assert decision["authority"] == "delegated"
        assert decision["inject"] is False
        assert "trusted for this user" in decision["failure_reason"]
        evidence = store.latest_evidence("migration", kind="delegated_context")
        assert evidence is not None
        assert evidence["body"]["decision"] == "rejected"
        assert evidence["body"]["provider"] is None
        reservation = store._conn.execute(
            "SELECT disposition FROM delegated_turn_reservations"
        ).fetchone()
        assert reservation["disposition"] == "provider_failure"
    finally:
        store.close()


def test_control_store_schema_five_has_no_raw_context_columns(tmp_path: Path) -> None:
    store = ControlStore(tmp_path / "control.db")
    try:
        assert SCHEMA_VERSION == 5
        columns = {row["name"] for row in store._conn.execute("PRAGMA table_info(delegated_context_acceptances)")}
        assert "context_text" not in columns
        assert "query" not in columns
    finally:
        store.close()


def test_schema_four_upgrades_additively_and_preserves_existing_turn(tmp_path: Path) -> None:
    path = tmp_path / "control.db"
    store = ControlStore(path)
    store.create_migration("migration", "openclaw", "subject")
    turn = store.insert_turn(
        "migration",
        query_sha256="a" * 64,
        session_id="session",
        host_run_id="run",
    )
    store.close()
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        DROP TABLE delegated_context_deliveries;
        DROP TABLE delegated_context_acceptances;
        DROP TABLE delegated_turn_reservations;
        UPDATE schema_meta SET value = '4' WHERE key = 'schema_version';
        """
    )
    connection.commit()
    connection.close()

    upgraded = ControlStore(path)
    try:
        assert upgraded._conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()["value"] == "5"
        assert upgraded._conn.execute(
            "SELECT id FROM turns WHERE id = ?", (turn["id"],)
        ).fetchone() is not None
        assert upgraded._conn.execute(
            "SELECT name FROM sqlite_master WHERE name = 'delegated_context_acceptances'"
        ).fetchone() is not None
    finally:
        upgraded.close()


def test_delegated_acceptance_survives_backup_and_restart(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    store = ControlStore(source)
    store.create_migration("migration", "openclaw", "subject")
    result = _verify(_json("inject.valid.json"))
    accepted = store.accept_delegated_context("migration", result)
    store.close()
    shutil.copy2(source, backup)

    restored = ControlStore(backup)
    try:
        retried = restored.accept_delegated_context("migration", result)
        assert retried["id"] == accepted["id"]
        assert retried["idempotent"] is True
    finally:
        restored.close()


def test_concurrent_exact_acceptance_creates_one_row(tmp_path: Path) -> None:
    path = tmp_path / "control.db"
    initial = ControlStore(path)
    initial.create_migration("migration", "openclaw", "subject")
    initial.close()
    result = _verify(_json("inject.valid.json"))
    barrier = threading.Barrier(2)
    outcomes: list[dict] = []
    failures: list[Exception] = []

    def accept() -> None:
        store = ControlStore(path)
        try:
            barrier.wait(timeout=2)
            outcomes.append(store.accept_delegated_context("migration", result))
        except Exception as exc:  # pragma: no cover - asserted below
            failures.append(exc)
        finally:
            store.close()

    threads = [threading.Thread(target=accept) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert failures == []
    assert len(outcomes) == 2
    assert {row["id"] for row in outcomes} == {outcomes[0]["id"]}
    assert sorted(row["idempotent"] for row in outcomes) == [False, True]

    check = ControlStore(path)
    try:
        count = check._conn.execute(
            "SELECT COUNT(*) AS n FROM delegated_context_acceptances"
        ).fetchone()["n"]
        assert count == 1
    finally:
        check.close()
