"""Current in-process task API adapter, isolated to a benchmark-owned store.

Not an authenticated remote integration or full-fidelity evidence adapter.
The host boundary derives the proposing role; only operator setup enables/binds.
"""
from __future__ import annotations

from pathlib import Path


class ProductRefusal(RuntimeError):
    product_refusal = True


class AtMemTaskAdapter:
    def __init__(self, path: Path, scope_id: str, task_id: str):
        from atmem.contracts import AuthorityScope
        from atmem.contracts.task_state import HostSessionIdentity
        from atmem.store.sqlite import SQLiteStore
        from atmem.task_state.service import TaskStateService
        self.scope = AuthorityScope("continuity-fixture", "fixture-agent", "trial-" + scope_id)
        self.identity = HostSessionIdentity(host_type="generic", session_key=task_id,
                                            session_epoch="trial-1")
        self.task_id = task_id
        self.store = SQLiteStore(path)
        self.service = TaskStateService(self.store)

    def setup(self, operation_id: str) -> None:
        from atmem.contracts.task_state import ActorRole, TaskItem, TaskStartRequest
        from atmem.task_state.binding import SessionBindingService
        from atmem.task_state.enablement import ScopeEnablement
        self.service.start(TaskStartRequest(
            task_id=self.task_id, scope=self.scope, profile_id="general",
            profile_version="general-v1", goal="Smoke fixture: commit one effect",
            actor="benchmark-operator", actor_role=ActorRole.OPERATOR,
            idempotency_key="setup:" + self.task_id),
            items=(TaskItem(item_id=operation_id, kind="step", title="Fixture effect"),))
        ScopeEnablement(self.store).enable(self.scope, actor="benchmark-operator")
        SessionBindingService(self.store, self.service.clock).register(
            self.scope, self.identity, task_id=self.task_id, actor="benchmark-operator",
            reason="explicit isolated benchmark setup")

    def status(self, operation_id: str) -> str:
        return self.service.get(self.scope, self.task_id).state.item(operation_id).status.value

    def set_status(self, operation_id: str, status: str, attempt_id: str,
                   receipt: dict | None = None) -> dict:
        from atmem.contracts.task_state import HostTaskProposalRequest
        from atmem.task_state.host_boundary import HostBoundary
        revision = self.service.get(self.scope, self.task_id).state.revision
        evidence = []
        if status == "completed":
            if not receipt or receipt.get("outcome") != "confirmed_succeeded":
                raise ValueError("completion requires retained destination receipt")
            event_id = self.store.append_audit_event(
                subject_id=self.scope.subject_id, actor="continuity-smoke",
                event_type="benchmark.destination_receipt_observed",
                payload={"scope": self.scope.to_dict(), "operation_id": operation_id,
                         "attempt_id": attempt_id, "receipt": receipt,
                         "assurance": "host_reported_not_independently_verified"})
            evidence = [{"kind": "audit_event", "reference_id": event_id}]
        request = HostTaskProposalRequest.from_dict({
            "identity": self.identity.to_dict(), "task_id": self.task_id,
            "base_revision": revision, "idempotency_key": f"{attempt_id}:{status}:{revision}",
            "adapter": "continuity-smoke", "evidence": evidence, "operations": [{
                "kind": "set_item_status", "item_id": operation_id, "status": status,
                "reason": "unknown external outcome" if status == "blocked" else "fixture observation",
            }]})
        result = HostBoundary(self.service, self.store).propose(self.scope, request)
        if result.get("outcome") not in {"accepted", "no_change"}:
            raise ProductRefusal(f"AtMem refused task proposal: {result.get('reason_code', result.get('reason_codes'))}")
        return result

    def close(self) -> None:
        self.store.close()
