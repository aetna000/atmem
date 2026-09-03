from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from atmem.delegated.contracts import DelegatedBinding, DelegatedContextRequest
from atmem.delegated.validation import parse_and_verify_envelope
from atmem.provider_adapters.models import ContextItem, ProviderProposal, ProviderRuntimeIdentity
from atmem.provider_adapters.runtime import ProviderRuntime, build_context, parse_request
from atmem.provider_adapters.signing import generate_keypair, load_private_key


def request_dict(*, maximum: int = 4096) -> dict:
    return DelegatedContextRequest.create(
        binding=DelegatedBinding("run", "turn", "session", "agent", "user", "workspace"),
        query="What do I like?", max_context_bytes=maximum, timeout_ms=10_000,
    ).to_dict()


def runtime(tmp_path: Path, provider) -> tuple[ProviderRuntime, SimpleNamespace]:
    private, public = tmp_path / "private.key", tmp_path / "public.key"
    public_value = generate_keypair(private, public)
    identity = ProviderRuntimeIdentity("test-provider", "1.0", "test", "primary")
    trust = SimpleNamespace(
        provider_id="test-provider", provider_version="1.0", provider_instance_id="test",
        key_id="primary", public_key_base64=public_value,
        workspace_ids=("workspace",), agent_ids=("agent",), user_ids=("user",),
    )
    return ProviderRuntime(provider=provider, identity=identity, private_key=load_private_key(private), adapter_kind="test"), trust


def test_runtime_produces_existing_verifiable_contract(tmp_path: Path) -> None:
    class Provider:
        def decide(self, request):
            return ProviderProposal.inject([ContextItem("User likes burgers.", "memory:1")])

    service, trust = runtime(tmp_path, Provider())
    envelope = service.handle(request_dict())
    verified = parse_and_verify_envelope(
        __import__("json").dumps(envelope), expected_binding=DelegatedBinding.from_dict(envelope["binding"]), trust=trust,
    )
    assert verified.context_text == "Memory: User likes burgers.\n"
    assert verified.source_refs == ("memory:1",)


def test_closed_request_and_digest_are_enforced() -> None:
    value = request_dict()
    value["unknown"] = True
    with pytest.raises(ValueError, match="fields"):
        parse_request(value)
    value = request_dict()
    value["query_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest"):
        parse_request(value)


def test_context_builder_never_slices_an_item() -> None:
    items = (ContextItem("short", "one"), ContextItem("x" * 100, "two"))
    context, refs = build_context(items, 20)
    assert context == b"Memory: short\n"
    assert refs == ("one",)


def test_key_permissions_fail_closed(tmp_path: Path) -> None:
    private, public = tmp_path / "private.key", tmp_path / "public.key"
    generate_keypair(private, public)
    private.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        load_private_key(private)


def test_expired_request_is_rejected() -> None:
    value = request_dict()
    value["deadline"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    with pytest.raises(TimeoutError):
        parse_request(value)
