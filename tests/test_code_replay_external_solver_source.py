import base64
from hashlib import sha1, sha256
import json

import pytest

from benchmarks.code_replay.external_solver_source import tracked_solver_snapshot


def fixture():
    raw = b"public base bytes\n"
    blob = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    files = {"src/public.py": base64.b64encode(raw).decode(),
             "tests/not-in-public-tree.py": base64.b64encode(b"must not escape").decode()}
    baseline = {"files": 1, "bytes": len(raw), "tree_fingerprint_sha256": sha256(json.dumps({"src/public.py": blob}, sort_keys=True).encode()).hexdigest()}
    commit = {"sha": "a" * 40, "tree": {"sha": "b" * 40}}
    tree = {"sha": "b" * 40, "truncated": False, "tree": [
        {"path": "src", "type": "tree", "mode": "040000", "sha": "c" * 40},
        {"path": "src/public.py", "type": "blob", "mode": "100755", "size": len(raw), "sha": blob}]}
    return files, baseline, commit, tree, "a" * 40


def test_only_tracked_public_blobs_escape_with_modes():
    result = tracked_solver_snapshot(*fixture())
    assert result["files"] == {"src/public.py": b"public base bytes\n"}
    assert result["modes"] == {"src/public.py": "100755"}
    assert result["untracked_files_exported"] == 0
    assert result["git_history_exported"] is False


@pytest.mark.parametrize("change", ["truncated", "wrong_commit", "wrong_tree", "symlink", "missing", "modified", "wrong_fingerprint", "duplicate", "escape"])
def test_private_extra_bytes_never_rescue_invalid_public_identity(change):
    args = list(fixture())
    files, baseline, commit, tree, expected = args
    if change == "truncated":
        tree["truncated"] = True
    elif change == "wrong_commit":
        commit["sha"] = "d" * 40
    elif change == "wrong_tree":
        tree["sha"] = "d" * 40
    elif change == "symlink":
        tree["tree"][1]["mode"] = "120000"
    elif change == "missing":
        del files["src/public.py"]
    elif change == "modified":
        files["src/public.py"] = base64.b64encode(b"tampered").decode()
    elif change == "wrong_fingerprint":
        baseline["tree_fingerprint_sha256"] = "0" * 64
    elif change == "duplicate":
        tree["tree"].append(tree["tree"][1])
    else:
        tree["tree"][1]["path"] = "../outside.py"
    with pytest.raises(ValueError):
        tracked_solver_snapshot(*args)


def projected_fixture(root):
    from benchmarks.code_replay.runtime_fixtures import tracked_projection
    from tests.test_code_replay_runtime_fixtures import POLICY, fixture as runtime_fixture
    listing = runtime_fixture(root)
    source, manifest, baseline = tracked_projection(root, listing, POLICY, writers_stopped=True)
    entries = []
    for row in listing.split(b"\0"):
        if not row:
            continue
        header, name = row.split(b"\t", 1)
        mode, kind, identity = header.decode().split()
        name = name.decode()
        size = manifest[name]["bytes"] if name in manifest else len(source[name])
        entries.append({"path": name, "type": kind, "mode": mode, "sha": identity, "size": size})
    original = {name: base64.b64encode(raw).decode() for name, raw in source.items()}
    return (original, baseline, {"sha": "a" * 40, "tree": {"sha": "b" * 40}},
            {"sha": "b" * 40, "truncated": False, "tree": entries}, "a" * 40), manifest, POLICY


def test_projected_export_verifies_full_public_union_but_exports_only_source(tmp_path):
    args, manifest, policy = projected_fixture(tmp_path)
    result = tracked_solver_snapshot(*args, runtime_manifest=manifest, runtime_policy=policy)
    assert set(result["files"]) == {"package/code.py"}
    assert result["runtime_projection"] == "v2"
    assert result["runtime_manifest"] == manifest
    assert result["omitted_runtime_files"] == 2
    with pytest.raises(ValueError):
        tracked_solver_snapshot(*args)


@pytest.mark.parametrize("change", ["missing_runtime", "runtime_identity", "overlap", "runtime_hash"])
def test_projected_export_refuses_missing_tampered_or_overlapping_runtime(tmp_path, change):
    args, manifest, policy = projected_fixture(tmp_path)
    original, baseline, commit, tree, expected = args
    if change == "missing_runtime":
        tree["tree"] = [entry for entry in tree["tree"] if entry["path"] != "tests/link.py"]
    elif change == "runtime_identity":
        next(entry for entry in tree["tree"] if entry["path"] == "tests/link.py")["sha"] = "0" * 40
    elif change == "overlap":
        original["tests/link.py"] = base64.b64encode(b"../package/code.py").decode()
    else:
        baseline["runtime_manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        tracked_solver_snapshot(*args, runtime_manifest=manifest, runtime_policy=policy)
