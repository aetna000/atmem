from __future__ import annotations

import asyncio
import importlib.util
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.error import HTTPError
from types import ModuleType, SimpleNamespace
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

import pytest


ROOT = Path(__file__).parents[1]
LONGMEM_ASSET = (
    ROOT / "research/production_benchmarks/adapters/longmemeval_atmem.py"
)
DOLPHIN_ADAPTER = ROOT / "research/production_benchmarks/dolphinbench.py"


def test_paid_entrypoints_preserve_installed_product_precedence() -> None:
    for name in ("run_longmem_pilot.py", "run_dolphin_development.py"):
        source = (ROOT / "research/production_benchmarks" / name).read_text(
            encoding="utf-8"
        )
        assert "sys.path.append(str(ROOT))" in source
        assert "installed_atmem_identity" in source
        assert "sys.path.insert(0, str(ROOT))" not in source


def test_dolphin_work_output_is_bound_separately_from_checkpoint(tmp_path: Path) -> None:
    from research.production_benchmarks.run_dolphin_development import (
        validate_work_directory,
    )

    configured_output = tmp_path / "run" / "atmem"
    checkpoint_root = tmp_path / "state"
    configured_output.mkdir(parents=True)
    checkpoint_root.mkdir()

    validate_work_directory(configured_output, configured_output)
    with pytest.raises(RuntimeError, match="configured output"):
        validate_work_directory(checkpoint_root, configured_output)


def test_dolphin_driver_returns_model_arguments_with_structured_app_result(
    monkeypatch,
) -> None:
    from research.production_benchmarks import dolphin_openai_driver

    @dataclass
    class InteractionRecord:
        settings: dict
        messages: list[dict]
        duration_ms: float | None = None
        attempts: list[dict] = field(default_factory=list)
        app_calls: list[dict] | None = None

    adapter_module = ModuleType("harness.adapter")
    adapter_module.InteractionRecord = InteractionRecord  # type: ignore[attr-defined]
    harness_package = ModuleType("harness")
    monkeypatch.setitem(sys.modules, "harness", harness_package)
    monkeypatch.setitem(sys.modules, "harness.adapter", adapter_module)
    replies = iter([
        {
            "choices": [{"finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": None, "tool_calls": [{
                    "id": "call-1", "type": "function", "function": {
                        "name": "send_message", "arguments": '{"text":"hi"}'
                    },
                }],
            }}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
        {
            "choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": "done",
            }}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 2},
        },
    ])
    monkeypatch.setattr(dolphin_openai_driver, "_post", lambda _payload: next(replies))
    monkeypatch.setenv("ATMEM_DOLPHIN_GPU_USD_PER_HOUR", "1.0")
    calls = []

    async def call_app(name, arguments):
        calls.append((name, arguments))
        return SimpleNamespace(content=[SimpleNamespace(text='{"ok":true}')])

    record = asyncio.run(dolphin_openai_driver.run(
        request=SimpleNamespace(dated_message="[2028-01-01] Send it."),
        tools=[SimpleNamespace(
            name="send_message", description="Send a message",
            inputSchema={"type": "object", "properties": {
                "text": {"type": "string"},
            }},
        )],
        call_app=call_app,
        memory_context="Relevant evidence.",
        model="fixture-model",
        max_cost_usd=1.0,
    ))

    assert calls == [("send_message", {"text": "hi"})]
    assert record.app_calls == [{
        "tool": "send_message",
        "args": {"text": "hi"},
        "result": {"ok": True},
    }]
    assert record.messages[-1]["content"] == "done"


def test_dolphin_driver_preserves_provider_http_error_detail(monkeypatch) -> None:
    from research.production_benchmarks import dolphin_openai_driver

    monkeypatch.setenv("ATMEM_DOLPHIN_AGENT_BASE_URL", "https://reader.test/v1")
    monkeypatch.setenv("ATMEM_DOLPHIN_AGENT_API_KEY", "secret")

    def fail(*_args, **_kwargs):
        raise HTTPError(
            "https://reader.test/v1/chat/completions", 400, "Bad Request", {},
            BytesIO(b'{"error":"tool parser is disabled"}'),
        )

    monkeypatch.setattr(dolphin_openai_driver.urllib.request, "urlopen", fail)
    with pytest.raises(RuntimeError, match="tool parser is disabled"):
        dolphin_openai_driver._post({"model": "fixture"})


def test_longmem_adapter_is_inert_product_api_only() -> None:
    source = LONGMEM_ASSET.read_text(encoding="utf-8")
    forbidden = (
        "question_type", "expected_answer", "gold", "axtree", "chunk",
        "._conn", ".store", "memory_proposals",
    )
    assert all(term not in source.casefold() for term in forbidden)
    assert '"accessibility_tree"' in source
    assert "form_context_episode" in source
    assert "freeze_context_engine" in source
    assert "prepare_context_v3" in source
    # V2 remains only as the governed media bridge; its prose is not returned.
    assert "media_package.media_references" in source


def test_longmem_checkpoint_restore_preserves_saved_retrieval_parameters(
    monkeypatch,
) -> None:
    memory_module = ModuleType("memory_modules.memory")

    class Memory:
        def __init__(self, memory_params):
            self.memory_params = dict(memory_params)

    memory_module.Memory = Memory  # type: ignore[attr-defined]
    memory_module.register_memory = lambda cls: cls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "memory_modules", ModuleType("memory_modules"))
    monkeypatch.setitem(sys.modules, "memory_modules.memory", memory_module)
    spec = importlib.util.spec_from_file_location(
        "_fixture_longmemeval_atmem", LONGMEM_ASSET
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    saved = {
        "memory_type": "atmem",
        "memory_params": {
            "database_path": "/build/atmem.db",
            "trajectory_pool_root": "/build/frozen-dataset",
            "subject_id": "subject",
            "agent_id": "agent",
            "workspace_id": "workspace",
            "limit": 20,
            "candidate_limit": 200,
            "context_bytes": 32_768,
        },
    }
    requested = {
        "memory_type": "atmem",
        "memory_params": {
            "database_path": "/run/atmem.db",
            "trajectory_pool_root": "/run/frozen-dataset",
            "subject_id": "subject",
            "agent_id": "agent",
            "workspace_id": "workspace",
        },
    }
    restored = module.AtMemMemory.reconcile_loaded_memory_config(saved, requested)
    assert restored["memory_params"] == {
        **saved["memory_params"],
        "database_path": "/run/atmem.db",
        "trajectory_pool_root": "/run/frozen-dataset",
    }

    conflicting = json.loads(json.dumps(requested))
    conflicting["memory_params"]["candidate_limit"] = 50
    with pytest.raises(RuntimeError, match="candidate_limit"):
        module.AtMemMemory.reconcile_loaded_memory_config(saved, conflicting)


def test_longmem_registry_patch_rejects_unrelated_edits(
    tmp_path: Path, monkeypatch
) -> None:
    from research.production_benchmarks import longmemeval_v2

    original = b"from .memory import Memory\n"
    registry = tmp_path / "memory.py"
    monkeypatch.setattr(longmemeval_v2, "_git_blob", lambda _root, _name: original)
    registry.write_text(
        original.decode().rstrip() + "\n"
        + "\n".join(longmemeval_v2.IMPORT_LINES) + "\n",
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


def test_longmem_agentrunbook_hash_embedder_patch_is_exact(
    tmp_path: Path, monkeypatch
) -> None:
    from research.production_benchmarks import longmemeval_v2

    original = (
        "import re\n"
        + longmemeval_v2.AGENTRUNBOOK_TOKENIZER_ORIGINAL
        + "\n"
        + longmemeval_v2.AGENTRUNBOOK_TRUNCATE_ORIGINAL
    ).encode()
    adapter = tmp_path / "agentrunbook_r.py"
    monkeypatch.setattr(longmemeval_v2, "_git_blob", lambda _root, _name: original)
    adapter.write_text(
        original.decode().replace(
            longmemeval_v2.AGENTRUNBOOK_TOKENIZER_ORIGINAL,
            longmemeval_v2.AGENTRUNBOOK_TOKENIZER_MARKER,
            1,
        ).replace(
            longmemeval_v2.AGENTRUNBOOK_TRUNCATE_ORIGINAL,
            longmemeval_v2.AGENTRUNBOOK_TRUNCATE_MARKER,
            1,
        ),
        encoding="utf-8",
    )
    assert longmemeval_v2._is_expected_agentrunbook_patch(tmp_path, adapter)

    adapter.write_text(adapter.read_text() + "unreviewed = True\n", encoding="utf-8")
    assert not longmemeval_v2._is_expected_agentrunbook_patch(tmp_path, adapter)


def test_checkpoint_builder_replaces_stale_embedding_readiness(tmp_path: Path) -> None:
    from research.production_benchmarks import prepare_longmem_memories

    ready = tmp_path / "embedding-ready.json"
    ready.write_text(
        json.dumps({"base_url": "http://127.0.0.1:1/v1"}), encoding="utf-8"
    )
    process, base_url = prepare_longmem_memories._start_embedding_proxy(ready)
    try:
        assert base_url != "http://127.0.0.1:1/v1"
        assert json.loads(ready.read_text(encoding="utf-8"))["base_url"] == base_url
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_runpod_reader_readiness_is_published_atomically(tmp_path: Path) -> None:
    from research.production_benchmarks.runpod_reader_proxy import write_ready_file

    ready = tmp_path / "reader-ready.json"
    write_ready_file(ready, "http://127.0.0.1:1234/v1")
    assert json.loads(ready.read_text(encoding="utf-8")) == {
        "base_url": "http://127.0.0.1:1234/v1"
    }
    assert not list(tmp_path.glob(".reader-ready.json.*.tmp"))


def test_checkpoint_tree_digest_streams_files(tmp_path: Path, monkeypatch) -> None:
    from research.production_benchmarks import prepare_longmem_memories

    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    (checkpoint / "memory.bin").write_bytes(b"bounded-read" * 1000)

    original_read_bytes = Path.read_bytes

    def reject_bulk_read(path: Path) -> bytes:
        if path == checkpoint / "memory.bin":
            raise AssertionError("checkpoint digest used an unbounded bulk read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_bulk_read)
    first = prepare_longmem_memories._digest_tree(checkpoint)
    second = prepare_longmem_memories._digest_tree(checkpoint)
    assert first == second
    assert first.startswith("sha256:")


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
        'if method in {"official-rag-query-to-slice-notes", "agentrunbook-r"}'
    )


def test_paid_runtime_preflight_is_complete_before_output(
    monkeypatch,
) -> None:
    from research.production_benchmarks import longmemeval_v2

    protocol = json.loads(
        (ROOT / "benchmarks/retrieval_quality/protocols/2.3.8.yaml").read_text()
    )
    environment = {
        "OPENAI_API_KEY": "fixture-openai",
        "RUNPOD_READER_API_KEY": "fixture-runpod-reader",
    }
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

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="requires credentials"):
        longmemeval_v2.preflight_paid_runtime(
            protocol, methods=("typed-local",), environment={}
        )

    source = (
        ROOT / "research/production_benchmarks/run_longmem_pilot.py"
    ).read_text(encoding="utf-8")
    assert source.index("preflight_paid_runtime(") < source.index(
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
        ) < adapter_source.rindex("_reserve_with_local_lock_wait(")


def test_no_egress_preflight_requires_account_key_not_ephemeral_reader_key(
    monkeypatch,
) -> None:
    from research.production_benchmarks import longmemeval_v2

    protocol = json.loads(
        (ROOT / "benchmarks/retrieval_quality/protocols/2.3.8.yaml").read_text()
    )
    expected_packages = protocol["paid_run_requirements"]["official_runtime_packages"]
    monkeypatch.setattr(
        longmemeval_v2, "package_version", lambda name: expected_packages[name]
    )
    result = longmemeval_v2.preflight_paid_runtime(
        protocol,
        methods=("no-retrieval", "typed-local"),
        environment={"OPENAI_API_KEY": "fixture-openai", "RUN_POD": "fixture-account"},
        require_live_reader=False,
    )
    assert result["reader_proxy_sha256"] == protocol["paid_run_requirements"][
        "reader_proxy_sha256"
    ]

    with pytest.raises(RuntimeError, match="RUN_POD"):
        longmemeval_v2.preflight_paid_runtime(
            protocol,
            methods=("typed-local",),
            environment={"OPENAI_API_KEY": "fixture-openai"},
            require_live_reader=False,
        )


def test_longmem_case_honours_fail_fast_cancellation_before_writes(
    tmp_path: Path,
) -> None:
    from research.production_benchmarks.longmemeval_v2 import (
        run_official_pilot_case,
    )

    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(RuntimeError, match="cancelled before start"):
        run_official_pilot_case(
            tmp_path,
            data_root=tmp_path,
            output_root=tmp_path / "must-not-exist",
            question_id="fixture",
            domain="web",
            method="typed-local",
            protocol_path=tmp_path / "missing-protocol.json",
            question_split={},
            pilot={},
            dolphin_split={},
            route_probe={},
            cancellation_event=cancelled,
        )
    assert not (tmp_path / "must-not-exist").exists()


def test_longmem_paid_routes_bind_comparator_controller_to_live_reader() -> None:
    source = (
        ROOT / "research/production_benchmarks/longmemeval_v2.py"
    ).read_text(encoding="utf-8")
    assert 'if method in {"official-rag-query-to-slice-notes", "agentrunbook-r"}' in source
    assert '"--controller-base-url", (' in source
    assert "reader_base_url" in source


def test_longmem_runner_requires_mem0_checkout_before_paid_output() -> None:
    source = (
        ROOT / "research/production_benchmarks/run_longmem_pilot.py"
    ).read_text(encoding="utf-8")
    requirement = 'raise RuntimeError("paid pilot requires ATMEM_MEM0_CHECKOUT")'
    assert requirement in source
    assert source.index(requirement) < source.index("output_root.mkdir")


def test_longmem_runner_validates_every_prebuilt_checkpoint_before_cost_reservation() -> None:
    source = (
        ROOT / "research/production_benchmarks/run_longmem_pilot.py"
    ).read_text(encoding="utf-8")
    requirement = '"pilot prebuilt AtMem memories are missing: "'
    assert requirement in source
    assert source.index(requirement) < source.index("output_root.mkdir")
    assert source.index(requirement) < source.index("reader_ledger.reserve")


def test_longmem_runtime_reservation_covers_the_complete_pod_envelope() -> None:
    from research.production_benchmarks.run_longmem_pilot import (
        _runtime_reservation_usd,
    )

    assert _runtime_reservation_usd({
        "usd_per_hour": 1.79,
        "maximum_active_seconds": 40_000,
    }) == pytest.approx(19.888888889)

    source = (
        ROOT / "research/production_benchmarks/run_longmem_pilot.py"
    ).read_text(encoding="utf-8")
    assert "reader_maximum = _runtime_reservation_usd(billing)" in source
    assert "* remaining_billed_seconds\n        / 3_600" not in source


def test_longmem_mac_controller_runs_exactly_one_case_at_a_time() -> None:
    protocol = json.loads(
        (ROOT / "benchmarks/retrieval_quality/protocols/2.3.8.yaml").read_text()
    )
    requirements = protocol["paid_run_requirements"]
    assert requirements["controller_case_concurrency"] == 1
    assert requirements["controller_case_concurrency"] <= requirements[
        "reader_runtime_billing"
    ]["max_num_seqs"]
    source = (
        ROOT / "research/production_benchmarks/run_longmem_pilot.py"
    ).read_text(encoding="utf-8")
    assert "max(1, len(llm_work))" not in source
    assert "ThreadPoolExecutor(max_workers=controller_case_concurrency)" in source
    assert "run_batch(non_llm_work, max_workers=1" in source
    assert "executor.submit(run_case, item, gated=False)" in source
    assert "_wait_for_judge_gate(llm_futures" not in source
    assert source.index(
        'billing = dict(requirements["reader_runtime_billing"])'
    ) < source.index('"gpu_reader_hardware": billing["hardware_id"]')


def test_longmem_runner_resumes_only_validated_checkpoint_pairs() -> None:
    source = (
        ROOT / "research/production_benchmarks/run_longmem_pilot.py"
    ).read_text(encoding="utf-8")
    assert 'parser.add_argument(\n        "--resume-progress"' in source
    assert 'progress["cases"] = cases' in source
    assert "allowed_pairs - seen_pairs" in source
    assert "resume progress contains an invalid or duplicate case" in source
    assert "resume case lacks its official scored artifact" in source
    assert 'output_root / "interrupted"' in source


def test_longmem_controller_can_retain_shared_remote_worker() -> None:
    source = (
        ROOT / "research/production_benchmarks/run_longmem_pilot.py"
    ).read_text(encoding="utf-8")
    assert 'ATMEM_RUNPOD_CLEANUP_OWNER", "runner"' in source
    assert 'cleanup_owner not in {"runner", "controller"}' in source
    assert '"retained_by_controller"' in source
    assert "if runner_owns_cleanup and not terminated:" in source


def test_longmem_complete_batch_has_no_artificial_wall_clock() -> None:
    source = (
        ROOT / "research/production_benchmarks/run_longmem_pilot.py"
    ).read_text(encoding="utf-8")
    assert "Qwen reader phase exceeded the frozen endpoint runtime" not in source
    assert "deadline = time.monotonic() + remaining_billed_seconds" not in source
    assert "deadline_monotonic=None" in source

    adapter = (
        ROOT / "research/production_benchmarks/longmemeval_v2.py"
    ).read_text(encoding="utf-8")
    assert 'str(models["longmemeval_judge"]["timeout_seconds"])' in adapter


def test_longmem_stage_checkpoint_never_stops_for_score() -> None:
    from research.production_benchmarks.run_longmem_pilot import (
        _selected_question_ids,
        _stage_checkpoint_summary,
    )

    protocols = ROOT / "benchmarks/retrieval_quality/protocols"
    pilot = json.loads(
        (protocols / "longmemeval-v2-development-5pct-v1.json").read_text()
    )
    gate = json.loads(
        (protocols / "longmemeval-v2-stage-gate-v1.json").read_text()
    )
    selected, claim = _selected_question_ids(pilot, gate)
    assert selected == gate["question_ids"]
    assert len(selected) == 6
    assert claim == "matched_progress_checkpoint_diagnostic"

    tied = [
        {"method": method, "score_bool": outcome}
        for method in ("typed-local", "agentrunbook-r")
        for outcome in (True, False)
    ]
    summary = _stage_checkpoint_summary(tied)
    assert summary["atmem_ahead"] is False
    assert summary["continuation_required"] is True
    assert summary["score_can_stop_run"] is False
    ahead = tied + [{"method": "typed-local", "score_bool": True}]
    summary = _stage_checkpoint_summary(ahead)
    assert summary["atmem_ahead"] is True
    assert summary["continuation_required"] is True
    assert summary["score_can_stop_run"] is False


def test_paid_benchmark_topology_keeps_gpu_inference_remote() -> None:
    protocol = json.loads(
        (ROOT / "benchmarks/retrieval_quality/protocols/2.3.8.yaml").read_text()
    )
    requirements = protocol["paid_run_requirements"]
    assert requirements["hardware_profile"].startswith("Apple-M2;")
    assert requirements["controller_case_concurrency"] == 1
    assert requirements["reader_runtime_billing"]["hardware_id"] == (
        "NVIDIA A100-SXM4-80GB"
    )
    assert requirements["provider_route"].startswith(
        "mac-controller+runpod-vllm-reader"
    )


def test_local_benchmark_resources_are_bounded(monkeypatch) -> None:
    from research.production_benchmarks.local_resources import (
        THREAD_LIMIT_ENV,
        configure_local_resource_limits,
    )

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("os.nice", lambda increment: 10 + increment)
    receipt = configure_local_resource_limits()
    assert receipt == {
        "case_concurrency": 1,
        "thread_limit": 1,
        "niceness": 20,
        "tokenizers_parallelism": False,
    }
    assert all(os.environ[name] == "1" for name in THREAD_LIMIT_ENV)
    assert os.environ["TOKENIZERS_PARALLELISM"] == "false"


def test_agmi_runner_pins_all_nine_attacks_without_score_assertions() -> None:
    protocol = json.loads(
        (ROOT / "benchmarks/retrieval_quality/protocols/agmi-atmem-v1.json").read_text()
    )
    assert protocol["source_commit"] == "115493a41a7b41952f92ec07e1ea0932926e194f"
    assert protocol["profiles"] == ["atmem-chain", "atmem-chain+checkpoint"]
    assert len(protocol["attacks"]) == 9
    assert protocol["execution"]["score_can_stop_run"] is False
    source = (
        ROOT / "research/production_benchmarks/run_agmi_integrity.py"
    ).read_text(encoding="utf-8")
    assert "AT_REST_ATTACKS_WITH_SNAPSHOT" in source
    assert "historical_published_result" in source
    assert "assert result.detected" not in source


def test_longmem_runner_keeps_mutable_databases_on_local_runtime_storage() -> None:
    runner = (
        ROOT / "research/production_benchmarks/run_longmem_pilot.py"
    ).read_text(encoding="utf-8")
    adapter = (
        ROOT / "research/production_benchmarks/longmemeval_v2.py"
    ).read_text(encoding="utf-8")
    assert 'TemporaryDirectory(prefix="atmem-longmem-cases-")' in runner
    assert "local_runtime_root=case_runtime_root" in runner
    assert '"ATMEM_LME_DATABASE_PATH": str(case_runtime / "atmem.db")' in adapter
    assert 'HouseholdApplication.initialize(\n            case_runtime / "atmem.db"' in adapter
    assert "runtime_paths = [case_runtime_root / question_id / method]" in runner
    assert "runtime_paths.append(mem0_runtime_root / question_id)" in runner
    assert "shutil.rmtree(runtime_path)" in runner


def test_checkpoint_resume_preserves_existing_matched_arm_receipts() -> None:
    source = (
        ROOT / "research/production_benchmarks/prepare_longmem_memories.py"
    ).read_text(encoding="utf-8")
    assert "targeted resume must not erase receipts" in source
    assert "for method in METHODS:" in source
    assert 'receipts.sort(key=lambda row:' in source


def test_runpod_reader_proxy_reassembles_sse_without_promoting_reasoning(
    monkeypatch,
) -> None:
    import urllib.request
    from research.production_benchmarks import runpod_reader_proxy

    class Upstream(BaseHTTPRequestHandler):
        user_agent = ""
        payload = None

        def log_message(self, _format, *_args):
            return

        def do_POST(self):  # noqa: N802
            type(self).user_agent = self.headers.get("User-Agent", "")
            type(self).payload = json.loads(
                self.rfile.read(int(self.headers["Content-Length"]))
            )
            chunks = [
                {"id": "fixture", "model": "fixture-reader", "choices": [{
                    "delta": {"reasoning_content": "private reasoning"},
                    "finish_reason": None,
                }]},
                {"id": "fixture", "model": "fixture-reader", "choices": [{
                    "delta": {"content": "final answer"},
                    "finish_reason": "stop",
                }]},
                {"choices": [], "usage": {
                    "prompt_tokens": 4, "completion_tokens": 2,
                    "total_tokens": 6,
                }},
            ]
            body = "".join(
                f"data: {json.dumps(chunk)}\n\n" for chunk in chunks
            ) + "data: [DONE]\n\n"
            encoded = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), runpod_reader_proxy.Handler)
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    monkeypatch.setenv(
        "ATMEM_RUNPOD_UPSTREAM_URL",
        f"http://127.0.0.1:{upstream.server_port}/v1",
    )
    monkeypatch.setenv("RUNPOD_READER_API_KEY", "fixture-key")
    monkeypatch.setenv("ATMEM_READER_REQUEST_MAX_BYTES", "1048576")
    monkeypatch.setenv("ATMEM_READER_SEED", "23801")
    monkeypatch.setenv("ATMEM_READER_STOP_SEQUENCES", '["}"]')
    monkeypatch.setenv("ATMEM_READER_INCLUDE_STOP_STR", "1")
    request = urllib.request.Request(
        f"http://127.0.0.1:{proxy.server_port}/v1/chat/completions",
        data=json.dumps({"model": "fixture-reader", "messages": []}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
    finally:
        proxy.shutdown()
        upstream.shutdown()
        proxy.server_close()
        upstream.server_close()
        proxy_thread.join(timeout=2)
        upstream_thread.join(timeout=2)
    message = result["choices"][0]["message"]
    assert message["content"] == "final answer"
    assert message["reasoning_content"] == "private reasoning"
    assert result["usage"]["total_tokens"] == 6
    assert Upstream.user_agent == "OpenAI/Python 3.19.2"
    assert Upstream.payload["seed"] == 23801
    assert Upstream.payload["stop"] == ["}"]
    assert Upstream.payload["include_stop_str_in_output"] is True


def test_reader_proxy_budget_applies_after_upstream_serialization() -> None:
    from research.production_benchmarks.runpod_reader_proxy import (
        encoded_upstream_body,
    )

    payload = {"model": "reader", "messages": [{"role": "user", "content": "x"}]}
    expanded = encoded_upstream_body(
        payload,
        10_000,
        seed=23801,
        stop_sequences=["}"],
        include_stop_str_in_output=True,
    )
    expanded_payload = json.loads(expanded)
    assert expanded_payload["seed"] == 23801
    assert expanded_payload["stop"] == ["}"]
    assert expanded_payload["include_stop_str_in_output"] is True
    assert len(expanded) > len(json.dumps(payload).encode())
    with pytest.raises(ValueError, match="serialized reader request"):
        encoded_upstream_body(
            payload,
            len(expanded) - 1,
            seed=23801,
            stop_sequences=["}"],
            include_stop_str_in_output=True,
        )


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
                "choices": [{"finish_reason": "stop", "message": {"content": '{"label": 1}'}}],
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
                "choices": [{"finish_reason": "stop", "message": {"content": '{"label": 1}'}}],
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
    from atmem.core.keys import sqlcipher_runtime_status
    from atmem.service.household import HouseholdApplication

    if not sqlcipher_runtime_status()["available"]:
        pytest.skip("LongMem V3 product-path fixture requires SQLCipher")
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
    database = tmp_path / "atmem.db"
    HouseholdApplication.initialize(database, encrypted=True, backend="file")
    adapter = loaded.AtMemMemory({
        "database_path": str(database),
        "subject_id": "subject",
        "agent_id": "agent",
        "workspace_id": "workspace",
        "trajectory_pool_root": str(pool),
        "require_encrypted": True,
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
        "actions": ["Open checkout", "Select Place order"],
        # A text state after an interleaved screenshot exercises V3's compact
        # canonical ordinals rather than relying on media being last.
        "states": [state, {
            "state_index": 1,
            "text": "The order confirmation page is visible.",
        }],
        "gold": "must never enter memory",
    })
    with pytest.raises(ValueError, match="escapes its source root"):
        adapter.insert({
            "id": "trajectory-escape",
            "states": [{"state_index": 0, "screenshot": "../../outside.png"}],
        })

    adapter._memory.freeze_context_engine(adapter.scope)
    result = adapter.query("What is the current checkout label?")
    metadata = adapter.post_query_hook(
        query="What is the current checkout label?",
        query_image=None,
        memory_context=result,
    )
    assert metadata["format"] == "atmem-longmemeval-query-metadata-v2"
    assert metadata["context_sha256"].startswith("sha256:")
    assert metadata["sufficiency"]["required_obligation_ids"]

    text = "\n".join(item["value"] for item in result if item["type"] == "text")
    assert "Place order" in text
    assert "must never enter memory" not in text
    returned_images = [Path(item["value"]) for item in result if item["type"] == "image"]
    assert len(returned_images) == 1
    assert returned_images[0] != image
    assert returned_images[0].read_bytes() == image.read_bytes()
    image.unlink()
    reconstructed = adapter.query("What is the current checkout label?")
    rebuilt_images = [
        Path(item["value"]) for item in reconstructed if item["type"] == "image"
    ]
    assert len(rebuilt_images) == 1
    assert rebuilt_images[0].is_file()
    assert rebuilt_images[0].read_bytes() == b"fixture image bytes"
    records = adapter._memory.store.list_records("subject", statuses=None)
    assert records
    assert {row["source_type"] for row in records} == {"tool_output"}
    assert {row["trust_tier"] for row in records} == {"host_asserted_observation"}
    procedure = adapter.query(
        "According to the usual workflow, how many actions complete checkout?"
    )
    assert "Select Place order" in "\n".join(
        item["value"] for item in procedure if item["type"] == "text"
    )
    adapter._memory.close()


def test_longmem_action_batches_are_bounded_ordered_and_lossless(
    monkeypatch,
) -> None:
    registry: dict[str, type] = {}

    class OfficialMemory:
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
    spec = importlib.util.spec_from_file_location("fixture_longmem_batches", LONGMEM_ASSET)
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)

    actions = [f"action-{index}-" + ("x" * 900) for index in range(20)]
    batches = loaded._ordered_action_batches("trajectory-large", actions)
    decoded = [json.loads(value) for value in batches]
    assert len(batches) > 1
    assert all(len(value.encode("utf-8")) <= 7_000 for value in batches)
    assert [item for batch in decoded for item in batch["actions"]] == actions
    assert [batch["action_offset"] for batch in decoded] == [0, 7, 14]


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


def test_dolphin_rejects_empty_or_length_terminated_agent_turns() -> None:
    from research.production_benchmarks.dolphinbench import (
        _require_completed_interaction,
    )

    with pytest.raises(RuntimeError, match="complete final answer"):
        _require_completed_interaction(SimpleNamespace(messages=[{
            "role": "assistant", "content": "", "finish_reason": "length",
        }]))


def test_dolphin_accepts_official_message_schema_with_driver_completion() -> None:
    from research.production_benchmarks.dolphinbench import _require_completed_interaction

    _require_completed_interaction(SimpleNamespace(
        messages=[{"role": "assistant", "content": "done"}],
        attempts=[{"driver_ok": True}],
    ))


def test_dolphin_rejects_length_terminated_grader_response() -> None:
    from research.production_benchmarks.dolphinbench import (
        require_completed_provider_response,
    )

    with pytest.raises(RuntimeError, match="complete final answer"):
        require_completed_provider_response({
            "choices": [{
                "finish_reason": "length",
                "message": {"content": '{"passed": true}'},
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
        }, role="grader")


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
            settings={"model": kwargs["model"]},
            messages=[
                {"role": "user", "content": kwargs["request"].dated_message},
                {"role": "assistant", "content": "done"},
            ],
            attempts=[{"cost_usd": 0.001, "driver_ok": True}],
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

    household_root = tmp_path / "separate-households"
    prepare_persona_households(tmp_path, household_root=household_root)
    adapter = AtMemDolphinAdapter(
        {
            "agent_driver": "fixture_dolphin_driver:run", "model": "fixture-model",
            "cost_cap_usd": 1.0, "max_interaction_cost_usd": 0.1,
            "allowed_test_ids": {"alex": ["test-1"], "morgan": [], "riley": []},
            "household_root": str(household_root),
            "authorized_history_import": True,
        },
        tmp_path,
    )
    assert adapter.root == household_root.resolve()
    assert adapter.identity()["authorized_history_import"] is True
    assert not (tmp_path / "atmem-personas").exists()
    ingestion = SimpleNamespace(
        persona="alex", phase="ingestion", interaction_id="history-1",
        dated_message="[2026-01-01] My favorite color is blue.", apps={},
    )
    adapter.run_interaction(ingestion)
    assert set(adapter._memories) == {"alex"}
    assert any(
        event["event_type"] == "memory.history_import_authorized"
        and event["actor"] == "benchmark-history-import:alex"
        for event in adapter._memories["alex"].store.list_audit_events("dolphin:alex")
    )
    checkpoint = adapter.freeze("alex")
    assert checkpoint["context_engine"]["source_count"] == 1
    assert checkpoint["context_engine"]["generation_state"] == "active"
    assert checkpoint["context_engine"]["storage"]["source_bytes"] > 0
    assert checkpoint["context_engine"]["storage"]["derived_to_source_ratio"] <= 1.5
    assert adapter._memories == {}
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
    assert adapter.total_cost_usd("ingestion") == 0.0
    assert adapter.total_cost_usd("tests") == 0.001
    with pytest.raises(RuntimeError, match="refusing a blind retry"):
        adapter.run_interaction(test)
    assert len(captured) == 1
    memory = adapter._memory("alex")
    observations = memory.list_context_observations(
        adapter._scope("alex"), source_session_ids=("history-1",)
    )
    assert len(observations) == 1
    assert observations[0]["content"].endswith("favorite color is blue.")
    memory.forget_context_observation(
        adapter._scope("alex"), observations[0]["id"], actor="test-evaluator"
    )
    removed = adapter._recall(memory, "alex", test.dated_message)
    gate = adapter._pre_action_gate_receipt(test, removed)
    assert gate["outcome"] == "blocked_missing_requirement"
    assert gate["model_invoked"] is False
    assert gate["tool_calls"] == 0
    adapter._reserve_interaction_cost("tests", "alex", "missing-cost")
    with pytest.raises(RuntimeError, match="neither aggregate nor attempt cost"):
        adapter._record_cost(
            "tests", "alex", "missing-cost",
            SimpleNamespace(settings={}, attempts=[]),
        )


def test_dolphin_source_chunking_is_bounded_and_lossless() -> None:
    from research.production_benchmarks.dolphinbench import _bounded_text_parts

    source = ("alpha beta gamma " * 400) + "tail"
    parts = _bounded_text_parts(source)

    assert "".join(parts) == source
    assert all(0 < len(part) <= 1_800 for part in parts)


def test_dolphin_mem0_recall_uses_text_without_atmem_package_contract() -> None:
    from research.production_benchmarks.dolphinbench import Mem0DolphinAdapter

    adapter = object.__new__(Mem0DolphinAdapter)
    request = SimpleNamespace(
        persona="alex", interaction_id="7",
    )

    assert adapter._context_from_recall("remembered fact") == "remembered fact"
    receipt = adapter._pre_action_gate_receipt(request, "remembered fact")
    assert receipt == {
        "format": "mem0-dolphin-pre-action-receipt-v1",
        "case_id": "alex:007",
        "outcome": "gate_open",
        "required_requirement_ids": [],
        "covered_requirement_ids": [],
        "missing_requirement_ids": [],
        "actual_reason": "matched_baseline_without_sufficiency_gate",
        "model_invoked": False,
        "tool_calls": 0,
        "error_type": None,
    }


def test_dolphin_development_runner_selects_before_official_execute(
    tmp_path: Path, monkeypatch
) -> None:
    from research.production_benchmarks import dolphinbench

    selected = {
        persona: {f"{index:03d}" for index in range(1, 11)}
        for persona in dolphinbench.PERSONAS
    }
    verification = {
        "source_commit": dolphinbench.PINNED_COMMIT,
        "development_profile_sha256": dolphinbench.PINNED_DEVELOPMENT_PROFILE_SHA256,
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
    adapter.identity = lambda: {"format": "atmem-dolphinbench-adapter-v1"}  # type: ignore[method-assign]
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

    assert len(executed) == 30
    assert set(executed) == {
        (persona, item) for persona, values in selected.items() for item in values
    }
    assert result["tests"] == 30
    assert result["checks"] == 30
    assert result["checks_passed"] == 30
    assert result["tasks_passed"] == 30
    assert result["system_failure_count"] == 0
    assert result["claim"] == "development-30-of-600-not-an-official-score"

    class FailureRunner(Runner):
        directory = tmp_path / "failure"

        def _execute(self, phase, persona, spec):
            if persona == "alex" and int(spec["id"]) == 1:
                raise TimeoutError("fixture timeout")
            return super()._execute(phase, persona, spec)

    for persona in dolphinbench.PERSONAS:
        checkpoint = FailureRunner.directory / "checkpoints" / f"{persona}.json"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text("{}", encoding="utf-8")
    failed = dolphinbench.evaluate_development(FailureRunner(), tmp_path / "checkout")
    assert failed["tests"] == 30
    assert failed["tasks_passed"] == 29
    assert failed["system_failure_count"] == 1
    assert failed["system_failures"][0]["error_type"] == "timeout"


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
