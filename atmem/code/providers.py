"""Tag routing through AtMem's existing signed delegated context contract."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

from atmem.code.application import CodeApplication, digest
from atmem.code.context import build_context
from atmem.code.contracts import CodeContextPackage, CodeContextRequest, _id
from atmem.delegated.client import request_context
from atmem.delegated.config import DelegatedConfigStore
from atmem.delegated.contracts import DelegatedBinding
from atmem.delegated.validation import parse_and_verify_envelope
from atmem.extract.validation import screen_content


@dataclass(frozen=True)
class CodeRoute:
    route_id: str
    registration_id: str
    tags: tuple[str, ...]
    profiles: tuple[str, ...]
    agents: tuple[str, ...]
    egress_enabled: bool = False
    fallback: str = "withhold"

    @classmethod
    def from_dict(cls, value: dict) -> "CodeRoute":
        fields = {"route_id", "registration_id", "tags", "profiles", "agents", "egress_enabled", "fallback"}
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError("route fields do not match the contract")
        _id("route_id", value["route_id"])
        if not isinstance(value["registration_id"], str) or len(value["registration_id"]) > 256:
            raise ValueError("invalid registration reference")
        for field in ("tags", "profiles", "agents"):
            items = value[field]
            if not isinstance(items, list) or not 1 <= len(items) <= 32 or any(not isinstance(item, str) for item in items) or len(set(items)) != len(items):
                raise ValueError(f"{field} must be a bounded unique list")
            for item in items:
                _id(field, item)
        if type(value["egress_enabled"]) is not bool or value["fallback"] not in {"withhold", "native"}:
            raise ValueError("invalid route egress or fallback setting")
        return cls(value["route_id"], value["registration_id"], tuple(value["tags"]),
                   tuple(value["profiles"]), tuple(value["agents"]), value["egress_enabled"], value["fallback"])

    def to_dict(self) -> dict:
        return {"route_id": self.route_id, "registration_id": self.registration_id,
                "tags": list(self.tags), "profiles": list(self.profiles), "agents": list(self.agents),
                "egress_enabled": self.egress_enabled, "fallback": self.fallback}


class CodeRouter:
    def __init__(self, application: CodeApplication, *, config=None, transport=request_context) -> None:
        self.app = application
        self.config = config or DelegatedConfigStore()
        self.transport = transport

    def configure(self, action: str, project: str, body: dict) -> dict:
        self.app.authorize(project)
        if action == "route-set":
            route = CodeRoute.from_dict(body["route"])
            # A route points only at an existing registration. Credentials and
            # endpoints are managed at the delegated-provider boundary.
            if not any(row.registration_id == route.registration_id for row in self.config.registrations()):
                raise ValueError("delegated provider must be registered first")
            self.app.store.put_code_document(self.app.subject_id, project, "route", route.route_id, route.to_dict())
            self.app.store.append_audit_event(subject_id=self.app.subject_id, event_type="code.route_configured", actor="user",
                                              payload={"project_id": project, "route": route.to_dict()})
        elif action == "route-delete":
            _id("route_id", body.get("route_id"))
            self.app.store.delete_code_documents(self.app.subject_id, project, "route", body["route_id"])
        return {"routes": self.app.store.code_documents(self.app.subject_id, project, "route")}

    def prepare(self, request: CodeContextRequest, *, tags: tuple[str, ...] = (), repository_root: str | None = None) -> dict:
        self.app.authorize(request.scope.project_id)
        if request.scope.subject_id != self.app.subject_id:
            raise PermissionError("context subject mismatch")
        if not screen_content(request.task, trusted=True).admissible:
            raise PermissionError("context query failed secret screening")
        if not isinstance(tags, tuple) or len(tags) > 32:
            raise ValueError("invalid request tags")
        for tag in tags:
            _id("tag", tag)
        routes = [CodeRoute.from_dict(row) for row in self.app.store.code_documents(self.app.subject_id, request.scope.project_id, "route")]
        matches = [row for row in routes if set(tags).intersection(row.tags)]
        if len(matches) > 1:
            raise ValueError("request matches multiple context routes")
        if not matches:
            return {"authority": "atmem", "package": build_context(self.app.memory, request, repository_root=repository_root), "decision": "native"}
        route = matches[0]
        if request.scope.profile_id not in route.profiles or request.scope.agent_id not in route.agents:
            raise PermissionError("tagged route is not authorized for this profile and agent")
        if not route.egress_enabled:
            raise PermissionError("route egress is disabled")
        if not screen_content(request.task, trusted=True).admissible:
            raise PermissionError("outbound query failed secret screening")
        previous = None
        try:
            registration = next((row for row in self.config.registrations() if row.registration_id == route.registration_id), None)
            if registration is None or not registration.enabled:
                raise PermissionError("delegated registration is disabled or absent")
            workspace = f"{request.scope.project_id}:{request.scope.profile_id}"
            if (workspace not in registration.workspace_ids or request.scope.agent_id not in registration.agent_ids
                    or self.app.subject_id not in registration.user_ids):
                raise PermissionError("provider registration does not authorize this exact scope")
            binding = DelegatedBinding(request.request_id, request.turn_id, request.session_id,
                                       request.scope.agent_id, self.app.subject_id, workspace)
            previous = self.app.store.code_document(self.app.subject_id, request.scope.project_id, "provider-receipt", request.request_id)
            if previous and previous.get("envelope"):
                if previous.get("request") != request.to_dict() or previous.get("tags") != list(tags) or previous.get("route_id") != route.route_id:
                    raise PermissionError("context request ID replay conflict")
                import json
                raw = json.dumps(previous["envelope"]).encode()
            else:
                raw = self.transport(registration, binding=binding, query=request.task)
            verified = parse_and_verify_envelope(raw, expected_binding=binding, trust=registration,
                                                  max_context_bytes=min(request.max_context_bytes, registration.max_context_bytes))
            if verified.context_text and not screen_content(verified.context_text, trusted=False).admissible:
                raise PermissionError("provider context failed screening")
            replay_id = digest([verified.provider_id, verified.provider_instance_id, verified.nonce])
            marker = {"binding": binding.to_dict(), "sha256": verified.envelope_sha256}
            with self.app.store.transaction():
                replay = self.app.store.code_document(self.app.subject_id, request.scope.project_id, "provider-replay", replay_id)
                if replay is not None and replay != marker:
                    raise PermissionError("delegated provider replay conflict")
                turn = {"request_sha256": digest(request.to_dict()), "envelope_sha256": verified.envelope_sha256}
                reserved = self.app.store.code_document(self.app.subject_id, request.scope.project_id, "provider-turn", request.request_id)
                if reserved is not None and reserved != turn:
                    raise PermissionError("a different provider result already reserved this request")
                self.app.store.put_code_document(self.app.subject_id, request.scope.project_id, "provider-replay", replay_id, marker)
                self.app.store.put_code_document(self.app.subject_id, request.scope.project_id, "provider-turn", request.request_id, turn)
            attributed = (f"[Delegated context from {verified.provider_id}]\n" + verified.context_text) if verified.context_text else ""
            if len(attributed.encode()) > request.max_context_bytes:
                raise ValueError("attributed provider context exceeds request budget")
            package = CodeContextPackage(request.request_id, attributed,
                                         sha256(attributed.encode()).hexdigest(), ())
            result = {"authority": "delegated-context", "package": package, "decision": verified.decision,
                      "provider": verified.provider_id, "result_sha256": verified.envelope_sha256,
                      "source_refs": verified.envelope.get("source_refs", []), "envelope": verified.envelope}
        except Exception as exc:
            package = (build_context(self.app.memory, request, repository_root=repository_root) if route.fallback == "native" else
                       CodeContextPackage(request.request_id, "", sha256(b"").hexdigest(), ()))
            result = {"authority": "atmem_fallback" if route.fallback == "native" else "delegated-context",
                      "package": package, "decision": "provider_failure", "failure_code": type(exc).__name__}
        if not previous or not previous.get("envelope") or result.get("envelope"):
            self.app.store.put_code_document(self.app.subject_id, request.scope.project_id, "provider-receipt", request.request_id,
                                             {**result, "package": result["package"].to_dict(), "route_id": route.route_id,
                                              "scope": request.scope.to_dict(), "request": request.to_dict(), "tags": list(tags)})
        return {key: value for key, value in result.items() if key != "envelope"}
