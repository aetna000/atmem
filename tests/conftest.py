from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest


def pytest_collection_modifyitems(items):
    """Keep POSIX benchmark-controller qualification separate from product OS support.

    These operators deliberately require dir_fd/O_DIRECTORY, process groups or
    Linux cgroups. Windows executes that controller in WSL/Linux, not natively.
    Do not suppress any AtMem product/adapter test here. macOS/Linux run them all.
    """
    import os
    if os.name!='nt':return
    modules={
        'test_code_replay_appserver_probe.py',
        'test_code_replay_confirmation_exports.py',
        'test_code_replay_confirmation_staging.py',
        'test_code_replay_corrective_execution.py',
        'test_code_replay_external_solver_source.py',
        'test_code_replay_external_source_boundary.py',
        'test_code_replay_public_test_bridge.py',
        'test_code_replay_public_tests.py',
        'test_code_replay_runner.py',
        'test_code_replay_runtime_fixtures.py',
        'test_code_replay_runtime_projection_control.py',
        'test_code_replay_solver_proposal.py',
        'test_swebench_transport_recovery.py',
        'test_swebench_warm_queries.py',
    }
    cases={
        ('test_code_replay_evidence.py','test_dead_solver_event_recovery_from_protected_backup_in_new_process'),
        ('test_swebench_pilot.py','test_new_product_runtime_is_explicitly_pinned_and_benchmark_scoped'),
        ('test_code_replay_windows_archive.py','test_keys_must_not_be_exported_to_external_volume'),
        ('test_context_engine_performance.py','test_performance_qualification_freezes_50k_and_100k_gates'),
    }
    for item in items:
        if item.path.name in modules or (item.path.name,item.originalname) in cases:
            item.add_marker(pytest.mark.skip(reason='POSIX-only replay/benchmark controller; native Windows product paths remain tested'))


@pytest.fixture
def code_env(tmp_path):
    from atmem.code.application import CodeApplication
    from atmem.code.contracts import CodeObservation, CodeScope
    from atmem.code.formation import CodeFormation
    from atmem.code.identity import CodeIdentity
    from atmem.memory import Memory

    memory = Memory(":memory:", auto_vectors=False)
    scope = CodeIdentity(memory.store).resolve(tmp_path, subject_id="local", profile_id="shared", agent_id="codex")
    app = CodeApplication(memory, subject_id="local")

    def seed(text="Remember that my preferred formatter is Ruff.", *, profile="shared", agent="codex"):
        lane = CodeScope("local", scope.project_id, profile, agent)
        event = CodeObservation("event-" + uuid4().hex, "session-1", "turn-" + uuid4().hex,
                                agent if agent in {"codex", "claude", "muse", "grok", "copilot"} else "test",
                                "user_turn", text, "2026-10-14T10:00:00+00:00", "conversation:turn", None, lane)
        result = CodeFormation(memory).form(event)
        assert result["formed"], result
        return result["record_ids"][0]

    yield SimpleNamespace(memory=memory, app=app, scope=scope, project=scope.project_id, root=tmp_path, seed=seed)
    memory.close()
