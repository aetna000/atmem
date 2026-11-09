"""Opt-in bridge from a pinned Hermes dispatch boundary to the shared proxy.

This is trusted application/plugin configuration, never a model tool. It does
not install Hermes, alter a Home, or certify qualification. Unregistered tools
are denied unless explicitly declared read-only by the application. The final
authorization hook is read-only and repeatable; only execution middleware may
consume approval and dispatch a protected effect.
"""
from contextvars import ContextVar
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import threading

from atmem.contracts.feedback import MCPInvocation, identifier
from atmem.core.canonical import canonical_json
from atmem.feedback.store import FeedbackError, snapshot


HOST_COMMIT = "1088e06e448bef2af736122a5d424082a57bf548"
BOUNDARY_FILES = {
    "agent/tool_authorization.py":"ff5d9a268e9b3a20fd374dcb6aa9b3bed4abc6b3734054657b499a307ba5da60",
    "agent/tool_executor.py":"54478ec332c28e19fb2b0614a1a6fee9ab667c7af3d8badc51d6fc62643d3033",
    "hermes_cli/plugins.py":"fd5cf7d4881565a5444664c1c5eae24f39236cbb832222b8e6dc5f01ec9520c7",
    "hermes_cli/plugins_dispatch.py":"8801ca7c61bc4acebd7f6f53c1830caaeee26460b283cd31a41404b1a128eb4a",
    "model_tools.py":"cdca1bc0b3ddfda18bb1872c39e8c444625afd63f267c4c2c43ceab1c48215af",
}


def verify_host_boundary(root):
    try:
        root = Path(root).resolve(strict=True)
        for name, expected in BOUNDARY_FILES.items():
            path = root / name
            if path.is_symlink() or not path.is_file():
                raise FeedbackError("unsupported_host_boundary")
            with path.open("rb") as stream:
                raw = stream.read(2_000_001)
            if len(raw) > 2_000_000 or sha256(raw).hexdigest() != expected:
                raise FeedbackError("unsupported_host_boundary")
    except OSError:
        raise FeedbackError("unsupported_host_boundary") from None
    return root


@dataclass
class _Permit:
    owner: object
    tool: str
    arguments_sha256: str
    identities: dict
    next_call: object
    lock: object
    started: bool = False


_CURRENT = ContextVar("atmem_hermes_feedback_dispatch", default=None)


class HermesFeedbackGuard:
    def __init__(self, dispatcher, *, host_root, session_resolver, read_tools=(), approval_resolver=None):
        self.host_root = verify_host_boundary(host_root)
        if not callable(session_resolver) or approval_resolver is not None and not callable(approval_resolver):
            raise ValueError("trusted application session/approval binding required")
        if type(read_tools) not in (tuple, frozenset) or len(read_tools) > 128:
            raise ValueError("bounded explicit read-only tool inventory required")
        self.read_tools = frozenset(identifier(tool) for tool in read_tools)
        self.dispatcher = dispatcher
        self.session_resolver = session_resolver
        self.approval_resolver = approval_resolver
        self._contracts = {}

    def register_tool(self, owner_credential, scope, *, tool, schema_version, schema, native_guard, requires_approval=False):
        if tool in self.read_tools:
            raise ValueError("a protected tool cannot also bypass as read-only")
        def invoke(arguments):
            permit = _CURRENT.get()
            if (permit is None or permit.owner is not self or permit.tool != tool
                    or permit.arguments_sha256 != sha256(canonical_json(arguments).encode()).hexdigest()):
                raise FeedbackError("dispatch_binding_missing")
            with permit.lock:
                if permit.started:
                    raise FeedbackError("dispatch_already_started")
                permit.started = True
            return permit.next_call(snapshot(arguments))
        self.dispatcher.register(owner_credential, scope, tool=tool, schema_version=schema_version,
            schema=schema, invoke=invoke, native_guard=native_guard, requires_approval=requires_approval)
        self._contracts[(scope.content_digest, tool)] = schema_version

    @staticmethod
    def _identities(context):
        values = {name:context.get(name) for name in ("session_id", "task_id", "turn_id", "tool_call_id")}
        if any(type(value) is not str or not value or len(value.encode()) > 256 for value in values.values()):
            raise FeedbackError("host_identity_unavailable")
        return values

    def invocation(self, session, *, tool_name, args, **context):
        """Expose the deterministic call binding for an owner approval workflow."""
        identities = self._identities(context)
        version = self._contracts.get((session.scope.content_digest, tool_name))
        if version is None:
            raise FeedbackError("unsupported_tool")
        key = "hermes-"+sha256(canonical_json(identities).encode()).hexdigest()
        approval = None
        if self.approval_resolver is not None:
            approval = self.approval_resolver(session, tool_name, snapshot(args), snapshot(identities), key)
        return MCPInvocation(tool_name, version, snapshot(args), key, approval)

    @staticmethod
    def _error(reason):
        return json.dumps({"error":"AtMem did not confirm tool execution", "reason":reason,
                           "retry":"inspect_receipt_before_repeating_unknown_effects"})

    def tool_execution(self, tool_name, args, next_call, **context):
        # Hermes middleware catches callback exceptions and may continue. Never
        # raise an ordinary error out of this boundary and accidentally run it.
        try:
            if tool_name in self.read_tools:
                return next_call(args)
            if _CURRENT.get() is not None:
                return self._error("nested_execution_not_supported")
            identities = self._identities(context)
            session = self.session_resolver(**snapshot(identities))
            invocation = self.invocation(session, tool_name=tool_name, args=args, **identities)
            permit = _Permit(self, tool_name, sha256(canonical_json(invocation.arguments).encode()).hexdigest(),
                             identities, next_call, threading.Lock())
            token = _CURRENT.set(permit)
            try:
                result = self.dispatcher.execute(session, invocation)
            finally:
                _CURRENT.reset(token)
            if result["status"] == "uncertain" and result.get("receipt_id"):
                # Idempotency preserves the original admitted intent. Inspect
                # its latest retained result; this never invokes the handler.
                result = self.dispatcher.inspect(session, receipt_id=result["receipt_id"])
            if result["status"] == "reported_complete":
                return result["result"]
            return self._error(result.get("reason", result["status"]))
        except Exception as exc:
            return self._error(exc.code if type(exc) is FeedbackError else "policy_unavailable")

    def authorize_tool_call(self, tool_name, args, **context):
        """Idempotent final check; never consumes approval or dispatches a call."""
        try:
            if tool_name in self.read_tools:
                return {"action":"allow"}
            permit = _CURRENT.get()
            if (permit is not None and permit.owner is self and permit.started and permit.tool == tool_name
                    and permit.identities == self._identities(context)
                    and permit.arguments_sha256 == sha256(canonical_json(args).encode()).hexdigest()):
                return {"action":"allow"}
        except Exception:
            pass
        return {"action":"block", "message":"AtMem requires an exact admitted protected dispatch."}

    def install(self, context):
        from hermes_cli import plugins
        if Path(plugins.__file__).resolve().parent.parent != self.host_root:
            raise FeedbackError("unsupported_host_boundary")
        verify_host_boundary(self.host_root)
        if "authorize_tool_call" not in plugins.VALID_HOOKS:
            raise FeedbackError("unsupported_host_boundary")
        context.register_hook("authorize_tool_call", self.authorize_tool_call)
        context.register_middleware("tool_execution", self.tool_execution)

    def capabilities(self, session):
        with self.dispatcher.feedback._authorized(session, None):
            return {"adapter":"hermes-feedback-guard-v1", "host_commit":HOST_COMMIT,
                    "scope":session.scope.to_dict(),
                    "covered_tools":sorted(tool for scope,tool in self._contracts if scope == session.scope.content_digest),
                    "unknown_tools":"blocked", "read_only_exceptions":sorted(self.read_tools),
                    "registration_only":True, "qualification":"not_established", "unintegrated_hosts":"advisory_only"}
