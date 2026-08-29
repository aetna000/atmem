from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
import json
import secrets
import sys
from typing import Any
from urllib.parse import parse_qs, urlparse

from atmem.control import ControlPlaneManager, ControlMode


class ControlDashboardServer(ThreadingHTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        manager: ControlPlaneManager,
        *,
        html: str,
    ) -> None:
        host, _ = address
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("memory control plane dashboard is loopback-only")
        super().__init__(address, ControlDashboardHandler)
        self.manager = manager
        self.html = html
        self.csrf_token = secrets.token_urlsafe(32)


class ControlDashboardHandler(BaseHTTPRequestHandler):
    server: ControlDashboardServer

    def do_GET(self) -> None:  # noqa: N802
        if not self._valid_host():
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid Host header"})
            return
        parsed = urlparse(self.path)
        path = _canonical_api_path(parsed.path)
        if path == "/":
            body = self.server.html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self._security_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/assets/atmem.jpg":
            body = files("atmem.control").joinpath("assets/atmem.jpg").read_bytes()
            self.send_response(HTTPStatus.OK)
            self._security_headers()
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/session":
            self._json(HTTPStatus.OK, {"csrf_token": self.server.csrf_token})
            return
        if path == "/api/product":
            from atmem.openclaw_install import (
                OPENCLAW_PLUGIN_PACKAGE,
                OPENCLAW_PLUGIN_VERSION,
            )

            try:
                pip_version = version("atmem")
            except PackageNotFoundError:
                pip_version = "development"
            self._json(
                HTTPStatus.OK,
                {
                    "atmem_pip_version": pip_version,
                    "atmem_npm_package": OPENCLAW_PLUGIN_PACKAGE,
                    "atmem_npm_version": OPENCLAW_PLUGIN_VERSION,
                    "x_url": "https://x.com/AtMemX",
                },
            )
            return
        if path == "/api/status":
            self._json(HTTPStatus.OK, self.server.manager.status())
            return
        if path == "/api/bridge/status":
            if self.server.manager.state().host != "openclaw":
                self._json(
                    HTTPStatus.OK,
                    {"available": False, "reason": "The generic adapter has no installable bridge."},
                )
                return
            from atmem.openclaw_install import openclaw_bridge_refresh_status

            try:
                self._json(HTTPStatus.OK, openclaw_bridge_refresh_status())
            except ValueError as exc:
                self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
            return
        if path == "/api/blackbox/runs":
            params = parse_qs(parsed.query)
            try:
                limit = int((params.get("limit") or ["50"])[0])
                offset = int((params.get("offset") or ["0"])[0])
                self._json(
                    HTTPStatus.OK,
                    self.server.manager.blackbox_runs(limit=limit, offset=offset),
                )
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path in {
            "/api/blackbox/flight",
            "/api/blackbox/story",
            "/api/blackbox/export",
        }:
            from atmem.control.blackbox import format_flight_report

            params = parse_qs(parsed.query)
            run_id = (params.get("run_id") or [""])[0].strip()
            if not run_id:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "run_id is required"})
                return
            try:
                report = self.server.manager.verify_blackbox_flight(run_id)
            except ValueError as exc:
                self._json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            if path == "/api/blackbox/flight":
                self._json(HTTPStatus.OK, report)
                return
            if path == "/api/blackbox/story":
                self._json(
                    HTTPStatus.OK,
                    self.server.manager.blackbox_flight_story(run_id),
                )
                return
            output_format = (params.get("format") or ["json"])[0]
            if output_format == "text":
                content = format_flight_report(report)
                content_type = "text/plain; charset=utf-8"
                suffix = "txt"
            elif output_format == "json":
                content = json.dumps(report, indent=2, sort_keys=True) + "\n"
                content_type = "application/json; charset=utf-8"
                suffix = "json"
            else:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "format must be json or text"},
                )
                return
            safe_run = "".join(
                char if char.isalnum() or char in {"-", "_"} else "-"
                for char in run_id
            )[:80]
            self._download(
                content,
                filename=f"atmem-blackbox-{safe_run}.{suffix}",
                content_type=content_type,
            )
            return
        if path == "/api/memory/search":
            params = parse_qs(parsed.query)
            query = (params.get("query") or [""])[0].strip()
            if not query:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "query is required"})
                return
            self._json(
                HTTPStatus.OK,
                self.server.manager.memory_search(
                    query,
                    limit=12,
                    agent_id=(params.get("agent_id") or [None])[0],
                    subject_id=(params.get("subject_id") or [None])[0],
                ),
            )
            return
        if path == "/api/memory/reviews":
            self._json(
                HTTPStatus.OK,
                self.server.manager.memory_reviews(),
            )
            return
        if path == "/api/memory/media-preview":
            if self.server.manager.state().host != "openclaw":
                self._json(
                    HTTPStatus.CONFLICT,
                    {"error": "media preview requires an adapter-owned local media reader"},
                )
                return
            from atmem.control.openclaw_native import resolve_mirror_review_image

            record_id = (parse_qs(parsed.query).get("record_id") or [""])[0].strip()
            try:
                preview = resolve_mirror_review_image(
                    self.server.manager.state(), record_id
                )
            except ValueError as exc:
                self._json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            path = preview["path"]
            self.send_response(HTTPStatus.OK)
            self._security_headers()
            self.send_header("Content-Type", str(preview["content_type"]))
            self.send_header("Content-Length", str(preview["bytes"]))
            self.send_header("Content-Disposition", "inline")
            self.send_header(
                "X-AtMem-Media-SHA256", str(preview["media_sha256"])
            )
            self.end_headers()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    self.wfile.write(chunk)
            return
        if path == "/api/memory/trace":
            query = (parse_qs(parsed.query).get("query") or [""])[0].strip()
            if not query:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "query is required"})
                return
            if self.server.manager.state().host == "openclaw":
                from atmem.control.openclaw_native import trace_mirror

                report = trace_mirror(self.server.manager.state(), query, limit=100)
            else:
                report = self.server.manager.memory_search(query, limit=100)
            self._json(HTTPStatus.OK, report)
            return
        if path in {"/api/memory/audit", "/api/memory/audit-export"}:
            params = parse_qs(parsed.query)
            value = lambda name, default="": (params.get(name) or [default])[0].strip()
            filters = {
                "query": value("query"),
                "event_type": value("event_type"),
                "actor": value("actor"),
                "session_id": value("session_id"),
                "record_id": value("record_id"),
                "since": value("since"),
                "until": value("until"),
                "direction": value("direction", "desc"),
            }
            if path == "/api/memory/audit-export":
                output_format = value("format", "json")
                try:
                    content, content_type = self.server.manager.export_memory_audit(
                        output_format=output_format, filters=filters
                    )
                except ValueError as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                self._download(
                    content,
                    filename=f"atmem-audit-investigation.{output_format}",
                    content_type=content_type,
                )
                return
            cursor_text = value("cursor")
            try:
                cursor = int(cursor_text) if cursor_text else None
                limit = int(value("limit", "100"))
                report = self.server.manager.memory_audit(
                    **filters,
                    cursor=cursor,
                    limit=limit,
                    include_facets=value("include_facets", "0") == "1",
                )
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._json(HTTPStatus.OK, report)
            return
        if path in {
            "/api/memory/record",
            "/api/memory/record-report",
            "/api/memory/deletion-receipt",
        }:
            params = parse_qs(parsed.query)
            record_id = (params.get("record_id") or [""])[0].strip()
            if not record_id:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "record_id is required"})
                return
            try:
                report = self.server.manager.memory_record(record_id)
            except ValueError as exc:
                self._json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            if path == "/api/memory/record":
                self._json(HTTPStatus.OK, report)
                return
            if path == "/api/memory/deletion-receipt":
                receipt = report.get("deletion_receipt")
                if not receipt:
                    self._json(
                        HTTPStatus.NOT_FOUND,
                        {"error": "this record has no deletion receipt"},
                    )
                    return
                self._download(
                    json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                    filename=f"atmem-deletion-{record_id}.json",
                    content_type="application/json; charset=utf-8",
                )
                return
            output_format = (params.get("format") or ["json"])[0]
            if output_format == "text":
                if self.server.manager.state().host == "openclaw":
                    from atmem.control.openclaw_native import format_mirror_record_report

                    content = format_mirror_record_report(report)
                else:
                    record = report.get("record") or {}
                    content = (
                        f"AtMem memory {record_id}\n"
                        f"Status: {report.get('status')}\n"
                        f"Subject: {record.get('subject_id')}\n"
                        f"Content: {record.get('content')}\n"
                        f"SHA-256: {record.get('content_sha256')}\n"
                    )
                self._download(
                    content,
                    filename=f"atmem-investigation-{record_id}.txt",
                    content_type="text/plain; charset=utf-8",
                )
                return
            if output_format != "json":
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "format must be json or text"},
                )
                return
            self._download(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                filename=f"atmem-investigation-{record_id}.json",
                content_type="application/json; charset=utf-8",
            )
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._same_origin() or not secrets.compare_digest(
            self.headers.get("X-CSRF-Token", ""), self.server.csrf_token
        ):
            self._json(HTTPStatus.FORBIDDEN, {"error": "CSRF check failed"})
            return
        try:
            body = self._body()
            path = _canonical_api_path(urlparse(self.path).path)
            if path == "/api/blackbox/acknowledge":
                run_id = str(body.get("run_id") or "").strip()
                attention_code = str(body.get("attention_code") or "").strip()
                if not run_id or not attention_code:
                    raise ValueError("run_id and attention_code are required")
                if not secrets.compare_digest(
                    str(body.get("confirm_run_id") or ""), run_id
                ):
                    raise ValueError("run confirmation does not match")
                self._json(
                    HTTPStatus.OK,
                    self.server.manager.acknowledge_blackbox_attention(
                        run_id,
                        attention_code,
                        actor="dashboard-reviewer",
                    ),
                )
                return
            if path == "/api/mode":
                mode = ControlMode(str(body["mode"]))
                if mode is not ControlMode.ACTIVE:
                    raise ValueError(
                        "use this endpoint only to activate AtMem; use /api/restore to return safely"
                    )
                expected_host = self.server.manager.state().host
                if not secrets.compare_digest(
                    str(body.get("confirm_host") or ""), expected_host
                ):
                    raise ValueError(
                        f"type the host name `{expected_host}` to confirm"
                    )
                if mode is ControlMode.ACTIVE:
                    self._json(
                        HTTPStatus.OK,
                        self.server.manager.activate(actor="dashboard-reviewer"),
                    )
                    return
            if path == "/api/memory/sync":
                self._json(
                    HTTPStatus.OK,
                    self.server.manager.sync_memory(),
                )
                return
            if path == "/api/memory/review":
                record_id = str(body.get("record_id") or "").strip()
                decision = str(body.get("decision") or "").strip()
                if not secrets.compare_digest(
                    str(body.get("confirm_record_id") or ""), record_id
                ):
                    raise ValueError("record confirmation does not match")
                self._json(
                    HTTPStatus.OK,
                    self.server.manager.review_memory(record_id, decision),
                )
                return
            if path == "/api/restore":
                self._json(
                    HTTPStatus.OK,
                    self.server.manager.deactivate(actor="dashboard-reviewer"),
                )
                return
            if path == "/api/restore-drill":
                if self.server.manager.state().host != "openclaw":
                    raise ValueError(
                        "restore drill requires an adapter with preserved native host state"
                    )
                from atmem.control.openclaw_native import restore_drill

                self._json(
                    HTTPStatus.OK,
                    restore_drill(self.server.manager.state()),
                )
                return
            if path == "/api/verify":
                self._json(
                    HTTPStatus.OK,
                    self.server.manager.verify(probe=bool(body.get("probe", False))),
                )
                return
            if path == "/api/bridge/refresh-test":
                expected_host = self.server.manager.state().host
                if expected_host != "openclaw":
                    raise ValueError(
                        "bridge refresh is available only for the OpenClaw adapter"
                    )
                if not secrets.compare_digest(
                    str(body.get("confirm_host") or ""), expected_host
                ):
                    raise ValueError(
                        f"type the host name `{expected_host}` to confirm"
                    )
                from atmem.openclaw_install import refresh_openclaw_bridge_and_test

                self._json(
                    HTTPStatus.OK,
                    refresh_openclaw_bridge_and_test(
                        state_path=self.server.manager.state_path
                    ),
                )
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except (KeyError, TypeError, ValueError) as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        del format, args

    def _same_origin(self) -> bool:
        host = self.headers.get("Host", "")
        allowed = {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }
        if host not in allowed:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in {f"http://{item}" for item in allowed}

    def _valid_host(self) -> bool:
        return self.headers.get("Host", "") in {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }

    def _body(self) -> dict[str, Any]:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if size < 0 or size > 1_000_000:
            raise ValueError("request body is too large")
        value = json.loads(self.rfile.read(size) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def _json(self, status: HTTPStatus, value: Any) -> None:
        body = json.dumps(value, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _download(self, value: str, *, filename: str, content_type: str) -> None:
        body = value.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")


def _canonical_api_path(path: str) -> str:
    """Keep legacy mirror URLs working while exposing host-neutral memory URLs."""

    if path.startswith("/api/mirror/"):
        return "/api/memory/" + path.removeprefix("/api/mirror/")
    return path


def dashboard_html() -> str:
    try:
        from atmem.control.ui import APP_HTML

        return APP_HTML
    except Exception as exc:  # dashboard must degrade, never crash
        print(
            f"atmem: dashboard assets unavailable ({exc}); serving JSON fallback",
            file=sys.stderr,
        )
        return _FALLBACK_HTML


_FALLBACK_HTML = """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>AtMem memory control plane</title>
<style>
body{font:16px system-ui;max-width:760px;margin:4rem auto;padding:0 1rem;color:#1a2b2f}
pre{background:#f1f4f3;padding:1rem;overflow:auto}button{padding:.6rem 1rem}
</style>
<h1>AtMem memory control plane</h1>
<p id="mode" role="status">Loading verified local state…</p>
<pre id="status"></pre>
<script>
let csrf="";
async function load(){
 const s=await fetch("/api/session").then(r=>r.json());csrf=s.csrf_token;
 const v=await fetch("/api/status").then(r=>r.json());
 document.querySelector("#mode").textContent=`Mode: ${v.mode} — context changes: ${v.changes_model_context}`;
 document.querySelector("#status").textContent=JSON.stringify(v,null,2);
} load();
</script></html>"""
