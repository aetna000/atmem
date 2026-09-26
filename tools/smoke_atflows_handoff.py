"""Installed AtFlows + AtMem read-only handoff smoke gate."""

from __future__ import annotations

import json
from importlib.metadata import version
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from atmem.control.manager import ControlPlaneManager
from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from atmem.integrations.atflows import fetch_traces, review_leads


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    atflows_bin = os.environ.get("ATFLOWS_BIN", "atflows")
    atflows_version = subprocess.check_output([atflows_bin, "--version"], text=True).strip()
    if version("atflows") != "0.1.4b2" or atflows_version != "atflows 0.1.4b2":
        raise RuntimeError("AtFlows installed version does not match the pinned handoff")
    with tempfile.TemporaryDirectory(prefix="atmem-atflows-smoke-") as root:
        root_path = Path(root)
        port = _free_port()
        environment = os.environ.copy()
        environment.update({
            "DATA_DIR": str(root_path / "atflows"),
            "DASHBOARD_PORT": str(port),
            "PROXY_PORT": str(_free_port()),
            "ATFLOWS_ADMIN_PASSWORD": "fixture-password-long-enough",
        })
        origin = f"http://127.0.0.1:{port}"
        with (root_path / "server.log").open("wb") as log:
            process = subprocess.Popen([atflows_bin], env=environment, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f"AtFlows server exited with {process.returncode}")
                    try:
                        with urlopen(f"{origin}/api/health", timeout=1) as response:
                            if json.load(response).get("status") == "ok":
                                break
                    except (URLError, TimeoutError):
                        time.sleep(0.3)
                else:
                    raise TimeoutError("AtFlows server did not become ready")

                manager = ControlPlaneManager.start(
                    host="generic", state_path=root_path / "state.json",
                    control_root=root_path / "control", subject_id="smoke-subject",
                    memory_db=root_path / "memory.db",
                )
                manager.record_blackbox_event(
                    event_type="tool.requested", run_id="smoke-run", session_id="smoke-session",
                    execution_id="smoke-run", event_id="smoke-event",
                    producer_instance_id="smoke", producer_epoch="epoch-1", producer_sequence=1,
                    event_time="2026-09-20T00:00:00.000Z", subject_id="smoke-subject",
                    payload={"tool_name": "fixture.tool", "_atmem_evidence": {"parts": [{"type": "text", "text": "PRIVATE SMOKE INPUT"}]}},
                )
                now_ms = int(time.time() * 1000)
                span = {
                    "resourceSpans": [{"resource": {"attributes": []}, "scopeSpans": [{"spans": [{
                        "traceId": "1234567890abcdef1234567890abcdef", "spanId": "1234567890abcdef",
                        "name": "fixture.failure", "startTimeUnixNano": str(now_ms * 1_000_000),
                        "endTimeUnixNano": str((now_ms + 10) * 1_000_000),
                        "attributes": [{"key": "session.id", "value": {"stringValue": "smoke-session"}}],
                        "status": {"code": 2, "message": "PRIVATE SMOKE ERROR"},
                    }]}]}],
                }
                request = Request(f"{origin}/v1/traces", data=json.dumps(span).encode(), headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request, timeout=10) as response:
                    if response.status not in (200, 202):
                        raise RuntimeError("AtFlows rejected the fixture span")
                traces = fetch_traces(base_url=origin, password=environment["ATFLOWS_ADMIN_PASSWORD"], session_id="smoke-session", since_ms=now_ms - 1000, until_ms=now_ms + 1000)
                report = review_leads(
                    manager.evidence_service(),
                    EvidencePrincipal("smoke-investigator", EvidenceRole.INVESTIGATOR, EvidenceScope("local", "smoke-subject")),
                    run_id="smoke-run", session_id="smoke-session", traces=traces,
                    since_ms=now_ms - 1000, until_ms=now_ms + 1000,
                )
                if not report["leads"] or "PRIVATE SMOKE" in json.dumps(report):
                    raise RuntimeError("AtFlows handoff failed its lead or redaction gate")
                accounts = manager.evidence_service().create_demo_accounts(subject_id="smoke-subject")
                token = next(row["token"] for row in accounts if row["role"] == "investigator")
                environment["ATMEM_EVIDENCE_TOKEN"] = token
                review_command = [
                    sys.executable, "-m", "atmem.cli", "atflows", "review", "smoke-run",
                    "--session-id", "smoke-session", "--since-ms", str(now_ms - 1000),
                    "--until-ms", str(now_ms + 1000),
                    "--state", str(root_path / "state.json"), "--base-url", origin,
                ]
                cli = subprocess.run(
                    review_command,
                    env=environment, text=True, capture_output=True, timeout=20, check=True,
                )
                cli_report = json.loads(cli.stdout)
                if len(cli_report["leads"]) != 1 or "PRIVATE SMOKE" in cli.stdout:
                    raise RuntimeError("AtMem CLI did not preserve the handoff or redaction boundary")
                human = subprocess.run(
                    [*review_command, "--human"],
                    env=environment, text=True, capture_output=True, timeout=20, check=True,
                )
                if "Review leads    1" not in human.stdout or "PRIVATE SMOKE" in human.stdout:
                    raise RuntimeError("AtMem human review did not preserve the handoff or redaction boundary")
                print(f"{atflows_version} + AtMem local handoff passed: {len(report['leads'])} lead")
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
