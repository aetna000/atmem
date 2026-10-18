"""Protected first-task parent/reference qualification; no solver interface."""
import argparse
import base64
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from uuid import uuid4

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.external_catalog import api, digest
from benchmarks.code_replay.external_qualify_worker import TASK_FILES, HARNESS_FILES


HARNESS_REVISION = "02e7a74ffd0b707aab73d203fe87bdc7c76afc8e"


def verified_blob(response, identity, size):
    if response.get("encoding") != "base64" or response.get("sha") != identity or not 0 < size <= 262144:
        raise ValueError("pinned bounded evaluator blob required")
    raw = base64.b64decode("".join(response["content"].split()), validate=True)
    if len(raw) != size or sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != identity:
        raise ValueError("evaluator Git blob bytes differ")
    return {"git_blob": identity, "sha256": sha256(raw).hexdigest(), "content_base64": base64.b64encode(raw).decode()}


def task_material(selected):
    tree = api("git/trees/" + selected["task_tree"])
    if tree.get("sha") != selected["task_tree"] or tree.get("truncated") is not False:
        raise ValueError("exact evaluator subtree required")
    entries = {entry["path"]: entry for entry in tree["tree"] if entry["path"] in TASK_FILES}
    if set(entries) != TASK_FILES:
        raise ValueError("missing pinned evaluator artifacts")
    result = {}
    for name, entry in entries.items():
        if entry["type"] != "blob" or entry["mode"] != "100644":
            raise ValueError("regular evaluator blobs required")
        result[name] = verified_blob(api("git/blobs/" + entry["sha"]), entry["sha"], entry["size"])
    return result


def harness_material():
    paths = {"constants.py": "swebench/harness/constants/__init__.py", "python.py": "swebench/harness/log_parsers/python.py",
             "grading.py": "swebench/harness/grading.py", "LICENSE": "LICENSE"}
    result = {}
    for name, path in paths.items():
        observed = subprocess.run(["gh", "api", "repos/SWE-bench/SWE-bench/contents/" + path + "?ref=" + HARNESS_REVISION],
                                  capture_output=True, check=True, timeout=30)
        response = json.loads(observed.stdout)
        result[name] = verified_blob(response, response["sha"], response["size"])
    assert set(result) == HARNESS_FILES
    return result


def worker_command(image, name, source):
    if not re.fullmatch(r"swebench/sweb\.eval\.x86_64\.[A-Za-z0-9_.-]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("immutable evaluator image required")
    if not re.fullmatch(r"atmem-reference-control-[0-9a-f]{32}", name):
        raise ValueError("unique evaluator container name required")
    return ["docker", "run", "--rm", "--pull=never", "--platform", "linux/amd64", "-i", "--name", name,
        "--label", "atmem.benchmark=external-reference-control-v1", "--network", "none", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--memory", "1g", "--cpus", "1", "--pids-limit", "128",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m", "--entrypoint", "/opt/miniconda3/envs/testbed/bin/python",
        image, "-I", "-S", "-c", source]


def execute_worker(command, payload, name):
    if shutil.disk_usage("/private/tmp").free < 8 * 1024 ** 3:
        return {"started": False, "reason": "host_free_space_below_8GiB"}
    with tempfile.TemporaryFile() as input_file, tempfile.TemporaryFile() as output:
        input_file.write(json.dumps(payload).encode()); input_file.seek(0)
        process = subprocess.Popen(command, stdin=input_file, stdout=output, stderr=subprocess.STDOUT)
        start, reason, cleanup_error = time.monotonic(), None, None
        try:
            while process.poll() is None:
                if time.monotonic() - start > 180: reason = "controller_timeout"
                elif output.tell() > 8_000_000: reason = "output_budget"
                elif shutil.disk_usage("/private/tmp").free < 8 * 1024 ** 3: reason = "host_space_guard"
                if reason:
                    process.terminate()
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=5)
                    break
                time.sleep(.25)
        finally:
            try:
                cleanup = subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
                if cleanup.returncode:
                    # --rm may already have removed a normally exited worker.
                    # A failed rm alone cannot distinguish that from a daemon error.
                    remaining = subprocess.run(["docker", "ps", "-a", "--filter", "name=^/" + name + "$",
                        "--format", "{{.Names}}"], capture_output=True, timeout=10)
                    if remaining.returncode or remaining.stdout.strip():
                        cleanup_error = "container_cleanup_nonzero"
            except (OSError, subprocess.TimeoutExpired) as exc:
                cleanup_error = type(exc).__name__
        process.wait()
        output_size = output.tell()
        if output_size > 8_000_000 and reason is None:
            reason = "output_budget"
        if cleanup_error is not None and reason is None:
            reason = "container_cleanup_failed"
        output.seek(0)
        raw = output.read(8_000_000)
        result = {"started": True, "reason": reason, "exit_code": process.returncode,
                  "elapsed_s": time.monotonic() - start, "raw_output_base64": base64.b64encode(raw).decode(),
                  "output_bytes": output_size, "raw_output_truncated": output_size > len(raw),
                  "cleanup_error": cleanup_error}
        if not reason and process.returncode == 0:
            try: result["worker"] = json.loads(raw)
            except ValueError: result["reason"] = "worker_protocol_invalid"
        return result


def qualifies(parent, reference):
    a, b = parent.get("worker", {}).get("grading", {}), reference.get("worker", {}).get("grading", {})
    return bool(not parent.get("reason") and not reference.get("reason")
                and not parent.get("worker", {}).get("worker_failure")
                and not reference.get("worker", {}).get("worker_failure")
                and parent.get("exit_code") == reference.get("exit_code") == 0 and a.get("results_found") and b.get("results_found")
                and a.get("expected_f2p", 0) > 0 and a.get("observed_f2p_failures", 0) > 0
                and b.get("resolution") == "RESOLVED_FULL")


def resource_resume_allowed(events):
    attempts = [event["envelope"]["payload"] for event in events
                if event["envelope"]["event_type"] == "external.reference_attempt"]
    return (len(attempts) == 2 and {row.get("phase") for row in attempts} == {"parent", "reference"}
            and all(row.get("started") is False and row.get("reason") == "host_free_space_below_8GiB"
                    and not row.get("worker") for row in attempts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("preflight", "runtime-proof", "state-root", "evidence-root"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--resource-resume-v2", action="store_true",
                        help="New recorded same-task control after v1's two zero-execution space stops only")
    args = parser.parse_args()
    if Path("/Volumes") in args.state_root.resolve().parents:
        raise ValueError("private evaluator material cannot be staged on MEM/RAM public volumes")
    args.state_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    run_id = "external-reference-control-v2-20261017" if args.resource_resume_v2 else "external-reference-control-v1-20261017"
    if vault.inspect(principal, run_id): raise ValueError("qualification already retained; no retry")
    if args.resource_resume_v2 and not resource_resume_allowed(vault.inspect(principal, "external-reference-control-v1-20261017")):
        raise ValueError("v2 requires both retained v1 workers never started because of host space")
    selection = json.loads((args.preflight / "selection.json").read_bytes())
    metadata = json.loads((args.preflight / "metadata.json").read_bytes())
    runtime = json.loads((args.runtime_proof / "result.json").read_bytes())
    if (metadata["selection_sha256"] != digest(selection) or not runtime.get("runtime", {}).get("passed")
        or runtime["plan"]["selection_sha256"] != digest(selection)
        or runtime["actual_image"]["Id"] != runtime["plan"]["image"].split("@")[-1]
        or runtime["actual_image"]["Architecture"] != "amd64"):
        raise ValueError("metadata/runtime qualification binding absent")
    selected, task = selection["selected"][0], metadata["reports"][0]
    if selected["instance_id"] != "marshmallow-code__marshmallow-1229" or task["instance_id"] != selected["instance_id"] or runtime["plan"]["instance_id"] != selected["instance_id"]:
        raise ValueError("first fixed task required")
    source = Path(__file__).with_name("external_qualify_worker.py").read_text()
    plan = {"instance_id": selected["instance_id"], "image": runtime["plan"]["image"],
        "selection_sha256": digest(selection), "harness_revision": HARNESS_REVISION,
        "source_sha256": {name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                          for name in ("external_qualification.py", "external_qualify_worker.py")},
        "policy_text": Path("specs/042-atmem-code/external-reference-control-v2.md" if args.resource_resume_v2
                            else "specs/042-atmem-code/external-reference-control-v1.md").read_text(),
        "prior_run": "external-reference-control-v1-20261017" if args.resource_resume_v2 else None,
        "solver_calls": 0}
    vault.capture(run_id=run_id, kind="external.reference_planned", principal=principal, payload=plan)
    results = {}
    try:
        material = {"instance_id": selected["instance_id"], "base_commit": task["metadata"]["base_commit"],
                    "task_files": task_material(selected), "harness_files": harness_material()}
        from benchmarks.code_replay.external_qualify_worker import validated_files
        validated_files({**material, "phase": "parent"})
        vault.capture(run_id=run_id, kind="external.private_material", principal=principal,
                      payload={**material, "worker_source_base64": base64.b64encode(source.encode()).decode()})
        for phase in ("parent", "reference"):
            name = "atmem-reference-control-" + uuid4().hex
            command = worker_command(plan["image"], name, source)
            vault.capture(run_id=run_id, kind="external.reference_dispatch", principal=principal,
                          payload={"phase": phase, "command": command, "material_sha256": digest(material)})
            result = execute_worker(command, {**material, "phase": phase}, name)
            results[phase] = result
            vault.capture(run_id=run_id, kind="external.reference_attempt", principal=principal, payload={"phase": phase, **result})
            print(json.dumps({"phase": phase, "controller_exit_code": result.get("exit_code"),
                "reason": result.get("reason"), "grading": result.get("worker", {}).get("grading")}), flush=True)
        summary = {"qualified": qualifies(results["parent"], results["reference"]), "solver_calls": 0,
                   "instance_id": selected["instance_id"], "scope": "first_task_parent_reference_control_only"}
        vault.capture(run_id=run_id, kind="external.reference_completed", principal=principal, payload=summary)
        with (args.state_root / "summary.json").open("x") as stream: json.dump(summary, stream, indent=2)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        vault.capture(run_id=run_id, kind="external.reference_failed", principal=principal,
                      payload={"exception_type": type(exc).__name__, "failure": str(exc), "completed_phases": sorted(results), "solver_calls": 0})
        raise


if __name__ == "__main__":
    main()
