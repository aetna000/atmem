import ast
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from benchmarks.code_replay.external_source_boundary import bootstrap_source, boundary_qualified


def fixture_results():
    rows = {}
    for phase in ("unchanged", "reference_as_proposal"):
        reference = phase == "reference_as_proposal"
        rows[phase] = {"exit_code": 0, "reason": None, "worker": {
            "phase": phase, "base_source_verified": True, "assembled_bytes_verified": True,
            "source_policy": {"source_roots": ["src/marshmallow/"], "test_roots": ["tests/"]},
            "original_sha256": "a" * 64, "candidate_sha256": ("b" if reference else "a") * 64,
            "assembled_sha256": ("b" if reference else "a") * 64,
            "changed_paths": ["src/marshmallow/fixture.py"] if reference else [],
            "ignored_test_changes": [], "out_of_scope_changes": [], "grading": {
                "results_found": True, "expected_f2p": 8, "expected_p2p": 61,
                "p2p_success": 61, "p2p_failure": 0, "p2p_skipped": 0,
                "f2p_success": 8 if reference else 0, "f2p_failure": 0 if reference else 8,
                "observed_f2p_failures": 0 if reference else 8,
                "resolution": "RESOLVED_FULL" if reference else "RESOLVED_NO"}}}
    return rows


def test_fixed_control_needs_both_actual_outcomes():
    rows = fixture_results()
    assert boundary_qualified(rows)
    assert not boundary_qualified({"unchanged": rows["unchanged"]})
    rows["unchanged"]["worker"]["grading"]["observed_f2p_failures"] = 0
    assert not boundary_qualified(rows)


def test_operator_bound_counts_and_roots_do_not_change_default_verification():
    rows = fixture_results()
    for phase, row in rows.items():
        reference = phase == "reference_as_proposal"
        w = row["worker"]
        w["source_policy"] = {"source_roots": ["requests/"], "test_roots": ["tests/"]}
        w["changed_paths"] = ["requests/module.py"] if reference else []
        w["grading"].update(expected_f2p=1, expected_p2p=31, p2p_success=31,
            f2p_success=1 if reference else 0, f2p_failure=0 if reference else 1,
            observed_f2p_failures=0 if reference else 1)
    assert not boundary_qualified(rows)
    assert boundary_qualified(rows, expected_f2p=1, expected_p2p=31, source_roots=("requests/",))
    rows["reference_as_proposal"]["worker"]["grading"]["p2p_success"] = 30
    assert not boundary_qualified(rows, expected_f2p=1, expected_p2p=31, source_roots=("requests/",))


@pytest.mark.parametrize("change", ["test_skip", "timeout", "out_of_scope", "missing_digest", "changed_policy", "unverified_bytes"])
def test_failure_and_boundary_violations_never_qualify(change):
    rows = fixture_results()
    worker = rows["reference_as_proposal"]["worker"]
    if change == "test_skip":
        worker["grading"]["p2p_skipped"] = 1
    elif change == "timeout":
        worker["worker_failure"] = "script_timeout"
    elif change == "out_of_scope":
        worker["out_of_scope_changes"] = ["pyproject.toml"]
    elif change == "missing_digest":
        del worker["assembled_sha256"]
    elif change == "changed_policy":
        worker["source_policy"]["source_roots"] = ["tests/"]
    else:
        worker["assembled_bytes_verified"] = False
    assert not boundary_qualified(rows)


def test_bootstrap_embeds_operator_modules_and_is_python39_compatible():
    source = bootstrap_source("# trusted pinned control source\n")
    ast.parse(source, feature_version=(3, 9))
    assert "# trusted pinned control source" in source
    assert "source_capture" in source and "source_policy" in source
    assert "external_candidate_worker.py" in source
    assert "# changed control source" in bootstrap_source("# changed control source\n")


def test_assembled_tree_cannot_keep_candidate_hidden_tests(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "atmem_external_control", SimpleNamespace())
    spec = importlib.util.spec_from_file_location("atmem_candidate_test", Path("benchmarks/code_replay/external_candidate_worker.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "package").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "package/a.py").write_bytes(b"fixed")
    (tmp_path / "tests/a.py").write_bytes(b"fake pass")
    current = {"package/a.py": b"fixed", "tests/a.py": b"fake pass"}
    assembled = {"package/a.py": b"fixed", "tests/a.py": b"frozen tests"}
    module.install_tree(tmp_path, current, assembled)
    assert (tmp_path / "tests/a.py").read_bytes() == b"frozen tests"


def test_worker_modules_have_python39_grammar():
    for name in ("external_candidate_worker.py", "source_policy.py", "source_capture.py"):
        ast.parse((Path("benchmarks/code_replay") / name).read_text(), feature_version=(3, 9))
