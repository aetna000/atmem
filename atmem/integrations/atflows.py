"""Optional, read-only AtFlows leads over authorized AtMem run evidence."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from http.cookiejar import CookieJar
import ipaddress
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, ProxyHandler, Request, build_opener

from atmem.evidence.models import EvidenceOperation, EvidencePrincipal, EvidenceScope
from atmem.evidence.service import EvidenceService


_MAX_ROWS = 100
_MAX_BODY = 2_000_000
_MAX_WINDOW_MS = 7 * 24 * 60 * 60 * 1000


def _identifier(value: str, name: str) -> str:
    clean = str(value or "").strip()
    if not clean or len(clean) > 512 or any(ord(char) < 32 for char in clean):
        raise ValueError(f"{name} must be a printable identifier of at most 512 characters")
    return clean


def _trace_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("AtFlows returned an invalid trace identifier")
    return value


def _loopback_origin(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("AtFlows URL must be a loopback HTTP origin")
    try:
        host = parsed.hostname or ""
        allowed = ipaddress.ip_address(host).is_loopback
        port = parsed.port
    except ValueError as exc:
        raise ValueError("AtFlows URL must be a loopback HTTP origin") from exc
    if not allowed or port is None:
        raise ValueError("AtFlows URL must be a loopback HTTP origin with a port")
    return f"http://[{host}]:{port}" if ":" in host else f"http://{host}:{port}"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _request_json(opener: Any, request: Request) -> Any:
    try:
        with opener.open(request, timeout=10) as response:
            body = response.read(_MAX_BODY + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("AtFlows local API request failed or authentication was denied") from exc
    if len(body) > _MAX_BODY:
        raise ValueError("AtFlows response exceeds the bounded review limit")
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("AtFlows returned invalid JSON") from exc


def auth_mode(base_url: str) -> str:
    """Discover which local account authority the AtFlows dashboard uses."""
    origin = _loopback_origin(base_url)
    status = _request_json(
        build_opener(ProxyHandler({}), _NoRedirect()),
        Request(f"{origin}/api/auth/status"),
    )
    return "atmem" if isinstance(status, dict) and status.get("mode") == "atmem" else "standalone"


def fetch_traces(
    *, base_url: str, password: str | None = None, atmem_session: str | None = None,
    session_id: str, since_ms: int, until_ms: int
) -> list[dict[str, Any]]:
    """Read one bounded AtFlows session window; never return trace bodies."""
    origin = _loopback_origin(base_url)
    session_id = _identifier(session_id, "session_id")
    if bool(password) == bool(atmem_session):
        raise ValueError("one AtFlows administrator password or AtMem session is required")
    if atmem_session and (len(atmem_session) > 512 or not re.fullmatch(r"[A-Za-z0-9_-]+", atmem_session)):
        raise ValueError("invalid AtMem session")
    if since_ms < 0 or until_ms <= since_ms or until_ms - since_ms > _MAX_WINDOW_MS:
        raise ValueError("review window must be positive and at most seven days")
    opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()), _NoRedirect())
    if password:
        login = Request(
            f"{origin}/api/auth/login",
            data=json.dumps({"username": "administrator", "password": password}).encode(),
            headers={"Content-Type": "application/json", "Origin": origin},
            method="POST",
        )
        auth = _request_json(opener, login)
        if not isinstance(auth, dict) or auth.get("authenticated") is not True or auth.get("password_change_required"):
            raise RuntimeError("AtFlows administrator sign-in is incomplete")
    query = urlencode({"session_id": session_id, "date_from": since_ms, "date_to": until_ms, "limit": _MAX_ROWS, "offset": 0})
    try:
        headers = {"Cookie": f"atmem_session={atmem_session}"} if atmem_session else {}
        rows = _request_json(opener, Request(f"{origin}/api/traces?{query}", headers=headers))
    finally:
        if password:
            try:
                _request_json(opener, Request(f"{origin}/api/auth/logout", data=b"{}", headers={"Content-Type": "application/json", "Origin": origin}, method="POST"))
            except (RuntimeError, ValueError):
                pass
    if not isinstance(rows, list) or len(rows) > _MAX_ROWS:
        raise ValueError("AtFlows returned an invalid bounded trace list")
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("session_id") != session_id:
            raise ValueError("AtFlows returned a trace outside the selected session")
        timestamp = row.get("timestamp")
        if type(timestamp) not in (int, float) or not since_ms <= timestamp <= until_ms:
            raise ValueError("AtFlows returned a trace outside the selected time window")
        result.append({
            "trace_id": _trace_identifier(str(row.get("trace_id") or row.get("id") or "")),
            "timestamp_ms": int(timestamp),
            "status": row.get("status"),
            "has_error": bool(row.get("error")),
        })
    return result


def review_leads(
    service: EvidenceService,
    principal: EvidencePrincipal,
    *,
    run_id: str,
    session_id: str,
    traces: list[dict[str, Any]],
    since_ms: int,
    until_ms: int,
) -> dict[str, Any]:
    """Compare untrusted telemetry with an exact authorized session identifier."""
    if since_ms < 0 or until_ms <= since_ms or until_ms - since_ms > _MAX_WINDOW_MS:
        raise ValueError("review window must be positive and at most seven days")
    if len(traces) > _MAX_ROWS:
        raise ValueError("review has too many AtFlows rows")
    run_id = _identifier(run_id, "run_id")
    session_id = _identifier(session_id, "session_id")
    target = EvidenceScope(principal.scope.tenant_id, principal.scope.subject_id, principal.scope.workspace_id, run_id)
    principal.authorize(EvidenceOperation.VIEW, target)
    matched = service.has_run_session(principal, run_id, session_id)
    if not matched:
        return {
            "format": "atmem-atflows-review-leads-v1",
            "run_id": run_id,
            "session_id": session_id,
            "correlation": "unverified",
            "reason": "no_authorized_atmem_evidence_with_exact_session_id",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "leads": [],
            "coverage": {"reported": False, "atflows_rows": None, "unique_traces": None, "truncated": None},
            "limitation": "Trace errors are review leads, not proof that memory caused an outcome.",
        }
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in traces:
        trace_id = _trace_identifier(str(row.get("trace_id") or ""))
        timestamp = row.get("timestamp_ms")
        if type(timestamp) is not int or not since_ms <= timestamp <= until_ms:
            raise ValueError("trace is outside the selected review window")
        status = row.get("status")
        failed = bool(row.get("has_error")) or (type(status) is int and status >= 400) or (isinstance(status, str) and status.lower() == "error")
        group = grouped.setdefault(trace_id, {"trace_id": trace_id, "first_seen_ms": timestamp, "last_seen_ms": timestamp, "failed": False})
        group["first_seen_ms"] = min(group["first_seen_ms"], timestamp)
        group["last_seen_ms"] = max(group["last_seen_ms"], timestamp)
        group["failed"] = group["failed"] or failed
    failures = [row for row in grouped.values() if row["failed"]]
    return {
        "format": "atmem-atflows-review-leads-v1",
        "run_id": run_id,
        "session_id": session_id,
        "correlation": "matching_session_id_untrusted_telemetry",
        "reason": None,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "leads": [{"reason_code": "observed_trace_error", "trace_id": row["trace_id"], "first_seen_ms": row["first_seen_ms"], "last_seen_ms": row["last_seen_ms"]} for row in failures],
        "coverage": {"reported": True, "atflows_rows": len(traces), "unique_traces": len(grouped), "truncated": len(traces) == _MAX_ROWS},
        "limitation": "Trace errors are review leads, not proof that memory caused an outcome.",
    }
