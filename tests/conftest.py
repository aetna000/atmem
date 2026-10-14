from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest


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
