import pytest

from benchmarks.code_replay.derived_runtime import (
    distribution_change_qualified, local_worker_command, vtk_recipe, qualified_build_records,
)


def test_local_content_identity_is_explicit_not_an_extension_of_ordinary_image_policy():
    from benchmarks.code_replay.external_qualification import worker_command
    identity = "sha256:" + "a" * 64
    name = "atmem-reference-control-" + "b" * 32
    command = local_worker_command(identity, name, "print('fixture')")
    assert identity in command and "--pull=never" in command
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--cpus") + 1] == "1"
    with pytest.raises(ValueError):
        worker_command(identity, name, "")
    with pytest.raises(ValueError):
        local_worker_command("mutable:latest", name, "")


def test_only_fixed_vtk_distribution_may_change():
    before = [{"name": "vtk", "version": "9.4.2"}, {"name": "setuptools", "version": "78.1.1"},
              {"name": "wheel", "version": "0.45.1"}, {"name": "other", "version": "1"}]
    after = [{**row, "version": "9.3.1"} if row["name"] == "vtk" else dict(row) for row in before]
    assert distribution_change_qualified(before, after)
    after[-1]["version"] = "2"
    assert not distribution_change_qualified(before, after)
    after[-1]["version"] = "1"
    assert not distribution_change_qualified(before, after[:-1])
    with pytest.raises(ValueError):
        distribution_change_qualified(before, after + [after[-1]])


def test_recipe_is_offline_and_does_not_modify_source_tests_or_build_dependency_versions():
    wheels = [{"package": name, "version": version, "filename": name + "-" + version + "-fixture.whl",
               "bytes": 12, "sha256": "a" * 64}
              for name, version in [("vtk", "9.3.1"), ("setuptools", "78.1.1"), ("wheel", "0.45.1")]]
    recipe = vtk_recipe("swebench/sweb.eval.x86_64.pyvista_1776_pyvista-4226@sha256:" + "a" * 64, wheels)
    assert "--no-index --no-deps" in recipe and "PIP_FIND_LINKS=" in recipe
    assert " /testbed" not in recipe and "pip install setuptools" not in recipe
    wheels[0]["version"] = "9.3.0"
    with pytest.raises(ValueError):
        vtk_recipe("swebench/sweb.eval.x86_64.pyvista_1776_pyvista-4226@sha256:" + "a" * 64, wheels)


def test_complete_pool_does_not_require_imputing_or_retrying_failed_builds():
    records = [{"instance_id": "task-" + str(i), "transport_exit": 0,
                "result": {"qualified": i != 7, "failure": "version_guard" if i == 7 else None}}
               for i in range(8)]
    expected = {row["instance_id"] for row in records}
    summary = {"original_candidates": 8, "qualified_identities": sorted(expected - {"task-7"})}
    assert [r["instance_id"] for r in qualified_build_records(records, summary, expected)] == [
        "task-" + str(i) for i in range(7)]
    with pytest.raises(ValueError, match="eight terminal"):
        qualified_build_records(records[:-1], summary, expected)
    with pytest.raises(ValueError, match="eight terminal"):
        qualified_build_records(records[:-1] + [records[0]], summary, expected)
    with pytest.raises(ValueError, match="summary differs"):
        qualified_build_records(records, {**summary, "qualified_identities": sorted(expected)}, expected)
    with pytest.raises(ValueError, match="summary differs"):
        qualified_build_records(records, {**summary, "qualified_identities": ["task-0"] * 7}, expected)
