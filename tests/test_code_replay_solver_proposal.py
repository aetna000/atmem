import ast
import base64
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from benchmarks.code_replay.grade import write_new_tree
from benchmarks.code_replay.solver_proposal import proposal_request, solver_bootstrap, proposal_controls_qualified


BASE = "456bacbbead4fa30a1a82892c9446ac9efb8055b"


def encoded(files):
    return {name: base64.b64encode(raw).decode() for name, raw in files.items()}


def request(files, candidate=None):
    source = {"base_commit": BASE, "files_base64": encoded(files),
        "modes": {name: "100644" for name in files}, "private_field": "never forward"}
    return proposal_request({"base_commit": BASE}, source, encoded(files if candidate is None else candidate))


@pytest.fixture
def worker(monkeypatch):
    def load(name, filename):
        spec = importlib.util.spec_from_file_location(name, Path("benchmarks/code_replay") / filename)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module
    monkeypatch.setitem(sys.modules, "atmem_native_tree", SimpleNamespace(write_new_tree=write_new_tree))
    monkeypatch.setitem(sys.modules, "atmem_external_control", SimpleNamespace())
    load("atmem_external_boundary", "external_candidate_worker.py")
    load("atmem_public_validation", "public_test_worker.py")
    return load("atmem_solver_worker_fixture", "solver_proposal_worker.py")


def test_request_roles_do_not_forward_source_metadata(worker):
    value = request({"src/marshmallow/a.py": b"pass\n"})
    assert set(value) == {"format", "material", "proposal"}
    assert "private_field" not in value["proposal"]
    _, _, original, candidate = worker.validate_request(value)
    assert original == candidate == {"src/marshmallow/a.py": b"pass\n"}


@pytest.mark.parametrize("failure", ["extra_envelope", "extra_proposal", "wrong_base", "git_path", "oversized_file", "wrong_mode"])
def test_bad_roles_files_modes_and_binding_refused(worker, failure):
    value = request({"src/marshmallow/a.py": b"pass\n"})
    if failure == "extra_envelope":
        value["pytest"] = {"paths": ["private"]}
    elif failure == "extra_proposal":
        value["proposal"]["eval.sh"] = "not allowed"
    elif failure == "wrong_base":
        value["material"]["base_commit"] = "a" * 40
    elif failure == "git_path":
        value["proposal"]["candidate_files_base64"][".git/config"] = "eA=="
    elif failure == "oversized_file":
        value["proposal"]["candidate_files_base64"]["large.py"] = base64.b64encode(b"x" * 1_000_001).decode()
    else:
        value["proposal"]["public_base_modes"]["src/marshmallow/a.py"] = "120000"
    with pytest.raises(ValueError):
        worker.validate_request(value)


def test_public_base_git_membership_and_bytes_are_verified(worker, tmp_path):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    path = tmp_path / "a.py"
    path.write_bytes(b"pass\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "a.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
        "-c", "user.name=fixture", "-c", "user.email=fixture@invalid", "commit", "--quiet", "-m", "fixture"], check=True)
    worker.verify_public_base(tmp_path, "HEAD", {"a.py": b"pass\n"}, {"a.py": "100644"})
    with pytest.raises(ValueError, match="identity"):
        worker.verify_public_base(tmp_path, "HEAD", {"a.py": b"different"}, {"a.py": "100644"})
    with pytest.raises(ValueError, match="extra"):
        worker.verify_public_base(tmp_path, "HEAD", {"a.py": b"pass\n", "extra.py": b"x"}, {"a.py": "100644"})
    with pytest.raises(ValueError, match="membership"):
        worker.verify_public_base(tmp_path, "HEAD", {"other.py": b"pass\n"}, {"other.py": "100644"})


@pytest.mark.parametrize("out_of_scope", [False, True])
def test_worker_preserves_frozen_tests_and_runtime_before_execution(worker, monkeypatch, tmp_path, capsys, out_of_scope):
    original = {"src/marshmallow/a.py": b"before", "tests/a.py": b"frozen public test"}
    frozen = {**original, "src/marshmallow.egg-info/PKG-INFO": b"protected runtime"}
    candidate = {**original, "src/marshmallow/a.py": b"after", "tests/a.py": b"fake pass"}
    if out_of_scope:
        candidate["pyproject.toml"] = b"not allowed"
    root, evaluator = tmp_path / "testbed", tmp_path / "evaluator"
    root.mkdir()
    write_new_tree(root, frozen)
    monkeypatch.setattr(worker, "Path", lambda value: root if value == "/testbed" else evaluator)
    monkeypatch.setattr(worker, "verify_public_base", lambda *args: None)
    monkeypatch.setattr(worker.control, "tracked_base", lambda base: {"fixture": True}, raising=False)
    monkeypatch.setattr(worker.control, "validated_files", lambda payload: {
        "task_files": {"eval.sh": b"fixture script", "test.patch": b"fixture tests", "tests.json": b"{}", "gold.patch": b"DO_NOT_WRITE"},
        "harness_files": {}}, raising=False)
    monkeypatch.setattr(worker.control, "os", SimpleNamespace(environ={}), raising=False)
    calls = []
    def execute(path, environment):
        calls.append(path)
        assert (root / "src/marshmallow/a.py").read_bytes() == b"after"
        assert (root / "tests/a.py").read_bytes() == b"frozen public test"
        assert (root / "src/marshmallow.egg-info/PKG-INFO").read_bytes() == b"protected runtime"
        assert not (evaluator / "gold.patch").exists()
        return 0, b"fixture output", b"", None
    monkeypatch.setattr(worker.control, "execute_script", execute, raising=False)
    monkeypatch.setattr(worker.control, "grade", lambda *args: {"fixture_only": True}, raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request(original, candidate))))
    if out_of_scope:
        with pytest.raises(PermissionError, match="out-of-scope"):
            worker.main()
        assert not calls and not evaluator.exists()
    else:
        worker.main()
        result = json.loads(capsys.readouterr().out)
        assert result["ignored_test_changes"] == ["tests/a.py"]
        assert result["image_only_bytes_preserved"] and not result["gold_patch_written"]
        assert len(calls) == 1


def test_bootstrap_reuses_existing_workers_and_loads_without_site_packages():
    source = solver_bootstrap("# fixture control only\n")
    ast.parse(source, feature_version=(3, 9))
    result = subprocess.run([sys.executable, "-I", "-S", "-c", source], input=b"{}", capture_output=True, timeout=10)
    assert result.returncode != 0 and b"exact private proposal envelope required" in result.stderr
    assert b"ModuleNotFoundError" not in result.stderr


def test_controls_require_role_and_real_prior_outcomes():
    from test_code_replay_external_source_boundary import fixture_results
    rows = fixture_results()
    for row in rows.values():
        row["worker"].update(phase="solver_proposal", public_base_verified=True,
            image_only_bytes_preserved=True, gold_patch_written=False)
    assert proposal_controls_qualified(rows)
    assert not proposal_controls_qualified({"unchanged": rows["unchanged"]})
    rows["reference_as_proposal"]["worker"]["gold_patch_written"] = True
    assert not proposal_controls_qualified(rows)
