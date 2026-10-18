"""One pinned image architecture control; no task code, tests or inference."""
import argparse
import base64
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time
from uuid import uuid4

from benchmarks.code_replay.external_catalog import digest


def command(image, name):
    if not re.fullmatch(r"swebench/sweb\.eval\.x86_64\.[A-Za-z0-9_.-]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("immutable benchmark image required")
    if not re.fullmatch(r"atmem-runtime-control-[0-9a-f]{32}", name):
        raise ValueError("unique benchmark container name required")
    return ["docker", "run", "--rm", "--pull=never", "--platform", "linux/amd64", "--name", name,
        "--label", "atmem.benchmark=external-runtime-control-v1", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--memory", "512m", "--cpus", "1",
        "--pids-limit", "64", "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--entrypoint", "/bin/sh", image, "-c",
        'uname -m && /opt/miniconda3/envs/testbed/bin/python -I -S -c \'import sys; print("PYTHON", sys.version.split()[0], sys.platform)\'']


def guarded_pull(image):
    minimum = 8 * 1024 ** 3
    if shutil.disk_usage("/private/tmp").free < minimum:
        return {"passed": False, "reason": "host_free_space_below_8GiB", "started": False}
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(["docker", "pull", "--platform", "linux/amd64", image],
            stdout=log, stderr=subprocess.STDOUT)
        started = time.monotonic()
        reason = None
        while process.poll() is None:
            if time.monotonic() - started > 180:
                reason = "pull_timeout"
            elif shutil.disk_usage("/private/tmp").free < minimum:
                reason = "host_free_space_guard"
            elif log.tell() > 2_000_000:
                reason = "pull_output_budget"
            if reason:
                try:
                    process.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    if process.poll() is None:
                        raise
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                break
            time.sleep(.25)
        process.wait()
        log.seek(0)
        raw = log.read(2_000_000)
        return {"passed": reason is None and process.returncode == 0, "reason": reason,
                "started": True, "exit_code": process.returncode,
                "elapsed_s": time.monotonic() - started, "output_base64": base64.b64encode(raw).decode()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("runtime control already retained; no silent retry")
    selection = json.loads((args.preflight / "selection.json").read_bytes())
    metadata_bytes = (args.preflight / "metadata.json").read_bytes()
    metadata = json.loads(metadata_bytes)
    registry = json.loads((args.preflight / "registry.json").read_bytes())
    from hashlib import sha256
    if metadata["selection_sha256"] != digest(selection) or registry["metadata_sha256"] != sha256(metadata_bytes).hexdigest():
        raise ValueError("preflight bindings differ")
    chosen, row = selection["selected"][0], registry["rows"][0]
    if chosen["instance_id"] != "marshmallow-code__marshmallow-1229" or chosen["instance_id"] != row["instance_id"]:
        raise ValueError("only first predeclared compatibility control allowed")
    manifests = row["manifests"]
    if len(manifests) != 1 or manifests[0]["platform"] != {"architecture": "amd64", "os": "linux"}:
        raise ValueError("expected amd64 registry descriptor required")
    image = row["image_tag"].rsplit(":", 1)[0] + "@" + manifests[0]["digest"]
    name = "atmem-runtime-control-" + uuid4().hex
    runtime_command = command(image, name)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    plan = {"image": image, "instance_id": chosen["instance_id"], "command": runtime_command,
        "selection_sha256": digest(selection), "solver_calls": 0, "minimum_free_gib": 8,
        "max_pull_seconds": 180, "max_runtime_seconds": 30}
    with (args.output / "planned.json").open("x") as stream:
        json.dump(plan, stream, indent=2)
    print(json.dumps({"state": "pulling_one_pinned_image", "instance_id": chosen["instance_id"]}), flush=True)
    result = {"plan": plan, "runtime_qualified": False}
    try:
        result["pull"] = guarded_pull(image)
    except Exception as exc:
        result["pull"] = {"passed": False, "reason": "pull_control_error",
                          "error": type(exc).__name__ + ": " + str(exc)}
    if result["pull"]["passed"] and shutil.disk_usage("/private/tmp").free < 8 * 1024 ** 3:
        result["pull"].update(passed=False, reason="host_free_space_guard_after_pull")
    if result["pull"]["passed"]:
        print(json.dumps({"state": "running_constrained_interpreter_control"}), flush=True)
        try:
            run = subprocess.run(runtime_command, capture_output=True, timeout=30)
            output = run.stdout.decode(errors="replace")
            result["runtime"] = {"exit_code": run.returncode, "stdout_base64": base64.b64encode(run.stdout).decode(),
                "stderr_base64": base64.b64encode(run.stderr).decode(), "passed": run.returncode == 0 and
                bool(re.fullmatch(r"x86_64\nPYTHON 3\.\d+\.\d+ linux\n", output))}
            inspected = subprocess.run(["docker", "image", "inspect", image], capture_output=True, check=True, timeout=10)
            actual = json.loads(inspected.stdout)[0]
            result["actual_image"] = {key: actual[key] for key in ("Id", "Architecture", "Os", "Size")}
        except subprocess.TimeoutExpired:
            result["runtime"] = {"passed": False, "reason": "runtime_timeout"}
        except Exception as exc:
            result["runtime"] = {"passed": False, "reason": "runtime_control_error",
                                 "error": type(exc).__name__ + ": " + str(exc)}
        finally:
            # Sole exact target is this freshly generated, labeled container.
            try:
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
            except Exception as exc:
                result["cleanup_error"] = type(exc).__name__ + ": " + str(exc)
    result["host_free_bytes_after"] = shutil.disk_usage("/private/tmp").free
    result["assurance"] = "shell_and_isolated_stdlib_execution_only_not_task_environment_reference_or_model_qualification"
    with (args.output / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
    print(json.dumps({"pull_passed": result["pull"]["passed"], "runtime_control_passed": result.get("runtime", {}).get("passed", False),
        "task_environment_qualified": False, "solver_calls": 0}), flush=True)


if __name__ == "__main__":
    main()
