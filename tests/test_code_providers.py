import base64
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def router_fixture(env):
    from atmem.code.providers import CodeRouter
    from atmem.delegated.config import DelegatedRegistration
    from atmem.delegated.contracts import DelegatedContextRequest
    from atmem.provider_adapters.models import ContextItem, ProviderProposal, ProviderRuntimeIdentity
    from atmem.provider_adapters.runtime import ProviderRuntime
    key = Ed25519PrivateKey.generate()
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    registration = DelegatedRegistration("docs", "1", "local", "key-1", public,
        "http://127.0.0.1:8788/v1/delegated-context", (env.project + ":shared",), ("codex",), ("local",), enabled=True)
    config = SimpleNamespace(registrations=lambda: [registration])
    runtime = ProviderRuntime(provider=SimpleNamespace(decide=lambda _: ProviderProposal.inject([ContextItem("Use the project formatter.", "docs:formatter")])),
                              identity=ProviderRuntimeIdentity("docs", "1", "local", "key-1"), private_key=key, adapter_kind="local-rag")
    calls = []

    def transport(registration, *, binding, query):
        calls.append(query)
        request = DelegatedContextRequest.create(binding=binding, query=query, max_context_bytes=4096, timeout_ms=3000)
        return json.dumps(runtime.handle(request.to_dict())).encode()

    router = CodeRouter(env.app, config=config, transport=transport)
    route = {"route_id": "docs-route", "registration_id": registration.registration_id, "tags": ["docs"],
             "profiles": ["shared"], "agents": ["codex"], "egress_enabled": True, "fallback": "withhold"}
    router.configure("route-set", env.project, {"route": route})
    return router, calls, route


def test_signed_provider_routing_and_no_unintended_egress(code_env):
    from atmem.code.contracts import CodeContextRequest
    env = code_env
    env.seed()
    router, calls, route = router_fixture(env)
    request = CodeContextRequest("request-1", "session-1", "turn-1", "formatter", 4096, env.scope)
    assert router.prepare(request)["authority"] == "atmem" and calls == []
    result = router.prepare(request, tags=("docs",))
    assert result["authority"] == "delegated-context"
    assert result["decision"] == "inject"
    assert "project formatter" in result["package"].content
    assert calls == ["formatter"]
    private = replace(request, scope=replace(env.scope, profile_id="private"))
    with pytest.raises(PermissionError):
        router.prepare(private, tags=("docs",))
    assert len(calls) == 1


def test_provider_failure_withholds_or_uses_configured_native_fallback(code_env):
    from atmem.code.contracts import CodeContextRequest
    env = code_env
    env.seed()
    router, _, route = router_fixture(env)
    router.transport = lambda *_args, **_kwargs: b'{"unsigned":"forged"}'
    request = CodeContextRequest("request-2", "session-1", "turn-2", "formatter", 4096, env.scope)
    result = router.prepare(request, tags=("docs",))
    assert result["decision"] == "provider_failure" and result["package"].content == ""
    router.configure("route-set", env.project, {"route": {**route, "fallback": "native"}})
    result = router.prepare(request, tags=("docs",))
    assert result["authority"] == "atmem_fallback"
    assert "Ruff" in result["package"].content
