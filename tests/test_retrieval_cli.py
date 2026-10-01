import json
import sys

import pytest

from atmem import Memory
from atmem import cli
from atmem.contracts import AuthorityScope, EpisodeIngestRequest, EpisodePart
from atmem.core.canonical import sha256_hex


def test_retrieval_cli_status_and_verified_explanation(tmp_path, monkeypatch, capsys):
    path = tmp_path / "retrieval.db"
    scope = AuthorityScope("cli-person", "cli-agent", "cli-workspace")
    text = "I am 45 years old."
    memory = Memory(path, auto_vectors=False, allow_insecure_typed_development=True)
    try:
        memory.form_episode(EpisodeIngestRequest(
            episode_id="cli-age", idempotency_key="cli-age-key", scope=scope,
            parts=(EpisodePart(
                part_id="age", ordinal=0, kind="text", source_type="user_message",
                content=text, content_sha256=f"sha256:{sha256_hex(text)}",
            ),),
        ))
    finally:
        memory.close()

    common = [str(path), "--subject", scope.subject_id, "--agent", scope.agent_id,
              "--workspace", scope.workspace_id, "--json"]
    monkeypatch.setattr(sys, "argv", ["atmem", "retrieval", "status", *common])
    cli.main()
    status = json.loads(capsys.readouterr().out)
    assert status["typed_units"][0]["count"] == 1
    assert status["activation"]["mode"] == "legacy"

    monkeypatch.setattr(sys, "argv", ["atmem", "retrieval", "setup", *common])
    cli.main()
    setup = json.loads(capsys.readouterr().out)
    assert setup["mode"] == "shadow"

    monkeypatch.setattr(sys, "argv", ["atmem", "retrieval", "rollback", *common])
    cli.main()
    rollback = json.loads(capsys.readouterr().out)
    assert rollback["mode"] == "legacy"

    monkeypatch.setattr(sys, "argv", ["atmem", "retrieval", "activate", *common])
    with pytest.raises(SystemExit) as blocked:
        cli.main()
    assert blocked.value.code == 2
    activation_error = json.loads(capsys.readouterr().out)
    assert "encrypted household" in activation_error["error"]

    monkeypatch.setattr(
        sys, "argv",
        ["atmem", "retrieval", "explain", *common, "How old am I?", "--verify"],
    )
    cli.main()
    explanation = json.loads(capsys.readouterr().out)
    assert explanation["need"]["type"] == "exact_fact"
    assert explanation["verification"]["sufficiency"]["status"] == "sufficient"
    assert "45" in explanation["verification"]["context_preview"]


def test_retrieval_cli_form_is_source_linked_and_fail_closed(tmp_path, monkeypatch, capsys):
    path = tmp_path / "retrieval.db"
    argv = [
        "atmem", "retrieval", "form", str(path),
        "--subject", "cli-person", "--agent", "cli-agent",
        "--workspace", "cli-workspace", "--json",
        "--episode-id", "cli-form-age", "--idempotency-key", "cli-form-age-v1",
        "--text", "I am 45 years old.",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    result = json.loads(capsys.readouterr().out)
    assert result["receipt"]["source_events_observed"] == 1
    assert result["outcomes"][0]["review_state"] == "rejected"
    assert "typed_memory_requires_encrypted_household" in result["outcomes"][0]["reason_codes"]
