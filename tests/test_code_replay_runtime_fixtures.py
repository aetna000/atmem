from hashlib import sha1
import os
from pathlib import Path
import stat

import pytest

from benchmarks.code_replay.runtime_fixtures import (
    MAX_ASSET, tracked_projection, validate_manifest, materialize_fixtures,
)
from benchmarks.code_replay.source_capture import capture_stopped_workspace
from benchmarks.code_replay.source_policy import SourcePolicy


POLICY = SourcePolicy(("package/",), test_roots=("tests/",))


def listing(root, paths):
    rows = []
    for name in paths:
        path = root / name
        raw = os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
        mode = "120000" if path.is_symlink() else "100755" if path.stat().st_mode & 0o111 else "100644"
        blob = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        rows.append(mode.encode() + b" blob " + blob.encode() + b"\t" + name.encode() + b"\0")
    return b"".join(rows)


def fixture(tmp_path):
    (tmp_path / "package").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "doc").mkdir()
    (tmp_path / "package/code.py").write_bytes(b"x = 1\n")
    # Transport/source fixtures, not conversation training data.
    (tmp_path / "doc/large.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 4_100_000)
    (tmp_path / "tests/link.py").symlink_to("../package/code.py")
    paths = ["package/code.py", "doc/large.png", "tests/link.py"]
    tree = listing(tmp_path, paths)
    return tree


def test_source_and_opaque_runtime_are_disjoint_complete_and_reverified(tmp_path):
    tree = fixture(tmp_path)
    source, manifest, summary = tracked_projection(tmp_path, tree, POLICY, writers_stopped=True)
    assert source == {"package/code.py": b"x = 1\n"}
    assert set(manifest) == {"doc/large.png", "tests/link.py"}
    assert summary["files"] == summary["source_files"] + summary["runtime_files"] == 3
    assert summary["source_bytes"] == len(b"x = 1\n")
    assert capture_stopped_workspace(tmp_path, writers_stopped=True,
        runtime_manifest=manifest, runtime_policy=POLICY) == source
    # Existing default refuses these fixtures rather than silently adopting v2.
    with pytest.raises(ValueError):
        capture_stopped_workspace(tmp_path, writers_stopped=True)


@pytest.mark.parametrize("change", ["asset", "link", "remove", "asset_to_link", "mode"])
def test_immutable_fixture_tampering_fails_before_source_capture(tmp_path, change):
    tree = fixture(tmp_path)
    _, manifest, _ = tracked_projection(tmp_path, tree, POLICY, writers_stopped=True)
    if change == "asset":
        with (tmp_path / "doc/large.png").open("r+b") as stream:
            stream.seek(100)
            stream.write(b"y")
    elif change == "link":
        (tmp_path / "tests/link.py").unlink()
        (tmp_path / "tests/link.py").symlink_to("../package/other.py")
    elif change == "remove":
        (tmp_path / "tests/link.py").unlink()
    elif change == "mode":
        (tmp_path / "doc/large.png").chmod(0o755)
    else:
        (tmp_path / "doc/large.png").unlink()
        (tmp_path / "doc/large.png").symlink_to("../package/code.py")
    with pytest.raises(ValueError):
        capture_stopped_workspace(tmp_path, writers_stopped=True,
            runtime_manifest=manifest, runtime_policy=POLICY)


@pytest.mark.parametrize("target", ["/etc/passwd", "../../outside", "../.git/config", ".."])
def test_escaping_or_git_fixture_links_rejected(tmp_path, target):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/link.py").symlink_to(target)
    with pytest.raises(ValueError):
        tracked_projection(tmp_path, listing(tmp_path, ["tests/link.py"]), POLICY, writers_stopped=True)


def test_implementation_links_and_unknown_special_members_rejected(tmp_path):
    (tmp_path / "package").mkdir()
    (tmp_path / "package/code.py").symlink_to("other.py")
    with pytest.raises(ValueError):
        tracked_projection(tmp_path, listing(tmp_path, ["package/code.py"]), POLICY, writers_stopped=True)
    with pytest.raises(ValueError):
        tracked_projection(tmp_path, b"160000 commit " + b"a" * 40 + b"\tdependency\0",
                           POLICY, writers_stopped=True)


def test_parent_symlinks_never_followed(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "real/code.py").write_bytes(b"pass\n")
    (tmp_path / "package").symlink_to("real", target_is_directory=True)
    with pytest.raises(OSError):
        tracked_projection(tmp_path, listing(tmp_path, ["package/code.py"]), POLICY, writers_stopped=True)


def test_blob_mismatch_duplicate_and_source_budget_rejected(tmp_path):
    (tmp_path / "package").mkdir()
    path = tmp_path / "package/code.py"
    path.write_bytes(b"pass\n")
    tree = listing(tmp_path, ["package/code.py"])
    with pytest.raises(ValueError):
        tracked_projection(tmp_path, tree + tree, POLICY, writers_stopped=True)
    path.write_bytes(b"different\n")
    with pytest.raises(ValueError):
        tracked_projection(tmp_path, tree, POLICY, writers_stopped=True)
    path.write_bytes(b"x" * 1_000_001)
    with pytest.raises(ValueError):
        tracked_projection(tmp_path, listing(tmp_path, ["package/code.py"]), POLICY, writers_stopped=True)


def test_false_asset_suffix_and_asset_budget_do_not_hide_source(tmp_path):
    (tmp_path / "doc").mkdir()
    path = tmp_path / "doc/file.png"
    path.write_bytes(b"not an image")
    with pytest.raises(ValueError):
        tracked_projection(tmp_path, listing(tmp_path, ["doc/file.png"]), POLICY, writers_stopped=True)
    with path.open("wb") as stream:
        stream.write(b"\x89PNG\r\n\x1a\n")
        stream.truncate(MAX_ASSET + 1)
    # Size guard precedes reading or allocating the oversized member.
    tree = b"100644 blob " + b"a" * 40 + b"\tdoc/file.png\0"
    with pytest.raises(ValueError):
        tracked_projection(tmp_path, tree, POLICY, writers_stopped=True)


def test_additional_unregistered_link_is_not_exempted(tmp_path):
    tree = fixture(tmp_path)
    _, manifest, _ = tracked_projection(tmp_path, tree, POLICY, writers_stopped=True)
    (tmp_path / "tests/new.py").symlink_to("../package/code.py")
    with pytest.raises(ValueError):
        capture_stopped_workspace(tmp_path, writers_stopped=True,
            runtime_manifest=manifest, runtime_policy=POLICY)


def test_manifest_cannot_hide_source_or_lie_about_literal_link(tmp_path):
    tree = fixture(tmp_path)
    _, manifest, _ = tracked_projection(tmp_path, tree, POLICY, writers_stopped=True)
    manifest["tests/link.py"]["link_target"] = "../package/other.py"
    with pytest.raises(ValueError):
        validate_manifest(manifest, POLICY)
    with pytest.raises(PermissionError):
        tracked_projection(tmp_path, tree, POLICY)


def test_hardlinked_assets_rejected(tmp_path):
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc/file.png").write_bytes(b"\x89PNG\r\n\x1a\npayload")
    os.link(tmp_path / "doc/file.png", tmp_path / "alias")
    with pytest.raises(ValueError):
        tracked_projection(tmp_path, listing(tmp_path, ["doc/file.png"]), POLICY, writers_stopped=True)


def test_public_workspace_materializes_exact_fixtures_without_following_links(tmp_path):
    root, workspace = tmp_path / "image", tmp_path / "work"
    root.mkdir()
    tree = fixture(root)
    source, manifest, _ = tracked_projection(root, tree, POLICY, writers_stopped=True)
    workspace.mkdir()
    (workspace / "package").mkdir()
    (workspace / "package/code.py").write_bytes(b"candidate source\n")
    materialize_fixtures(root, workspace, manifest, POLICY, writers_stopped=True)
    assert (workspace / "doc/large.png").read_bytes() == (root / "doc/large.png").read_bytes()
    assert os.readlink(workspace / "tests/link.py") == "../package/code.py"
    assert (workspace / "package/code.py").read_bytes() == b"candidate source\n"
    assert capture_stopped_workspace(workspace, writers_stopped=True,
        runtime_manifest=manifest, runtime_policy=POLICY) == {"package/code.py": b"candidate source\n"}
    with pytest.raises(FileExistsError):
        materialize_fixtures(root, workspace, manifest, POLICY, writers_stopped=True)


def test_public_materialization_does_not_follow_candidate_parent_links(tmp_path):
    root, workspace = tmp_path / "image", tmp_path / "work"
    root.mkdir()
    tree = fixture(root)
    _, manifest, _ = tracked_projection(root, tree, POLICY, writers_stopped=True)
    workspace.mkdir()
    (workspace / "doc").symlink_to(root / "doc", target_is_directory=True)
    with pytest.raises(OSError):
        materialize_fixtures(root, workspace, manifest, POLICY, writers_stopped=True)
