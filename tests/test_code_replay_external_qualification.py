import ast
import base64
import subprocess
import sys
from types import SimpleNamespace
from hashlib import sha256

import pytest

from benchmarks.code_replay.external_qualification import qualifies, worker_command
from benchmarks.code_replay.external_qualification import execute_worker, resource_resume_allowed
from benchmarks.code_replay.external_qualify_worker import validated_files, dependency_wired_module, dependency_wired_tree, TASK_FILES, HARNESS_FILES
from benchmarks.code_replay.external_qualify_worker import TASK_BINDINGS, task_binding, grade


def test_standalone_worker_asset_profile_matches_shared_boundary():
    from benchmarks.code_replay import external_qualify_worker as worker
    from benchmarks.code_replay import source_policy as shared
    assert worker.ASSET_SUFFIXES == shared.ASSET_SUFFIXES
    for name in ("ext/logo.ai", "ext/logo.AI", "src/module.py", "ext/logo.ai.py", "notes.txt"):
        assert worker.file_byte_limit(name) == shared.file_byte_limit(name)
    assert shared.file_byte_limit("src/module.py") == 1_000_000
    assert shared.file_byte_limit("ext/logo.ai") == 4_000_000


@pytest.mark.parametrize("identity", sorted(TASK_BINDINGS))
def test_preselected_task_uses_bound_base_and_upstream_parser(identity):
    base, parser = TASK_BINDINGS[identity]
    assert task_binding(identity, base) == (base, parser)
    value = payload()
    value.update(instance_id=identity, base_commit=base)
    assert validated_files(value, task_identity=identity)["task_files"]["test.patch"] == b"data"
    value["base_commit"] = "0" * 40
    with pytest.raises(ValueError, match="task/base"):
        validated_files(value, task_identity=identity)


@pytest.mark.parametrize("identity", sorted(TASK_BINDINGS))
def test_selected_source_roots_never_admit_tests(identity):
    from benchmarks.code_replay.external_qualify_worker import task_source_roots
    from benchmarks.code_replay.source_policy import SourcePolicy
    roots, tests = task_source_roots(identity, TASK_BINDINGS[identity][0])
    policy = SourcePolicy(roots, test_roots=tests)
    assert policy.source(roots[0] + "module.py")
    assert not policy.source("tests/test_module.py")
    if identity.startswith("pylint-dev"):
        assert not policy.source("astroid/tests/test_module.py")


def test_generic_qualification_does_not_loosen_original_proposal_validator(tmp_path):
    value = payload()
    value.update(instance_id="psf__requests-1327", base_commit=TASK_BINDINGS["psf__requests-1327"][0])
    with pytest.raises(ValueError, match="fixed task"):
        validated_files(value)
    with pytest.raises(ValueError, match="preselected"):
        task_binding("unselected__project-1", "a" * 40)
    with pytest.raises(ValueError, match="parser"):
        grade(b"", {}, {}, tmp_path, parser_name="arbitrary_function")


def entry(raw):
    return {"content_base64": base64.b64encode(raw).decode(), "sha256": sha256(raw).hexdigest()}


def payload():
    task = {name: entry(b"data") for name in TASK_FILES}
    task["eval.sh"] = entry(b"before\ndata\nafter\n")
    return {"phase": "parent", "instance_id": "marshmallow-code__marshmallow-1229", "base_commit": "a" * 40,
            "task_files": task, "harness_files": {name: entry(b"data") for name in HARNESS_FILES}}


def test_role_bound_payload_has_no_hint_or_source_identity_override():
    good = payload()
    assert validated_files(good)["task_files"]["test.patch"] == b"data"
    good["task_files"]["hints.md"] = entry(b"not allowed")
    with pytest.raises(ValueError, match="role-bound"):
        validated_files(good)


def test_evaluator_blob_mutation_rejected():
    value = payload()
    value["task_files"]["gold.patch"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="identity"):
        validated_files(value)


def test_hidden_test_patch_must_match_script_without_modification():
    value = payload()
    value["task_files"]["test.patch"] = entry(b"different tests")
    with pytest.raises(ValueError, match="embedded"):
        validated_files(value)


def test_dependency_wiring_preserves_function_logic_and_defers_annotations():
    raw = b"from absent_library import Type\ndef parser(value: Type):\n    return value + 1\n"
    namespace = dependency_wired_module(raw, {}, "fixture.py")
    assert namespace["parser"](4) == 5
    assert namespace["parser"].__annotations__["value"] == "Type"
    original_function = ast.parse(raw).body[1]
    actual_function = dependency_wired_tree(raw, "fixture.py").body[1]
    assert ast.dump(original_function, include_attributes=False) == ast.dump(actual_function, include_attributes=False)


def test_qualification_needs_actual_failure_not_missing_tests():
    parent = {"exit_code": 0, "worker": {"grading": {"results_found": True, "expected_f2p": 1, "observed_f2p_failures": 1}}}
    reference = {"exit_code": 0, "worker": {"grading": {"results_found": True, "resolution": "RESOLVED_FULL"}}}
    assert qualifies(parent, reference)
    parent["worker"]["grading"]["observed_f2p_failures"] = 0
    assert not qualifies(parent, reference)
    parent["worker"]["grading"]["observed_f2p_failures"] = 1
    reference["reason"] = "controller_timeout"
    assert not qualifies(parent, reference)


def test_evaluator_container_has_no_owner_mounts_network_or_privilege():
    cmd = worker_command("swebench/sweb.eval.x86_64.example@sha256:" + "a" * 64,
                         "atmem-reference-control-" + "b" * 32, "pass")
    assert "--pull=never" in cmd and cmd[cmd.index("--network") + 1] == "none"
    assert "--mount" not in cmd and "--volume" not in cmd and "--privileged" not in cmd
    assert "no-new-privileges" in cmd and "ALL" == cmd[cmd.index("--cap-drop") + 1]


@pytest.mark.parametrize("cleanup_kind", ["timeout", "nonzero", "success", "already_removed"])
def test_cleanup_failure_never_discards_worker_output(monkeypatch, cleanup_kind):
    import benchmarks.code_replay.external_qualification as module
    monkeypatch.setattr(module.shutil, "disk_usage", lambda _: SimpleNamespace(free=10 * 1024 ** 3))

    def cleanup(command, **kwargs):
        if cleanup_kind == "timeout":
            raise subprocess.TimeoutExpired(command, 10)
        if cleanup_kind == "already_removed":
            return SimpleNamespace(returncode=1 if command[1] == "rm" else 0, stdout=b"")
        return SimpleNamespace(returncode=1 if cleanup_kind == "nonzero" else 0, stdout=b"")

    monkeypatch.setattr(module.subprocess, "run", cleanup)
    result = execute_worker([sys.executable, "-c", 'import sys; sys.stdout.buffer.write(b\'{"fixture": true}\\n\')'], {}, "fixture-no-container")
    assert base64.b64decode(result["raw_output_base64"]) == b'{"fixture": true}\n'
    assert result["raw_output_truncated"] is False
    if cleanup_kind in {"success", "already_removed"}:
        assert result["reason"] is None
        assert result["worker"] == {"fixture": True}
    else:
        assert result["reason"] == "container_cleanup_failed"
        assert result["cleanup_error"] is not None


def test_resource_resume_cannot_relabel_executed_or_missing_attempts():
    rows = [{"envelope": {"event_type": "external.reference_attempt", "payload": {
        "phase": phase, "started": False, "reason": "host_free_space_below_8GiB"}}}
        for phase in ("parent", "reference")]
    assert resource_resume_allowed(rows)
    assert not resource_resume_allowed(rows[:1])
    rows[0]["envelope"]["payload"]["started"] = True
    assert not resource_resume_allowed(rows)
    rows[0]["envelope"]["payload"]["started"] = False
    rows[0]["envelope"]["payload"]["worker"] = {"grading": {"results_found": True}}
    assert not resource_resume_allowed(rows)


def test_script_timeout_preserves_both_output_streams(monkeypatch):
    import benchmarks.code_replay.external_qualify_worker as worker

    def expired(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 120, output=b"partial stdout", stderr=b"partial stderr")

    monkeypatch.setattr(worker.subprocess, "run", expired)
    assert worker.execute_script("fixture.sh", {}) == (None, b"partial stdout", b"partial stderr", "script_timeout")


def test_timed_out_worker_cannot_qualify_even_with_passed_markers():
    parent = {"exit_code": 0, "worker": {"grading": {"results_found": True, "expected_f2p": 1, "observed_f2p_failures": 1}}}
    reference = {"exit_code": 0, "worker": {"grading": {"results_found": True, "resolution": "RESOLVED_FULL"}, "worker_failure": "script_timeout"}}
    assert not qualifies(parent, reference)
