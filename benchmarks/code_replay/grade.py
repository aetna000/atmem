"""Evaluator-only frozen behavioral grading of source-only historical trees.

No solver-facing invocation exists. Returned raw test bytes must be retained by
the protected evidence service, never sent back as adaptive hidden feedback.
"""
from dataclasses import dataclass
from hashlib import sha256
import io
import re
from pathlib import Path, PurePosixPath
import subprocess
import shutil
import tarfile
import tempfile
import time

from benchmarks.code_replay.contracts import commit
from benchmarks.code_replay.prepare import git
from benchmarks.code_replay.sandbox import permission_arguments


def tree_files(checkout: Path, revision: str):
    commit(revision, "tree_revision")
    raw = git(checkout, "archive", "--format=tar", revision)
    if len(raw) > 40_000_000:
        raise ValueError("source archive budget exceeded")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or ".git" in path.parts:
                raise ValueError("unsafe historical source path")
            if member.isdir():
                continue
            if not member.isfile() or member.size > 1_000_000:
                raise ValueError("unsupported historical member")
            files[member.name] = archive.extractfile(member).read()
    return files


def write_new_tree(root: Path, files: dict[str, bytes]):
    if any(root.iterdir()):
        raise ValueError("grader workspace must be newly created and empty")
    for name, data in files.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or str(path) != name:
            raise ValueError("unsafe source path")
        target = root.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)


@dataclass(frozen=True)
class GradeObservation:
    exit_code: int | None
    elapsed_ms: int
    output: bytes
    environment_error: bool

    def summary(self):
        return {"exit_code": self.exit_code, "elapsed_ms": self.elapsed_ms,
                "output_sha256": sha256(self.output).hexdigest(), "environment_error": self.environment_error,
                "passed": self.exit_code == 0 and not self.environment_error}


def grade_files(files, *, python: Path, interpreter_root: Path, test_paths: tuple[str, ...], timeout=180):
    # Preserve the venv executable path: resolving its symlink discards that
    # environment's site-packages selection.
    python = python.absolute()
    if not python.is_file():
        raise ValueError("pinned grader Python is missing")
    if not test_paths or any(not p.startswith("tests/") or ".." in PurePosixPath(p).parts for p in test_paths):
        raise ValueError("frozen repository test paths required")
    # Keep workspaces for reproducibility; no broad recursive cleanup is used.
    root = Path(tempfile.mkdtemp(prefix="atmem-click-grader-"))
    write_new_tree(root, files)
    # Disable ambient pytest plugins and keep the tested import rooted at src.
    environment = {"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8",
                   "PYTHONPATH": str(root / "src"), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                   "PYTHONDONTWRITEBYTECODE": "1"}
    (root / "tmp").mkdir()
    runtime_root = python.parent.parent
    codex = shutil.which("codex")
    if codex is None:
        raise ValueError("Codex sandbox executable is missing")
    bootstrap = ('import os,sys,runpy; os.environ["TMPDIR"]=' + repr(str(root / "tmp")) + '; '
                 'import flit_core.buildapi; os.mkdir(".grader-metadata"); '
                 'flit_core.buildapi.prepare_metadata_for_build_wheel(".grader-metadata"); '
                 'sys.path.insert(0,os.path.abspath(".grader-metadata")); '
                 'runpy.run_module("pytest",run_name="__main__")')
    command = [codex, "sandbox", "-C", str(root), "-P", "click-replay",
               *permission_arguments((interpreter_root, runtime_root)), str(python), "-c",
               bootstrap,
               "-q", "--tb=short", "-p", "no:cacheprovider", "--basetemp", str(root / "tmp/pytest"), *test_paths]
    # This upstream case demands read access to the literal /tmp. Granting it
    # would expose evaluator/grader directories. Exclude the same environment-
    # dependent case for parent, reference and every solver patch, not failures
    # discovered after solving. Other Path behavior remains tested.
    command += ["--deselect=tests/test_commands.py::test_other_command_invoke_with_defaults[opt_params12-/tmp]"]
    start = time.monotonic()
    try:
        # Codex must retain its own runtime PATH, not the restricted child PATH.
        # Explicit allowlist: no household credentials or provider environment.
        result = subprocess.run(command, env=environment, capture_output=True, timeout=timeout)
        output = result.stdout + result.stderr
        setup_errors = bool(re.search(rb"\b[1-9][0-9]* errors?\b", output.split(b"short test summary info")[-1]))
        return GradeObservation(result.returncode, int((time.monotonic() - start) * 1000), output,
                                result.returncode not in (0, 1) or setup_errors)
    except subprocess.TimeoutExpired as exc:
        return GradeObservation(None, int((time.monotonic() - start) * 1000), (exc.stdout or b"") + (exc.stderr or b""), True)


def qualification(checkout, parent, reference, *, python, interpreter_root, test_paths):
    """Both trees receive identical frozen reference tests and parent config."""
    parent_files, reference_files = tree_files(checkout, parent), tree_files(checkout, reference)
    frozen = {name: data for name, data in reference_files.items() if name.startswith("tests/")}
    results = {}
    for name, sources in (("parent", parent_files), ("reference", reference_files)):
        # Test code/config must be identical in the pair. Source is the variable.
        tree = {**parent_files, **frozen}
        for path in list(tree):
            if path.startswith("src/"):
                del tree[path]
        tree.update({path: data for path, data in sources.items() if path.startswith("src/")})
        results[name] = grade_files(tree, python=python, interpreter_root=interpreter_root, test_paths=test_paths)
    return results
