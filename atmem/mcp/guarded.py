"""Application-owned dispatch, not an advisory permission hint.

Handlers and schemas are registered by the owner application. Model arguments
cannot select arbitrary endpoints, executable code, scopes or approval grants.
Persist intent before invoking a handler. Unknown write effects are never retried.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import nullcontext
from hashlib import sha256
import uuid
from contextvars import copy_context
import queue
import threading

from atmem.contracts.feedback import MCPInvocation, identifier
from atmem.core.canonical import canonical_json
from atmem.evidence.models import EvidenceOperation
from atmem.feedback.store import FeedbackError, snapshot
from atmem.feedback.observability import measured
from atmem.rules.compiler import compile_rule
from atmem.rules.evaluator import evaluate
from atmem.rules.lifecycle import RuleLifecycle


def validate_schema(schema, *, depth=0):
    """Reject unsupported contracts at registration, before discovery/admission."""
    if type(schema) is not dict or depth > 8:
        raise FeedbackError("unsupported_schema")
    kind = schema.get("type")
    allowed = {"object": {"type", "properties", "required", "additionalProperties", "enum"},
               "string": {"type", "maxLength", "enum"}, "integer": {"type", "minimum", "maximum", "enum"},
               "boolean": {"type", "enum"}, "null": {"type", "enum"}}
    if kind not in allowed or set(schema)-allowed[kind]:
        raise FeedbackError("unsupported_schema")
    if kind == "object":
        props, required = schema.get("properties", {}), schema.get("required", [])
        if (schema.get("additionalProperties") is not False or type(props) is not dict
                or type(required) is not list or any(type(k) is not str for k in required)
                or len(set(required)) != len(required) or set(required)-set(props)
                or any(type(k) is not str or not 0 < len(k.encode()) <= 256 for k in props)):
            raise FeedbackError("unsupported_schema")
        for child in props.values():
            validate_schema(child, depth=depth+1)
    if kind == "string" and (type(schema.get("maxLength", 65536)) is not int or not 0 <= schema.get("maxLength", 65536) <= 65536):
        raise FeedbackError("unsupported_schema")
    if kind == "integer" and (any(type(schema.get(k, default)) is not int for k, default in (("minimum", -2**53), ("maximum", 2**53)))
            or not -2**53 <= schema.get("minimum", -2**53) <= schema.get("maximum", 2**53) <= 2**53):
        raise FeedbackError("unsupported_schema")
    if "enum" in schema:
        values = schema["enum"]
        if type(values) is not list or not 0 < len(values) <= 128:
            raise FeedbackError("unsupported_schema")
        for value in values:
            try:
                validate_arguments({k:v for k,v in schema.items() if k != "enum"}, value)
            except FeedbackError:
                raise FeedbackError("unsupported_schema") from None


def validate_arguments(schema, arguments):
    """Small closed JSON schema subset: reject unsupported constructs."""
    if type(schema) is not dict or set(schema) - {"type", "properties", "required", "additionalProperties", "enum", "maxLength", "minimum", "maximum"}:
        raise FeedbackError("unsupported_schema")
    kind = schema.get("type")
    types = {"object": dict, "string": str, "integer": int, "boolean": bool, "null": type(None)}
    if kind not in types or type(arguments) is not types[kind]:
        raise FeedbackError("invalid_arguments")
    if kind == "object":
        if schema.get("additionalProperties") is not False:
            raise FeedbackError("unsupported_schema")
        props = schema.get("properties", {})
        if set(arguments)-set(props) or set(schema.get("required", []))-set(arguments):
            raise FeedbackError("invalid_arguments")
        for name, value in arguments.items():
            validate_arguments(props[name], value)
    if "enum" in schema and not any(type(v) is type(arguments) and v == arguments for v in schema["enum"]):
        raise FeedbackError("invalid_arguments")
    if kind == "string" and len(arguments) > schema.get("maxLength", 65536):
        raise FeedbackError("invalid_arguments")
    if kind == "integer" and not schema.get("minimum", -2**53) <= arguments <= schema.get("maximum", 2**53):
        raise FeedbackError("invalid_arguments")


@dataclass(frozen=True)
class Handler:
    schema: dict
    version: str
    invoke: object
    native_guard: object
    requires_approval: bool = False
    with_context: bool = False


class GuardedDispatcher:
    def __init__(self, feedback, *, versions: dict, timeout_seconds=5):
        if type(timeout_seconds) not in (float, int) or not 0 < timeout_seconds <= 30:
            raise ValueError("bounded dispatch timeout required")
        self.feedback = feedback
        self.versions = snapshot(versions)
        self.lifecycle = RuleLifecycle(feedback)
        self._handlers = {}
        self.timeout_seconds = timeout_seconds
        self._running = set()
        self._lock = threading.Lock()

    def _invoke(self, session, tool, callback):
        key = (session.scope.content_digest, tool)
        with self._lock:
            if key in self._running or len(self._running) >= 8:
                raise FeedbackError("handler_busy")
            self._running.add(key)
        results = queue.Queue(maxsize=1)
        context = copy_context()
        def run():
            try:
                results.put((True, context.run(callback)))
            except BaseException:
                results.put((False, None))
            finally:
                with self._lock:
                    self._running.discard(key)
        try:
            threading.Thread(target=run, daemon=True, name="atmem-guarded-effect").start()
        except RuntimeError:
            with self._lock:
                self._running.discard(key)
            raise FeedbackError("handler_unavailable") from None
        try:
            ok, result = results.get(timeout=self.timeout_seconds)
        except queue.Empty:
            raise FeedbackError("handler_timeout") from None
        if not ok:
            raise FeedbackError("handler_uncertain")
        return result

    def register(self, owner_credential, scope, *, tool, schema_version, schema, invoke, native_guard, requires_approval=False,
                 with_context=False):
        principal = self.feedback._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        identifier(tool)
        identifier(schema_version)
        schema = snapshot(schema)
        if type(with_context) is not bool or type(requires_approval) is not bool or not callable(invoke) or not callable(native_guard) or schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            raise ValueError("explicit closed handler and native guard required")
        validate_schema(schema)
        value = {"tool": tool, "schema_version": schema_version,
                 "schema_sha256": sha256(canonical_json(schema).encode()).hexdigest(), "versions": self.versions,
                 "requires_approval": requires_approval, "with_context": with_context}
        with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            tx.put("proxy_handler", tool, value, expected_revision=tx.revision("proxy_handler", tool))
            tx.audit(principal.principal_id, "register_handler", allowed=True)
        self._handlers[(scope.content_digest, tool)] = Handler(schema, schema_version, invoke, native_guard, requires_approval, with_context)

    def approve(self, owner_credential, scope, *, principal_id, invocation: MCPInvocation, expires_at: int):
        principal = self.feedback._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        identifier(principal_id)
        if type(expires_at) is not int or not self.feedback.clock() < expires_at <= self.feedback.clock()+300:
            raise ValueError("approval expiry within five minutes required")
        invocation = MCPInvocation.from_dict(invocation.to_dict())
        if invocation.approval_id is not None:
            raise ValueError("approve the final arguments before assigning approval_id")
        approval_id = "approval-"+uuid.uuid4().hex
        with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            binding = self._approval_binding(tx, invocation.tool)
            tx.put("call_approval", approval_id, {"principal_id": principal_id, "tool": invocation.tool,
                   "schema_version": invocation.schema_version, "arguments": invocation.arguments,
                   "idempotency_key": invocation.idempotency_key,
                   "binding": binding, "expires_at": expires_at, "used": False}, expected_revision=0)
            tx.audit(principal.principal_id, "approve_call", allowed=True)
        return approval_id

    @staticmethod
    def _approval_binding(tx, tool):
        return sha256(canonical_json({"handler_generation": tx.revision("proxy_handler", tool),
            "rules": list(tx.iter_kind("rule_lifecycle")),
            "proposals": list(tx.iter_kind("rule_proposal"))}).encode()).hexdigest()

    @measured("proxy.execute")
    def execute(self, session, invocation: MCPInvocation):
        invocation = MCPInvocation.from_dict(invocation.to_dict())
        call_wire = invocation.to_dict()
        canonical = self.feedback.memory.store.transaction() if self.feedback.memory is not None else nullcontext()
        with canonical, self.feedback._authorized(session, "execute") as (tx, principal):
            if self.feedback.memory is None:
                raise FeedbackError("missing_evidence")
            handler = self._handlers.get((session.scope.content_digest, invocation.tool))
            if handler is None:
                raise FeedbackError("unsupported_tool")
            payload = {"invocation": call_wire, "actor_id": principal.principal_id}
            registered = tx.get("proxy_handler", invocation.tool)
            if (registered is None or registered["schema_version"] != invocation.schema_version
                    or handler.version != invocation.schema_version or registered["versions"] != self.versions
                    or registered["requires_approval"] != handler.requires_approval
                    or registered.get("with_context", False) != handler.with_context
                    or registered["schema_sha256"] != sha256(canonical_json(handler.schema).encode()).hexdigest()):
                raise FeedbackError("schema_drift")
            cached = tx.cached("proxy_execute", invocation.idempotency_key, payload)
            if cached is not None:
                return cached
            if tx.get("proxy_write_hold", invocation.tool) is not None:
                raise FeedbackError("uncertain_effect_requires_reconciliation")
            validate_arguments(handler.schema, invocation.arguments)
            # The native guard sees detached arguments; modifications cannot alter
            # what is later evaluated or sent to the handler.
            try:
                checked_arguments = snapshot(invocation.arguments)
                native_allowed = (self._invoke(session, "guard:"+invocation.tool, lambda: handler.native_guard(checked_arguments)) is True
                                  and canonical_json(checked_arguments) == canonical_json(invocation.arguments))
            except Exception:
                native_allowed = False
            rules = self.lifecycle.current(tx, kind="rule", versions=self.versions, tool=invocation.tool)
            compiled = tuple(compile_rule(candidate, handler.schema) for row, candidate in rules
                             if row["state"] == "active" and candidate.tool == invocation.tool)
            approval = tx.get("call_approval", invocation.approval_id) if invocation.approval_id else None
            approval_valid = bool(approval and not approval["used"] and approval["expires_at"] > self.feedback.clock()
                                  and approval["principal_id"] == principal.principal_id and approval["tool"] == invocation.tool
                                  and approval["schema_version"] == invocation.schema_version
                                  and approval["idempotency_key"] == invocation.idempotency_key
                                  and approval["binding"] == self._approval_binding(tx, invocation.tool)
                                  and canonical_json(approval["arguments"]) == canonical_json(invocation.arguments))
            with self.feedback.observability.measure(session.scope, "rule.evaluate"):
                decision = evaluate(compiled, invocation, native_allowed=native_allowed, approval_valid=approval_valid)
            if decision.allowed and handler.requires_approval and not approval_valid:
                return tx.once("proxy_execute", invocation.idempotency_key, payload,
                               lambda: {"status": "blocked", "reason": "approval_required", "effect": "not_dispatched"})
            shadow = []
            for row, candidate in rules:
                if row["state"] == "shadow":
                    try:
                        would = evaluate((compile_rule(candidate, handler.schema),), invocation, native_allowed=native_allowed)
                        shadow.append({"rule_id": candidate.rule_id, "would_allow": would.allowed, "reason": would.reason})
                    except FeedbackError:
                        shadow.append({"rule_id": candidate.rule_id, "reason": "not_evaluable"})
            if not decision.allowed:
                return tx.once("proxy_execute", invocation.idempotency_key, payload,
                               lambda: {"status": "blocked", "reason": decision.reason, "effect": "not_dispatched"})
            if decision.approval_required or handler.requires_approval:
                approval["used"] = True
                tx.put("call_approval", invocation.approval_id, approval, expected_revision=tx.revision("call_approval", invocation.approval_id))
            receipt_id = "execution-"+uuid.uuid4().hex
            intent = {"receipt_id": receipt_id, "invocation": call_wire, "actor_id": principal.principal_id,
                      "status": "uncertain", "effect": "possibly_dispatched", "policy": list(decision.applicable_rule_ids),
                      "retry": "do_not_reexecute", "shadow": shadow}
            tx.put("proxy_execution", receipt_id, intent, expected_revision=0)
            # Scope/tool hold survives process restart and a changed retry key.
            # Keep it content-free so source deletion cannot enable a duplicate.
            tx.put("proxy_write_hold", invocation.tool, {"receipt_id": receipt_id},
                   expected_revision=tx.revision("proxy_write_hold", invocation.tool))
            tx.once("proxy_execute", invocation.idempotency_key, payload, lambda: intent)
            # Admission commits while the source lock is held. Revocation after
            # this point cannot undo an in-flight effect; the intent says so.
        try:
            context = {"receipt_id": receipt_id, "idempotency_key": invocation.idempotency_key,
                       "actor_id": principal.principal_id, "scope": session.scope.to_dict()}
            def invoke_handler():
                arguments = snapshot(invocation.arguments)
                return handler.invoke(arguments, context=snapshot(context)) if handler.with_context else handler.invoke(arguments)
            result = snapshot(self._invoke(session, invocation.tool, invoke_handler))
            final = {**intent, "status": "reported_complete", "effect": "handler_reported", "result": result}
        except Exception:
            # Handler errors may follow a completed write. Preserve uncertainty;
            # never turn this into an automatic retry or expose exception text.
            return intent
        try:
            with self.feedback._authorized(session, "execute") as (tx, _):
                tx.put("proxy_execution", receipt_id, final, expected_revision=1)
                if tx.get("proxy_write_hold", invocation.tool) != {"receipt_id": receipt_id}:
                    raise FeedbackError("execution_hold_changed")
                tx.put("proxy_write_hold", invocation.tool, {}, deleted=True,
                          expected_revision=tx.revision("proxy_write_hold", invocation.tool))
        except FeedbackError:
            return intent
        # The immutable idempotency record deliberately retains admission/unknown.
        # Subsequent calls inspect the execution receipt rather than execute again.
        return final

    def reconcile(self, owner_credential, scope, *, receipt_id, verification_id):
        """Clear an unknown-effect hold only from a trusted terminal backend receipt.

        The registered independent verifier must have read the backend operation
        journal, not merely current destination state. This does not replay a call
        or grant permission for a new call. Missing/deleted evidence stays blocked.
        """
        from atmem.contracts.feedback import OutcomeRecord, VerificationReceipt
        identifier(receipt_id)
        identifier(verification_id)
        with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            execution = tx.get("proxy_execution", receipt_id)
            proof = tx.get("verification", verification_id)
            if execution is None or proof is None:
                raise FeedbackError("missing_evidence")
            if execution.get("status") == "verified_complete" and execution.get("verification_id") == verification_id:
                return execution
            receipt = VerificationReceipt.from_dict(proof)
            from atmem.feedback.verification import VerificationService
            registry = tx.get("verifier", VerificationService._key(receipt.verifier_id, execution["invocation"]["tool"],
                                                                  execution["invocation"]["schema_version"]))
            if (registry is None or not registry["active"] or registry["version"] != receipt.verifier_version
                    or registry["assurance"] != "independent_readback" or registry["binding"] != "effect_receipt"):
                raise FeedbackError("verifier_changed")
            row = tx.get("outcome_revision", receipt.outcome_sha256)
            evidence = tx.get("readback_evidence", receipt.evidence_id)
            if row is None or evidence is None:
                raise FeedbackError("missing_evidence")
            outcome = OutcomeRecord.from_dict(row["outcome"])
            observation = next((v for v in outcome.observations if v.invocation_id == receipt.invocation_id), None)
            invocation = execution["invocation"]
            statuses = {r.get("effect_status", "unknown") for r in tx.iter_kind("verification")
                        if r["outcome_sha256"] == receipt.outcome_sha256 and r["invocation_id"] == receipt.invocation_id
                        and r["assurance"] == "independent_readback" and r.get("binding") == "effect_receipt"
                        and r.get("effect_status", "unknown") != "unknown"}
            if (receipt.assurance != "independent_readback" or receipt.binding != "effect_receipt"
                    or receipt.effect_status == "unknown" or len(statuses) != 1
                    or observation is None or observation.evidence_id != receipt_id
                    or observation.tool != invocation["tool"] or observation.schema_version != invocation["schema_version"]
                    or canonical_json(observation.arguments) != canonical_json(invocation["arguments"])
                    or evidence["evidence"].get("proxy_execution_id") != receipt_id
                    or evidence["evidence"].get("backend_terminal") is not True):
                raise FeedbackError("unverified_effect")
            tool = invocation["tool"]
            with self._lock:
                if (scope.content_digest, tool) in self._running:
                    raise FeedbackError("handler_busy")
            hold = tx.get("proxy_write_hold", tool)
            if hold != {"receipt_id": receipt_id}:
                raise FeedbackError("execution_hold_changed")
            final = {**execution, "status": "verified_complete", "effect": "independent_terminal_readback",
                     "effect_status":receipt.effect_status, "task_success":"not_implied",
                     "verification_id": verification_id}
            tx.put("proxy_execution", receipt_id, final, expected_revision=tx.revision("proxy_execution", receipt_id))
            tx.put("proxy_write_hold", tool, {}, deleted=True, expected_revision=tx.revision("proxy_write_hold", tool))
            tx.audit(principal.principal_id, "reconcile_execution", allowed=True)
            return final

    def inspect(self, session, receipt_id):
        with self.feedback._authorized(session, "read") as (tx, _):
            result = tx.get("proxy_execution", identifier(receipt_id))
            if result is None:
                raise FeedbackError("denied")
            return result

    def tools(self, session):
        with self.feedback._authorized(session, "execute") as (tx, _):
            result = []
            for (scope_digest, tool), handler in sorted(self._handlers.items()):
                if scope_digest != session.scope.content_digest:
                    continue
                registered = tx.get("proxy_handler", tool)
                if (registered is None or registered["schema_version"] != handler.version
                        or registered["versions"] != self.versions
                        or registered["schema_sha256"] != sha256(canonical_json(handler.schema).encode()).hexdigest()):
                    continue
                result.append({"tool": tool, "schema_version": handler.version,
                               "inputSchema": snapshot(handler.schema), "requires_approval": handler.requires_approval})
            return {"tools": result[:128], "total": len(result), "truncated": len(result)>128}
