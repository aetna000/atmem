"""Public development tests only. No evaluator inputs or host filesystem mounts."""
import base64
from hashlib import sha1, sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from atmem_native_tree import write_new_tree
from benchmarks.code_replay.source_policy import checked_snapshot, file_byte_limit
from benchmarks.code_replay.source_capture import capture_stopped_workspace


FIELDS = {"format", "base_commit", "public_base_files_base64", "public_base_modes", "candidate_files_base64", "pytest"}
BASE = globals().get("PINNED_BASE", "456bacbbead4fa30a1a82892c9446ac9efb8055b")
SOURCE_SUBDIR = globals().get("PINNED_SOURCE_SUBDIR", "src")
IMAGE_EXTRAS = globals().get("PINNED_IMAGE_EXTRAS")
RUNTIME_EXCLUSIONS = globals().get("PINNED_RUNTIME_EXCLUSIONS", ())


def decode_files(values):
    if not isinstance(values, dict) or len(values) > 10000:
        raise ValueError("bounded regular public file map required")
    files, total = {}, 0
    for name, encoded in values.items():
        if not isinstance(encoded, str) or len(encoded) > 4 * ((file_byte_limit(name) + 2) // 3):
            raise ValueError("bounded public file encoding required")
        raw = base64.b64decode(encoded, validate=True)
        total += len(raw)
        if total > 40_000_000:
            raise ValueError("public file byte budget exceeded")
        files[name] = raw
    checked_snapshot(files)
    if any(".git" in PurePosixPath(name).parts for name in files):
        raise ValueError("Git metadata cannot enter public test source")
    return files


def pytest_arguments(value):
    if not isinstance(value, dict) or set(value) != {"paths", "keyword", "max_failures"}:
        raise ValueError("exact public pytest options required")
    paths = value["paths"]
    if not isinstance(paths, list) or not 1 <= len(paths) <= 8:
        raise ValueError("one to eight public test selectors required")
    for item in paths:
        if not isinstance(item, str) or not 1 <= len(item) <= 512:
            raise ValueError("bounded public test selector required")
        pieces = item.split("::")
        path = PurePosixPath(pieces[0])
        allowed = globals().get("PINNED_TEST_PATHS", ("tests",))
        in_tests = any(pieces[0] == root or (PurePosixPath(root).suffix != ".py"
                       and PurePosixPath(root) in path.parents) for root in allowed)
        if (str(path) != pieces[0] or path.is_absolute() or ".." in path.parts or "\\" in item
            or not path.parts or not in_tests
            or any(not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.\[\]-]*", node) for node in pieces[1:])):
            raise ValueError("test selector must stay under public tests")
    keyword, maximum = value["keyword"], value["max_failures"]
    if keyword is not None and (not isinstance(keyword, str) or not 1 <= len(keyword) <= 256 or "\0" in keyword):
        raise ValueError("bounded pytest keyword required")
    if type(maximum) is not int or not 0 <= maximum <= 10:
        raise ValueError("bounded pytest maximum failures required")
    args = ["-q", "-p", "no:cacheprovider", "--color=no", "--maxfail=" + str(maximum)]
    if keyword is not None:
        args += ["-k", keyword]
    return args + paths


def validate_request(payload):
    if not isinstance(payload, dict) or set(payload) != FIELDS or payload.get("format") != "atmem-public-pytest-request-v1" or payload.get("base_commit") != BASE:
        raise ValueError("exact public-only test request required")
    original, candidate = decode_files(payload["public_base_files_base64"]), decode_files(payload["candidate_files_base64"])
    modes = payload["public_base_modes"]
    if not isinstance(modes, dict) or set(modes) != set(original) or any(mode not in {"100644", "100755"} for mode in modes.values()):
        raise ValueError("public base executable modes required")
    return original, candidate, pytest_arguments(payload["pytest"])


def run_bounded(command, *, cwd, environment, seconds=120, byte_cap=4_000_000):
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, cwd=cwd, env=environment, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True)
        start, reason = time.monotonic(), None
        while process.poll() is None:
            if time.monotonic() - start >= seconds:
                reason = "public_test_timeout"
            elif os.fstat(log.fileno()).st_size > byte_cap:
                reason = "public_test_output_budget"
            if reason:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
                break
            time.sleep(.1)
        process.wait()
        size = os.fstat(log.fileno()).st_size
        if size > byte_cap and reason is None:
            reason = "public_test_output_budget"
        log.seek(0)
        raw = log.read(byte_cap)
        return {"exit_code": process.returncode, "reason": reason, "elapsed_s": time.monotonic() - start,
            "output_base64": base64.b64encode(raw).decode(), "output_bytes": size,
            "output_truncated": size > len(raw)}


def main():
    payload = json.load(sys.stdin)
    original, candidate, pytest_args = validate_request(payload)
    root = Path("/testbed")
    environment = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    listing = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r", "-z", BASE], env=environment)
    runtime_manifest = globals().get("PINNED_RUNTIME_MANIFEST")
    capture_kwargs = {}
    if runtime_manifest is not None:
        from benchmarks.code_replay.runtime_fixtures import tracked_projection, materialize_fixtures
        from benchmarks.code_replay.source_policy import SourcePolicy
        if globals().get("PINNED_RUNTIME_PROJECTION") != "v2":
            raise ValueError("explicit operator runtime projection required")
        runtime_policy = SourcePolicy(globals()["PINNED_SOURCE_ROOTS"], test_roots=globals()["PINNED_TEST_ROOTS"])
        projected, observed_fixtures, _ = tracked_projection(root, listing, runtime_policy, writers_stopped=True)
        if projected != original or observed_fixtures != runtime_manifest:
            raise ValueError("pinned public source/runtime union differs from image")
        if set(candidate) & set(runtime_manifest):
            raise ValueError("candidate overlaps immutable runtime fixture")
        capture_kwargs = {"runtime_manifest": runtime_manifest, "runtime_policy": runtime_policy}
    identities = {}
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, kind, identity = metadata.split()
        name = path.decode()
        if runtime_manifest is not None and name in runtime_manifest:
            item = runtime_manifest[name]
            if kind != b"blob" or mode.decode() != item["mode"] or identity.decode() != item["git_blob"]:
                raise ValueError("public runtime fixture Git identity differs")
            continue
        if kind != b"blob" or name not in original or mode.decode() != payload["public_base_modes"][name]:
            raise ValueError("image/public base membership differs")
        raw = original[name]
        if sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest().encode() != identity:
            raise ValueError("public input differs from image Git identity")
        identities[name] = identity.decode()
    if set(identities) != set(original):
        raise ValueError("public base has extra files")
    if any(name.startswith(prefix) or name == prefix[:-1] for name in original for prefix in RUNTIME_EXCLUSIONS):
        raise ValueError("runtime exclusion overlaps public base")
    image_files = capture_stopped_workspace(root, writers_stopped=True,
        excluded_runtime_roots=RUNTIME_EXCLUSIONS, **capture_kwargs)
    if any(image_files.get(name) != raw for name, raw in original.items()):
        raise ValueError("image source differs from public base")
    extras = image_files.keys() - original.keys()
    allowed_metadata = {"PKG-INFO", "SOURCES.txt", "dependency_links.txt", "not-zip-safe", "zip-safe", "requires.txt", "top_level.txt"}
    if IMAGE_EXTRAS is None:
        if any(not name.startswith("src/marshmallow.egg-info/") or PurePosixPath(name).name not in allowed_metadata for name in extras):
            raise ValueError("undeclared image-only repository artifact")
    elif set(IMAGE_EXTRAS) != extras or any(sha256(image_files[name]).hexdigest() != IMAGE_EXTRAS[name] for name in extras):
        raise ValueError("pinned image-only artifact bytes differ")
    if extras & candidate.keys():
        raise ValueError("candidate cannot replace image runtime metadata")
    git_dir = root / ".git"
    common = subprocess.check_output(["git", "-C", str(root), "rev-parse", "--git-common-dir"], env=environment, text=True).strip()
    if git_dir.is_symlink() or not git_dir.is_dir() or (root / common).resolve() != git_dir:
        raise ValueError("standalone disposable repository Git store required")
    if (git_dir / "objects/info/alternates").exists():
        raise ValueError("external Git object store prohibited")
    for path in (Path("/eval.sh"), Path("/gold.patch"), Path("/test.patch"), Path("/tests.json"), Path("/opt/atmem-evaluator")):
        if path.exists() or path.is_symlink():
            raise ValueError("evaluator artifact in public worker")
    # Exact task-owned container overlay target, never the host or image itself.
    # No repository script has run. Removing this verified object store prevents
    # development tests from traversing future target-repository Git objects.
    shutil.rmtree(git_dir)
    if git_dir.exists():
        raise ValueError("disposable Git store removal failed")
    workspace = Path("/work")
    workspace.mkdir(mode=0o700, exist_ok=False)
    write_new_tree(workspace, candidate)
    for name in candidate:
        (workspace / name).chmod(0o755 if payload["public_base_modes"].get(name) == "100755" else 0o644)
    if runtime_manifest is not None:
        materialize_fixtures(root, workspace, runtime_manifest, runtime_policy, writers_stopped=True)
    environment.update({"PATH": "/opt/miniconda3/envs/testbed/bin:/opt/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PYTHONPATH": str(workspace / SOURCE_SUBDIR), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTEST_ADDOPTS": "", "PY_COLORS": "0"})
    command = [sys.executable, "-m", "pytest", *pytest_args]
    observation = run_bounded(command, cwd=workspace, environment=environment)
    print(json.dumps({**observation, "public_source_files": len(candidate), "public_base_files": len(original),
        "candidate_sha256": sha256(json.dumps({name: sha256(raw).hexdigest() for name, raw in sorted(candidate.items())}, sort_keys=True).encode()).hexdigest(),
        "original_git_object_store_removed": True, "image_only_runtime_files": len(extras),
        "workspace": str(workspace), "command": command, "evaluator_material_received": False,
        "assurance": "isolated_public_development_test_signal_not_hidden_grade_or_model_result"}), flush=True)


if __name__ == "__main__":
    main()
