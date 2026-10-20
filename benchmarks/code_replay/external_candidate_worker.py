"""Evaluator-only source assembly; bootstrap supplies pinned operator modules."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import atmem_external_control as control
from benchmarks.code_replay.source_policy import SourcePolicy, checked_snapshot, collect_source_patch, governed_solution
from benchmarks.code_replay.source_capture import capture_stopped_workspace


def install_tree(root, current, assembled, *, excluded_runtime_roots=(),
                 runtime_manifest=None, runtime_policy=None):
    checked_snapshot(current)
    checked_snapshot(assembled)
    # Root is private, disposable /testbed, with all writers stopped. Every
    # captured entry was regular and descriptor-checked; no solver runs here.
    for name in sorted(current.keys() - assembled.keys()):
        (root / name).unlink()
    for name, raw in assembled.items():
        if current.get(name) == raw:
            continue
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    if capture_stopped_workspace(root, writers_stopped=True, excluded_runtime_roots=excluded_runtime_roots,
        runtime_manifest=runtime_manifest, runtime_policy=runtime_policy) != assembled:
        raise ValueError("assembled grader bytes differ")


def source_digest(files):
    return sha256(json.dumps({name: sha256(raw).hexdigest() for name, raw in sorted(files.items())}, sort_keys=True).encode()).hexdigest()


def main():
    payload = json.load(sys.stdin)
    phase = payload.get("source_boundary_phase")
    if phase not in {"unchanged", "reference_as_proposal"}:
        raise ValueError("fixed evaluator diagnostic phase required; no solver endpoint")
    profile = payload.get("task_profile")
    if profile not in {None, "selected-six-v1", "selected-six-v2", "registered-eligibility-v2"}:
        raise ValueError("fixed operator task profile required")
    parser_name = None
    runtime_exclusions = ()
    if profile:
        _, parser_name = control.task_binding(payload["instance_id"], payload["base_commit"])
        source_roots, test_roots = control.task_source_roots(payload["instance_id"], payload["base_commit"])
        if profile in {"selected-six-v2", "registered-eligibility-v2"}:
            runtime_exclusions = control.task_runtime_exclusions(payload["instance_id"], payload["base_commit"])
        files = control.validated_files({**payload, "phase": "parent"}, task_identity=payload["instance_id"])
    else:
        source_roots, test_roots = ("src/marshmallow/",), ("tests/",)
        files = control.validated_files({**payload, "phase": "parent"})
    baseline = control.tracked_base(payload["base_commit"])
    projection_version = globals().get("PINNED_RUNTIME_PROJECTION")
    if projection_version not in (None, "v2"):
        raise ValueError("unknown operator runtime projection version")
    runtime_manifest = None
    if projection_version:
        if baseline.get("format") != "atmem-source-runtime-projection-v2":
            raise ValueError("bound control did not verify source/runtime projection")
        runtime_manifest = control.RUNTIME_MANIFEST
    root, directory = Path("/testbed"), Path("/opt/atmem-evaluator")
    directory.mkdir(mode=0o700, exist_ok=False)
    for name, raw in files["task_files"].items():
        (directory / name).write_bytes(raw)
    expected = json.loads(files["task_files"]["tests.json"])
    policy = SourcePolicy(source_roots, test_roots=test_roots)
    capture_kwargs = {"runtime_manifest": runtime_manifest,
        "runtime_policy": policy if runtime_manifest is not None else None}
    if runtime_exclusions:
        tracked = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r", "-z", "--name-only", payload["base_commit"]])
        if any(name.decode().startswith(excluded) or name.decode() == excluded[:-1]
               for name in tracked.split(b"\0") if name for excluded in runtime_exclusions):
            raise ValueError("runtime exclusion overlaps tracked repository source")
    original = capture_stopped_workspace(root, writers_stopped=True,
        excluded_runtime_roots=runtime_exclusions, **capture_kwargs)
    if not any(policy.source(name) for name in original):
        raise ValueError("predeclared source policy has no implementation coverage")
    if phase == "reference_as_proposal":
        applied = subprocess.run(["git", "-C", str(root), "apply", "--whitespace=nowarn", str(directory / "gold.patch")], capture_output=True)
        if applied.returncode:
            raise ValueError("verified reference patch did not apply")
    candidate = capture_stopped_workspace(root, writers_stopped=True,
        excluded_runtime_roots=runtime_exclusions, **capture_kwargs)
    proposal = collect_source_patch(original, candidate, policy)
    assembled = governed_solution(original, proposal, policy)
    install_tree(root, candidate, assembled, excluded_runtime_roots=runtime_exclusions, **capture_kwargs)
    environment = dict(control.os.environ)
    environment["PATH"] = "/opt/miniconda3/envs/testbed/bin:/opt/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    exit_code, stdout, stderr, failure = control.execute_script(directory / "eval.sh", environment)
    result = {"phase": phase, "script_exit_code": exit_code, "worker_failure": failure,
        "tracked_base": baseline, "base_source_verified": True,
        "original_sha256": source_digest(original), "candidate_sha256": source_digest(candidate),
        "assembled_sha256": source_digest(assembled), "assembled_bytes_verified": True,
        "source_policy": {"source_roots": list(policy.source_roots), "test_roots": list(policy.test_roots)},
        "excluded_runtime_roots": list(runtime_exclusions),
        "changed_paths": proposal["changed_paths"], "ignored_test_changes": proposal["ignored_test_changes"],
        "out_of_scope_changes": proposal["out_of_scope_changes"],
        "candidate_files_base64": {name: base64.b64encode(raw).decode() for name, raw in candidate.items()},
        "original_files_base64": {name: base64.b64encode(raw).decode() for name, raw in original.items()},
        "original_files_sha256": {name: sha256(raw).hexdigest() for name, raw in original.items()},
        "stdout_base64": base64.b64encode(stdout).decode(), "stderr_base64": base64.b64encode(stderr).decode(),
        "assurance": "evaluator_reference_through_snapshot_boundary_not_model_performance"}
    if runtime_manifest is not None:
        result["runtime_projection"] = "v2"
        result["runtime_manifest"] = runtime_manifest
        result["runtime_fixtures_verified"] = True
    try:
        if parser_name:
            result["grading"] = control.grade(stdout + stderr, expected, files["harness_files"], directory, parser_name=parser_name)
        else:
            result["grading"] = control.grade(stdout + stderr, expected, files["harness_files"], directory)
    except Exception as exc:
        result["grading"] = {}
        result["grading_error"] = type(exc).__name__
        result["worker_failure"] = result["worker_failure"] or "upstream_grading_error"
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
