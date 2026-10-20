"""Public tests of an explicitly submitted patch, never a live-worktree claim."""
import base64
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import atmem_public_validation as public
from benchmarks.code_replay.source_policy import SourcePolicy, path_name
from benchmarks.code_replay.source_capture import capture_stopped_workspace


FIELDS = {"format", "base_commit", "public_base_files_base64", "public_base_modes", "patch", "pytest"}


def validate_request(payload):
    if (not isinstance(payload, dict) or set(payload) != FIELDS
        or payload.get("format") != "atmem-public-patch-tests-v1"):
        raise ValueError("exact public patch request required")
    patch = payload["patch"]
    if not isinstance(patch, str) or len(patch.encode()) > 262144 or "\0" in patch:
        raise ValueError("bounded UTF-8 text patch required")
    original, _, _ = public.validate_request({key: value for key, value in {
        **payload, "format": "atmem-public-pytest-request-v1", "candidate_files_base64": payload["public_base_files_base64"]}.items()
        if key != "patch"})
    return original


def patch_paths(raw):
    paths = []
    policy = SourcePolicy(globals().get("PINNED_SOURCE_ROOTS", ("src/marshmallow/",)),
        test_roots=globals().get("PINNED_TEST_ROOTS", ("tests/",)))
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        pieces = entry.split(b"\t", 2)
        if len(pieces) != 3 or not pieces[0].isdigit() or not pieces[1].isdigit():
            raise ValueError("regular text patch statistics required")
        name = path_name(pieces[2].decode())
        if ".git" in Path(name).parts or not (policy.source(name) or policy.test(name)):
            raise ValueError("public patch must stay in implementation or tests")
        paths.append(name)
    if not 1 <= len(paths) <= 128:
        raise ValueError("one to 128 patch paths required")
    return paths


def main():
    payload = json.load(sys.stdin)
    original = validate_request(payload)
    patch = payload["patch"].encode()
    environment = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    workspace = Path("/public-patch")
    workspace.mkdir(mode=0o700, exist_ok=False)
    public.write_new_tree(workspace, original)
    if patch.strip():
        # Reject copy/rename/binary/symlink/submodule metadata before Git writes.
        lines = payload["patch"].splitlines()
        if any(line.startswith(("rename from ", "rename to ", "copy from ", "copy to ", "GIT binary patch", "Binary files "))
            or (line.startswith(("new file mode ", "deleted file mode ", "old mode ", "new mode "))
                and line.rsplit(" ", 1)[-1] not in {"100644", "100755"}) for line in lines):
            raise ValueError("only regular text-file patches supported")
        stats = subprocess.run(["git", "-C", str(workspace), "apply", "--numstat", "-z", "-"],
            input=patch, capture_output=True, env=environment, timeout=10)
        if stats.returncode:
            raise ValueError("public patch cannot be parsed")
        patch_paths(stats.stdout)
        applied = subprocess.run(["git", "-C", str(workspace), "apply", "--whitespace=nowarn", "-"],
            input=patch, capture_output=True, env=environment, timeout=10)
        if applied.returncode:
            raise ValueError("public patch does not apply to base")
    # Only Git has written this private, disposable copy, and Git has exited.
    # No claim that the independently editable agent workspace was frozen.
    candidate = capture_stopped_workspace(workspace, writers_stopped=True)
    request = {key: value for key, value in {**payload, "format": "atmem-public-pytest-request-v1",
        "candidate_files_base64": {name: base64.b64encode(raw).decode() for name, raw in candidate.items()}}.items() if key != "patch"}
    original_stdin = sys.stdin
    captured = io.StringIO()
    from contextlib import redirect_stdout
    try:
        sys.stdin = io.StringIO(json.dumps(request))
        with redirect_stdout(captured):
            public.main()
    finally:
        sys.stdin = original_stdin
    result = json.loads(captured.getvalue())
    result.update(patch_sha256=sha256(patch).hexdigest(), tested_candidate_files_base64=request["candidate_files_base64"],
        assurance="public_tests_of_supplied_patch_not_current_agent_worktree_or_hidden_grading")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
