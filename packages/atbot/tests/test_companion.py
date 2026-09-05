from __future__ import annotations

import importlib.util
import json
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from atbot.cli import _parser
from atbot.companion import CompanionRuntime
from atbot.config import AtBotConfig
from atbot.config import ProviderConfig
from atbot.domain import ProviderResult
from atbot.providers.anthropic import AnthropicProvider
from atbot.providers.openai_compatible import OpenAICompatibleProvider
from atbot.providers.router import ModelRouter


def companion() -> CompanionRuntime:
    return CompanionRuntime(AtBotConfig(providers=[]))


def test_public_companion_has_no_independent_agent_or_storage() -> None:
    capabilities = companion().capabilities()

    assert capabilities["role"] == "atmem-intelligence-companion"
    assert capabilities["protocol_version"] == "1"
    assert capabilities["version"]
    assert capabilities["independent_agent"] is False
    assert capabilities["canonical_storage"] is False


def test_router_supports_native_anthropic_without_changing_authority(monkeypatch) -> None:
    monkeypatch.setattr(AnthropicProvider, "available", lambda self: True)
    router = ModelRouter(
        AtBotConfig(
            remote_egress_allowed=True,
            providers=[
                ProviderConfig(
                    name="anthropic",
                    kind="anthropic",
                    model="claude-sonnet-4-5",
                    endpoint="https://api.anthropic.com/v1",
                    api_key_env="ANTHROPIC_API_KEY",
                    egress_class="remote",
                )
            ],
        )
    )
    selected = router.select(remote=True)
    assert isinstance(selected, AnthropicProvider)
    assert selected.egress_class == "remote"


def test_router_uses_sdk_independent_openai_compatible_provider(monkeypatch) -> None:
    monkeypatch.setattr(OpenAICompatibleProvider, "available", lambda self: True)
    router = ModelRouter(AtBotConfig())

    selected = router.select()

    assert isinstance(selected, OpenAICompatibleProvider)


def test_removed_authority_and_agent_modules_are_not_packaged() -> None:
    assert importlib.util.find_spec("atbot.agent") is None
    assert importlib.util.find_spec("atbot.runtime") is None
    assert importlib.util.find_spec("atbot.gateway") is None
    assert importlib.util.find_spec("atbot.capabilities") is None


def test_cli_exposes_companion_operations_only() -> None:
    parser = _parser()
    subparsers = next(
        action for action in parser._actions if hasattr(action, "choices") and action.choices
    )

    assert set(subparsers.choices) == {"init", "status", "doctor", "serve"}


def test_package_does_not_depend_on_atmem_authority_code() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]

    assert all(
        not str(requirement).partition("[")[0].casefold().startswith("atmem")
        for requirement in project["dependencies"]
    )


def test_config_has_no_memory_or_authority_identity() -> None:
    value = AtBotConfig(providers=[]).to_dict()

    assert "memory_path" not in value
    assert "subject_id" not in value
    assert "agent_id" not in value
    assert "workspace_id" not in value
    assert "allowed_tools" not in value
    assert "skill_directories" not in value


def test_legacy_config_is_read_but_authority_fields_are_discarded() -> None:
    value = AtBotConfig.from_dict(
        {
            "format": "atbot-config-v1",
            "profile": "memory-companion",
            "host": "127.0.0.1",
            "port": 8770,
            "remote_egress_allowed": False,
            "providers": [],
            "memory_path": "/tmp/retired-atbot.db",
            "subject_id": "retired-subject",
            "agent_id": "retired-agent",
            "workspace_id": "retired-workspace",
            "recent_message_limit": 10,
            "max_task_steps": 8,
            "allowed_tools": ["memory_recall"],
            "skill_directories": [],
        }
    ).to_dict()

    assert set(value) == {
        "format",
        "profile",
        "host",
        "port",
        "remote_egress_allowed",
        "providers",
    }
    assert "/tmp/retired-atbot.db" not in json.dumps(value)


def test_companion_ranks_only_ids_supplied_by_atmem() -> None:
    result = companion().answer_query(
        query="What do you remember about me?",
        candidates=[{"record_id": "rec_allowed", "content": "User likes blue cars."}],
    )

    assert result["ranked_record_ids"] == ["rec_allowed"]
    assert "blue cars" in result["answer"]


class _CapturingProvider:
    name = "test"
    model = "capture"
    egress_class = "local"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.payload = None

    def complete(self, *, system, prompt, schema=None):
        del system, schema
        self.payload = json.loads(prompt)
        if self.fail:
            raise RuntimeError("provider failed")
        allowed = self.payload["eligible_memories"]
        value = {
            "answer": "Supported answer.",
            "ranked_record_ids": ["rec_unknown", allowed[-1]["record_id"]],
            "explanation": "test ranking",
        }
        return ProviderResult(
            text=json.dumps(value),
            structured=value,
            provider=self.name,
            model=self.model,
            egress_class=self.egress_class,
        )


def test_companion_forwards_only_bounded_opaque_support_signals(monkeypatch) -> None:
    runtime = companion()
    provider = _CapturingProvider()
    monkeypatch.setattr(runtime.router, "select", lambda **kwargs: provider)
    signals = {
        "support_aggregation_version": "supporting-evidence-v1",
        "record_score": 0.8,
        "support_score": 0.7,
        "aggregate_score": 0.821,
        "eligible_support_count": 2,
        "support_group_id": "sgrp_" + "a" * 64,
        "source_session_id": "must-not-egress",
        "unbounded_internal_value": "must-not-egress",
    }
    result = runtime.answer_query(
        query="Which evidence applies?",
        candidates=[
            {
                "record_id": "rec_first",
                "content": "First eligible memory.",
                "score": 0.821,
                "signals": signals,
            },
            {
                "record_id": "rec_second",
                "content": "Second eligible memory.",
                "score": 0.7,
            },
        ],
    )

    forwarded = provider.payload["eligible_memories"][0]
    assert forwarded["support_group_id"] == "sgrp_" + "a" * 64
    assert forwarded["aggregate_score"] == 0.821
    assert "source_session_id" not in json.dumps(provider.payload)
    assert "unbounded_internal_value" not in json.dumps(provider.payload)
    assert result["ranked_record_ids"] == ["rec_second"]


def test_companion_provider_failure_uses_first_aggregate_order(monkeypatch) -> None:
    runtime = companion()
    provider = _CapturingProvider(fail=True)
    monkeypatch.setattr(runtime.router, "select", lambda **kwargs: provider)
    result = runtime.answer_query(
        query="Which evidence applies?",
        candidates=[
            {"record_id": "rec_supported", "content": "Supported evidence.", "score": 0.9},
            {"record_id": "rec_decoy", "content": "Decoy evidence.", "score": 0.8},
        ],
    )
    assert result["ranked_record_ids"] == ["rec_supported"]
    assert result["model"] == "eligible-candidate-fallback-v1"


def test_companion_overview_removes_source_template_noise() -> None:
    result = companion().answer_query(
        query="What do you remember about me?",
        candidates=[
            {"record_id": "rec_fact", "content": "JT likes burgers."},
            {"record_id": "rec_heading", "content": "# USER.md - About Your Human."},
            {
                "record_id": "rec_template",
                "content": "Learn about the person you're helping. Update this as you go.",
            },
        ],
    )

    assert result["ranked_record_ids"] == ["rec_fact"]
    assert "USER.md" not in result["answer"]


def test_query_expansion_is_content_free_and_bounded() -> None:
    result = companion().expand_query("what is my fav food")

    assert result["content_received"] is False
    assert "food preference" in result["expanded_queries"]
    assert len(result["expanded_queries"]) <= 6


def test_companion_proposes_but_never_admits_or_stores() -> None:
    result = companion().propose_memories("I prefer window seats")

    assert result["format"] == "atbot-memory-proposals-v1"
    assert result["proposals"][0]["fact"] == "I prefer window seats"
    assert result["authority_decision"] is None
    assert result["canonical_storage"] is False
    assert result["proposals"][0]["related_record_ids"] == []


def test_companion_does_not_propose_questions() -> None:
    result = companion().propose_memories("What food do I prefer?")

    assert result["proposals"] == []


def test_companion_proposes_task_delta_without_claiming_authority(monkeypatch) -> None:
    runtime = companion()

    class _TaskProvider:
        name = "test"
        model = "task-reader"
        egress_class = "none"

        def complete(self, *, system, prompt, schema=None):
            return ProviderResult(
                text="",
                structured={
                    "operations": [
                        {
                            "kind": "set_item_status",
                            "item_id": "item-1",
                            "status": "completed",
                        }
                    ]
                },
                provider=self.name,
                model=self.model,
                egress_class=self.egress_class,
            )

    monkeypatch.setattr(runtime.router, "select", lambda **kwargs: _TaskProvider())
    result = runtime.propose_task_state(
        snapshot={
            "task_id": "task-1",
            "revision": 3,
            "phase": "execute",
            "phases": ["execute", "complete"],
            "items": [{"item_id": "item-1", "status": "running"}],
            "constraints": [],
            "sources_to_inspect": [],
        },
        observation="The item completed.",
        task_id="task-1",
        base_revision=3,
    )

    assert result["delta"]["base_revision"] == 3
    assert result["authority_decision"] is None
    assert result["canonical_storage"] is False
    assert runtime.capabilities()["features"]["task_state_proposals"] is True
