"""Pinned native retail tool boundary. Reference replay is NOT an agent score."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import multiprocessing as mp
from multiprocessing.connection import wait
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import platform
try:
    import tomllib
except ModuleNotFoundError:  # Test collection remains compatible with AtMem's Python 3.10.
    import tomli as tomllib

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from .manifest import UPSTREAM_COMMIT, digest, file_digest, git_head

LOCK = Path(__file__).with_name("protocol-lock.json")
SOURCE_LOCK = Path(__file__).with_name("retail-source-lock.json")
MAX_MESSAGE = 16 * 1024 * 1024


def dependency_versions(root: Path) -> dict:
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    if platform.python_version() not in SpecifierSet(project["requires-python"]):
        raise ValueError("Python version does not satisfy pinned upstream")
    versions = {}
    for raw in project["dependencies"]:
        requirement = Requirement(raw)
        if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
            continue
        version = importlib.metadata.version(requirement.name)
        if version not in requirement.specifier:
            raise ValueError(f"dependency outside upstream constraints: {requirement.name}")
        versions[requirement.name] = version
    return versions


def send_json(connection, value):
    payload = json.dumps(value, allow_nan=False).encode()
    if len(payload) > MAX_MESSAGE:
        raise ValueError("retail IPC message too large")
    connection.send_bytes(payload)


def receive_json(connection):
    return json.loads(connection.recv_bytes(MAX_MESSAGE))


def verify_checkout(root: Path) -> dict:
    """Verify bytes, not only HEAD; reject extra executable modules and symlinks."""
    root = root.resolve()
    if git_head(root) != UPSTREAM_COMMIT:
        raise ValueError("wrong upstream commit")
    trees = ["src", "data/tau2", "LICENSE", "pyproject.toml"]
    entries = subprocess.check_output(
        ["git", "--no-replace-objects", "ls-tree", "-r", "-z", UPSTREAM_COMMIT, "--", *trees], cwd=root
    ).split(b"\0")
    hashes = {}
    for entry in filter(None, entries):
        meta, relative = entry.decode().split("\t")
        mode, kind, blob = meta.split()
        path = root / relative
        if kind != "blob" or mode not in {"100644", "100755"} or path.is_symlink():
            raise ValueError(f"unsupported upstream file: {relative}")
        if not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError(f"missing/redirected upstream file: {relative}")
        content = path.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if actual != blob:
            raise ValueError(f"modified upstream file: {relative}")
        hashes[relative] = hashlib.sha256(content).hexdigest()
    known_top = {Path(name).parts[1] for name in hashes if name.startswith("src/")}
    if any(p.name not in known_top for p in (root / "src").iterdir()):
        raise ValueError("unexpected src entry could shadow dependencies")
    for path in (root / "src").rglob("*"):
        if path.is_symlink() or (path.is_file() and path.suffix in {".py", ".so", ".pyd"}
                                 and str(path.relative_to(root)) not in hashes):
            raise ValueError("untracked or redirected upstream module")
    lock = json.loads(LOCK.read_text())
    for field, relative in {"tasks_sha256": "tasks.json", "database_sha256": "db.json",
                            "split_sha256": "split_tasks.json"}.items():
        if hashes[f"data/tau2/domains/retail/{relative}"] != lock["upstream"][field]:
            raise ValueError("upstream disagrees with protocol lock")
    stamp = {"commit": UPSTREAM_COMMIT, "tree_sha256": digest(hashes),
            "policy_sha256": hashes["data/tau2/domains/retail/policy.md"],
            "tools_sha256": hashes["src/tau2/domains/retail/tools.py"]}
    if stamp != json.loads(SOURCE_LOCK.read_text()):
        raise ValueError("upstream tree disagrees with independent source lock")
    return stamp


def pilot_task(root: Path, task_id: str) -> dict:
    # This evaluator-only function may read labels. No task/labels reach the tool server.
    lock = json.loads(LOCK.read_text())
    if task_id not in lock["split"]["pilot_ids"]:
        raise ValueError("development replay is restricted to locked pilot IDs")
    verify_checkout(root)
    tasks = json.loads((root / "data/tau2/domains/retail/tasks.json").read_text())
    return next(t for t in tasks if str(t["id"]) == task_id)


def offline_guard(root: Path) -> list[str]:
    """Permanent child-process guard; no network or subprocess execution after import setup."""
    keep = {k: v for k, v in os.environ.items()
            if k in {"PATH", "TMPDIR", "LANG", "SYSTEMROOT", "WINDIR"}}
    os.environ.clear()
    os.environ.update(keep, PYTHON_DOTENV_DISABLED="1", LITELLM_LOCAL_MODEL_COST_MAP="True",
                      TAU2_DATA_DIR=str(root / "data"), LANGSMITH_TRACING="false",
                      LANGCHAIN_TRACING_V2="false")
    attempts = []

    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg",
                     "socket.bind", "socket.gethostbyname", "socket.gethostbyaddr",
                     "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn",
                     "os.spawn", "os.fork", "os.forkpty"}:
            attempts.append(event)
            raise PermissionError("offline retail worker forbids network and child commands")

    sys.addaudithook(audit)
    return attempts


def _load_environment(root: Path):
    sys.path.insert(0, str(root / "src"))
    sys.dont_write_bytecode = True
    allowed = {p.resolve() for p in (root / "src").rglob("*.py")}
    # dont_write_bytecode alone does not prevent reading poisoned in-tree caches.
    with tempfile.TemporaryDirectory(prefix="continuity-pycache-") as cache:
        sys.pycache_prefix = cache
        from loguru import logger
        logger.remove()  # Public tool payloads belong in evidence, not incidental console logs.
        from tau2.domains.retail.environment import get_environment
    for name, module in list(sys.modules.items()):
        location = getattr(module, "__file__", None)
        if location and Path(location).resolve().is_relative_to(root) and Path(location).resolve() not in allowed:
            raise ValueError("imported unverified file under upstream checkout")
        if name == "tau2" or name.startswith("tau2."):
            if location and not Path(location).resolve().is_relative_to(root / "src/tau2"):
                raise ValueError("imported tau2 outside pinned checkout")
    return get_environment()


def _response(environment, call: dict) -> dict:
    from tau2.data_model.message import ToolCall
    response = environment.get_response(ToolCall.model_validate(call))
    # Wall-clock receipt time is not semantic parity; retain every other field.
    return response.model_dump(mode="json", exclude={"timestamp"})


def _serve(root: str, public, oracle, stamp: dict):
    try:
        directory = Path(root)
        if verify_checkout(directory) != stamp:
            raise ValueError("upstream changed before child start")
        attempts = offline_guard(directory)
        environment = _load_environment(directory)
        if attempts:
            raise PermissionError("offline import attempted egress")
        initial = environment.tools.db.model_dump(mode="json")
        initial_hash = environment.get_db_hash()
        journal = []
        send_json(public, {"ready": True, "pid": os.getpid(), "stamp": stamp,
                     "tools": [t.openai_schema for t in environment.get_tools()]})
        while True:
            for connection in wait([public, oracle]):
                message = receive_json(connection)
                if connection is oracle:
                    if message == "stop":
                        return
                    if message == "snapshot":
                        send_json(oracle, {"initial": initial, "final": environment.tools.db.model_dump(mode="json"),
                                     "initial_db_hash": initial_hash, "final_db_hash": environment.get_db_hash(),
                                     "journal": journal, "egress_attempts": attempts})
                    else:
                        send_json(oracle, {"error": "unknown evaluator request"})
                elif isinstance(message, dict) and message.get("method") == "tool":
                    before = environment.get_db_hash()
                    response = _response(environment, message["call"])
                    journal.append({"sequence": len(journal), "call": message["call"],
                                    "response": response, "before": before,
                                    "after": environment.get_db_hash()})
                    if attempts:
                        raise PermissionError("offline egress attempted")
                    send_json(public, response)
                else:
                    send_json(public, {"error": "unknown public request"})
    except EOFError:
        return
    except Exception as error:
        send_json(locals().get("connection", public), {"worker_error": f"{type(error).__name__}: {error}"})
    finally:
        public.close()
        oracle.close()


class RetailProcess:
    """Evaluator owns lifecycle/oracle. Only the public connection is a tool boundary."""

    def __init__(self, root: Path, timeout: float = 60):
        self.root = root.resolve()
        self.stamp = verify_checkout(self.root)
        self.timeout = timeout
        ctx = mp.get_context("spawn")
        self.public, public_child = ctx.Pipe()
        self.oracle, oracle_child = ctx.Pipe()
        self.process = ctx.Process(target=_serve, args=(str(self.root), public_child, oracle_child, self.stamp))
        self.process.start()
        public_child.close()
        oracle_child.close()
        try:
            self.info = self._receive(self.public)
            if not self.info.get("ready"):
                raise RuntimeError("retail worker failed startup")
        except BaseException:
            self.close()
            raise

    def _receive(self, connection):
        if not connection.poll(self.timeout):
            raise TimeoutError("retail process response timed out")
        result = receive_json(connection)
        if "worker_error" in result:
            raise RuntimeError(result["worker_error"])
        return result

    def call(self, call: dict) -> dict:
        send_json(self.public, {"method": "tool", "call": call})
        return self._receive(self.public)

    def snapshot(self) -> dict:
        send_json(self.oracle, "snapshot")
        return self._receive(self.oracle)

    def close(self):
        if self.process.is_alive():
            try:
                send_json(self.oracle, "stop")
            except OSError:
                pass
            self.process.join(5)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(5)
        self.public.close()
        self.oracle.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _native_replay(root: str, calls: list[dict], connection):
    try:
        directory = Path(root)
        verify_checkout(directory)
        attempts = offline_guard(directory)
        environment = _load_environment(directory)
        from tau2.data_model.message import ToolCall
        initial = environment.tools.db.model_dump(mode="json")
        responses = [environment.get_response(ToolCall.model_validate(call)).model_dump(
            mode="json", exclude={"timestamp"}) for call in calls]
        send_json(connection, {"responses": responses, "initial": initial,
                         "final": environment.tools.db.model_dump(mode="json"),
                         "egress_attempts": attempts})
    except Exception as error:
        send_json(connection, {"worker_error": f"{type(error).__name__}: {error}"})
    finally:
        connection.close()


def reference_parity(root: Path, task_id: str) -> dict:
    task = pilot_task(root, task_id)
    dependencies = dependency_versions(root)
    if task.get("initial_state"):
        raise ValueError("initial-state replay not yet supported; do not silently ignore it")
    if any(a.get("requestor", "assistant") != "assistant" for a in task["evaluation_criteria"]["actions"]):
        raise ValueError("user-side reference action not supported")
    calls = [{"id": f"reference-{i}", "name": a["name"], "arguments": a["arguments"],
              "requestor": "assistant"} for i, a in enumerate(task["evaluation_criteria"]["actions"])]
    with RetailProcess(root) as remote:
        responses = [remote.call(call) for call in calls]
        observed = remote.snapshot()
        previous = observed["initial_db_hash"]
        for event in observed["journal"]:
            if event["before"] != previous:
                raise ValueError("discontinuous retail effect journal")
            previous = event["after"]
        if previous != observed["final_db_hash"]:
            raise ValueError("retail effect journal does not match final state")
        if ([e["call"] for e in observed["journal"]] != calls or
                [e["response"] for e in observed["journal"]] != responses):
            raise ValueError("retail effect journal does not match public transcript")
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe(False)
        native = ctx.Process(target=_native_replay, args=(str(root.resolve()), calls, child))
        native.start()
        child.close()
        try:
            direct = remote._receive(parent)
        finally:
            native.join(5)
            if native.is_alive():
                native.kill()
                native.join(5)
            parent.close()
        matched = (responses == direct["responses"] and observed["initial"] == direct["initial"]
                   and observed["final"] == direct["final"] and not observed["egress_attempts"]
                   and not direct["egress_attempts"])
        if verify_checkout(root) != remote.stamp:
            raise ValueError("upstream changed during replay")
        return {"evidence_level": "engineering-tool-parity", "production_claims_allowed": False,
                "agent_evaluation": False, "task_id": task_id, "source": remote.stamp,
                "provenance": {"python": platform.python_version(),
                    "upstream_dependency_versions": dependencies,
                    "files": {p.name: file_digest(p) for p in [Path(__file__),
                        Path(__file__).with_name("manifest.py"), LOCK, SOURCE_LOCK]},
                    "installed_package_metadata": {name: importlib.metadata.version(name) for name in
                        ["tau2", "pydantic", "loguru", "deepdiff", "docstring-parser", "litellm"]}},
                "tool_schema_sha256": digest(remote.info["tools"]), "calls": len(calls),
                "matched": matched, "response_sha256": digest(responses),
                "native_response_sha256": digest(direct["responses"]),
                "final_state_sha256": digest(observed["final"]),
                "native_final_state_sha256": digest(direct["final"]),
                "responses": responses, "native_responses": direct["responses"],
                "tool_errors": sum(bool(r.get("error")) for r in responses),
                "state_changed": observed["initial"] != observed["final"],
                "egress_attempts": observed["egress_attempts"] + direct["egress_attempts"],
                "excluded_parity_fields": ["ToolMessage.timestamp"],
                "limitation": "Evaluator reference actions, not autonomous agent or no-fault upstream score. "
                    "Audit hooks are tripwires, not a hostile-code/native-code sandbox; "
                    "concurrent malicious swap-and-restore of source is out of scope."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--task-id", default="0")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    result = reference_parity(args.upstream, args.task_id)
    result["harness_sha256"] = file_digest(Path(__file__))
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps(result))
    if not result["matched"]:
        raise SystemExit("native/wrapped tool parity failed")


if __name__ == "__main__":
    main()
