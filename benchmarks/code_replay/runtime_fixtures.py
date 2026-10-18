"""Operator-only immutable fixtures, verified without traversing symlinks.

All writers must be stopped. This is a bounded projection of a pinned tree,
not a snapshot of a live filesystem and not a model-controlled omission list.
"""
from hashlib import sha1, sha256
import json
import os
from pathlib import PurePosixPath
import posixpath
import re
import stat

from benchmarks.code_replay.source_policy import path_name, file_byte_limit


MAX_ASSET = 32_000_000
MAX_ASSETS = 256_000_000
ASSETS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".ttf", ".otf",
    ".woff", ".woff2", ".pdf", ".ai",
})
FIELDS = {"role", "mode", "git_blob", "sha256", "bytes"}


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _asset_signature(name, prefix):
    suffix = PurePosixPath(name).suffix.lower()
    if suffix == ".png":
        return prefix.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return prefix.startswith(b"\xff\xd8\xff")
    if suffix == ".gif":
        return prefix.startswith((b"GIF87a", b"GIF89a"))
    if suffix == ".webp":
        return prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP"
    if suffix == ".ico":
        return prefix.startswith(b"\x00\x00\x01\x00")
    if suffix == ".ttf":
        return prefix.startswith((b"\x00\x01\x00\x00", b"true", b"typ1"))
    if suffix == ".otf":
        return prefix.startswith(b"OTTO")
    if suffix == ".woff":
        return prefix.startswith(b"wOFF")
    if suffix == ".woff2":
        return prefix.startswith(b"wOF2")
    if suffix == ".pdf":
        return prefix.startswith(b"%PDF-")
    if suffix == ".ai":
        return prefix.startswith((b"%PDF-", b"%!PS"))
    return False


def fixture_role(name, mode, policy):
    path_name(name)
    if mode == "120000":
        if not any(name.startswith(root) for root in policy.test_roots):
            raise ValueError("only protected test fixture links may be opaque")
        return "test_symlink"
    if mode not in {"100644", "100755"}:
        raise ValueError("unsupported tracked mode")
    if PurePosixPath(name).suffix.lower() in ASSETS and not policy.source(name):
        return "binary_asset"
    return None


def _link_target(name, raw):
    try:
        target = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("UTF-8 literal fixture link required") from exc
    if not target or len(raw) > 4096 or "\\" in target or "\0" in target or target.startswith("/"):
        raise ValueError("bounded relative fixture link required")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
    path_name(resolved)
    return target


def validate_manifest(manifest, policy):
    if type(manifest) is not dict or len(manifest) > 10000:
        raise ValueError("bounded operator fixture manifest required")
    total = 0
    for name, item in manifest.items():
        path_name(name)
        if type(item) is not dict:
            raise ValueError("fixture object required")
        role = item.get("role")
        expected_fields = FIELDS | ({"link_target"} if role == "test_symlink" else set())
        if (set(item) != expected_fields or role not in {"test_symlink", "binary_asset"}
            or fixture_role(name, item["mode"], policy) != role
            or type(item["bytes"]) is not int or not 1 <= item["bytes"] <= MAX_ASSET
            or not isinstance(item["git_blob"], str)
            or re.fullmatch("[0-9a-f]{40}", item["git_blob"]) is None
            or not isinstance(item["sha256"], str)
            or re.fullmatch("[0-9a-f]{64}", item["sha256"]) is None):
            raise ValueError("invalid fixture role or identity")
        if role == "test_symlink":
            if type(item["link_target"]) is not str:
                raise ValueError("literal fixture target required")
            raw = item["link_target"].encode("utf-8")
            _link_target(name, raw)
            if (len(raw) != item["bytes"] or sha256(raw).hexdigest() != item["sha256"]
                or sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != item["git_blob"]):
                raise ValueError("fixture link identity differs")
        else:
            total += item["bytes"]
            if total > MAX_ASSETS:
                raise ValueError("immutable asset inventory budget exceeded")
    return manifest


def read_member(parent, leaf, name, mode, blob, policy):
    """Read/verify one direct child of an already no-follow opened directory."""
    role = fixture_role(name, mode, policy)
    before = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
    if before.st_nlink != 1:
        raise ValueError("singly linked tracked member required")
    raw = None
    if role == "test_symlink":
        if not stat.S_ISLNK(before.st_mode):
            raise ValueError("fixture link mode differs")
        raw = os.readlink(os.fsencode(leaf), dir_fd=parent)
        target = _link_target(name, raw)
        size = len(raw)
        git_digest = sha1(b"blob " + str(size).encode() + b"\0" + raw)
        digest = sha256(raw)
    else:
        limit = MAX_ASSET if role else file_byte_limit(name)
        if (not stat.S_ISREG(before.st_mode) or before.st_size > limit
            or bool(before.st_mode & 0o111) != (mode == "100755")):
            raise ValueError("bounded regular tracked member with matching mode required")
        descriptor = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent)
        try:
            opened = os.fstat(descriptor)
            if _identity(opened) != _identity(before):
                raise ValueError("tracked member changed before read")
            size, prefix, chunks = 0, b"", []
            git_digest = sha1(b"blob " + str(before.st_size).encode() + b"\0")
            digest = sha256()
            while True:
                chunk = os.read(descriptor, min(65536, limit + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise ValueError("tracked member byte budget exceeded")
                if len(prefix) < 16:
                    prefix = (prefix + chunk)[:16]
                git_digest.update(chunk)
                digest.update(chunk)
                if role is None:
                    chunks.append(chunk)
            if _identity(os.fstat(descriptor)) != _identity(opened) or size != opened.st_size:
                raise ValueError("tracked member changed during read")
            if role == "binary_asset" and not _asset_signature(name, prefix):
                raise ValueError("opaque asset signature differs from suffix")
            if role is None:
                raw = b"".join(chunks)
        finally:
            os.close(descriptor)
    if _identity(os.stat(leaf, dir_fd=parent, follow_symlinks=False)) != _identity(before):
        raise ValueError("tracked member changed after read")
    if git_digest.hexdigest() != blob:
        raise ValueError("tracked member Git blob differs")
    item = {"role": role, "mode": mode, "git_blob": blob,
            "sha256": digest.hexdigest(), "bytes": size}
    if role == "test_symlink":
        item["link_target"] = target
    return raw if role is None else None, item


def verify_fixture(parent, leaf, name, expected, policy):
    _, observed = read_member(parent, leaf, name, expected["mode"], expected["git_blob"], policy)
    if observed != expected:
        raise ValueError("immutable runtime fixture changed")


def tracked_projection(root, listing, policy, *, writers_stopped=False):
    """Verify the disjoint source/runtime union against exact Git ls-tree bytes."""
    if writers_stopped is not True:
        raise PermissionError("workspace writers must be stopped")
    if (type(listing) is not bytes or len(listing) > 4_000_000
        or not listing or not listing.endswith(b"\0")):
        raise ValueError("bounded pinned Git tree listing required")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    root_fd = os.open(root, flags)
    source, manifest, identities = {}, {}, {}
    source_bytes, runtime_bytes = 0, 0
    try:
        root_identity = _identity(os.fstat(root_fd))
        for record in listing.split(b"\0"):
            if not record:
                continue
            header, encoded_name = record.split(b"\t", 1)
            mode, kind, blob = header.decode("ascii").split()
            name = path_name(encoded_name.decode("utf-8"))
            if name in identities or len(identities) >= 10000 or kind != "blob" or re.fullmatch("[0-9a-f]{40}", blob) is None:
                raise ValueError("exact unique bounded Git blob members required")
            parent = os.dup(root_fd)
            try:
                parts = name.split("/")
                for part in parts[:-1]:
                    child = os.open(part, flags, dir_fd=parent)
                    os.close(parent)
                    parent = child
                raw, item = read_member(parent, parts[-1], name, mode, blob, policy)
            finally:
                os.close(parent)
            identities[name] = blob
            if item["role"]:
                manifest[name] = item
                runtime_bytes += item["bytes"]
                if runtime_bytes > MAX_ASSETS:
                    raise ValueError("runtime inventory byte budget exceeded")
            else:
                source_bytes += len(raw)
                if source_bytes > 40_000_000:
                    raise ValueError("source projection byte budget exceeded")
                source[name] = raw
        if _identity(os.stat(root, follow_symlinks=False)) != root_identity:
            raise ValueError("workspace root changed during projection")
    finally:
        os.close(root_fd)
    validate_manifest(manifest, policy)
    return source, manifest, {
        "format": "atmem-source-runtime-projection-v2",
        "files": len(identities), "source_files": len(source), "source_bytes": source_bytes,
        "runtime_files": len(manifest), "runtime_bytes": runtime_bytes,
        "tree_fingerprint_sha256": sha256(json.dumps(identities, sort_keys=True).encode()).hexdigest(),
        "runtime_manifest_sha256": sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
    }


def materialize_fixtures(image_root, workspace, manifest, policy, *, writers_stopped=False):
    """Copy verified opaque assets/literal links into a new public test tree."""
    if writers_stopped is not True:
        raise PermissionError("workspace writers must be stopped")
    validate_manifest(manifest, policy)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    source_root, target_root = os.open(image_root, flags), None
    try:
        target_root = os.open(workspace, flags)
        for name, item in sorted(manifest.items()):
            source_parent, target_parent = os.dup(source_root), os.dup(target_root)
            try:
                parts = name.split("/")
                for part in parts[:-1]:
                    source_child = os.open(part, flags, dir_fd=source_parent)
                    os.close(source_parent)
                    source_parent = source_child
                    try:
                        os.mkdir(part, 0o755, dir_fd=target_parent)
                    except FileExistsError:
                        pass
                    target_child = os.open(part, flags, dir_fd=target_parent)
                    os.close(target_parent)
                    target_parent = target_child
                leaf = parts[-1]
                verify_fixture(source_parent, leaf, name, item, policy)
                if item["role"] == "test_symlink":
                    os.symlink(item["link_target"], leaf, dir_fd=target_parent)
                else:
                    reader = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                     dir_fd=source_parent)
                    try:
                        writer = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                                         | os.O_CLOEXEC, 0o755 if item["mode"] == "100755" else 0o644,
                                         dir_fd=target_parent)
                        try:
                            copied = 0
                            while True:
                                chunk = os.read(reader, min(65536, item["bytes"] + 1 - copied))
                                if not chunk:
                                    break
                                copied += len(chunk)
                                if copied > item["bytes"]:
                                    raise ValueError("runtime fixture grew during copy")
                                pending = memoryview(chunk)
                                while pending:
                                    written = os.write(writer, pending)
                                    if written <= 0:
                                        raise OSError("short runtime fixture write")
                                    pending = pending[written:]
                            if copied != item["bytes"]:
                                raise ValueError("runtime fixture shortened during copy")
                        finally:
                            os.close(writer)
                    finally:
                        os.close(reader)
                verify_fixture(source_parent, leaf, name, item, policy)
                verify_fixture(target_parent, leaf, name, item, policy)
            finally:
                os.close(source_parent)
                os.close(target_parent)
    finally:
        if target_root is not None:
            os.close(target_root)
        os.close(source_root)
