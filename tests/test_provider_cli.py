from __future__ import annotations

import json
from pathlib import Path

import pytest

from atmem import cli
from atmem.provider_adapters import lifecycle


def run_cli(monkeypatch, capsys, *args: str) -> tuple[str, str]:
    monkeypatch.setattr("sys.argv", ["atmem", *args])
    cli.main()
    captured = capsys.readouterr()
    return captured.out, captured.err


def test_provider_init_is_private_and_does_not_enable_authority(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("ATMEM_PROVIDER_ROOT", str(tmp_path / "providers"))
    output, _ = run_cli(
        monkeypatch, capsys, "provider", "init", "memories", "--kind", "mem0",
        "--factory", "tests.provider_fixtures:mem0_client", "--json",
    )
    result = json.loads(output)
    root = tmp_path / "providers" / "memories"
    assert result["startup_enabled_authority"] is False
    assert result["authority_activation"] == "separate_atmem_delegated_registration"
    assert root.joinpath("config.json").stat().st_mode & 0o777 == 0o600
    assert root.joinpath("private.key").stat().st_mode & 0o777 == 0o600
    assert "--workspace YOUR_WORKSPACE --agent YOUR_AGENT --user YOUR_USER" in result["registration_command"]
    assert "enable" not in result["registration_command"]

    status, _ = run_cli(monkeypatch, capsys, "provider", "status", "--json")
    assert json.loads(status)["providers"][0]["instance"] == "memories"

    with pytest.raises(SystemExit):
        run_cli(monkeypatch, capsys, "provider", "remove", "memories")
    run_cli(monkeypatch, capsys, "provider", "remove", "memories", "--yes", "--json")
    assert not root.exists()


def test_factory_is_required_for_graph_and_agent(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("ATMEM_PROVIDER_ROOT", str(tmp_path / "providers"))
    for kind in ("langgraph", "pydantic-ai"):
        with pytest.raises(SystemExit) as error:
            run_cli(monkeypatch, capsys, "provider", "init", kind, "--kind", kind)
        assert error.value.code == 2


def test_status_does_not_expose_factory_or_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ATMEM_PROVIDER_ROOT", str(tmp_path / "providers"))
    lifecycle.initialize(instance="safe", kind="mem0", port=8788, factory="secret.module:factory")
    value = json.dumps(lifecycle.status("safe"))
    assert "secret.module" not in value
    assert "API_KEY" not in value


def test_provider_cli_guides_legacy_migration_rotation_and_revocation(tmp_path, monkeypatch, capsys):
    from atmem.delegated.transport import load_keyring
    monkeypatch.setenv("ATMEM_PROVIDER_ROOT", str(tmp_path / "providers"))
    lifecycle.initialize(instance="legacy", kind="mem0", port=8788, factory="test:factory")
    root = tmp_path / "providers/legacy"
    # A beta provider had no auth configuration; keep its response keys untouched.
    public_before = (root / "public.key").read_bytes()
    (root / "request-auth.json").unlink()
    assert lifecycle.status("legacy")["request_authentication"] == "migration_required"
    with pytest.raises(ValueError):
        lifecycle.start("legacy")
    output, _ = run_cli(monkeypatch, capsys, "provider", "auth-init", "legacy", "--json")
    old = json.loads(output)
    assert Path(old["request_secret_file"]).read_text().strip() not in output
    output, _ = run_cli(monkeypatch, capsys, "provider", "auth-rotate", "legacy", "--overlap-seconds", "300", "--json")
    new = json.loads(output)
    assert old["request_key_id"] != new["request_key_id"]
    assert len(load_keyring(root / "request-auth.json")["keys"]) == 2
    run_cli(monkeypatch, capsys, "provider", "auth-revoke", "legacy", "--request-key-id", old["request_key_id"], "--json")
    assert len(load_keyring(root / "request-auth.json")["keys"]) == 1
    assert (root / "public.key").read_bytes() == public_before
