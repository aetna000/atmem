"""Repository-neutral source-only boundary over trusted regular-file snapshots.

This module never reads a worktree or trusts mutable Git status/HEAD. Its caller
must supply bounded regular-file snapshots and enforce filesystem/symlink safety.
It is not a complete external benchmark runner or a replacement grader.
"""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath


ASSET_SUFFIXES = frozenset({".ai", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2"})


def file_byte_limit(name):
    """Retain ordinary repository assets without enlarging source-code limits."""
    path_name(name)
    return 4_000_000 if PurePosixPath(name).suffix.lower() in ASSET_SUFFIXES else 1_000_000


def path_name(value):
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise ValueError("canonical repository-relative path required")
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or ".." in path.parts or str(path) != value or path.parts[0] == ".git":
        raise ValueError("canonical repository-relative path required")
    return value


@dataclass(frozen=True)
class SourcePolicy:
    source_roots: tuple[str, ...]
    test_roots: tuple[str, ...] = ("tests/",)
    extensions: tuple[str, ...] = (".py",)

    def __post_init__(self):
        if not self.source_roots or not self.test_roots or len(self.source_roots) + len(self.test_roots) > 16:
            raise ValueError("explicit bounded source/test roots required")
        roots = self.source_roots + self.test_roots
        for root in roots:
            if not isinstance(root, str) or not root.endswith("/"):
                raise ValueError("explicit directory roots required")
            path_name(root[:-1])
            if root[:-1] in {".", "tests", "test"} and root in self.source_roots:
                raise ValueError("tests cannot become implementation roots")
        for group in (self.source_roots, self.test_roots):
            if any(a.startswith(b) for i, a in enumerate(group) for j, b in enumerate(group) if i != j):
                raise ValueError("duplicate/overlapping roots within a role")
        if any(source.startswith(test) for source in self.source_roots for test in self.test_roots):
            raise ValueError("implementation roots cannot be inside protected tests")
        if not self.extensions or any(not isinstance(e, str) or not e.startswith(".") or "/" in e or "\\" in e for e in self.extensions):
            raise ValueError("explicit implementation extensions required")

    def source(self, name):
        return (any(name.startswith(root) for root in self.source_roots)
                and not any(name.startswith(root) for root in self.test_roots)
                and PurePosixPath(name).suffix in self.extensions)

    def test(self, name):
        return any(name.startswith(root) for root in self.test_roots) and name.endswith(".py")


def checked_snapshot(files):
    if not isinstance(files, dict) or len(files) > 10000:
        raise ValueError("bounded regular-file snapshot required")
    total = 0
    for name, raw in files.items():
        path_name(name)
        if type(raw) is not bytes or len(raw) > file_byte_limit(name):
            raise ValueError("bounded regular file bytes required")
        total += len(raw)
        if total > 40_000_000:
            raise ValueError("snapshot byte budget exceeded")


def collect_source_patch(original, candidate, policy):
    checked_snapshot(original)
    checked_snapshot(candidate)
    changed = sorted(name for name in original.keys() | candidate.keys() if original.get(name) != candidate.get(name))
    if len(changed) > 128:
        raise ValueError("changed-file limit exceeded")
    sources = {name: raw for name, raw in candidate.items() if policy.source(name)}
    ignored = [name for name in changed if policy.test(name)]
    violations = [name for name in changed if not policy.source(name) and not policy.test(name)]
    return {"changed_paths": changed, "source_files": sources, "ignored_test_changes": ignored,
        "out_of_scope_changes": violations,
        "source_sha256": {name: sha256(raw).hexdigest() for name, raw in sorted(sources.items())},
        "assurance": "snapshot_comparison_not_mutable_git_HEAD; tests_never_substituted_into_grader"}


def governed_solution(frozen_grader, proposal, policy):
    checked_snapshot(frozen_grader)
    if proposal["out_of_scope_changes"]:
        raise PermissionError("out-of-scope candidate changes cannot be graded as compliant")
    sources = proposal["source_files"]
    checked_snapshot(sources)
    if any(not policy.source(name) for name in sources):
        raise PermissionError("only authorized implementation files may replace grader source")
    result = {name: raw for name, raw in frozen_grader.items() if not policy.source(name)}
    result.update(sources)
    return result


def governed_public_proposal(frozen_grader, public_original, candidate, policy):
    """Compare public solver state, preserving private image-only runtime files.

    The caller supplies verified same-revision public original bytes, BEFORE
    injecting hidden tests. Image-only files never become editable merely by
    matching an implementation root. This function does not capture a live
    filesystem, authorize a repository or execute tests.
    """
    for snapshot in (frozen_grader, public_original, candidate):
        checked_snapshot(snapshot)
    if any(frozen_grader.get(name) != raw for name, raw in public_original.items()):
        raise PermissionError("public original differs from frozen base")
    protected = frozen_grader.keys() - public_original.keys()
    if protected & candidate.keys():
        raise PermissionError("candidate cannot replace image-only runtime files")
    proposal = collect_source_patch(public_original, candidate, policy)
    projection = {name: raw for name, raw in frozen_grader.items()
                  if name not in protected or not policy.source(name)}
    assembled = governed_solution(projection, proposal, policy)
    assembled.update({name: frozen_grader[name] for name in protected if policy.source(name)})
    return assembled, proposal
