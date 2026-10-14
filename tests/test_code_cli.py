import pytest


def test_search_inspection_correction_and_scope_checks_share_one_boundary(code_env):
    from atmem.code.application import CodeApplication
    env = code_env
    record = env.seed()
    assert "Ruff" in env.app.dispatch("search", {"project_id": env.project, "query": "formatter"})["records"][0]["content"]
    assert env.app.inspect(env.project, record)["source"]["message"]
    replacement = env.app.correct(env.project, record, "My preferred formatter is Black.")
    current = env.app.records(env.project)
    assert [row["id"] for row in current] == [replacement["record"]["id"]]
    assert "Black" in current[0]["content"]
    assert env.app.records(env.project, agent="codex", memory_class="preference")[0]["id"] == current[0]["id"]
    assert env.app.records(env.project, agent="claude") == []
    with pytest.raises(PermissionError):
        CodeApplication(env.memory, subject_id="other").inspect(env.project, record)


def test_config_validation_and_private_lane_filters(code_env):
    env = code_env
    env.seed()
    private = env.seed("Remember that my preferred editor is Vim.", profile="private", agent="claude")
    assert env.app.records(env.project, profile="private", agent="claude")[0]["id"] == private
    assert env.app.records(env.project, profile="private", agent="codex") == []
    assert env.app.settings(env.project, {"auto_capture": False})["auto_capture"] is False
    with pytest.raises(ValueError):
        env.app.settings(env.project, {"max_context_bytes": True})
    with pytest.raises(ValueError):
        env.app.settings(env.project, {"disable_scope_enforcement": True})
