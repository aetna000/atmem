import pytest


def test_clear_preview_is_exact_and_preserves_adjacent_scope(code_env):
    from atmem.code.deletion import CodeDeletion
    env = code_env
    env.seed()
    private = env.seed("Remember that my preferred editor is Vim.", profile="private", agent="claude")
    deletion = CodeDeletion(env.app)
    preview = deletion.preview(env.project, profile="shared")
    assert preview["record_count"] == 1
    receipt = deletion.clear(env.project, preview["preview_token"])
    assert receipt["local_verified"] is True
    assert env.app.records(env.project, profile="shared") == []
    assert env.app.records(env.project, profile="private")[0]["id"] == private
    with pytest.raises(ValueError):
        deletion.clear(env.project, preview["preview_token"])


def test_clear_rejects_changed_selection(code_env):
    from atmem.code.deletion import CodeDeletion
    env = code_env
    env.seed()
    deletion = CodeDeletion(env.app)
    preview = deletion.preview(env.project)
    env.seed("Remember that my preferred editor is Vim.")
    with pytest.raises(ValueError, match="changed since preview"):
        deletion.clear(env.project, preview["preview_token"])
    assert len(env.app.records(env.project)) == 2


def test_clear_reports_external_provider_data_as_unconfirmed(code_env):
    from atmem.code.deletion import CodeDeletion
    env = code_env
    env.seed()
    env.memory.store.put_code_document("local", env.project, "route", "external", {"route_id": "external"})
    deletion = CodeDeletion(env.app)
    result = deletion.clear(env.project, deletion.preview(env.project)["preview_token"])
    assert result["local_verified"] is True
    assert result["complete"] is False
    assert result["external_status"] == "not_requested"
