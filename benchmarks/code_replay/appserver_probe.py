"""Zero-inference app-server configuration/sandbox qualification.

This diagnostic cannot start a model turn. It does not replace the scored exec
runner, recover old usage, change owner configuration or authorize API billing.
"""
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.grade import write_new_tree
from benchmarks.code_replay.runner import allocate_session
from benchmarks.code_replay.sandbox import permission_arguments


class ConfigRPC:
    ALLOWED = {"initialize", "thread/start", "config/read", "command/exec"}

    def __init__(self, command, *, cwd, env):
        self.command, self.sent, self.messages = command, [], []
        self.raw = {"stdout": bytearray(), "stderr": bytearray()}
        self.pending = b""
        self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ, "stdout")
        self.selector.register(self.process.stderr, selectors.EVENT_READ, "stderr")

    def send(self, message):
        if message.get("method") not in self.ALLOWED | {"initialized"}:
            raise ValueError("zero-inference diagnostic method not permitted")
        self.sent.append(message)
        self.process.stdin.write(json.dumps(message).encode() + b"\n")
        self.process.stdin.flush()

    def call(self, method, params, timeout=15):
        request_id = len(self.sent) + 1
        self.send({"method": method, "params": params, "id": request_id})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            reply = next((m for m in self.messages if m.get("id") == request_id and
                          ("result" in m or "error" in m)), None)
            if reply is not None:
                if "error" in reply:
                    raise RuntimeError("app-server rejected " + method)
                return reply["result"]
            self.pump(min(.2, max(0, deadline - time.monotonic())))
        raise TimeoutError("bounded app-server reply timeout: " + method)

    def pump(self, timeout=.2):
        if not self.selector.get_map():
            raise RuntimeError("app-server stream closed before reply")
        for key, _ in self.selector.select(timeout):
            chunk = os.read(key.fileobj.fileno(), 65536)
            if not chunk:
                self.selector.unregister(key.fileobj)
                continue
            self.raw[key.data].extend(chunk)
            if sum(map(len, self.raw.values())) > 8_000_000:
                raise RuntimeError("diagnostic stream budget exceeded")
            if key.data == "stdout":
                self.pending += chunk
                while b"\n" in self.pending:
                    line, self.pending = self.pending.split(b"\n", 1)
                    message = json.loads(line)
                    if not isinstance(message, dict):
                        raise ValueError("app-server event object required")
                    self.messages.append(message)
                    if "method" in message and "id" in message:
                        raise PermissionError("unexpected server request in no-approval diagnostic")

    def close(self):
        self.selector.close()
        # Do not signal a PID/process group after reaping it.
        if self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                # A child may have exited between poll and killpg on macOS.
                # Reap a confirmed exit; never discard an error for a live child.
                if self.process.poll() is None:
                    raise
            self.process.wait(timeout=5)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()


def configuration_command(session, interpreter):
    return [str(session.executable), "app-server", "--listen", "stdio://", "--strict-config",
        "-c", 'default_permissions="click-replay"', "-c", 'approval_policy="never"',
        "-c", 'web_search="disabled"', "-c", 'model="gpt-6-luna"',
        "-c", 'model_reasoning_effort="low"',
        *permission_arguments((session.executable.parent, interpreter))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ram-root", "auth-file", "state-root", "evidence-root", "interpreter"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--subscription-only", action="store_true")
    args = parser.parse_args()
    if not args.subscription_only:
        parser.error("subscription-only qualification required; no API/GPU dispatch")
    args.state_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    session = allocate_session(args.ram_root, args.auth_file)
    library = args.interpreter / "lib/python3.12"
    files = {name: (library / name).read_bytes() for name in ("logging/__init__.py", "logging/handlers.py", "LICENSE.txt")}
    write_new_tree(session.workspace, files)
    marker = "PUBLIC_DIAGNOSTIC_DENIED_CANARY_" + os.urandom(12).hex()
    canary = args.state_root / "denied-canary.txt"
    with canary.open("x") as stream:
        stream.write(marker)
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    run_id = "usage-rpc-config-p1-20261017"
    if vault.inspect(principal, run_id):
        raise ValueError("diagnostic run already retained; do not overwrite or retry invisibly")
    command = configuration_command(session, args.interpreter)
    rpc = ConfigRPC(command, cwd=session.workspace, env={"PATH": "/usr/bin:/bin",
        "CODEX_HOME": str(session.cli_home), "TMPDIR": str(session.temporary), "LANG": "en_US.UTF-8"})
    proof, failure = {}, None
    try:
        rpc.call("initialize", {"clientInfo": {"name": "atmem-code-benchmark", "version": "1.0.0"}})
        rpc.send({"method": "initialized"})
        thread = rpc.call("thread/start", {"model": "gpt-6-luna", "ephemeral": True,
            "cwd": str(session.workspace), "approvalPolicy": "never"})
        if thread["model"] != "gpt-6-luna" or thread["approvalPolicy"] != "never" or thread["cwd"] != str(session.workspace):
            raise PermissionError("thread binding/model/approval changed")
        config = rpc.call("config/read", {"cwd": str(session.workspace), "includeLayers": False})
        if config["config"].get("default_permissions") != "click-replay":
            raise PermissionError("named permissions profile not effective")
        positive = rpc.call("command/exec", {"command": ["/usr/bin/head", "-n", "1", "LICENSE.txt"],
            "cwd": str(session.workspace), "timeoutMs": 3000, "outputBytesCap": 1024})
        negative = rpc.call("command/exec", {"command": ["/bin/cat", str(canary)],
            "cwd": str(session.workspace), "timeoutMs": 3000, "outputBytesCap": 1024})
        if positive["exitCode"] != 0 or negative["exitCode"] == 0 or marker in negative.get("stdout", ""):
            raise PermissionError("actual app-server native source/isolation control failed")
        proof = {"passed": True, "model_calls": 0, "model": thread["model"],
            "named_profile": "click-replay", "public_read_passed": True, "canary_read_denied": True,
            "assurance": "configuration_and_operator_command_route_only_not_model_or_usage_qualification"}
    except BaseException as exc:
        failure = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        cleanup_failure = None
        try:
            rpc.close()
        except Exception as exc:
            cleanup_failure = type(exc).__name__ + ": " + str(exc)
        vault.capture(run_id=run_id, kind="appserver.configuration_probe", principal=principal, payload={
            "proof": proof, "failure": failure, "cleanup_failure": cleanup_failure,
            "model_calls": 0, "command": command,
            "requests": rpc.sent, "messages": rpc.messages,
            "stdout_base64": base64.b64encode(rpc.raw["stdout"]).decode(),
            "stderr_base64": base64.b64encode(rpc.raw["stderr"]).decode(),
            "cli_sha256": sha256(session.executable.read_bytes()).hexdigest(),
            "probe_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_sha256": {name: sha256(raw).hexdigest() for name, raw in files.items()}})
        if cleanup_failure is not None and failure is None:
            raise RuntimeError(cleanup_failure)
    print(json.dumps(proof))


if __name__ == "__main__":
    main()
