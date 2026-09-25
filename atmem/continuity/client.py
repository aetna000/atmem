"""A normal application client; recovery decisions come from AtMem, not the host."""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
import uuid
import warnings
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.request import HTTPCookieProcessor
from http.cookiejar import CookieJar
from contextvars import ContextVar
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from threading import BoundedSemaphore, Thread


_attempt_observer = ContextVar("atmem_continuity_attempt_observer", default=None)


def record_charge(*, charge_id, charge_source, cost_microusd=None,
                  input_tokens=None, output_tokens=None, price_source=None):
    """Report actual tool/provider usage within a governed callback.

    No inference, pricing lookup, or retry. Missing prices remain unknown. Returns
    False if observation is unavailable; never changes the tool's authority.
    """
    emit = _attempt_observer.get()
    if emit is None:
        return False
    values = {"charge_id": charge_id, "charge_source": charge_source,
              "cost_microusd": cost_microusd, "input_tokens": input_tokens,
              "output_tokens": output_tokens, "price_source": price_source}
    return emit({key: value for key, value in values.items() if value is not None})


class RecoveryBlocked(RuntimeError):
    pass


def operator_credential(url, username, password, principal_id, *, workflow_id=None, coordinator=False, workspace_id=None):
    """Use an ordinary signed-in operator session, then close that session."""
    base = _base(url)
    opener = build_opener(ProxyHandler({}), _NoRedirect(), HTTPCookieProcessor(CookieJar()))
    def post(path, body, csrf=""):
        request = Request(base + path, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-CSRF-Token": csrf})
        with opener.open(request, timeout=30) as response:
            return json.load(response)
    login = post("/api/auth/login", {"username": username, "password": password})
    csrf = login["csrf_token"]
    try:
        if login.get("account", {}).get("password_change_required"):
            raise PermissionError("change the temporary password in the dashboard first")
        return post("/v1/evidence/grants", {"principal_id": principal_id,
            "role": "continuity_coordinator" if coordinator else "continuity_host" if workflow_id else "evidence_collector",
            "run_id": workflow_id, "workspace_id": workspace_id}, csrf)
    finally:
        try:
            post("/api/auth/logout", {}, csrf)
        except Exception:
            warnings.warn("Credential request finished, but its temporary dashboard session could not be closed; check Sessions in Settings.", RuntimeWarning)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PermissionError("credentialed requests cannot follow redirects")


def _base(url):
    parsed = urlsplit(url)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("use a base URL without credentials, query or fragment")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}):
        raise ValueError("remote service requires HTTPS; HTTP is limited to loopback")
    return url.rstrip("/")


@dataclass(frozen=True)
class Tool:
    """Callbacks enforce destination timeout/identity and return original receipts.

    Callback signature: (arguments, operation_id, idempotency_key, timeout_seconds).
    Query never returns guessed success: unknown/not-found stays unknown.
    """
    execute: object
    query: object = None


class ContinuityClient:
    def __init__(self, url, token, *, observer=None):
        self.url = _base(url)
        if not token:
            raise ValueError("a scoped AtMem credential is required")
        self.token = token
        self.observer = observer
        self.observation_errors = []
        self.observation_error_count = 0
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body, allow_nan=False).encode()
        request = Request(self.url + path, data=data, method=method,
                          headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        # No hidden retry: a lost authorization response is not a new dispatch.
        with self.opener.open(request, timeout=30) as response:
            return json.load(response)

    def create(self, workflow_key, operations):
        return self.request("POST", "/v1/continuity", {"workflow_key": workflow_key, "operations": operations})

    def configure(self, workflow_id, enabled):
        return self.request("POST", f"/v1/continuity/{workflow_id}/configure", {"enabled": enabled})

    def get(self, workflow_id):
        return self.request("GET", f"/v1/continuity/{workflow_id}")

    def _observe(self, workflow_id, decision, event, *, retry, recovery, accounting=None):
        if self.observer is None:
            return False
        value = {"format": "atmem.continuity.v1", "event_id": "ce_" + uuid.uuid4().hex,
                 "workflow_id": workflow_id, "operation_id": decision["operation_id"],
                 "run_id": decision["run_id"], "attempt_id": decision["attempt_id"],
                 "event": event, "time": time.time(), "retry": retry, "recovery": recovery}
        try:
            if accounting:
                for key, number in accounting.items():
                    if key in {"cost_microusd", "input_tokens", "output_tokens"} and (type(number) is not int or not 0 <= number <= 9007199254740991):
                        raise ValueError("invalid usage amount")
                    if key in {"charge_id", "charge_source", "price_source"} and (not isinstance(number, str) or not number or len(number) > (128 if key == "charge_source" else 256)):
                        raise ValueError("invalid accounting provenance")
                if "cost_microusd" in accounting and not accounting.get("price_source"):
                    raise ValueError("known price requires provenance")
                value.update(accounting)
            self.observer(value)
            return True
        except Exception as exc:
            # Visibility failure is surfaced to the host but cannot change work.
            self.observation_error_count += 1
            if len(self.observation_errors) < 100:
                self.observation_errors.append(type(exc).__name__)
            return False

    def run_operation(self, workflow_id, name, tools, *, run_id=None):
        workflow = self.get(workflow_id)
        operation = next((op for op in workflow["operations"] if op["name"] == name), None)
        if operation is None:
            raise ValueError("operation not found")
        tool = tools.get(operation["tool"])
        if tool is None or not callable(tool.execute):
            raise ValueError("register the declared tool before starting")
        if operation["capability"] == "query" and not callable(tool.query):
            raise ValueError("register the declared receipt query before starting")
        run_id = run_id or "run_" + uuid.uuid4().hex
        attempt_id = "attempt_" + uuid.uuid4().hex
        decision = self.request("POST", f"/v1/continuity/{workflow_id}/begin",
                                {"name": name, "run_id": run_id, "attempt_id": attempt_id})
        if decision["action"] == "completed":
            return decision["receipt"]["result"]
        if decision["action"] == "blocked":
            raise RecoveryBlocked(decision["reason"])
        if decision["action"] not in {"execute", "query"}:
            raise RecoveryBlocked("unsupported_controller_action")
        retry = bool(operation["attempts"])
        recovery = any(attempt["run_id"] != run_id for attempt in operation["attempts"])
        self._observe(workflow_id, decision, decision["action"], retry=retry, recovery=recovery)
        context = _attempt_observer.set(lambda accounting: self._observe(workflow_id, decision, "usage", retry=retry, recovery=recovery, accounting=accounting))
        try:
            callback = tool.query if decision["action"] == "query" else tool.execute
            receipt = callback(decision["arguments"], decision["operation_id"],
                               decision["idempotency_key"], decision["timeout_seconds"])
            if not isinstance(receipt, dict):
                raise ValueError("tool must return a receipt object")
            encoded_receipt = json.dumps(receipt, allow_nan=False).encode()
            if len(encoded_receipt) > 65536:
                raise ValueError("receipt exceeds 64 KiB")
            receipt = json.loads(encoded_receipt)
            if receipt.get("outcome") == "confirmed_succeeded" and "result" not in receipt:
                raise ValueError("successful receipt requires an original result")
        except Exception:
            try:
                self.request("POST", f"/v1/continuity/{workflow_id}/outcome", {
                    "name": name, "lease_token": decision["lease_token"], "run_id": run_id,
                    "attempt_id": attempt_id, "receipt": {"outcome": "unknown"}})
            except Exception:
                pass
            self._observe(workflow_id, decision, "unknown", retry=retry, recovery=recovery)
            raise
        finally:
            _attempt_observer.reset(context)
        outcome = self.request("POST", f"/v1/continuity/{workflow_id}/outcome", {
            "name": name, "lease_token": decision["lease_token"], "run_id": run_id,
            "attempt_id": attempt_id, "receipt": receipt})
        self._observe(workflow_id, decision, "completed" if outcome["status"] == "completed" else "unknown", retry=retry, recovery=recovery)
        if not outcome["accepted"] or outcome["status"] != "completed":
            raise RecoveryBlocked(outcome.get("reason", "needs_confirmation"))
        return receipt["result"]

    def run(self, workflow_id, tools, *, run_id=None):
        run_id = run_id or "run_" + uuid.uuid4().hex
        return {op["name"]: self.run_operation(workflow_id, op["name"], tools, run_id=run_id)
                for op in self.get(workflow_id)["operations"]}


class AtFlowsObserver:
    _slots = BoundedSemaphore(8)

    def __init__(self, url, token):
        self.url, self.token = _base(url), token
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def __call__(self, event):
        # Bound wall-clock waiting, including DNS and a slow response body.
        # Daemon workers cannot delay agent shutdown; cap lingering requests.
        if not self._slots.acquire(blocking=False):
            raise TimeoutError("observer delivery capacity unavailable")
        future = Future()
        def deliver():
            try:
                future.set_result(self._send(event))
            except BaseException as exc:
                future.set_exception(exc)
            finally:
                self._slots.release()
        try:
            Thread(target=deliver, daemon=True).start()
        except BaseException:
            self._slots.release()
            raise
        try:
            return future.result(timeout=2)
        except FutureTimeoutError as exc:
            # Python 3.10 uses a distinct futures exception; expose the same
            # public timeout type on every supported Python version.
            raise TimeoutError("observer delivery timed out") from exc

    def _send(self, event):
        request = Request(self.url + "/v1/continuity/events", data=json.dumps(event, allow_nan=False).encode(),
                          headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.token})
        with self.opener.open(request, timeout=2) as response:
            body = response.read(8193)
            if len(body) > 8192:
                raise ValueError("observer acknowledgement too large")
            acknowledgement = json.loads(body)
            if not isinstance(acknowledgement, dict) or acknowledgement.get("accepted") is not True:
                raise ValueError("observer did not acknowledge acceptance")
            return acknowledgement


def langgraph_node(client, workflow_id, name, tools, *, result_key="result"):
    """Use as a normal StateGraph node; leave checkpoints and scheduling to LangGraph."""
    def node(state, config=None):
        configured = (config or {}).get("configurable", {})
        result = client.run_operation(workflow_id, name, tools, run_id=configured.get("continuity_run_id"))
        return {result_key: result}
    return node
