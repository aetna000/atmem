"""Installed AtMem and AtFlows delegated-login smoke gate."""
from __future__ import annotations

from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
from threading import Thread
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

from atmem.control.manager import ControlPlaneManager
from atmem.control.web import ControlDashboardServer


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


with tempfile.TemporaryDirectory(prefix="atmem-atflows-shared-login-") as root:
    root_path = Path(root)
    manager = ControlPlaneManager.start(host="generic", state_path=root_path / "state.json", control_root=root_path / "control", subject_id="fixture-subject")
    manager.record_blackbox_event(
        event_type="tool.requested", run_id="fixture-run", session_id="fixture",
        execution_id="fixture-run", event_id="fixture-event",
        producer_instance_id="fixture", producer_epoch="epoch-1", producer_sequence=1,
        event_time="2026-09-20T00:00:00.000Z", subject_id="fixture-subject",
        payload={"tool_name": "fixture.tool"},
    )
    identity = manager.identity_service()
    first_password = identity.bootstrap()["password"]
    first_session = identity.login("administrator", first_password)
    identity.change_password(first_session["session_token"], first_password, "new-local-test-password-long")
    atmem = ControlDashboardServer(("127.0.0.1", 0), manager, html="safe")
    thread = Thread(target=atmem.serve_forever, daemon=True)
    thread.start()
    atmem_origin = f"http://127.0.0.1:{atmem.server_port}"
    dashboard_port = free_port()
    env = os.environ.copy()
    env.update({
        "DATA_DIR": str(root_path / "atflows"),
        "DASHBOARD_PORT": str(dashboard_port),
        "PROXY_PORT": str(free_port()),
        "ATFLOWS_ATMEM_AUTH_URL": atmem_origin,
    })
    env["ATFLOW_RUNTIME_DIR"] = str(root_path / "runtime")
    log_path = root_path / "atflows.log"
    with log_path.open("wb") as log:
        process = subprocess.Popen([os.environ.get("ATFLOWS_BIN", "atflows")], env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            atflows_origin = f"http://127.0.0.1:{dashboard_port}"
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(f"AtFlows exited early: {log_path.read_text()[-1000:]}")
                try:
                    with urlopen(f"{atflows_origin}/api/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError(f"AtFlows did not start: {log_path.read_text()[-1000:]}")
            opener = build_opener(HTTPCookieProcessor(CookieJar()))
            with opener.open(Request(f"{atmem_origin}/api/auth/login", data=json.dumps({"username": "administrator", "password": "new-local-test-password-long"}).encode(), headers={"Content-Type": "application/json", "Origin": atmem_origin}, method="POST")) as response:
                assert json.load(response)["authenticated"]
            with opener.open(f"{atflows_origin}/api/auth/status") as response:
                status = json.load(response)
                assert status["authenticated"] and status["account"]["role"] == "administrator" and status["mode"] == "atmem", status
            from atmem.integrations.atflows import auth_mode, fetch_traces
            assert auth_mode(atflows_origin) == "atmem"
            session = identity.login("administrator", "new-local-test-password-long")
            try:
                assert fetch_traces(base_url=atflows_origin, atmem_session=session["session_token"], session_id="fixture", since_ms=0, until_ms=1000) == []
            finally:
                identity.logout(session["session_token"])
            with opener.open(f"{atflows_origin}/api/traces") as response:
                assert response.status == 200
            accounts = manager.evidence_service().create_demo_accounts(subject_id="fixture-subject")
            env["ATMEM_EVIDENCE_TOKEN"] = next(row["token"] for row in accounts if row["role"] == "investigator")
            env["ATMEM_USERNAME"] = "administrator"
            env["ATMEM_PASSWORD"] = "new-local-test-password-long"
            review = subprocess.run(
                [os.environ.get("ATMEM_BIN", "atmem"), "atflows", "review", "fixture-run",
                 "--session-id", "fixture", "--since-ms", "0", "--until-ms", "1000",
                 "--state", str(root_path / "state.json"), "--base-url", atflows_origin],
                env=env, capture_output=True, text=True, timeout=20, check=True,
            )
            assert json.loads(review.stdout)["leads"] == []
            try:
                opener.open(f"{atflows_origin}/api/users")
            except HTTPError as exc:
                assert exc.code == 409
            else:
                raise AssertionError("AtFlows local user management was not disabled")
            with opener.open(Request(f"{atflows_origin}/api/auth/logout", data=b"{}", headers={"Origin": atflows_origin, "Content-Type": "application/json"}, method="POST")) as response:
                assert json.load(response)["authenticated"] is False
            with opener.open(f"{atmem_origin}/api/auth/status") as response:
                assert json.load(response)["authenticated"] is False
            assert not (root_path / "atflows" / "admin-auth.json").exists()
            print("AtMem-owned login, role, delegated CLI review, protected AtFlows API, disabled local users, and shared logout passed")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            atmem.shutdown()
            atmem.server_close()
