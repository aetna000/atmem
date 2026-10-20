import ast
from hashlib import sha256
from pathlib import Path

import pytest

from benchmarks.code_replay.runtime_projection_control import (
    projected_control_source, projection_program,
)
from benchmarks.code_replay.external_source_boundary import bootstrap_source


def registration():
    return {
        "bindings": {"pylint-dev__pylint-5730": ["a" * 40, "parse_log_pytest"]},
        "source_profiles": {"pylint-dev__pylint-5730": [["pylint/"], ["tests/"]]},
    }


def test_projection_registration_preserves_upstream_grading_and_is_not_request_selected():
    original = Path("benchmarks/code_replay/external_qualify_worker.py").read_text()
    projected, proof = projected_control_source(original, registration())
    assert projected.replace(proof["registration_source"], "") == original
    assert proof["prior_worker_sha256"] == sha256(original.encode()).hexdigest()
    assert proof["upstream_grading_logic_changed"] is False
    for program in (projection_program(projected, diagnostic=True),
                    projection_program(projected),
                    bootstrap_source(projected, result_transport="zlib-v1", runtime_projection=True)):
        ast.parse(program, feature_version=(3, 9))
        assert "atmem-source-runtime-projection-v2" in program
    default = bootstrap_source(original)
    default_globals = ast.literal_eval(ast.parse(default).body[-1].value.args[1])
    assert default_globals == {"__name__": "__main__"}


def test_unknown_or_widened_registration_refused():
    original = Path("benchmarks/code_replay/external_qualify_worker.py").read_text()
    changed = registration()
    changed["source_profiles"]["pylint-dev__pylint-5730"] = [["other/"], ["tests/"]]
    with pytest.raises(ValueError):
        projected_control_source(original, changed)
    with pytest.raises(ValueError):
        projected_control_source(original, {"bindings": {}, "source_profiles": {}})
    with pytest.raises(ValueError):
        bootstrap_source(original, runtime_projection="v2")


def test_codec_only_program_matches_complete_bootstrap_not_brace_spelling():
    from benchmarks.code_replay.windows_runtime_projection import codec_only_program
    from benchmarks.code_replay.runtime_projection_control import projection_modules
    source = Path('benchmarks/code_replay/external_qualify_worker.py').read_text()
    prior = {'program': bootstrap_source(source, result_transport='zlib-v1', runtime_projection=True),
             'modules': projection_modules()}
    codec = Path('benchmarks/code_replay/result_transport.py').read_text()
    assert codec_only_program(prior, codec) == bootstrap_source(
        source, result_transport='lzma-v2', runtime_projection=True)
    with pytest.raises(ValueError):
        codec_only_program({**prior, 'program': prior['program'].replace('.result_printer()', '.unknown()')}, codec)


def test_candidate_assembly_preserves_and_reverifies_opaque_fixtures(tmp_path, monkeypatch):
    import importlib.util
    import sys
    from types import SimpleNamespace
    from benchmarks.code_replay.runtime_fixtures import tracked_projection
    from benchmarks.code_replay.source_policy import SourcePolicy
    from tests.test_code_replay_runtime_fixtures import fixture
    monkeypatch.setitem(sys.modules, "atmem_external_control", SimpleNamespace())
    specification = importlib.util.spec_from_file_location("fixture_assembly",
        Path("benchmarks/code_replay/external_candidate_worker.py"))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    tree = fixture(tmp_path)
    policy = SourcePolicy(("package/",), test_roots=("tests/",))
    source, manifest, _ = tracked_projection(tmp_path, tree, policy, writers_stopped=True)
    candidate = {"package/code.py": b"x = 2\n"}
    module.install_tree(tmp_path, source, candidate, runtime_manifest=manifest, runtime_policy=policy)
    assert (tmp_path / "package/code.py").read_bytes() == b"x = 2\n"
    assert (tmp_path / "tests/link.py").is_symlink()
    assert (tmp_path / "doc/large.png").stat().st_size == 4_100_008
    (tmp_path / "tests/link.py").unlink()
    with pytest.raises(ValueError):
        module.install_tree(tmp_path, candidate, candidate, runtime_manifest=manifest, runtime_policy=policy)
