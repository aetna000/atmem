import pytest

from benchmarks.code_replay.source_policy import SourcePolicy, collect_source_patch, governed_solution


@pytest.mark.parametrize("root", ["src/marshmallow/", "requests/", "astroid/"])
def test_non_click_sources_and_frozen_tests_are_supported(root):
    source = root + "example.py"
    original = {source: b"old", "tests/test_example.py": b"public", "pyproject.toml": b"fixed"}
    candidate = {**original, source: b"new", "tests/test_example.py": b"solver tests"}
    policy = SourcePolicy((root,))
    proposal = collect_source_patch(original, candidate, policy)
    assert proposal["ignored_test_changes"] == ["tests/test_example.py"]
    frozen = {**original, "tests/test_example.py": b"held-out immutable"}
    result = governed_solution(frozen, proposal, policy)
    assert result[source] == b"new" and result["tests/test_example.py"] == b"held-out immutable"
    assert candidate["tests/test_example.py"] == b"solver tests"


def test_source_deletion_and_addition_do_not_rely_on_git_status():
    policy = SourcePolicy(("package/",))
    original = {"package/old.py": b"old", "tests/test_case.py": b"fixed"}
    candidate = {"package/new.py": b"new", "tests/test_case.py": b"fixed"}
    proposal = collect_source_patch(original, candidate, policy)
    result = governed_solution(original, proposal, policy)
    assert "package/old.py" not in result and result["package/new.py"] == b"new"


def test_configuration_tampering_is_not_silently_ignored():
    original = {"package/code.py": b"old", "pyproject.toml": b"fixed"}
    policy = SourcePolicy(("package/",))
    proposal = collect_source_patch(original, {**original, "pyproject.toml": b"skip tests"}, policy)
    with pytest.raises(PermissionError, match="out-of-scope"):
        governed_solution(original, proposal, policy)


@pytest.mark.parametrize("roots", [("../package/",), ("/package/",), ("./",), ("tests/",), (".git/",)])
def test_unsafe_source_roots_rejected(roots):
    with pytest.raises(ValueError): SourcePolicy(roots)


def test_implementation_inside_protected_tests_is_rejected():
    with pytest.raises(ValueError, match="protected tests"):
        SourcePolicy(("tests/package/",), ("tests/",))


def test_nested_package_tests_remain_frozen():
    policy = SourcePolicy(("package/",), ("package/tests/",))
    original = {"package/code.py": b"old", "package/tests/test_case.py": b"original"}
    candidate = {"package/code.py": b"new", "package/tests/test_case.py": b"fake pass"}
    proposal = collect_source_patch(original, candidate, policy)
    frozen = {**original, "package/tests/test_case.py": b"held-out assertions"}
    assert "package/tests/test_case.py" not in proposal["source_files"]
    assert governed_solution(frozen, proposal, policy)["package/tests/test_case.py"] == b"held-out assertions"


def test_test_injection_in_proposal_cannot_override_frozen_grader():
    policy = SourcePolicy(("package/",))
    proposal = {"out_of_scope_changes": [], "source_files": {"tests/test_case.py": b"pass"}}
    with pytest.raises(PermissionError, match="implementation"):
        governed_solution({"tests/test_case.py": b"real assertions"}, proposal, policy)


def test_non_bytes_snapshot_member_is_not_a_regular_file_proof():
    with pytest.raises(ValueError, match="bytes"):
        collect_source_patch({}, {"package/code.py": "/owner/secret"}, SourcePolicy(("package/",)))
