from types import SimpleNamespace

import pytest


def session(role="administrator", subject="local"):
    return {"account": {"role": role, "password_change_required": False,
                         "scope": {"subject_id": subject, "workspace_id": None}}}


def test_dashboard_auth_and_get_cannot_mutate():
    from atmem.code.dashboard import execute
    with pytest.raises(PermissionError):
        execute(None, session("viewer"), {"action": "search", "project_id": "project-1"})
    with pytest.raises(PermissionError):
        execute(None, session("investigator"), {"action": "config", "changes": {"auto_capture": False}})
    with pytest.raises(PermissionError):
        execute(None, session("investigator"), {"action": "projects", "subject_id": "other"})
    with pytest.raises(PermissionError, match="POST"):
        execute(None, session(), {"action": "forget", "project_id": "project-1", "record_id": "record-1"}, read_only=True)


def test_dashboard_and_cli_share_persistent_configuration(tmp_path):
    pytest.importorskip("sqlcipher3")
    from atmem.code.application import CodeApplication
    from atmem.code.dashboard import execute
    from atmem.code.identity import CodeIdentity
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    database = tmp_path / "memory.db"
    HouseholdApplication.initialize(database, encrypted=True)
    memory = Memory(database, auto_vectors=False)
    scope = CodeIdentity(memory.store).resolve(tmp_path, subject_id="local", profile_id="shared", agent_id="codex")
    CodeApplication(memory, subject_id="local").settings(scope.project_id, {"auto_capture": False})
    memory.close()
    manager = SimpleNamespace(state=lambda: None, _generic_memory_db=lambda _: database)
    body = {"action": "config", "project_id": scope.project_id}
    assert execute(manager, session(), body, read_only=True)["settings"]["auto_capture"] is False
    execute(manager, session(), {**body, "changes": {"auto_recall": False}})
    memory = Memory(database, auto_vectors=False)
    try:
        settings = CodeApplication(memory, subject_id="local").settings(scope.project_id)
        assert settings["auto_capture"] is False and settings["auto_recall"] is False
    finally:
        memory.close()
