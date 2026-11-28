"""Bind the local agent team to the signed-in dashboard account."""

from atmem.agent_team import run_agent_team
from atmem.memory import Memory


def execute(manager, identity_session, body: dict) -> dict:
    if set(body) - {"question", "policy", "max_calls"}:
        raise ValueError("Only question, policy and max_calls are accepted.")

    def binding():
        account = identity_session()["account"]
        access = account["scope"]
        if (account["role"] not in {"administrator", "investigator", "evidence_collector"}
                or account.get("password_change_required") or access.get("run_id")):
            raise PermissionError("Workspace memory access is required to run this team.")
        state, warning = manager.effective_state()
        if warning or not state.mode.influences_agent:
            raise PermissionError("Live team runs require an active AtMem memory provider.")
        scope, path = manager._memory_authority_scope(state, subject_id=access["subject_id"], agent_id=None)
        if access.get("workspace_id") and access["workspace_id"] != scope.workspace_id:
            raise PermissionError("Workspace is outside the signed-in account scope.")
        if manager.delegated_context_applies(agent_id=scope.agent_id, user_id=scope.subject_id,
                                            workspace_id=scope.workspace_id):
            raise PermissionError("This workspace uses a delegated context provider.")
        return account["username"], scope, path

    original = binding()
    _, scope, path = original

    def check_authority():
        if binding() != original:
            raise PermissionError("The signed-in workspace changed during the run.")

    memory = Memory(path, auto_vectors=False, retain_query_text=False)
    try:
        result = run_agent_team(memory, scope, body.get("question"), policy=body.get("policy", "adaptive"),
                                max_calls=body.get("max_calls", 2), check_authority=check_authority)
        check_authority()
        return result
    finally:
        memory.close()
