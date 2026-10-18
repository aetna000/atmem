"""Private evaluator: bounded public proposals, frozen tests, upstream grading.

Never expose this endpoint, its inputs or its outputs as a solver tool. It is
specific to the first qualified task, not a multi-repository qualification.
"""
import base64
from hashlib import sha1
import json
from pathlib import Path
import subprocess
import sys

import atmem_external_control as control
import atmem_external_boundary as boundary
import atmem_public_validation as public
from benchmarks.code_replay.source_policy import SourcePolicy, governed_public_proposal
from benchmarks.code_replay.source_capture import capture_stopped_workspace


PROPOSAL_FIELDS = {"format", "base_commit", "public_base_files_base64", "public_base_modes", "candidate_files_base64"}


def validate_request(payload):
    if (not isinstance(payload, dict) or set(payload) != {"format", "material", "proposal"}
        or payload.get("format") != "atmem-private-proposal-evaluation-v1"):
        raise ValueError("exact private proposal envelope required")
    proposal, material = payload["proposal"], payload["material"]
    if (not isinstance(proposal, dict) or set(proposal) != PROPOSAL_FIELDS
        or proposal.get("format") != "atmem-public-source-proposal-v1" or not isinstance(material, dict)
        or proposal.get("base_commit") != material.get("base_commit")):
        raise ValueError("bound public source proposal required")
    # Reuse bounded file/path/mode decoding. No caller-supplied pytest options
    # or private data are admitted through the public proposal role.
    original, candidate, _ = public.validate_request({**proposal,
        "format": "atmem-public-pytest-request-v1",
        "pytest": {"paths": ["tests"], "keyword": None, "max_failures": 0}})
    return material, proposal, original, candidate


def verify_public_base(root, base, original, modes, *, runtime_manifest=None, runtime_policy=None):
    fixtures = {}
    if runtime_manifest is not None:
        from benchmarks.code_replay.runtime_fixtures import validate_manifest
        if runtime_policy is None:
            raise ValueError("operator runtime policy required")
        fixtures = validate_manifest(runtime_manifest, runtime_policy)
    listing = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r", "-z", base])
    names = set()
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, kind, identity = metadata.split()
        name = path.decode()
        if name in fixtures:
            item = fixtures[name]
            if (name in original or kind != b"blob" or mode.decode() != item["mode"]
                or identity.decode() != item["git_blob"]):
                raise ValueError("public/runtime base membership or identity differs")
            names.add(name)
            continue
        if kind != b"blob" or name not in original or modes[name] != mode.decode():
            raise ValueError("public base membership or mode differs")
        raw = original[name]
        if sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest().encode() != identity:
            raise ValueError("public base Git identity differs")
        names.add(name)
    if names != set(original) | set(fixtures):
        raise ValueError("public base contains extra files")


def main():
    material, request, public_original, candidate = validate_request(json.load(sys.stdin))
    selected_task = globals().get("PINNED_TASK_ID")
    runtime_exclusions = globals().get("PINNED_RUNTIME_EXCLUSIONS", ())
    parser_name = None
    if selected_task:
        if material.get("instance_id") != selected_task:
            raise ValueError("material differs from operator task identity")
        _, parser_name = control.task_binding(selected_task, material["base_commit"])
        files = control.validated_files({**material, "phase": "parent"}, task_identity=selected_task)
    else:
        files = control.validated_files({**material, "phase": "parent"})
    baseline = control.tracked_base(material["base_commit"])
    root, directory = Path("/testbed"), Path("/opt/atmem-evaluator")
    policy = SourcePolicy(globals().get("PINNED_SOURCE_ROOTS", ("src/marshmallow/",)),
        test_roots=globals().get("PINNED_TEST_ROOTS", ("tests/",)))
    runtime_manifest = globals().get("PINNED_RUNTIME_MANIFEST")
    if runtime_manifest is not None:
        if (globals().get("PINNED_RUNTIME_PROJECTION") != "v2"
            or baseline.get("format") != "atmem-source-runtime-projection-v2"
            or control.RUNTIME_MANIFEST != runtime_manifest):
            raise ValueError("operator runtime fixtures differ from pinned image")
        if set(candidate) & set(runtime_manifest):
            raise ValueError("candidate overlaps immutable runtime fixture")
    elif baseline.get("format") == "atmem-source-runtime-projection-v2":
        raise ValueError("source/runtime projection requires explicit operator manifest")
    capture_kwargs = ({"runtime_manifest": runtime_manifest, "runtime_policy": policy}
                      if runtime_manifest is not None else {})
    verify_public_base(root, material["base_commit"], public_original, request["public_base_modes"], **capture_kwargs)
    if any(name.startswith(prefix) or name == prefix[:-1] for name in public_original for prefix in runtime_exclusions):
        raise ValueError("runtime exclusion overlaps public repository source")
    original = capture_stopped_workspace(root, writers_stopped=True,
        excluded_runtime_roots=runtime_exclusions, **capture_kwargs)
    assembled, proposal = governed_public_proposal(original, public_original, candidate, policy)
    protected = original.keys() - public_original.keys()
    if any(assembled.get(name) != original[name] for name in protected):
        raise ValueError("image-only runtime bytes changed")
    boundary.install_tree(root, original, assembled, excluded_runtime_roots=runtime_exclusions, **capture_kwargs)
    # The reference patch is not needed to evaluate a solver proposal. Keep it
    # out of the evaluator filesystem rather than write an unused gold artifact.
    directory.mkdir(mode=0o700, exist_ok=False)
    for name in ("eval.sh", "test.patch", "tests.json"):
        (directory / name).write_bytes(files["task_files"][name])
    expected = json.loads(files["task_files"]["tests.json"])
    environment = dict(control.os.environ)
    environment.update({"PATH": "/opt/miniconda3/envs/testbed/bin:/opt/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1"})
    exit_code, stdout, stderr, failure = control.execute_script(directory / "eval.sh", environment)
    result = {"phase": "solver_proposal", "script_exit_code": exit_code, "worker_failure": failure,
        "tracked_base": baseline, "base_source_verified": True, "public_base_verified": True,
        "original_sha256": boundary.source_digest(original), "candidate_sha256": boundary.source_digest(candidate),
        "assembled_sha256": boundary.source_digest(assembled), "assembled_bytes_verified": True,
        "image_only_bytes_preserved": True, "gold_patch_written": False,
        "source_policy": {"source_roots": list(policy.source_roots), "test_roots": list(policy.test_roots)},
        "changed_paths": proposal["changed_paths"], "ignored_test_changes": proposal["ignored_test_changes"],
        "out_of_scope_changes": proposal["out_of_scope_changes"],
        "public_candidate_files_base64": request["candidate_files_base64"],
        "assembled_files_base64": {name: base64.b64encode(raw).decode() for name, raw in assembled.items()},
        "stdout_base64": base64.b64encode(stdout).decode(), "stderr_base64": base64.b64encode(stderr).decode(),
        "assurance": "private_upstream_grading_of_public_proposal_not_model_origin_proof"}
    if runtime_manifest is not None:
        result.update(runtime_projection="v2", runtime_fixtures_verified=True)
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
