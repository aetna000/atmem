from __future__ import annotations

import json
from pathlib import Path
import stat
import tomllib

import pytest

from atmem.control.atbot_service import (
    ATBOT_DISTRIBUTION,
    AtBotServiceManager,
    PINNED_ATBOT_VERSION,
    provider_profiles,
)


def test_pinned_version_matches_the_monorepo_package() -> None:
    value = tomllib.loads(Path("packages/atbot/pyproject.toml").read_text(encoding="utf-8"))
    assert ATBOT_DISTRIBUTION == value["project"]["name"]
    assert PINNED_ATBOT_VERSION == value["project"]["version"]


def test_atbot_is_a_required_pinned_atmem_dependency() -> None:
    value = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert f"{ATBOT_DISTRIBUTION}=={PINNED_ATBOT_VERSION}" in value["project"][
        "dependencies"
    ]


def test_private_installer_resolves_only_the_owned_distribution(
    tmp_path: Path, monkeypatch
) -> None:
    manager = AtBotServiceManager(tmp_path / "atbot")
    commands: list[list[str]] = []

    def run(command, **kwargs):
        commands.append([str(value) for value in command])

    monkeypatch.setattr("atmem.control.atbot_service.subprocess.run", run)
    result = manager.install()

    assert commands[1][-1] == f"atmem-atbot=={PINNED_ATBOT_VERSION}"
    assert all(command[-1] != f"atbot=={PINNED_ATBOT_VERSION}" for command in commands)
    assert result["package"] == f"atmem-atbot=={PINNED_ATBOT_VERSION}"


def test_profiles_cover_local_frontier_and_custom_providers_without_secrets() -> None:
    profiles = provider_profiles()
    assert {
        "local-ollama",
        "local-openai",
        "openrouter",
        "openai",
        "deepseek",
        "xai",
        "anthropic",
        "huggingface",
        "custom-api",
    } <= set(profiles)
    assert profiles["anthropic"]["kind"] == "anthropic"
    assert profiles["huggingface"]["endpoint"] == "https://router.huggingface.co/v1"
    assert all("api_key" not in row for row in profiles.values())


def test_configure_is_private_local_first_and_has_no_authority_fields(tmp_path: Path) -> None:
    manager = AtBotServiceManager(tmp_path / "atbot")
    result = manager.configure()
    value = json.loads(Path(result["config_path"]).read_text(encoding="utf-8"))

    assert stat.S_IMODE(Path(result["config_path"]).stat().st_mode) == 0o600
    assert value["remote_egress_allowed"] is False
    assert value["providers"][0]["endpoint"] == "http://127.0.0.1:11434"
    assert not ({"memory_path", "subject_id", "workspace_id", "agent_id"} & set(value))


def test_configure_requires_explicit_remote_egress(tmp_path: Path) -> None:
    manager = AtBotServiceManager(tmp_path / "atbot")
    with pytest.raises(ValueError, match="remote-egress-allowed"):
        manager.configure(endpoint="https://models.example.test/v1")


def test_hosted_profile_stores_only_the_key_variable_name(tmp_path: Path) -> None:
    manager = AtBotServiceManager(tmp_path / "atbot")
    result = manager.configure(profile="openrouter", model="anthropic/claude-sonnet-4.5")
    provider = result["config"]["providers"][0]
    assert result["config"]["remote_egress_allowed"] is True
    assert provider["api_key_env"] == "OPENROUTER_API_KEY"
    assert provider["endpoint"] == "https://openrouter.ai/api/v1"
    assert "OPENROUTER_API_KEY" in result["setup_actions"][0]
    assert "sk-" not in json.dumps(result)


def test_skip_preference_prevents_repeated_first_run_prompt(tmp_path: Path) -> None:
    manager = AtBotServiceManager(tmp_path / "atbot")
    assert manager.skip_setup()["skipped"] is True
    assert manager.preference_path.is_file()
    manager.configure(force=True)
    assert not manager.preference_path.exists()


def test_missing_service_reports_exact_setup_actions(tmp_path: Path, monkeypatch) -> None:
    manager = AtBotServiceManager(tmp_path / "atbot")
    monkeypatch.setattr(manager, "_executable", lambda: None)
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.health",
        lambda self: {"available": False, "reason": "not running"},
    )

    status = manager.status()
    assert status["running"] is False
    assert status["compatible"] is False
    assert status["setup_actions"] == [
        "Run `atmem atbot install`.",
        "Run `atmem atbot configure`.",
    ]
    assert manager.doctor()["degraded_safe"] is True


def test_status_never_exposes_csrf_and_fallback_disables_available_state(
    tmp_path: Path, monkeypatch
) -> None:
    manager = AtBotServiceManager(tmp_path / "atbot")
    manager.skip_setup()
    monkeypatch.setattr(manager, "_executable", lambda: None)
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.health",
        lambda self: {
            "available": True,
            "csrf_token": "private-companion-secret",
            "canonical_storage": False,
        },
    )

    status = manager.status()
    assert status["running"] is True
    assert status["available"] is False
    assert status["fallback_selected"] is True
    assert "csrf_token" not in status["health"]
    assert "private-companion-secret" not in json.dumps(status)
