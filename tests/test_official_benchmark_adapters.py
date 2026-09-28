from __future__ import annotations

import importlib.util
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
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
        "question_type", "expected_answer", "gold", "axtree", "chunk",
        "._conn", ".store", "memory_proposals",
    )
    assert all(term not in source.casefold() for term in forbidden)
    assert '"accessibility_tree"' in source
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


def test_longmem_retry_patch_is_exact(tmp_path: Path, monkeypatch) -> None:
    from research.production_benchmarks import longmemeval_v2

    original = b"OPENAI_MAX_RETRIES = 10\nother = True\n"
    harness = tmp_path / "harness.py"
    monkeypatch.setattr(longmemeval_v2, "_git_blob", lambda _root, _name: original)
    harness.write_text(
        original.decode().replace(
            longmemeval_v2.RETRY_ORIGINAL, longmemeval_v2.RETRY_MARKER, 1
        ),
        encoding="utf-8",
    )
    assert longmemeval_v2._is_expected_retry_patch(
        tmp_path, harness, "evaluation/harness.py"
    )
    harness.write_text(harness.read_text() + "unreviewed = True\n", encoding="utf-8")
    assert not longmemeval_v2._is_expected_retry_patch(
        tmp_path, harness, "evaluation/harness.py"
    )


def test_paid_proxy_and_harness_environments_are_credential_isolated() -> None:
    from research.production_benchmarks import longmemeval_v2

    environment = {
        "PATH": "/fixture/bin",
        "HF_TOKEN": "hf-secret",
        "OPENAI_API_KEY": "openai-secret",
        "ATMEM_BENCHMARK_ROOT": "/fixture/evidence",
    }
    hf = longmemeval_v2._proxy_environment(environment, "HF_TOKEN")
    judge = longmemeval_v2._proxy_environment(environment, "OPENAI_API_KEY")
    assert hf["HF_TOKEN"] == "hf-secret"
    assert "OPENAI_API_KEY" not in hf
    assert judge["OPENAI_API_KEY"] == "openai-secret"
    assert "HF_TOKEN" not in judge
    source = LONGMEM_ASSET.parents[1].joinpath("longmemeval_v2.py").read_text()
    assert 'harness_environment.pop("OPENAI_API_KEY", None)' in source
    assert '"--max-completion-tokens"' in source
    assert '"--memory-context-max-tokens"' in source
    assert '"--evaluator-reasoning-effort"' in source
    assert source.index("pilot method has no price-derived reservation") < source.index(
        'if method == "official-rag-query-to-slice-notes"'
    )


def test_paid_runtime_preflight_is_complete_before_output(
    monkeypatch,
) -> None:
    from research.production_benchmarks import longmemeval_v2

    protocol = json.loads(
        (ROOT / "benchmarks/retrieval_quality/protocols/2.3.8.yaml").read_text()
    )
    environment = {"HF_TOKEN": "fixture-hf", "OPENAI_API_KEY": "fixture-openai"}
    expected_packages = protocol["paid_run_requirements"]["official_runtime_packages"]
    monkeypatch.setattr(
        longmemeval_v2, "package_version", lambda name: expected_packages[name]
    )
    result = longmemeval_v2.preflight_paid_runtime(
        protocol, methods=("no-retrieval", "typed-local"), environment=environment
    )
    assert result["judge_proxy_sha256"] == protocol["paid_run_requirements"][
        "judge_proxy_sha256"
    ]

    monkeypatch.setattr(longmemeval_v2, "package_version", lambda _name: "0.0")
    with pytest.raises(RuntimeError, match="official runtime package differs"):
        longmemeval_v2.preflight_paid_runtime(
            protocol, methods=("typed-local",), environment=environment
        )
    monkeypatch.setattr(
        longmemeval_v2, "package_version", lambda name: expected_packages[name]
    )

    broken = json.loads(json.dumps(protocol))
    broken["paid_run_requirements"]["judge_proxy_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="judge_proxy_sha256 differs"):
        longmemeval_v2.preflight_paid_runtime(
            broken, methods=("typed-local",), environment=environment
        )

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="requires credentials"):
        longmemeval_v2.preflight_paid_runtime(
            protocol, methods=("typed-local",), environment={}
        )

    source = (
        ROOT / "research/production_benchmarks/run_longmem_pilot.py"
    ).read_text(encoding="utf-8")
    assert source.index("preflight_paid_runtime(protocol") < source.index(
        "output_root.mkdir"
    )
    assert source.index(
        '!= pilot["selected_input_manifest_sha256"]'
    ) < source.index("output_root.mkdir")
    adapter_source = (
        ROOT / "research/production_benchmarks/longmemeval_v2.py"
    ).read_text(encoding="utf-8")
    assert adapter_source.index(
        "_preflight_official_harness_import(root, run_environment)"
    ) < adapter_source.index("hf_ledger.reserve")


def test_judge_proxy_allows_one_egress_and_records_content_free_usage(
    tmp_path: Path, monkeypatch
) -> None:
    import urllib.error
    import urllib.request
    from research.production_benchmarks import openai_judge_proxy

    class Upstream(BaseHTTPRequestHandler):
        calls = 0

        def log_message(self, _format, *_args):
            return

        def do_POST(self):  # noqa: N802
            type(self).calls += 1
            length = int(self.headers["Content-Length"])
            self.rfile.read(length)
            body = json.dumps({
                "choices": [{"message": {"content": '{"label": 1}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    monkeypatch.setattr(
        openai_judge_proxy,
        "UPSTREAM",
        f"http://127.0.0.1:{upstream.server_port}/v1/chat/completions",
    )
    usage_path = tmp_path / "usage.json"
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), openai_judge_proxy.Handler)
    proxy.state = openai_judge_proxy.State(  # type: ignore[attr-defined]
        usage_path, "fixture-upstream-key"
    )
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    body = json.dumps({
        "model": openai_judge_proxy.MODEL,
        "messages": [{"role": "user", "content": "private fixture"}],
        "max_completion_tokens": 128,
    }).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{proxy.server_port}/v1/chat/completions",
        data=body,
        headers={"Authorization": "Bearer local-proxy", "Content-Type": "application/json"},
    )
    try:
        multiple_body = json.dumps({
            "model": openai_judge_proxy.MODEL,
            "messages": [],
            "max_completion_tokens": 128,
            "n": 2,
        }).encode()
        multiple = urllib.request.Request(
            f"http://127.0.0.1:{proxy.server_port}/v1/chat/completions",
            data=multiple_body,
            headers={
                "Authorization": "Bearer local-proxy",
                "Content-Type": "application/json",
            },
        )
        with pytest.raises(urllib.error.HTTPError) as rejected:
            urllib.request.urlopen(multiple)
        assert rejected.value.code == 400
        assert Upstream.calls == 0
        with urllib.request.urlopen(request) as response:
            assert response.status == 200
        with pytest.raises(urllib.error.HTTPError) as retry:
            urllib.request.urlopen(request)
        assert retry.value.code == 429
        evidence = json.loads(usage_path.read_text())
        assert evidence["requests"] == 1
        assert evidence["prompt_tokens"] == 100
        assert evidence["completion_tokens"] == 10
        assert "private fixture" not in usage_path.read_text()
        assert Upstream.calls == 1
    finally:
        proxy.shutdown()
        proxy.server_close()
        upstream.shutdown()
        upstream.server_close()


def test_judge_proxy_preserves_reserved_cost_when_usage_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    import urllib.error
    import urllib.request
    from research.production_benchmarks import openai_judge_proxy

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, _format, *_args):
            return

        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers["Content-Length"]))
            body = json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    monkeypatch.setattr(
        openai_judge_proxy,
        "UPSTREAM",
        f"http://127.0.0.1:{upstream.server_port}/v1/chat/completions",
    )
    usage_path = tmp_path / "usage.json"
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), openai_judge_proxy.Handler)
    proxy.state = openai_judge_proxy.State(usage_path, "fixture-key")  # type: ignore[attr-defined]
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    request = urllib.request.Request(
        f"http://127.0.0.1:{proxy.server_port}/v1/chat/completions",
        data=json.dumps({
            "model": openai_judge_proxy.MODEL,
            "messages": [],
            "max_completion_tokens": 128,
        }).encode(),
        headers={"Authorization": "Bearer local-proxy", "Content-Type": "application/json"},
    )
    try:
        with pytest.raises(urllib.error.HTTPError) as failed:
            urllib.request.urlopen(request)
        assert failed.value.code == 502
        evidence = json.loads(usage_path.read_text())
        assert evidence["state"] == "egress_started"
        assert evidence["cost_usd"] == openai_judge_proxy.RESERVED_MAXIMUM_USD
        assert evidence["prompt_tokens"] is None
    finally:
        proxy.shutdown()
        proxy.server_close()
        upstream.shutdown()
        upstream.server_close()


def test_judge_proxy_waits_for_reader_phase_gate(
    tmp_path: Path, monkeypatch
) -> None:
    import time
    import urllib.request
    from research.production_benchmarks import openai_judge_proxy

    class Upstream(BaseHTTPRequestHandler):
        calls = 0

        def log_message(self, _format, *_args):
            return

        def do_POST(self):  # noqa: N802
            type(self).calls += 1
            self.rfile.read(int(self.headers["Content-Length"]))
            body = json.dumps({
                "choices": [{"message": {"content": '{"label": 1}'}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    monkeypatch.setattr(
        openai_judge_proxy,
        "UPSTREAM",
        f"http://127.0.0.1:{upstream.server_port}/v1/chat/completions",
    )
    usage_path = tmp_path / "usage.json"
    gate_path = tmp_path / "reader-complete.gate"
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), openai_judge_proxy.Handler)
    proxy.state = openai_judge_proxy.State(  # type: ignore[attr-defined]
        usage_path,
        "fixture-key",
        gate_file=gate_path,
        gate_timeout_seconds=5,
    )
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    request = urllib.request.Request(
        f"http://127.0.0.1:{proxy.server_port}/v1/chat/completions",
        data=json.dumps({
            "model": openai_judge_proxy.MODEL,
            "messages": [],
            "max_completion_tokens": 128,
        }).encode(),
        headers={"Authorization": "Bearer local-proxy", "Content-Type": "application/json"},
    )
    outcome: dict[str, int] = {}

    def send() -> None:
        with urllib.request.urlopen(request) as response:
            outcome["status"] = response.status

    client = threading.Thread(target=send, daemon=True)
    client.start()
    try:
        for _ in range(100):
            if usage_path.is_file() and json.loads(usage_path.read_text())["state"] == (
                "waiting_for_reader_phase_gate"
            ):
                break
            time.sleep(0.01)
        else:
            pytest.fail("judge proxy did not expose the waiting state")
        assert Upstream.calls == 0
        gate_path.write_text("ready\n")
        client.join(timeout=5)
        assert outcome == {"status": 200}
        assert Upstream.calls == 1
        assert json.loads(usage_path.read_text())["state"] == "completed"
    finally:
        proxy.shutdown()
        proxy.server_close()
        upstream.shutdown()
        upstream.server_close()


def test_longmem_runner_charges_missing_required_judge_usage_conservatively(
    tmp_path: Path,
) -> None:
    from research.production_benchmarks.longmemeval_v2 import _judge_usage

    missing = _judge_usage(
        {"eval_function": "llm_abstention_checker"},
        tmp_path / "missing.json",
        reservation_usd=0.12,
    )
    assert missing["state"] == "usage_missing_after_required_judge"
    assert missing["cost_usd"] == 0.12

    deterministic = _judge_usage(
        {"eval_function": "exact_match"},
        tmp_path / "missing.json",
        reservation_usd=0.12,
    )
    assert deterministic["state"] == "not_required"
    assert deterministic["cost_usd"] == 0.0


def test_longmem_paid_pilot_preflight_requires_prepared_media(tmp_path: Path) -> None:
    from research.production_benchmarks.run_longmem_pilot import preflight_pilot_data

    (tmp_path / "haystacks").mkdir()
    (tmp_path / "haystacks/lme_v2_small.json").write_text(
        json.dumps({"question-1": ["trajectory-1"]}), encoding="utf-8"
    )
    (tmp_path / "questions.jsonl").write_text(
        json.dumps({"id": "question-1", "domain": "web", "image": None}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "trajectories.jsonl").write_text(
        json.dumps({
            "id": "trajectory-1",
            "states": [{"screenshot": "screenshots/trajectory-1/0.png"}],
        }) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "checksums.sha256").write_text("fixture\n", encoding="utf-8")
    content_sha256 = {
        relative: hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest()
        for relative in (
            "checksums.sha256",
            "haystacks/lme_v2_small.json",
            "questions.jsonl",
            "trajectories.jsonl",
        )
    }
    dataset = {"dataset_revision": "fixture-revision", "content_sha256": content_sha256}
    with pytest.raises(RuntimeError, match="not prepared"):
        preflight_pilot_data(tmp_path, ["question-1"], dataset)

    screenshot = tmp_path / "screenshots/trajectory-1/0.png"
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"fixture")
    result = preflight_pilot_data(tmp_path, ["question-1"], dataset)
    report = result.report()
    assert report["question_count"] == 1
    assert report["trajectory_count"] == 1
    assert report["trajectory_screenshot_count"] == 1
    assert report["dataset_revision"] == "fixture-revision"
    assert report["content_retained"] is False

    (tmp_path / "questions.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="differs from pinned revision"):
        preflight_pilot_data(tmp_path, ["question-1"], dataset)


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
        "accessibility_tree": "The current checkout label is Place order.",
        "thought": "Use the visible checkout control.",
        "screenshot": "trajectory-1/screen.png",
        "expected_answer": "must never enter memory",
    }
    adapter.insert({
        "id": "trajectory-1", "goal": "checkout", "outcome": "completed",
        "start_url": "https://shop.example",
        "actions": ["Open checkout", "Select Place order"], "states": [state],
        "gold": "must never enter memory",
    })
    with pytest.raises(ValueError, match="escapes its source root"):
        adapter.insert({
            "id": "trajectory-escape",
            "states": [{"state_index": 0, "screenshot": "../../outside.png"}],
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


def test_dolphin_official_checkout_and_frozen_split_are_rederived(
    tmp_path: Path, monkeypatch
) -> None:
    import subprocess
    from research.production_benchmarks import dolphinbench

    checkout = tmp_path / "dolphinbench"
    development: list[str] = []
    confirmation: list[str] = []
    personas: dict[str, dict[str, int]] = {}
    salt = "fixture-salt"
    for persona in dolphinbench.PERSONAS:
        directory = checkout / "tests" / persona
        directory.mkdir(parents=True)
        for number in range(1, 201):
            (directory / f"{number:03}.yaml").write_text("fixture: true\n")
        ids = [f"{number:03}" for number in range(1, 201)]
        selected = set(sorted(
            ids,
            key=lambda value: (
                hashlib.sha256(
                    salt.encode() + b"\0" + f"{persona}:{value}".encode()
                ).hexdigest(),
                value,
            ),
        )[:6])
        development.extend(f"{persona}:{value}" for value in ids if value in selected)
        confirmation.extend(f"{persona}:{value}" for value in ids if value not in selected)
        personas[persona] = {"development": 6, "confirmation": 194, "total": 200}
    subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
    subprocess.run(["git", "add", "."], cwd=checkout, check=True)
    subprocess.run(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.test",
         "commit", "-qm", "fixture"],
        cwd=checkout, check=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=checkout, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    split = {
        "format": "atmem-dolphinbench-task-split-v1",
        "source_commit": commit,
        "salt": salt,
        "selection_rule": "fixture deterministic selection",
        "claim_class": "development_plumbing_and_cost_calibration",
        "development_ids": development,
        "confirmation_ids": confirmation,
        "personas": personas,
    }
    split["split_sha256"] = hashlib.sha256(json.dumps(
        split, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()).hexdigest()
    monkeypatch.setattr(dolphinbench, "PINNED_COMMIT", commit)
    monkeypatch.setattr(
        dolphinbench, "PINNED_SPLIT_SHA256", split["split_sha256"]
    )
    result = dolphinbench.verify_official_checkout(checkout, split)
    assert result["development_count"] == 18
    assert result["held_out_count"] == 582
    assert result["content_retained"] is False


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
            "allowed_test_ids": {"alex": ["test-1"], "morgan": [], "riley": []},
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

    outside_split = SimpleNamespace(
        persona="alex", phase="tests", interaction_id="test-2",
        dated_message="[2026-02-01] Outside split", apps={},
    )
    with pytest.raises(ValueError, match="outside the frozen allowed split"):
        adapter.run_interaction(outside_split)

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


def test_dolphin_development_runner_selects_before_official_execute(
    tmp_path: Path, monkeypatch
) -> None:
    from research.production_benchmarks import dolphinbench

    selected = {
        persona: {f"{index:03d}" for index in range(1, 7)}
        for persona in dolphinbench.PERSONAS
    }
    verification = {
        "source_commit": dolphinbench.PINNED_COMMIT,
        "development_ids": sorted(
            f"{persona}:{item}"
            for persona, values in selected.items()
            for item in values
        ),
    }
    monkeypatch.setattr(
        dolphinbench,
        "_frozen_development_split",
        lambda _checkout: (verification, selected),
    )

    durable = ModuleType("harness.durable_json")

    def save_json(path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    durable.save_json = save_json  # type: ignore[attr-defined]
    harness = ModuleType("harness")
    monkeypatch.setitem(sys.modules, "harness", harness)
    monkeypatch.setitem(sys.modules, "harness.durable_json", durable)

    adapter = object.__new__(dolphinbench.AtMemDolphinAdapter)
    adapter.allowed_test_ids = selected
    adapter.verify_checkpoint = lambda _persona, _checkpoint: None  # type: ignore[method-assign]
    executed: list[tuple[str, str]] = []

    class Runner:
        directory = tmp_path

        def __init__(self):
            self.adapter = adapter
            self.release = {
                persona: {"tests": [{"id": index} for index in range(1, 201)]}
                for persona in dolphinbench.PERSONAS
            }

        def _saved_cost(self, phase):
            assert phase == "ingestion"
            return 0.1

        def _execute(self, phase, persona, spec):
            assert phase == "tests"
            executed.append((persona, str(spec["id"]).zfill(3)))
            return {"row": {}}

        def _path(self, phase, persona, item_id):
            return self.directory / phase / persona / f"{item_id}.json"

        def _grade(self, _spec, _evidence):
            return {"checks": [{"check": 0, "passed": True}]}

        def _collect_cost(self, phase):
            assert phase == "tests"
            return 0.18

    for persona in dolphinbench.PERSONAS:
        checkpoint = tmp_path / "checkpoints" / f"{persona}.json"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text("{}", encoding="utf-8")

    result = dolphinbench.evaluate_development(Runner(), tmp_path / "checkout")

    assert len(executed) == 18
    assert set(executed) == {
        (persona, item) for persona, values in selected.items() for item in values
    }
    assert result["tests"] == 18
    assert result["checks"] == 18
    assert result["claim"] == "development-18-of-600-not-an-official-score"


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
