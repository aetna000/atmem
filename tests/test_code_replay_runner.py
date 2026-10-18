"""Harness control-flow tests, never historical task-performance evidence."""
import json
from pathlib import Path
import sys
import time

import pytest

from benchmarks.code_replay import runner, history
from benchmarks.code_replay.frozen import digest_files, solution_tree
from benchmarks.code_replay.pilot import summary_counts, usage
from tests.test_knowledge_lifecycle import init_repository, FixtureWorker


def test_grader_uses_only_frozen_tests_and_solver_source():
    grader = {"tests/test_x.py": b"sealed", "pyproject.toml": b"config", "src/click/core.py": b"old"}
    candidate = {"tests/test_x.py": b"cheat", "pyproject.toml": b"cheat", "src/click/core.py": b"fix"}
    result = solution_tree(grader, candidate)
    assert result == {"tests/test_x.py": b"sealed", "pyproject.toml": b"config", "src/click/core.py": b"fix"}
    assert digest_files(result) != digest_files(grader)


def test_measurements_use_last_summary_and_report_missing_tokens_unknown():
    assert summary_counts(b"E assert '100 failed'\n2 failed, 10 passed, 3 skipped in 1.2s\n") == {
        "failed": 2, "passed": 10, "skipped": 3}
    assert usage([])["input_tokens"] is None
    assert usage([{"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 7}}]) == {
        "input_tokens": 100, "output_tokens": 7, "cached_tokens": 20}


def test_parent_exit_does_not_leave_descendant_pipe_hanging(tmp_path, monkeypatch):
    fake = tmp_path / "fake-cli"
    fake.write_text("#!" + sys.executable + "\nimport os,time\nif os.fork()==0:\n time.sleep(30)\nelse:\n os._exit(0)\n")
    fake.chmod(0o700)
    monkeypatch.setattr(runner, "permission_arguments", lambda roots: [])
    workspace, home, temporary = [tmp_path / n for n in ("workspace", "home", "tmp")]
    for path in (workspace, home, temporary):
        path.mkdir()
    started = time.monotonic()
    observed = runner.run_cli(runner.Session(tmp_path, workspace, home, temporary, fake), "probe", max_seconds=1)
    assert time.monotonic() - started < 5
    assert observed["stop_reason"] == "wall_budget"


def test_reaped_parent_never_gets_a_late_group_signal(tmp_path, monkeypatch):
    fake = tmp_path / "fake-cli"
    fake.write_text("#!" + sys.executable + "\nprint('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":1,\"cached_input_tokens\":0,\"output_tokens\":1}}')\n")
    fake.chmod(0o700)
    monkeypatch.setattr(runner, "permission_arguments", lambda roots: [])
    def forbidden(*args):
        raise PermissionError("reused process group must not be signalled")
    monkeypatch.setattr(runner.os, "killpg", forbidden)
    workspace, home, temporary = [tmp_path / name for name in ("workspace", "home", "tmp")]
    for path in (workspace, home, temporary):
        path.mkdir()
    observed = runner.run_cli(runner.Session(tmp_path, workspace, home, temporary, fake), "probe")
    assert observed["exit_code"] == 0 and observed["stop_reason"] is None
    assert usage(observed["events"])["input_tokens"] == 1


def test_product_bridge_does_not_capture_task_prompt_and_requires_typed_report(code_env, monkeypatch):
    env = code_env
    init_repository(env)
    monkeypatch.setattr(history, "ExtractionWorker", lambda image: FixtureWorker())
    lane = history.ProductLane(env.memory, env.root, environment_sha256="a" * 64, experience=True)
    prepared = lane.prepare(run_id="disjoint-harness", task="main function", image_id=FixtureWorker.image_id)
    assert prepared["previous_candidates"] == 0
    assert prepared["exposure"]["graph_evidence"]["knowledge_snapshot_id"]
    assert "AtMem structure" in prepared["package"].content
    assert prepared["package"].memory_ids == ()
    assert lane.capture_report("report", "main", [], ["main.py"])["reason"] == "no_typed_agent_observation"
    assert env.memory.store.code_documents(lane.scope.subject_id, lane.scope.project_id, "code-experience") == []


def test_structure_only_bridge_never_creates_a_partial_execution_identity(code_env, monkeypatch):
    env = code_env
    init_repository(env)
    (env.root / 'large.py').write_bytes(b'#' + b'x' * 2100000)
    monkeypatch.setattr(history, 'ExtractionWorker', lambda image: FixtureWorker())
    lane = history.ProductLane(env.memory, env.root, environment_sha256='a' * 64, experience=False)
    def forbidden(*args, **kwargs):
        raise AssertionError('structure-only must not request an execution identity')
    monkeypatch.setattr(lane.experiences, 'capture_snapshot', forbidden)
    prepared = lane.prepare(run_id='structure-with-omission', task='main function', image_id=FixtureWorker.image_id)
    assert prepared['state_identity'] == 'covered_structure_source'
    assert prepared['index']['excluded_counts']['file_budget'] == 1
    assert prepared['previous_candidates'] == 0 and prepared['applicability'] == []
    assert prepared['package'].memory_ids == ()
    assert 'main' in prepared['package'].content


def test_reduced_protocol_uses_ledger_order_not_branch_authorship_order():
    from benchmarks.code_replay.contracts import StructureExperienceProtocol
    from tests.test_code_replay_two_arm import paired_row
    row = paired_row()
    row["tasks"][1]["solution_cutoff"] = "2020-01-20T00:00:00Z"
    assert StructureExperienceProtocol.from_dict(row).to_dict()["tasks"][1]["order"] == 2
