import os

import pytest

from benchmarks.code_replay.source_capture import capture_stopped_workspace
from benchmarks.code_replay.source_policy import SourcePolicy, collect_source_patch, governed_solution


pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX-only worker boundary")


def capture(root):
    return capture_stopped_workspace(root, writers_stopped=True)


def test_stopped_workspace_required(tmp_path):
    with pytest.raises(PermissionError, match="stopped"):
        capture_stopped_workspace(tmp_path)


def test_runtime_cache_exclusion_is_explicit_and_not_a_general_ignore(tmp_path):
    (tmp_path / ".eggs").mkdir()
    (tmp_path / ".eggs/private-link").symlink_to(tmp_path / "absent")
    (tmp_path / "module.py").write_bytes(b"pass\n")
    with pytest.raises(ValueError):
        capture(tmp_path)
    assert capture_stopped_workspace(tmp_path, writers_stopped=True, excluded_runtime_roots=(".eggs/",)) == {"module.py": b"pass\n"}
    with pytest.raises(ValueError, match="unsupported runtime"):
        capture_stopped_workspace(tmp_path, writers_stopped=True, excluded_runtime_roots=("tests/",))


def test_exact_bytes_and_git_metadata_exclusion(tmp_path):
    (tmp_path / "package").mkdir()
    (tmp_path / "package/a.py").write_bytes(b"name = '\xe4\xb8\xad'\r\n")
    (tmp_path / ".git").symlink_to(tmp_path / "absent")
    assert capture(tmp_path) == {"package/a.py": b"name = '\xe4\xb8\xad'\r\n"}


@pytest.mark.parametrize("kind", ["file_link", "directory_link", "hard_link", "fifo"])
def test_external_and_special_entries_refused(tmp_path, kind):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    (outside / "secret").write_bytes(b"not source")
    if kind == "file_link":
        (tmp_path / "bad.py").symlink_to(outside / "secret")
    elif kind == "directory_link":
        (tmp_path / "package").symlink_to(outside, target_is_directory=True)
    elif kind == "hard_link":
        os.link(outside / "secret", tmp_path / "bad.py")
    else:
        os.mkfifo(tmp_path / "bad.py")
    with pytest.raises(ValueError):
        capture(tmp_path)


def test_root_symlink_refused(tmp_path):
    alias = tmp_path.parent / (tmp_path.name + "-alias")
    alias.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        capture(alias)


def test_file_size_bound(tmp_path):
    (tmp_path / "big.py").write_bytes(b"x" * 1_000_001)
    with pytest.raises(ValueError, match="bounded"):
        capture(tmp_path)


def test_large_asset_is_captured_exactly_but_cannot_be_mutated(tmp_path):
    (tmp_path / "ext").mkdir()
    asset = bytes(range(256)) * 8553
    (tmp_path / "ext/logo.ai").write_bytes(asset)
    original = capture(tmp_path)
    assert original == {"ext/logo.ai": asset}
    policy = SourcePolicy(("package/",))
    proposal = collect_source_patch(original, {"ext/logo.ai": asset + b"changed"}, policy)
    assert proposal["out_of_scope_changes"] == ["ext/logo.ai"]
    with pytest.raises(PermissionError, match="out-of-scope"):
        governed_solution(original, proposal, policy)


def test_asset_limit_is_bounded_and_does_not_apply_to_code(tmp_path):
    (tmp_path / "large.ai").write_bytes(b"x" * 4_000_001)
    with pytest.raises(ValueError, match="bounded"):
        capture(tmp_path)


def test_assets_still_share_the_original_total_snapshot_bound():
    from benchmarks.code_replay.source_policy import checked_snapshot
    asset = b"x" * 4_000_000
    files = {f"ext/{i}.ai": asset for i in range(10)}
    checked_snapshot(files)
    with pytest.raises(ValueError, match="snapshot byte budget"):
        checked_snapshot({**files, "ext/overflow.ai": b"x"})


def test_mutation_during_read_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "a.py"
    source.write_bytes(b"before")
    actual_read = os.read
    changed = False

    def racing_read(fd, size):
        nonlocal changed
        raw = actual_read(fd, size)
        if not changed:
            changed = True
            source.write_bytes(b"after mutation")
        return raw

    monkeypatch.setattr(os, "read", racing_read)
    with pytest.raises(ValueError, match="changed"):
        capture(tmp_path)


def test_new_entry_during_read_is_rejected(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_bytes(b"source")
    actual_read = os.read
    changed = False

    def racing_read(fd, size):
        nonlocal changed
        raw = actual_read(fd, size)
        if not changed:
            changed = True
            (tmp_path / "new.py").write_bytes(b"late entry")
        return raw

    monkeypatch.setattr(os, "read", racing_read)
    with pytest.raises(ValueError, match="directory changed"):
        capture(tmp_path)


def test_captured_test_edits_do_not_replace_grader(tmp_path):
    (tmp_path / "package").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "package/a.py").write_bytes(b"fixed")
    (tmp_path / "tests/test_a.py").write_bytes(b"fake pass")
    policy = SourcePolicy(("package/",))
    base = {"package/a.py": b"bug", "tests/test_a.py": b"original"}
    frozen = {**base, "tests/hidden.py": b"hidden grading"}
    proposal = collect_source_patch(base, capture(tmp_path), policy)
    merged = governed_solution(frozen, proposal, policy)
    assert merged == {**frozen, "package/a.py": b"fixed"}
    assert proposal["ignored_test_changes"] == ["tests/test_a.py"]
