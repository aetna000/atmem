import ast
import base64
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from benchmarks.code_replay.grade import write_new_tree
from benchmarks.code_replay.public_test_control import public_bootstrap, public_command, public_request, success


@pytest.mark.parametrize("identity", ["marshmallow-code__marshmallow-1810", "psf__requests-1327", "pylint-dev__astroid-934", "pylint-dev__astroid-1616"])
def test_operator_task_base_is_bound_in_worker_not_request(worker, identity):
    from benchmarks.code_replay.external_qualify_worker import TASK_BINDINGS
    from benchmarks.code_replay.public_test_control import public_task_settings
    task = {"instance_id": identity, "base_commit": TASK_BINDINGS[identity][0], "image_extras_sha256": {}}
    settings = public_task_settings(task)
    namespace = {"__name__": "bound_public_fixture", **settings}
    exec(compile(Path("benchmarks/code_replay/public_test_worker.py").read_text(), "bound_public_fixture.py", "exec"), namespace)
    snapshot = source()
    snapshot["base_commit"] = task["base_commit"]
    value = public_request(snapshot, snapshot["files_base64"], paths=["tests"])
    assert namespace["validate_request"](value)[0] == {"tests/example.py": b"pass\n"}
    assert settings["PINNED_SOURCE_SUBDIR"] == ("src" if identity.startswith("marshmallow") else ".")
    root_test = {"paths": ["test_requests.py"], "keyword": None, "max_failures": 0}
    if identity == "psf__requests-1327":
        assert namespace["pytest_arguments"](root_test)[-1] == "test_requests.py"
    else:
        with pytest.raises(ValueError):
            namespace["pytest_arguments"](root_test)
    value["base_commit"] = "0" * 40
    with pytest.raises(ValueError, match="public-only"):
        namespace["validate_request"](value)


def test_public_task_configuration_cannot_choose_paths_or_unselected_identity():
    from benchmarks.code_replay.public_test_control import public_task_settings
    task = {"instance_id": "psf__requests-1327", "base_commit": "e7786ec14fdf20e8c373eddc9ac0f67d211cb1b9", "image_extras_sha256": {}}
    for key in ("source_roots", "pytest", "runtime_exclusions", "gold.patch"):
        with pytest.raises(ValueError, match="exact pinned"):
            public_task_settings({**task, key: []})
    with pytest.raises(ValueError, match="task/base"):
        public_task_settings({**task, "base_commit": "0" * 40})
    with pytest.raises(ValueError, match="digest"):
        public_task_settings({**task, "image_extras_sha256": {"build/runtime.py": "not a digest"}})


@pytest.fixture
def worker(monkeypatch):
    monkeypatch.setitem(sys.modules, "atmem_native_tree", SimpleNamespace(write_new_tree=write_new_tree))
    spec = importlib.util.spec_from_file_location("atmem_public_worker_fixture", Path("benchmarks/code_replay/public_test_worker.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source():
    return {"base_commit": "456bacbbead4fa30a1a82892c9446ac9efb8055b",
        "files_base64": {"tests/example.py": base64.b64encode(b"pass\n").decode()},
        "modes": {"tests/example.py": "100644"}, "gold.patch": "never forward"}


def test_role_constructor_never_forwards_evaluator_fields(worker):
    original = source()
    request = public_request(original, original["files_base64"], paths=["tests"])
    assert set(request) == worker.FIELDS
    assert "gold.patch" not in request
    public, candidate, args = worker.validate_request(request)
    assert public == candidate == {"tests/example.py": b"pass\n"}
    assert args[-1] == "tests"
    request["eval.sh"] = "not allowed"
    with pytest.raises(ValueError, match="public-only"):
        worker.validate_request(request)


@pytest.mark.parametrize("selector", ["/etc/passwd", "tests/../../private", "--help", "tests/a.py::bad;cat", "tests\\outside.py", "./tests"])
def test_test_selectors_cannot_change_command_or_scope(worker, selector):
    with pytest.raises(ValueError):
        worker.pytest_arguments({"paths": [selector], "keyword": None, "max_failures": 0})


def test_keywords_are_argv_data_and_resource_flags_bounded(worker):
    args = worker.pytest_arguments({"paths": ["tests/example.py::TestPublic::test_one"], "keyword": "alpha or beta", "max_failures": 2})
    assert args[args.index("-k") + 1] == "alpha or beta"
    assert "--maxfail=2" in args
    for bad in (True, -1, 11):
        with pytest.raises(ValueError):
            worker.pytest_arguments({"paths": ["tests"], "keyword": None, "max_failures": bad})


def test_registered_nested_test_directories_are_not_special_cased(worker, monkeypatch):
    monkeypatch.setattr(worker, 'PINNED_TEST_PATHS', ('package/checks', 'test_legacy.py'), raising=False)
    for selector in ('package/checks', 'package/checks/unit/test_format.py',
                     'package/checks/unit/test_format.py::TestFormat::test_one',
                     'test_legacy.py', 'test_legacy.py::test_one'):
        assert worker.pytest_arguments({'paths': [selector], 'keyword': None, 'max_failures': 0})[-1] == selector
    for selector in ('package/checks_other/test_one.py', 'package/checks/../../private.py',
                     'package/checks/../checks/test_one.py', 'test_legacy.py/nested.py',
                     '/package/checks/test_one.py', './package/checks/test_one.py',
                     'package/checks/test_one.py::bad;command', 'package/checks\\test_one.py',
                     'package/implementation.py', 'tests/test_one.py'):
        with pytest.raises(ValueError):
            worker.pytest_arguments({'paths': [selector], 'keyword': None, 'max_failures': 0})


def test_git_metadata_and_oversized_files_refused(worker):
    for name, raw in ((".git/config", b"not permitted"), ("tests/.git/objects/data", b"not permitted"), ("large.py", b"a" * 1_000_001)):
        with pytest.raises(ValueError):
            worker.decode_files({name: base64.b64encode(raw).decode()})


def test_bounded_assets_decode_without_increasing_code_limit(worker):
    asset = b"asset" * 450000
    assert worker.decode_files({"ext/logo.ai": base64.b64encode(asset).decode()}) == {"ext/logo.ai": asset}
    for name, raw in (("ext/logo.ai.py", asset), ("ext/logo.ai", b"x" * 4_000_001)):
        with pytest.raises(ValueError):
            worker.decode_files({name: base64.b64encode(raw).decode()})


def test_partial_output_survives_public_timeout(worker, tmp_path):
    result = worker.run_bounded([sys.executable, "-u", "-c", 'print("partial",flush=True);import time;time.sleep(5)'],
        cwd=tmp_path, environment=os.environ.copy(), seconds=.2)
    assert result["reason"] == "public_test_timeout"
    assert base64.b64decode(result["output_base64"]) == b"partial\n"
    assert result["exit_code"] != 0


def test_fast_output_cannot_evade_budget(worker, tmp_path):
    result = worker.run_bounded([sys.executable, "-c", 'print("x"*100000)'], cwd=tmp_path,
        environment=os.environ.copy(), byte_cap=1024)
    assert result["reason"] == "public_test_output_budget"
    assert result["output_truncated"] is True
    assert len(base64.b64decode(result["output_base64"])) == 1024


def test_public_container_never_receives_mounts_env_or_network():
    command = public_command("swebench/sweb.eval.x86_64.example@sha256:" + "a" * 64,
        "atmem-reference-control-" + "b" * 32, "pass")
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--label") + 1] == "atmem.benchmark=external-public-tests-v1"
    assert not any(option in command for option in ("--mount", "-v", "--volume", "-e", "--env", "--privileged"))


def test_bootstrap_has_python39_grammar_and_loads_without_host_packages():
    bootstrap = public_bootstrap()
    ast.parse(bootstrap, feature_version=(3, 9))
    result = subprocess.run([sys.executable, "-I", "-S", "-c", bootstrap], input=b"{}", capture_output=True, timeout=10)
    assert result.returncode != 0
    assert b"exact public-only test request required" in result.stderr
    assert b"ModuleNotFoundError" not in result.stderr


def test_clean_process_exit_alone_is_not_a_qualified_public_test():
    result = {"exit_code": 0, "worker": {"exit_code": 0, "reason": None,
        "output_truncated": False, "output_base64": base64.b64encode(b"3 passed in 0.1s").decode(),
        "original_git_object_store_removed": True, "evaluator_material_received": False}}
    assert success(result)
    result["worker"]["original_git_object_store_removed"] = False
    assert not success(result)
    result["worker"]["original_git_object_store_removed"] = True
    result["worker"]["output_base64"] = base64.b64encode(b"no tests ran").decode()
    assert not success(result)
