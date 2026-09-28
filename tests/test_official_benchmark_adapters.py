from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

import pytest


ROOT = Path(__file__).parents[1]
LONGMEM_ASSET = (
    ROOT / "research/production_benchmarks/adapters/longmemeval_atmem.py"
)
DOLPHIN_ADAPTER = ROOT / "research/production_benchmarks/dolphinbench.py"


def test_longmem_adapter_is_inert_product_api_only() -> None:
    source = LONGMEM_ASSET.read_text(encoding="utf-8")
    forbidden = (
        "question_type", "expected_answer", "gold", "accessibility_tree",
        "axtree", "chunk", "._conn", ".store", "memory_proposals",
    )
    assert all(term not in source.casefold() for term in forbidden)
    assert "form_episode" in source
    assert "eligible_candidates" in source
    assert "prepare_context_v2" in source


def test_longmem_registry_patch_rejects_unrelated_edits(
    tmp_path: Path, monkeypatch
) -> None:
    from research.production_benchmarks import longmemeval_v2

    original = b"from .memory import Memory\n"
    registry = tmp_path / "memory.py"
    monkeypatch.setattr(longmemeval_v2, "_git_blob", lambda _root, _name: original)
    registry.write_text(
        original.decode().rstrip() + "\n" + longmemeval_v2.IMPORT_LINE + "\n",
        encoding="utf-8",
    )
    assert longmemeval_v2._is_expected_registry_patch(tmp_path, registry)

    registry.write_text(
        "UNREVIEWED = True\n" + registry.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    assert not longmemeval_v2._is_expected_registry_patch(tmp_path, registry)


def test_longmem_adapter_preserves_official_state_media_and_native_trust(
    tmp_path: Path, monkeypatch
) -> None:
    registry: dict[str, type] = {}

    class OfficialMemory:
        memory_type = ""

        def __init__(self, memory_params):
            self.memory_params = dict(memory_params)

    def register(cls):
        registry[cls.memory_type] = cls
        return cls

    package = ModuleType("memory_modules")
    module = ModuleType("memory_modules.memory")
    module.Memory = OfficialMemory  # type: ignore[attr-defined]
    module.register_memory = register  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "memory_modules", package)
    monkeypatch.setitem(sys.modules, "memory_modules.memory", module)
    spec = importlib.util.spec_from_file_location("fixture_longmem_atmem", LONGMEM_ASSET)
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)

    pool = tmp_path / "pool"
    image = pool / "trajectory-1" / "screen.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"fixture image bytes")
    adapter = loaded.AtMemMemory({
        "database_path": str(tmp_path / "atmem.db"),
        "subject_id": "subject",
        "agent_id": "agent",
        "workspace_id": "workspace",
        "trajectory_pool_root": str(pool),
        "require_encrypted": False,
        "context_bytes": 32_000,
    })
    state = {
        "state_index": 0,
        "step": 0,
        "url": "https://shop.example/checkout",
        "action": None,
        "thoughts": None,
        "text": "The current checkout label is Place order.",
        "screenshot": "screen.png",
        "expected_answer": "must never enter memory",
    }
    adapter.insert({
        "id": "trajectory-1", "goal": "checkout", "outcome": "completed",
        "start_url": "https://shop.example",
        "actions": ["Open checkout", "Select Place order"], "states": [state],
        "gold": "must never enter memory",
    })

    result = adapter.query("What is the current checkout label?")

    text = "\n".join(item["value"] for item in result if item["type"] == "text")
    assert "Place order" in text
    assert "must never enter memory" not in text
    assert {item["value"] for item in result if item["type"] == "image"} == {str(image)}
    records = adapter._memory.store.list_records("subject", statuses=None)
    assert records
    assert {row["source_type"] for row in records} == {"tool_output"}
    assert {row["trust_tier"] for row in records} == {"host_asserted_observation"}
    procedure = adapter.query("How should I complete checkout? and what are the steps?")
    assert "Select Place order" in "\n".join(
        item["value"] for item in procedure if item["type"] == "text"
    )
    adapter._memory.close()


def test_dolphin_adapter_keeps_personas_isolated_and_benchmark_logic_out() -> None:
    source = DOLPHIN_ADAPTER.read_text(encoding="utf-8")
    forbidden = (
        "expected_answer", "from graders", "gold_answer", "test_spec", "dataset_path",
        "._conn", ".store", "memory_proposals",
    )
    assert all(term not in source.casefold() for term in forbidden)
    assert 'PERSONAS = ("alex", "morgan", "riley")' in source
    assert "writes_allowed\": request.phase == \"ingestion\"" in source
    assert "request.phase == \"ingestion\"" in source


def test_dolphin_adapter_ingests_then_reads_without_changing_checkpoint(
    tmp_path: Path, monkeypatch
) -> None:
    from atmem.core.keys import sqlcipher_runtime_status
    from atmem.core import keys
    from research.production_benchmarks.dolphinbench import (
        AtMemDolphinAdapter,
        prepare_persona_households,
    )

    if not sqlcipher_runtime_status()["available"]:
        pytest.skip("sqlcipher3 runtime is not installed")
    monkeypatch.setattr(keys, "DEFAULT_KEY_PATH", tmp_path / "keys" / "db.key")

    @dataclass
    class InteractionRecord:
        settings: dict
        messages: list[dict]
        duration_ms: float | None = None
        attempts: list[dict] = field(default_factory=list)
        app_calls: list[dict] | None = None

    captured: list[str] = []

    async def driver(**kwargs):
        assert kwargs["max_cost_usd"] == 0.1
        captured.append(kwargs["memory_context"])
        return InteractionRecord(
            settings={"model": kwargs["model"], "cost_usd": 0.001},
            messages=[{"role": "user", "content": kwargs["request"].dated_message}],
        )

    driver_module = ModuleType("fixture_dolphin_driver")
    driver_module.run = driver  # type: ignore[attr-defined]
    adapter_module = ModuleType("harness.adapter")
    adapter_module.InteractionRecord = InteractionRecord  # type: ignore[attr-defined]
    harness_package = ModuleType("harness")

    class Apps:
        async def list_tools(self):
            return SimpleNamespace(tools=[])

        async def call_tool(self, *_args, **_kwargs):
            raise AssertionError("fixture agent made an unexpected app call")

    @asynccontextmanager
    async def connect_apps(_settings):
        yield Apps()

    examples_package = ModuleType("examples")
    connection_module = ModuleType("examples.mcp_connection")
    connection_module.connect_apps = connect_apps  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fixture_dolphin_driver", driver_module)
    monkeypatch.setitem(sys.modules, "harness", harness_package)
    monkeypatch.setitem(sys.modules, "harness.adapter", adapter_module)
    monkeypatch.setitem(sys.modules, "examples", examples_package)
    monkeypatch.setitem(sys.modules, "examples.mcp_connection", connection_module)

    prepare_persona_households(tmp_path)
    adapter = AtMemDolphinAdapter(
        {
            "agent_driver": "fixture_dolphin_driver:run", "model": "fixture-model",
            "cost_cap_usd": 1.0, "max_interaction_cost_usd": 0.1,
        },
        tmp_path,
    )
    ingestion = SimpleNamespace(
        persona="alex", phase="ingestion", interaction_id="history-1",
        dated_message="[2026-01-01] My favorite color is blue.", apps={},
    )
    adapter.run_interaction(ingestion)
    checkpoint = adapter.freeze("alex")
    test = SimpleNamespace(
        persona="alex", phase="tests", interaction_id="test-1",
        dated_message="[2026-02-01] What is my favorite color?", apps={},
    )
    adapter.run_interaction(test)

    assert "blue" in captured[-1]
    adapter.verify_checkpoint("alex", checkpoint)
    assert adapter.total_cost_usd("ingestion") == 0.001
    assert adapter.total_cost_usd("tests") == 0.001
    with pytest.raises(RuntimeError, match="refusing a blind retry"):
        adapter.run_interaction(test)
    assert len(captured) == 2
    adapter._reserve_interaction_cost("tests", "alex", "missing-cost")
    with pytest.raises(RuntimeError, match="neither aggregate nor attempt cost"):
        adapter._record_cost(
            "tests", "alex", "missing-cost",
            SimpleNamespace(settings={}, attempts=[]),
        )


def test_paid_call_ledger_is_durable_and_refuses_blind_retry(tmp_path: Path) -> None:
    from research.production_benchmarks.cost_ledger import DurableCostLedger

    path = tmp_path / "costs.json"
    ledger = DurableCostLedger(path, total_cap_usd=0.2)
    ledger.reserve("case-1", provider="fixture", maximum_usd=0.1)

    with pytest.raises(RuntimeError, match="refusing a blind retry"):
        DurableCostLedger(path, total_cap_usd=0.2).reserve(
            "case-1", provider="fixture", maximum_usd=0.1
        )

    completed = ledger.complete("case-1", cost_usd=0.08)
    assert completed["state"] == "completed"
    assert completed["cost_usd"] == 0.08
    with pytest.raises(RuntimeError, match="cost cap"):
        ledger.reserve("case-2", provider="fixture", maximum_usd=0.11)
