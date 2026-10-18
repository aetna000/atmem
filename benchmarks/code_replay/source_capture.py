"""POSIX descriptor-relative source capture for a stopped, disposable solver.

The caller must stop ALL workspace writers before capture and keep them stopped
through grading. This is not an atomic snapshot of a live/adversarial filesystem.
No Git command or repository code runs. By default only top-level .git is
excluded. An evaluator may explicitly exclude its untracked .eggs runtime cache
after independently proving it contains no tracked repository paths.
"""
import os
import stat

from benchmarks.code_replay.source_policy import checked_snapshot, path_name, file_byte_limit


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def capture_stopped_workspace(root, *, writers_stopped=False, excluded_runtime_roots=(),
                              runtime_manifest=None, runtime_policy=None):
    if writers_stopped is not True:
        raise PermissionError("workspace writers must be stopped before capture")
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("descriptor-relative POSIX capture unavailable")
    # Evaluator-only pip cache projection, never an arbitrary caller path list.
    # The evaluator must independently prove this root is not tracked source.
    if excluded_runtime_roots not in ((), (".eggs/",)):
        raise ValueError("unsupported runtime exclusion")
    fixtures, seen_fixtures = {}, set()
    if runtime_manifest is not None:
        from benchmarks.code_replay.runtime_fixtures import validate_manifest, verify_fixture
        if runtime_policy is None:
            raise ValueError("operator runtime fixture policy required")
        fixtures = validate_manifest(runtime_manifest, runtime_policy)
    elif runtime_policy is not None:
        raise ValueError("runtime policy without a manifest prohibited")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    result, total, entries = {}, 0, 0

    def visit(directory, prefix="", depth=0):
        nonlocal total, entries
        if depth > 32:
            raise ValueError("workspace depth budget exceeded")
        before_directory = os.fstat(directory)
        for name in sorted(os.listdir(directory)):
            if not prefix and name == ".git":
                continue
            if not prefix and name + "/" in excluded_runtime_roots:
                continue
            entries += 1
            if entries > 10000:
                raise ValueError("workspace entry budget exceeded")
            relative = path_name(prefix + name)
            before = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if relative in fixtures:
                verify_fixture(directory, name, relative, fixtures[relative], runtime_policy)
                seen_fixtures.add(relative)
            elif stat.S_ISDIR(before.st_mode):
                child = os.open(name, flags | os.O_DIRECTORY, dir_fd=directory)
                try:
                    if _identity(os.fstat(child)) != _identity(before):
                        raise ValueError("workspace directory changed during capture")
                    visit(child, relative + "/", depth + 1)
                finally:
                    os.close(child)
            elif stat.S_ISREG(before.st_mode):
                limit = file_byte_limit(relative)
                if before.st_nlink != 1 or before.st_size > limit:
                    raise ValueError("bounded singly-linked regular files required")
                child = os.open(name, flags | os.O_NONBLOCK, dir_fd=directory)
                try:
                    opened = os.fstat(child)
                    if _identity(opened) != _identity(before):
                        raise ValueError("workspace file changed during capture")
                    chunks, size = [], 0
                    while True:
                        chunk = os.read(child, min(65536, limit + 1 - size))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        size += len(chunk)
                        if size > limit:
                            raise ValueError("workspace file byte budget exceeded")
                    if _identity(os.fstat(child)) != _identity(opened) or size != opened.st_size:
                        raise ValueError("workspace file changed during capture")
                    total += size
                    if total > 40_000_000:
                        raise ValueError("workspace snapshot byte budget exceeded")
                    result[relative] = b"".join(chunks)
                finally:
                    os.close(child)
            else:
                raise ValueError("symlinks and special workspace files prohibited")
            after = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if _identity(after) != _identity(before):
                raise ValueError("workspace entry changed during capture")
        if _identity(os.fstat(directory)) != _identity(before_directory):
            raise ValueError("workspace directory changed during capture")

    descriptor = os.open(root, flags | os.O_DIRECTORY)
    try:
        root_identity = _identity(os.fstat(descriptor))
        visit(descriptor)
        if _identity(os.stat(root, follow_symlinks=False)) != root_identity:
            raise ValueError("workspace root changed during capture")
    finally:
        os.close(descriptor)
    if seen_fixtures != set(fixtures):
        raise ValueError("immutable runtime fixture missing from workspace")
    checked_snapshot(result)
    return result
