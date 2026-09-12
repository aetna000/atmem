"""One authorization and response model shared by HTTP, SDK, MCP and CLI."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from typing import Any, Callable
import uuid

from atmem.contracts.versions import capabilities
from atmem.core.canonical import canonical_json, sha256_hex


AGENT_OPERATIONS = frozenset({"memory:create", "memory:read", "query:run", "review:status", "health:read", "capabilities:read"})
ADMIN_OPERATIONS = AGENT_OPERATIONS | frozenset({"review:decide", "audit:read", "config:read", "config:write", "memory:delete", "migration:run", "lifecycle:write", "onboarding:run"})


class APIError(RuntimeError):
    def __init__(self, code: str, message: str, *, status: int = 400, request_id: str | None = None) -> None:
        self.code, self.status, self.request_id = code, status, request_id
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {"format": "atmem-api-error-v1", "error": {"code": self.code, "message": str(self)}, "request_id": self.request_id}


@dataclass(frozen=True, slots=True)
class APIPrincipal:
    principal_id: str
    role: str
    subject_id: str
    agent_id: str | None = None
    workspace_id: str | None = None
    tenant_id: str = "local"
    evidence_role: str | None = None

    @property
    def operations(self) -> frozenset[str]:
        return ADMIN_OPERATIONS if self.role == "admin" else AGENT_OPERATIONS

    def require(self, operation: str) -> None:
        if operation not in self.operations:
            raise APIError("forbidden", "operation is not available to this principal", status=403)

    @property
    def scope_sha256(self) -> str:
        return sha256_hex(canonical_json({"tenant_id": self.tenant_id, "subject_id": self.subject_id, "agent_id": self.agent_id, "workspace_id": self.workspace_id, "role": self.role}))


@dataclass(frozen=True, slots=True)
class CursorPage:
    items: tuple[dict[str, Any], ...]
    next_cursor: str | None
    count: int
    total: int
    request_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"format": "atmem-cursor-page-v1", "items": list(self.items), "next_cursor": self.next_cursor, "count": self.count, "total": self.total, "request_id": self.request_id}


class AtMemApplication:
    def __init__(self, manager: Any) -> None:
        self.manager = manager

    def health(self, principal: APIPrincipal) -> dict[str, Any]:
        principal.require("health:read")
        status = self.manager.status()
        return {"format": "atmem-api-health-v1", "status": "healthy" if status else "degraded", "mode": status.get("mode"), "limitations": [], "request_id": _request_id()}

    def capability_manifest(self, principal: APIPrincipal) -> dict[str, Any]:
        principal.require("capabilities:read")
        return {**capabilities(), "request_id": _request_id(), "allowed_operations": sorted(principal.operations)}

    def create_memory(self, principal: APIPrincipal, message: str, *, idempotency_key: str, session_id: str | None = None) -> dict[str, Any]:
        principal.require("memory:create")
        clean = str(message).strip()
        if not clean or not idempotency_key.strip():
            raise APIError("invalid_request", "message and idempotency_key are required")
        return self._idempotent(principal, "memory:create", idempotency_key, {"message": clean, "session_id": session_id}, lambda: self.manager.capture(clean, session_id=session_id, authenticated_user=True, subject_id=principal.subject_id, agent_id=principal.agent_id))

    def query(self, principal: APIPrincipal, query: str) -> dict[str, Any]:
        principal.require("query:run")
        if not str(query).strip():
            raise APIError("invalid_request", "query is required")
        return {"format": "atmem-api-query-result-v1", "result": self.manager.memory_query(str(query), subject_id=principal.subject_id, agent_id=principal.agent_id), "request_id": _request_id()}

    def list_memories(self, principal: APIPrincipal, *, query: str = "", limit: int = 50, cursor: str | None = None) -> CursorPage:
        principal.require("memory:read")
        bounded = max(1, min(int(limit), 100))
        offset = _decode_cursor(cursor, principal.scope_sha256) if cursor else 0
        result = self.manager.memory_search(query, limit=500, subject_id=principal.subject_id, agent_id=principal.agent_id, include_pending=principal.role == "admin")
        rows = sorted(result.get("records") or [], key=lambda item: (str(item.get("created_at") or ""), str(item.get("id") or "")))
        selected = tuple(rows[offset : offset + bounded])
        next_cursor = _encode_cursor(offset + bounded, principal.scope_sha256) if offset + bounded < len(rows) else None
        return CursorPage(selected, next_cursor, len(selected), len(rows), _request_id())

    def reviews(self, principal: APIPrincipal) -> dict[str, Any]:
        principal.require("review:status")
        value = self.manager.memory_reviews()
        if principal.role != "admin":
            value = {"format": value.get("format", "atmem-review-status-v1"), "count": int(value.get("count", 0))}
        return {**value, "request_id": _request_id()}

    def audit(self, principal: APIPrincipal, *, limit: int = 100, cursor: int | None = None) -> dict[str, Any]:
        principal.require("audit:read")
        return {**self.manager.memory_audit(limit=max(1, min(limit, 100)), cursor=cursor), "request_id": _request_id()}

    def executions(self, principal: APIPrincipal, *, limit: int = 50) -> dict[str, Any]:
        from atmem.service.executions import ExecutionService

        return {**ExecutionService(self.manager).list(principal, limit=limit), "request_id": _request_id()}

    def execution(self, principal: APIPrincipal, execution_id: str) -> dict[str, Any]:
        from atmem.service.executions import ExecutionService

        return {**ExecutionService(self.manager).get(principal, execution_id), "request_id": _request_id()}

    def evidence_status(self, principal: APIPrincipal) -> dict[str, Any]:
        self._evidence_principal(principal)
        return {**self.manager.evidence_service().protection_status(), "request_id": _request_id()}

    def evidence_run(self, principal: APIPrincipal, run_id: str) -> dict[str, Any]:
        evidence_principal = self._evidence_principal(principal)
        events = self.manager.evidence_service().events(evidence_principal, run_id)
        return {
            "format": "atmem-protected-evidence-run-v1",
            "run_id": run_id,
            "events": events,
            "request_id": _request_id(),
        }

    def evidence_reconstruct(self, principal: APIPrincipal, run_id: str) -> dict[str, Any]:
        evidence_principal = self._evidence_principal(principal)
        return {
            **self.manager.evidence_service().reconstruct(evidence_principal, run_id),
            "request_id": _request_id(),
        }

    def evidence_search(self, principal: APIPrincipal, query: str) -> dict[str, Any]:
        evidence_principal = self._evidence_principal(principal)
        return {
            "format": "atmem-protected-evidence-search-v1",
            "query": query,
            "events": self.manager.evidence_service().search(evidence_principal, query),
            "request_id": _request_id(),
        }

    def evidence_replay_manifest(self, principal: APIPrincipal, run_id: str) -> dict[str, Any]:
        evidence_principal = self._evidence_principal(principal)
        return {**self.manager.evidence_service().replay_manifest(evidence_principal, run_id), "request_id": _request_id()}

    def evidence_delete(self, principal: APIPrincipal, run_id: str, *, confirmation: str) -> dict[str, Any]:
        evidence_principal = self._evidence_principal(principal)
        return {**self.manager.evidence_service().delete_run(evidence_principal, run_id, confirmation=confirmation), "request_id": _request_id()}

    def evidence_rotate(self, principal: APIPrincipal, *, confirmation: str) -> dict[str, Any]:
        evidence_principal = self._evidence_principal(principal)
        return {**self.manager.evidence_service().rotate_key(evidence_principal, confirmation=confirmation), "request_id": _request_id()}

    def evidence_lock(self, principal: APIPrincipal, *, confirmation: str) -> dict[str, Any]:
        evidence_principal = self._evidence_principal(principal)
        return {**self.manager.evidence_service().lock(evidence_principal, confirmation=confirmation), "request_id": _request_id()}

    def evidence_unlock(self, principal: APIPrincipal, *, confirmation: str) -> dict[str, Any]:
        evidence_principal = self._evidence_principal(principal)
        return {**self.manager.evidence_service().unlock(evidence_principal, confirmation=confirmation), "request_id": _request_id()}

    def evidence_grant(self, principal: APIPrincipal, body: dict[str, Any]) -> dict[str, Any]:
        from atmem.evidence import EvidenceRole, EvidenceScope

        evidence_principal = self._evidence_principal(principal)
        scope = EvidenceScope(
            evidence_principal.scope.tenant_id,
            evidence_principal.scope.subject_id,
            body.get("workspace_id") or evidence_principal.scope.workspace_id,
            body.get("run_id"),
        )
        return {
            **self.manager.evidence_service().grant(
                evidence_principal,
                principal_id=str(body.get("principal_id") or ""),
                role=EvidenceRole(str(body.get("role") or "")),
                scope=scope,
            ),
            "request_id": _request_id(),
        }

    def evidence_revoke(self, principal: APIPrincipal, principal_id: str) -> dict[str, Any]:
        evidence_principal = self._evidence_principal(principal)
        return {
            "principal_id": principal_id,
            "revoked": self.manager.evidence_service().revoke(
                evidence_principal, principal_id=principal_id
            ),
            "request_id": _request_id(),
        }

    def evidence_plaintext_export(
        self, principal: APIPrincipal, run_id: str, *, confirmation: str
    ) -> dict[str, Any]:
        evidence_principal = self._evidence_principal(principal)
        content = self.manager.evidence_service().plaintext_export(
            evidence_principal, run_id, confirmation=confirmation
        )
        return {
            "format": "atmem-plaintext-evidence-export-v1",
            "run_id": run_id,
            "content_base64": base64.b64encode(content).decode(),
            "warning": "AtMem encryption no longer protects the decoded plaintext copy.",
            "streaming": False,
            "request_id": _request_id(),
        }

    def evidence_capture_mode(
        self, principal: APIPrincipal, mode: str
    ) -> dict[str, Any]:
        from atmem.evidence import CaptureMode

        evidence_principal = self._evidence_principal(principal)
        return {
            **self.manager.evidence_service().set_capture_mode(
                evidence_principal, CaptureMode(mode)
            ),
            "request_id": _request_id(),
        }

    def configuration(self, principal: APIPrincipal) -> dict[str, Any]:
        principal.require("config:read")
        return {"format": "atmem-api-configuration-v1", "status": self.manager.status(), "request_id": _request_id()}

    def feature_status(self, principal: APIPrincipal, feature: str) -> dict[str, Any]:
        principal.require("capabilities:read")
        known = {"graph", "storage", "adapters", "interchange", "lifecycle", "media", "onboarding", "production"}
        if feature not in known:
            raise APIError("not_found", "unknown feature capability", status=404)
        manifest = capabilities()
        return {"format": "atmem-feature-status-v1", "feature": feature, "available": True, "mode": self.manager.status().get("mode"), "framework_adapters": manifest.get("framework_adapters") if feature == "adapters" else None, "request_id": _request_id()}

    def lifecycle(self, principal: APIPrincipal, record_id: str, *, evaluated_at: str | None = None) -> dict[str, Any]:
        principal.require("memory:read")
        from atmem.lifecycle import LifecycleService
        from atmem.memory import Memory
        memory=Memory(self.manager._generic_memory_db(self.manager.state()),retain_query_text=False)
        try: return {**LifecycleService(memory.store).inspect(principal.subject_id,record_id,evaluated_at=evaluated_at),"request_id":_request_id()}
        finally: memory.close()

    def transition_lifecycle(self, principal: APIPrincipal, body: dict[str, Any]) -> dict[str, Any]:
        principal.require("lifecycle:write")
        from atmem.lifecycle import LifecycleService, LifecycleState, LifecycleTransition
        from atmem.memory import Memory
        memory=Memory(self.manager._generic_memory_db(self.manager.state()),retain_query_text=False)
        try:
            request=LifecycleTransition(str(body["record_id"]),principal.subject_id,LifecycleState(str(body["to_state"])),int(body["base_generation"]),principal.principal_id,str(body["reason"]),tuple(body.get("evidence") or ()))
            return {"format":"atmem-api-lifecycle-result-v1","receipt":LifecycleService(memory.store).transition(request).to_dict(),"request_id":_request_id()}
        finally: memory.close()

    def interchange_plan(self, principal: APIPrincipal, body: dict[str, Any]) -> dict[str, Any]:
        principal.require("migration:run")
        from atmem.interchange import ArchiveRecord, InterchangeImporter, ScopeMap
        from atmem.memory import Memory
        scope=ScopeMap(principal.subject_id,str(body["workspace_id"]),str(body["agent_id"]),principal.tenant_id)
        records=[ArchiveRecord(str(row["source_id"]),str(row["content"]),scope,status=str(row.get("status","active")),source=str(row.get("source","neutral")),metadata=dict(row.get("metadata") or {})) for row in body.get("records",())]
        memory=Memory(self.manager._generic_memory_db(self.manager.state()),retain_query_text=False)
        try: return {**InterchangeImporter(memory).dry_run(records).to_dict(),"request_id":_request_id()}
        finally: memory.close()

    def revoke_media(self, principal: APIPrincipal, artifact_id: str) -> dict[str, Any]:
        principal.require("memory:delete")
        from atmem.media.service import MediaService
        from atmem.memory import Memory
        memory=Memory(self.manager._generic_memory_db(self.manager.state()),retain_query_text=False)
        try: return {**MediaService(memory.store).revoke(artifact_id),"request_id":_request_id()}
        finally: memory.close()

    def _idempotent(self, principal: APIPrincipal, operation: str, key: str, payload: dict[str, Any], call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        from atmem.memory import Memory
        state = self.manager.state()
        database = self.manager._generic_memory_db(state)
        memory = Memory(database, retain_query_text=False)
        digest = sha256_hex(canonical_json(payload))
        try:
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            with memory.store.transaction():
                row = memory.store._conn.execute("SELECT payload_sha256,response_json,status_code FROM api_idempotency_receipts WHERE principal_scope_sha256=? AND operation=? AND idempotency_key=?", (principal.scope_sha256, operation, key)).fetchone()
                if row:
                    if str(row["payload_sha256"]) != digest:
                        raise APIError("idempotency_conflict", "idempotency key was already used with a different payload", status=409)
                    if int(row["status_code"]) == 102:
                        raise APIError("operation_in_progress", "the idempotent operation is already in progress", status=409)
                    return json.loads(row["response_json"])
                memory.store._conn.execute("INSERT INTO api_idempotency_receipts VALUES(?,?,?,?,?,?,?,?)", (principal.scope_sha256, operation, key, digest, "{}", 102, now.isoformat(), (now + timedelta(days=1)).isoformat()))
            try:
                response = {"format": "atmem-api-mutation-result-v1", "result": call(), "request_id": _request_id(), "idempotent_replay": False}
            except BaseException:
                # A caller may safely retry only when the mutation itself did
                # not return. Keep the claim as an explicit ambiguous outcome
                # rather than risking a duplicate side effect.
                with memory.store.transaction():
                    memory.store._conn.execute("UPDATE api_idempotency_receipts SET response_json=?,status_code=500 WHERE principal_scope_sha256=? AND operation=? AND idempotency_key=?", (json.dumps({"format": "atmem-api-error-v1", "error": {"code": "mutation_outcome_unknown", "message": "mutation failed after its idempotency claim"}}), principal.scope_sha256, operation, key))
                raise
            with memory.store.transaction():
                memory.store._conn.execute("UPDATE api_idempotency_receipts SET response_json=?,status_code=200 WHERE principal_scope_sha256=? AND operation=? AND idempotency_key=?", (json.dumps(response, sort_keys=True), principal.scope_sha256, operation, key))
            return response
        finally:
            memory.close()

    @staticmethod
    def _evidence_principal(principal: APIPrincipal):
        from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope

        if principal.evidence_role is None:
            raise APIError(
                "forbidden",
                "an explicit evidence privilege is required",
                status=403,
            )
        return EvidencePrincipal(
            principal_id=principal.principal_id,
            role=EvidenceRole(principal.evidence_role),
            scope=EvidenceScope(
                principal.tenant_id,
                principal.subject_id,
                principal.workspace_id,
            ),
        )


def _request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


def _encode_cursor(offset: int, scope_sha256: str) -> str:
    return base64.urlsafe_b64encode(canonical_json({"offset": offset, "scope_sha256": scope_sha256}).encode()).decode().rstrip("=")


def _decode_cursor(cursor: str, scope_sha256: str) -> int:
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if value["scope_sha256"] != scope_sha256:
            raise ValueError
        return max(0, int(value["offset"]))
    except Exception as exc:
        raise APIError("invalid_cursor", "cursor is invalid or belongs to another scope", status=400) from exc
