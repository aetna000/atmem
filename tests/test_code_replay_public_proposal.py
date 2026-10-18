import pytest

from benchmarks.code_replay.source_policy import SourcePolicy, governed_public_proposal


def test_private_runtime_and_frozen_tests_survive_public_source_proposal():
    policy = SourcePolicy(("package/",))
    public = {"package/a.py": b"before", "tests/a.py": b"public test"}
    frozen = {**public, "package/generated.py": b"protected image runtime", "private-metadata": b"private"}
    candidate = {**public, "package/a.py": b"after", "tests/a.py": b"fake test", "package/new.py": b"new source"}
    result, proposal = governed_public_proposal(frozen, public, candidate, policy)
    assert result == {**frozen, "package/a.py": b"after", "package/new.py": b"new source"}
    assert proposal["ignored_test_changes"] == ["tests/a.py"]
    assert not proposal["out_of_scope_changes"]


def test_unchanged_public_tree_is_not_a_deletion_of_image_only_files():
    public = {"package/a.py": b"unchanged"}
    frozen = {**public, "private-runtime": b"keep", "package/generated.py": b"keep too"}
    assembled, proposal = governed_public_proposal(frozen, public, public, SourcePolicy(("package/",)))
    assert assembled == frozen
    assert proposal["changed_paths"] == []


def test_image_only_source_cannot_be_overwritten_as_a_new_file():
    public = {"package/a.py": b"original"}
    frozen = {**public, "package/generated.py": b"private runtime"}
    candidate = {**public, "package/generated.py": b"replacement"}
    with pytest.raises(PermissionError, match="image-only"):
        governed_public_proposal(frozen, public, candidate, SourcePolicy(("package/",)))


def test_wrong_public_base_refused_before_assembly():
    public = {"package/a.py": b"wrong baseline"}
    with pytest.raises(PermissionError, match="differs"):
        governed_public_proposal({"package/a.py": b"actual baseline"}, public, public, SourcePolicy(("package/",)))


def test_public_source_deletion_is_applied_without_deleting_private_runtime():
    public = {"package/a.py": b"deleted", "package/b.py": b"keep"}
    frozen = {**public, "package/generated.py": b"private runtime"}
    assembled, _ = governed_public_proposal(frozen, public, {"package/b.py": b"keep"}, SourcePolicy(("package/",)))
    assert assembled == {"package/b.py": b"keep", "package/generated.py": b"private runtime"}
