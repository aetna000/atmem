"""Scoped operation authority backed by the encrypted evidence vault."""
from __future__ import annotations

from contextlib import contextmanager
import copy
import math
import re
import secrets
import time
import uuid
import hashlib
import json

from atmem.evidence.models import CaptureMode, EvidenceOperation, EvidenceRole, EvidenceScope
from atmem.evidence.service import EvidenceService
from atmem.core.canonical import canonical_json


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("use an opaque identifier of 1–128 letters, digits, underscores or hyphens")
    return value


class ContinuityService:
    """Only this service decides whether a governed operation may be attempted."""

    MAX_OPEN_COORDINATOR_WORKFLOWS = 500
    MAX_COORDINATOR_RETAINED_BYTES = 64 * 1024 * 1024
    MAX_REVISIONS = 2000

    def __init__(self, evidence: EvidenceService, *, clock=time.time):
        self.evidence = evidence
        self.clock = clock

    def _fresh(self):
        # Reopen per operation: an old instance must not retain a locked/rotated key.
        return EvidenceService(self.evidence.root, vault_id=self.evidence.vault_id,
                               home_root=self.evidence.home_root)

    @contextmanager
    def _store(self):
        with self.evidence.key_transition_lock(), self._fresh()._store() as store, store.atomic():
            yield store

    @staticmethod
    def _authorize(principal, workflow, *, control=False):
        scope = EvidenceScope(**workflow["scope"])
        target = EvidenceScope(scope.tenant_id, scope.subject_id, scope.workspace_id, workflow["workflow_id"])
        if principal.role is EvidenceRole.CONTINUITY_COORDINATOR:
            if control or workflow.get("creator_role") != principal.role.value or workflow.get("creator_id") != principal.principal_id:
                raise PermissionError("coordinator may use only its own workflows and cannot change operator controls")
            principal.authorize(EvidenceOperation.CONTINUITY, target)
        elif principal.role is EvidenceRole.CONTINUITY_HOST:
            if control or principal.scope.run_id != workflow["workflow_id"]:
                raise PermissionError("host credential is limited to its bound workflow")
            principal.authorize(EvidenceOperation.CONTINUITY, target)
        else:
            principal.authorize(EvidenceOperation.CONTINUITY if control else EvidenceOperation.VIEW, target)

    @staticmethod
    def _latest(store, workflow_id):
        result = None
        late = {}
        for document in store.documents():
            if document.get("record_type") == "continuity_event" and document.get("workflow_id") == workflow_id:
                entry = document.get("entry", {})
                if entry.get("event") == "late_receipt" and entry.get("operation_id"):
                    late[entry["operation_id"]] = late.get(entry["operation_id"], 0) + 1
            if document.get("record_type") == "continuity_tombstone" and document.get("workflow_id") == workflow_id:
                raise ValueError("workflow deleted; it cannot be resumed")
            if document.get("record_type") == "continuity" and document["workflow"]["workflow_id"] == workflow_id:
                if document["workflow"]["revision"] != (result["revision"] + 1 if result else 1):
                    raise ValueError("workflow revision history is inconsistent")
                result = document["workflow"]
        if result is None:
            raise ValueError("workflow not found")
        if result.get("format") != "atmem-workflow-v1":
            raise ValueError("unsupported workflow version")
        for operation in result["operations"]:
            operation["late_receipts"] = max(operation.get("late_receipts", 0), late.get(operation["operation_id"], 0))
        return result

    def _check_storage_budget(self, store, principal, workflow, extra_bytes):
        if workflow.get("creator_role") != EvidenceRole.CONTINUITY_COORDINATOR.value:
            return
        documents = list(store.documents())
        owned = {doc["workflow"]["workflow_id"] for doc in documents
                 if doc.get("record_type") == "continuity"
                 and doc["workflow"].get("creator_id") == workflow["creator_id"]
                 and doc["workflow"].get("creator_role") == workflow["creator_role"]
                 and doc["workflow"].get("scope") == workflow["scope"]}
        used = sum(len(canonical_json(doc).encode()) for doc in documents
                   if doc.get("workflow", {}).get("workflow_id", doc.get("workflow_id")) in owned)
        latest = {}
        for doc in documents:
            if doc.get("record_type") == "continuity" and doc["workflow"]["workflow_id"] in owned:
                latest[doc["workflow"]["workflow_id"]] = doc["workflow"]
        # A granted attempt reserves its final snapshot and two copies of the
        # maximum receipt (event and operation result). Other work cannot spend
        # this headroom. Expired but unsuperseded leases retain the reservation.
        reserved = sum(len(canonical_json(value).encode()) + 2 * 65536 + 4096
                       for value in latest.values()
                       if any(op.get("lease_hash") and op["status"] == "uncertain" for op in value["operations"]))
        if used + reserved + extra_bytes > self.MAX_COORDINATOR_RETAINED_BYTES:
            raise ValueError("coordinator retained history limit reached; operator must export and delete finished workflows before admitting more work")

    def _save(self, store, principal, workflow, event):
        if store.capture_mode() is not CaptureMode.FULL:
            raise PermissionError("continuity writes require full encrypted capture")
        now = float(self.clock())
        if not math.isfinite(now) or now < workflow.get("clock_high_water", 0):
            raise ValueError("controller clock moved backwards; recovery paused")
        safety_control = event in {"disabled", "abandoned_not_completed"}
        finishing_attempt = event in {"completed", "needs_confirmation"}
        limit = self.MAX_REVISIONS + len(workflow["operations"]) + 2 if safety_control or finishing_attempt else self.MAX_REVISIONS
        if event == "enabled":
            limit -= 1  # Administrative re-enable cannot consume receipt headroom.
        if workflow["revision"] >= limit:
            raise ValueError("workflow revision limit reached; no further changes admitted")
        workflow["clock_high_water"] = now
        workflow["revision"] += 1
        workflow["history"].append({"event": event, "actor": principal.principal_id, "time": now})
        for entry in workflow["history"]:
            store.append({"record_type": "continuity_event", "workflow_id": workflow["workflow_id"],
                          "entry": entry}, partition_id="continuity:" + workflow["workflow_id"])
        workflow["history"] = []
        store.append({"record_type": "continuity", "workflow": workflow},
                     partition_id="continuity:" + workflow["workflow_id"])
        # Exact accounting inside the atomic transaction: over-cap writes roll
        # back before authorization is returned. Operator stop has reserved room.
        if not safety_control and not finishing_attempt:
            self._check_storage_budget(store, principal, workflow, 0)

    @staticmethod
    def _key_namespace(value):
        return value.get("creator_id") if value.get("creator_role") == EvidenceRole.CONTINUITY_COORDINATOR.value else None

    @staticmethod
    def _view(workflow):
        value = copy.deepcopy(workflow)
        for operation in value["operations"]:
            operation.pop("lease_hash", None)
            operation.pop("idempotency_key", None)
        return value

    def create(self, principal, workflow_key, operations, *, activate=False):
        identifier(workflow_key)
        if not isinstance(activate, bool):
            raise ValueError("activate must be boolean")
        principal.authorize(EvidenceOperation.CONTINUITY, principal.scope)
        if principal.role is EvidenceRole.CONTINUITY_HOST or principal.scope.run_id:
            raise PermissionError("a workflow operator credential is required")
        if principal.role is EvidenceRole.CONTINUITY_COORDINATOR and (not principal.scope.workspace_id or not activate):
            raise PermissionError("coordinator creation requires explicit workspace and activation")
        if not isinstance(operations, list) or not 1 <= len(operations) <= 200:
            raise ValueError("provide between 1 and 200 operations")
        if principal.role is EvidenceRole.CONTINUITY_COORDINATOR and len(operations) != 1:
            raise ValueError("coordinator workflows contain exactly one governed tool call")
        definitions = []
        if len(json.dumps(operations, allow_nan=False).encode()) > 262144:
            raise ValueError("workflow definition exceeds 256 KiB")
        names = set()
        for raw in operations:
            if not isinstance(raw, dict) or "name" not in raw:
                raise ValueError("each operation requires a name and tool")
            name = identifier(raw["name"])
            if name in names:
                raise ValueError("duplicate operation name")
            names.add(name)
            capability = raw.get("capability", "none")
            if type(raw.get("timeout_seconds", 30)) not in {int, float} or type(raw.get("retention_seconds", 0)) not in {int, float}:
                raise ValueError("timeout and retention must be numbers, not booleans or null")
            timeout = float(raw.get("timeout_seconds", 30))
            retention = float(raw.get("retention_seconds", 0))
            if capability not in {"none", "query", "idempotent"} or not 0 < timeout <= 90:
                raise ValueError("invalid tool capability or timeout")
            if not math.isfinite(retention) or retention < 0:
                raise ValueError("invalid retention")
            if capability == "idempotent" and retention <= timeout + 30:
                raise ValueError("idempotency retention must exceed timeout plus safety margin")
            if not isinstance(raw.get("arguments", {}), dict) or not isinstance(raw.get("tool"), str) or not raw["tool"]:
                raise ValueError("tool name and argument object required")
            definitions.append({"name": name, "tool": raw["tool"], "arguments": copy.deepcopy(raw.get("arguments", {})),
                                "capability": capability, "timeout_seconds": timeout, "retention_seconds": retention})
        scope = principal.scope.to_dict()
        with self._store() as store:
            if store.capture_mode() is not CaptureMode.FULL:
                raise PermissionError("full encrypted evidence capture is required for continuity")
            owned_latest = {}
            for doc in store.documents():
                value = doc.get("workflow", doc)
                if not isinstance(value, dict):
                    continue
                if doc.get("record_type") == "continuity" and value.get("scope") == scope and value.get("creator_id") == principal.principal_id and value.get("creator_role") == principal.role.value:
                    owned_latest[value["workflow_id"]] = value
                elif doc.get("record_type") == "continuity_tombstone":
                    owned_latest.pop(value.get("workflow_id"), None)
                namespace = principal.principal_id if principal.role is EvidenceRole.CONTINUITY_COORDINATOR else None
                legacy_tombstone = doc.get("record_type") == "continuity_tombstone" and "creator_role" not in value
                if value.get("workflow_key") == workflow_key and value.get("scope") == scope and (legacy_tombstone or self._key_namespace(value) == namespace):
                    if doc.get("record_type") == "continuity_tombstone":
                        raise ValueError("workflow key was deleted; choose new work explicitly")
                    if doc.get("record_type") == "continuity":
                        self._authorize(principal, value)
                        if canonical_json(value["definitions"]) != canonical_json(definitions):
                            raise ValueError("workflow key conflicts with existing definition")
                        return self._view(self._latest(store, value["workflow_id"]))
            open_count = sum(any(op["status"] not in {"completed", "abandoned"} for op in value["operations"])
                             for value in owned_latest.values())
            if principal.role is EvidenceRole.CONTINUITY_COORDINATOR and open_count >= self.MAX_OPEN_COORDINATOR_WORKFLOWS:
                raise ValueError("coordinator open workflow limit reached; finish or ask the operator to resolve existing work")
            workflow = {"format": "atmem-workflow-v1", "workflow_id": "wf_" + uuid.uuid4().hex,
                        "workflow_key": workflow_key, "scope": scope, "enabled": activate,
                        "creator_id": principal.principal_id, "creator_role": principal.role.value,
                        "definitions": definitions, "revision": 0, "history": [], "operations": []}
            for definition in definitions:
                workflow["operations"].append({**definition, "operation_id": "op_" + uuid.uuid4().hex,
                    "idempotency_key": "ik_" + uuid.uuid4().hex, "status": "pending", "attempts": [], "receipt": None})
            store.enable_continuity_format()
            self._save(store, principal, workflow, "created_enabled" if activate else "created_disabled")
            return self._view(workflow)

    def get(self, principal, workflow_id):
        with self._store() as store:
            workflow = self._latest(store, identifier(workflow_id))
            self._authorize(principal, workflow)
            store.access_event(self.evidence._audit(principal, "continuity_view", principal.scope, True,
                                                   workflow_id=workflow_id))
            result = self._view(workflow)
            result["history"] = [doc["entry"] for doc in store.documents()
                                 if doc.get("record_type") == "continuity_event" and doc.get("workflow_id") == workflow_id]
            return result

    def list(self, principal):
        principal.authorize(EvidenceOperation.VIEW, principal.scope)
        with self._store() as store:
            latest = {}
            for doc in store.documents():
                if doc.get("record_type") == "continuity":
                    value = doc["workflow"]
                    try:
                        self._authorize(principal, value)
                    except PermissionError:
                        continue
                    latest[value["workflow_id"]] = value
                elif doc.get("record_type") == "continuity_tombstone":
                    latest.pop(doc["workflow_id"], None)
            store.access_event(self.evidence._audit(principal, "continuity_list", principal.scope, True))
            summaries = []
            for workflow in latest.values():
                value = self._view(workflow)
                value.pop("definitions", None)
                for operation in value["operations"]:
                    operation.pop("arguments", None)
                    operation["has_receipt"] = operation.pop("receipt", None) is not None
                summaries.append(value)
            return summaries

    def configure(self, principal, workflow_id, *, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be boolean")
        with self._store() as store:
            workflow = self._latest(store, identifier(workflow_id))
            self._authorize(principal, workflow, control=True)
            if workflow["enabled"] == enabled:
                return self._view(workflow)
            if enabled and store.capture_mode() is not CaptureMode.FULL:
                raise PermissionError("full encrypted evidence capture is required")
            workflow["enabled"] = enabled
            self._save(store, principal, workflow, "enabled" if enabled else "disabled")
            return self._view(workflow)

    @staticmethod
    def _operation(workflow, name):
        return next((op for op in workflow["operations"] if op["name"] == name), None)

    def begin(self, principal, workflow_id, name, run_id, attempt_id):
        identifier(run_id); identifier(attempt_id)
        with self._store() as store:
            workflow = self._latest(store, identifier(workflow_id))
            self._authorize(principal, workflow, control=principal.role not in {EvidenceRole.CONTINUITY_HOST, EvidenceRole.CONTINUITY_COORDINATOR})
            op = self._operation(workflow, name)
            if op is None:
                raise ValueError("operation not found")
            now = float(self.clock())
            if not math.isfinite(now) or now < workflow.get("clock_high_water", 0):
                raise ValueError("controller clock moved backwards")
            reply = {"action": "blocked", "reason": "needs_confirmation", "operation_id": op["operation_id"]}
            if not workflow["enabled"] or store.capture_mode() is not CaptureMode.FULL:
                reply["reason"] = "workflow_disabled_or_capture_unavailable"
            elif op["status"] == "completed":
                reply.update(action="completed", reason="saved_receipt", receipt=op["receipt"])
            elif op["status"] == "abandoned":
                reply["reason"] = "abandoned"
            elif any(previous["status"] != "completed" for previous in workflow["operations"][:workflow["operations"].index(op)]):
                reply["reason"] = "earlier_work_unfinished"
            elif any(a["attempt_id"] == attempt_id for a in op["attempts"]):
                reply["reason"] = "attempt_already_issued"
            elif op.get("lease_until", 0) > now:
                reply["reason"] = "attempt_in_progress"
            elif len(op["attempts"]) >= 100:
                reply["reason"] = "attempt_limit_reached"
            elif workflow["revision"] >= self.MAX_REVISIONS - 2:
                reply["reason"] = "workflow_revision_limit_reached"
            else:
                action = "execute" if op["status"] == "pending" else "blocked"
                if op["status"] == "uncertain":
                    if op["capability"] == "query":
                        action = "query"
                    elif op["capability"] == "idempotent":
                        if now + op["timeout_seconds"] + 30 < op["first_dispatch"] + op["retention_seconds"]:
                            action = "execute"
                        else:
                            reply["reason"] = "idempotency_window_expired"
                if action != "blocked":
                    op.setdefault("first_dispatch", now)
                    op["status"] = "uncertain"
                    lease_token = secrets.token_urlsafe(32)
                    op["lease_hash"] = hashlib.sha256(lease_token.encode()).hexdigest()
                    op["lease_until"] = now + 120
                    op["attempts"].append({"attempt_id": attempt_id, "run_id": run_id, "mode": action, "started": now})
                    reply.update(action=action, reason="authorized_attempt", lease_token=lease_token,
                                 idempotency_key=op["idempotency_key"], arguments=op["arguments"], tool=op["tool"],
                                 timeout_seconds=op["timeout_seconds"], lease_until=op["lease_until"],
                                 run_id=run_id, attempt_id=attempt_id)
            if reply["action"] in {"execute", "query"}:
                self._save(store, principal, workflow, "begin:" + reply["reason"])
            reply["revision"] = workflow["revision"]
            return reply

    def outcome(self, principal, workflow_id, name, lease_token, receipt, *, run_id, attempt_id):
        if len(json.dumps(receipt, allow_nan=False).encode()) > 65536:
            raise ValueError("receipt exceeds 64 KiB")
        with self._store() as store:
            workflow = self._latest(store, identifier(workflow_id))
            self._authorize(principal, workflow, control=principal.role not in {EvidenceRole.CONTINUITY_HOST, EvidenceRole.CONTINUITY_COORDINATOR})
            op = self._operation(workflow, name)
            if op is None or not isinstance(receipt, dict):
                raise ValueError("operation and receipt object required")
            valid = bool(op.get("lease_hash")) and secrets.compare_digest(hashlib.sha256(str(lease_token).encode()).hexdigest(), op["lease_hash"])
            valid = valid and bool(op["attempts"]) and op["attempts"][-1]["run_id"] == run_id and op["attempts"][-1]["attempt_id"] == attempt_id
            # Expiry stops new dispatch/renewal; an unsuperseded receipt still
            # describes the original operation and must not be thrown away.
            valid = valid and op["status"] == "uncertain"
            if not valid:
                if op.get("late_receipts", 0) >= 10:
                    raise ValueError("late receipt limit reached")
                now = float(self.clock())
                if not math.isfinite(now) or now < workflow.get("clock_high_water", 0):
                    raise ValueError("controller clock moved backwards; recovery paused")
                document = {"record_type": "continuity_event", "workflow_id": workflow_id,
                    "entry": {"event": "late_receipt", "receipt": receipt, "actor": principal.principal_id,
                              "operation_id": op["operation_id"], "run_id": run_id, "attempt_id": attempt_id, "time": now}}
                if store.capture_mode() is not CaptureMode.FULL:
                    raise PermissionError("continuity writes require full encrypted capture")
                store.append(document, partition_id="continuity:" + workflow_id)
                self._check_storage_budget(store, principal, workflow, 0)
                return {"accepted": False, "reason": "stale_lease", "status": op["status"]}
            confirmed = receipt.get("outcome") == "confirmed_succeeded" and receipt.get("operation_id") == op["operation_id"] and bool(receipt.get("effect_id")) and "result" in receipt
            op["attempts"][-1].update(ended=float(self.clock()), outcome="completed" if confirmed else "unknown")
            workflow["history"].append({"event": "receipt", "receipt": receipt, "attempt_id": attempt_id,
                                       "run_id": run_id, "operation_id": op["operation_id"]})
            op["lease_until"] = 0
            op["lease_hash"] = ""
            if confirmed:
                op["status"] = "completed"
                op["receipt"] = {**receipt, "assurance": "host_reported"}
            self._save(store, principal, workflow, "completed" if confirmed else "needs_confirmation")
            return {"accepted": True, "status": op["status"]}

    def abandon(self, principal, workflow_id, name, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("explain why this work is being stopped")
        with self._store() as store:
            workflow = self._latest(store, identifier(workflow_id))
            self._authorize(principal, workflow, control=True)
            op = self._operation(workflow, name)
            if op is None or op["status"] == "completed":
                raise ValueError("only unfinished work can be abandoned")
            if op["status"] == "abandoned":
                return self._view(workflow)
            if op.get("lease_until", 0) > float(self.clock()):
                raise ValueError("attempt is still in progress; wait before abandoning")
            op.update(status="abandoned", lease_hash="", lease_until=0)
            workflow["history"].append({"event": "operator_attestation", "reason": reason,
                                       "actor": principal.principal_id, "operation_id": op["operation_id"]})
            self._save(store, principal, workflow, "abandoned_not_completed")
            return self._view(workflow)

    def renew(self, principal, workflow_id, name, lease_token, *, run_id, attempt_id):
        with self._store() as store:
            workflow = self._latest(store, identifier(workflow_id))
            self._authorize(principal, workflow, control=principal.role not in {EvidenceRole.CONTINUITY_HOST, EvidenceRole.CONTINUITY_COORDINATOR})
            op = self._operation(workflow, name)
            now = float(self.clock())
            if not workflow["enabled"] or not op or not op.get("lease_hash") or op["status"] != "uncertain":
                raise ValueError("no active attempt to renew")
            if not secrets.compare_digest(hashlib.sha256(str(lease_token).encode()).hexdigest(), op["lease_hash"]) or now > op["lease_until"] or op["attempts"][-1]["run_id"] != run_id or op["attempts"][-1]["attempt_id"] != attempt_id:
                raise ValueError("stale lease")
            if op["attempts"][-1].get("renewals", 0) >= 10:
                raise ValueError("lease renewal limit reached")
            if workflow["revision"] >= self.MAX_REVISIONS - 1:
                raise ValueError("revision capacity reserved for the attempt receipt")
            op["attempts"][-1]["renewals"] = op["attempts"][-1].get("renewals", 0) + 1
            op["lease_until"] = now + 120
            self._save(store, principal, workflow, "lease_renewed")
            return {"lease_until": op["lease_until"]}
