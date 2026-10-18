"""Authenticated dashboard commands use the same Code application as CLI."""

from atmem.code.application import CodeApplication
from atmem.memory import Memory


READ_ACTIONS = {"projects", "search", "inspect", "routes", "hosts", "host-status", "graph-search", "graph-status", "reviews"}
READ_ACTIONS |= {"knowledge-query", "knowledge-status", "knowledge-source"}


def execute(manager, session: dict, body: dict, *, read_only: bool = False) -> dict:
    account = session["account"]
    role = account["role"]
    if account.get("password_change_required") or role not in {"investigator", "evidence_collector", "administrator"}:
        raise PermissionError("memory access requires an investigator or administrator account")
    scope = account["scope"]
    action = str(body.get("action") or "projects")
    read = action in READ_ACTIONS or action == "config" and "changes" not in body
    if read_only and not read:
        raise PermissionError("Code mutations require a CSRF-protected POST")
    if not read and role != "administrator":
        raise PermissionError("Administrator access required to change Code memory")
    subject = str(body.get("subject_id") or scope["subject_id"])
    if subject != scope["subject_id"] and role != "administrator":
        raise PermissionError("subject is outside the signed-in scope")
    workspace = scope.get("workspace_id")
    if workspace and body.get("project_id") != workspace:
        raise PermissionError("project is outside the signed-in workspace")
    memory = Memory(manager._generic_memory_db(manager.state()), auto_vectors=False)
    try:
        return CodeApplication(memory, subject_id=subject).dispatch(action, body)
    finally:
        memory.close()
