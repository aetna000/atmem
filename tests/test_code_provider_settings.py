"""Provider route settings use the same persistent CLI/dashboard boundary."""
import base64
from types import SimpleNamespace

import pytest


def test_route_dashboard_parity_and_tag_cannot_grant_authority(tmp_path, monkeypatch):
    pytest.importorskip("sqlcipher3")
    from atmem.code.application import CodeApplication
    from atmem.code.dashboard import execute
    from atmem.code.identity import CodeIdentity
    from atmem.code.providers import CodeRouter
    from atmem.code.contracts import CodeContextRequest
    from atmem.delegated.config import DelegatedConfigStore, DelegatedRegistration
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    database = tmp_path / "memory.db"
    HouseholdApplication.initialize(database, encrypted=True)
    memory = Memory(database, auto_vectors=False)
    scope = CodeIdentity(memory.store).resolve(tmp_path, subject_id="local", profile_id="shared", agent_id="codex")
    registration = DelegatedRegistration("docs", "1", "local", "key-1", base64.b64encode(bytes(32)).decode(),
                                        "http://127.0.0.1:8788/context", (scope.project_id + ":shared",), ("codex",), ("local",))
    monkeypatch.setattr(DelegatedConfigStore, "registrations", lambda _: [registration])
    route = {"route_id": "docs", "registration_id": registration.registration_id, "tags": ["docs"],
             "profiles": ["shared"], "agents": ["codex"], "egress_enabled": False, "fallback": "withhold"}
    try:
        app = CodeApplication(memory, subject_id="local")
        app.dispatch("route-set", {"project_id": scope.project_id, "route": route})
        manager = SimpleNamespace(state=lambda: None, _generic_memory_db=lambda _: database)
        session = {"account": {"role": "administrator", "password_change_required": False,
                                "scope": {"subject_id": "local", "workspace_id": None}}}
        body = {"project_id": scope.project_id, "action": "routes"}
        assert execute(manager, session, body, read_only=True)["routes"] == [route]
        execute(manager, session, {**body, "action": "route-set", "route": {**route, "fallback": "native"}})
        assert app.dispatch("routes", body)["routes"][0]["fallback"] == "native"
        def unexpected(*_args, **_kwargs):
            pytest.fail("disabled egress reached transport")
        router = CodeRouter(app, transport=unexpected)
        request = CodeContextRequest("request-1", "session-1", "turn-1", "formatter", 4096, scope)
        with pytest.raises(PermissionError, match="egress"):
            router.prepare(request, tags=("docs",))
        with pytest.raises(ValueError):
            router.prepare(request, tags=("http://unregistered.invalid",))
        execute(manager, session, {**body, "action": "route-delete", "route_id": "docs"})
        assert app.dispatch("routes", body)["routes"] == []
    finally:
        memory.close()
