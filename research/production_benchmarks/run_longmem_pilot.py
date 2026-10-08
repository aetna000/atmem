"""Run the frozen matched LongMemEval-V2 five-percent development profile."""

from __future__ import annotations

import argparse
import atexit
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.append(str(ROOT))

from research.production_benchmarks.longmemeval_v2 import (  # noqa: E402
    DatasetPreflight,
    current_hardware_profile,
    preflight_paid_runtime,
    preflight_reader_processor,
    preflight_selected_data,
    run_official_pilot_case,
    verify_installed_adapter,
)
from atmem.benchmark.contracts import (  # noqa: E402
    canonical_digest,
    validate_retrieval_quality_protocol,
)
from atmem.benchmark.finalization import validate_finalization_gate  # noqa: E402
from atmem.benchmark.attribution import validate_attribution_artifacts  # noqa: E402
from research.production_benchmarks.cost_ledger import DurableCostLedger  # noqa: E402
from research.production_benchmarks.matched_results import write_longmem  # noqa: E402
from research.production_benchmarks.matched_results import write_longmem_controls  # noqa: E402
from research.production_benchmarks.installed_product import (  # noqa: E402
    installed_atmem_identity,
)


PROTOCOLS = ROOT / "benchmarks/retrieval_quality/protocols"
SCORED_METHODS = ("no-retrieval", "typed-local", "mem0-oss", "agentrunbook-r")
CONTROL_METHODS = ("verified-evidence",)
METHODS = (*SCORED_METHODS, *CONTROL_METHODS)
OPTIONAL_RECOMMENDED_METHODS = ("agentrunbook-c", "agentrunbook-c-v2")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _attribution_summary(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Serialize both the shared review policy and benchmark-specific pins."""
    summary: dict[str, Any] = {
        "review_protocol": {
            "protocol_sha256": canonical_digest(artifacts["review_protocol"]),
        }
    }
    for name in ("longmemeval_v2", "dolphinbench"):
        row = artifacts[name]
        summary[name] = {
            "manifest_sha256": row["manifest"]["manifest_sha256"],
            "equivalence_sha256": row["equivalence"]["receipt_sha256"],
        }
    return summary


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tree_digest(root: Path) -> str:
    """Content-bind a prebuilt memory tree without retaining its contents."""
    if not root.is_dir():
        raise RuntimeError(f"benchmark checkpoint root does not exist: {root}")
    files: dict[str, str] = {}
    for path in sorted(
        value for value in root.rglob("*")
        if value.is_file() and not value.name.startswith("._") and value.name != ".DS_Store"
    ):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        files[path.relative_to(root).as_posix()] = digest.hexdigest()
    if not files:
        raise RuntimeError("benchmark checkpoint root contains no files")
    return "sha256:" + _canonical_digest(files)


def _expected_probe_set_sha256() -> str:
    probes = []
    for condition in (
        "short_control", "oracle_evidence", "product_context",
        "worst_budget_multimodal",
    ):
        for _ in range(3):
            probes.append({
                "probe_id": f"reader-{condition}-{len(probes)}",
                "role": "reader", "condition": condition,
            })
    probes.extend({
        "probe_id": f"judge-{index}", "role": "judge",
        "condition": "official_judge",
    } for index in range(3))
    return canonical_digest(probes)


def _installed_product(expected_version: str) -> dict[str, str]:
    return installed_atmem_identity(expected_version)


def _question_domains(data_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in (data_root / "questions.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        question_id = str(row.get("id") or "")
        domain = str(row.get("domain") or "")
        if question_id and domain in {"web", "enterprise"}:
            result[question_id] = domain
    return result


def _question_evaluators(data_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in (data_root / "questions.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        question_id = str(row.get("id") or "")
        evaluator = str(row.get("eval_function") or "").split("|", 1)[0]
        if question_id:
            result[question_id] = evaluator
    return result


def _sound_reader_complete() -> None:
    import subprocess

    sound = Path("/System/Library/Sounds/Glass.aiff")
    if sys.platform == "darwin" and sound.is_file():
        for _ in range(4):
            subprocess.run(
                ["afplay", os.fspath(sound)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def _probe_reader(base_url: str, api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "OpenAI/Python 3.19.2",
        },
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
        status = response.status
    models = [str(row.get("id")) for row in payload.get("data", [])]
    return {
        "status": status,
        "duration_ms": round((time.monotonic() - started) * 1_000, 3),
        "models": models,
    }


def _terminate_runpod_pod(pod_id: str) -> bool:
    binary = os.environ.get("RUNPODCTL_BIN", "runpodctl")
    environment = dict(os.environ)
    environment["RUNPOD_API_KEY"] = environment["RUN_POD"]
    completed = subprocess.run(
        [binary, "pod", "delete", pod_id],
        env=environment,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
    )
    return completed.returncode == 0


def _wait_for_reader_proxy(process: subprocess.Popen[bytes], ready: Path) -> str:
    for _ in range(200):
        if ready.is_file():
            value = str(json.loads(ready.read_text(encoding="utf-8"))["base_url"])
            if value.startswith("http://127.0.0.1:"):
                return value
            raise RuntimeError("reader proxy advertised a non-loopback URL")
        if process.poll() is not None:
            raise RuntimeError("reader proxy exited before readiness")
        time.sleep(0.05)
    raise RuntimeError("reader proxy did not become ready")


def _wait_for_judge_gate(
    futures: list[Future[dict[str, Any]]],
    usage_paths: list[Path],
    *,
    deadline: float,
) -> None:
    while True:
        waiting = 0
        for future, path in zip(futures, usage_paths, strict=True):
            # run_case converts every ordinary case failure into a denominator
            # row. A completed failed case therefore needs no judge gate.
            if future.done():
                waiting += 1
                continue
            if not path.is_file():
                continue
            try:
                state = json.loads(path.read_text(encoding="utf-8")).get("state")
            except (OSError, json.JSONDecodeError):
                continue
            waiting += state == "waiting_for_reader_phase_gate"
        if waiting == len(usage_paths):
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("Qwen reader phase exceeded the frozen endpoint runtime")
        time.sleep(0.5)


def preflight_pilot_data(
    data_root: Path, question_ids: list[str], dataset: dict[str, Any]
) -> DatasetPreflight:
    return preflight_selected_data(
        data_root,
        question_ids,
        dataset_revision=str(dataset["dataset_revision"]),
        expected_sha256=dict(dataset["content_sha256"]),
    )


def _write_progress(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
    if os.name == "posix":
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _case_score(output_dir: Path) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in (output_dir / "per_question.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line
    ]
    if len(rows) != 1:
        raise RuntimeError("pilot case must contain exactly one scored question")
    row = rows[0]
    return {
        "question_id": row["question_id"],
        "score": float(row["score"]),
        "score_bool": bool(row["score_bool"]),
        "category": row["category"],
        "eval_function": row["eval_function"],
        "memory_context_token_count": int(row["memory_context_token_count"]),
        "memory_context_was_truncated": bool(row["memory_context_was_truncated"]),
        "memory_post_query_metadata": row.get("memory_post_query_metadata"),
        "response_parsed_boxed": row.get("response_parsed_boxed"),
        "is_unknown": bool(row.get("is_unknown")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--confirm-paid-run", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--finalization-gate")
    args = parser.parse_args()
    if not args.confirm_paid_run:
        raise SystemExit("refusing paid pilot without --confirm-paid-run")
    if subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip():
        raise SystemExit("paid pilot requires the exact clean reviewed commit")
    checkout = Path(args.checkout).expanduser().resolve()
    data_root = Path(args.data_root).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    benchmark_root_value = os.environ.get("ATMEM_BENCHMARK_ROOT", "").strip()
    if not benchmark_root_value:
        raise SystemExit(
            "paid pilot requires ATMEM_BENCHMARK_ROOT for shared cost accounting"
        )
    benchmark_root = Path(benchmark_root_value).expanduser().resolve()
    try:
        output_root.relative_to(benchmark_root)
    except ValueError as exc:
        raise SystemExit(
            "paid pilot output must be inside ATMEM_BENCHMARK_ROOT"
        ) from exc

    protocol_path = PROTOCOLS / "2.3.8.yaml"
    protocol = _load(protocol_path)
    question_split = _load(PROTOCOLS / "longmemeval-v2-question-split-v1.json")
    pilot = _load(PROTOCOLS / "longmemeval-v2-development-5pct-v1.json")
    dolphin_split = _load(PROTOCOLS / "dolphinbench-development-5pct-v1.json")
    route_probe = _load(PROTOCOLS / "provider-route-probe-v1.json")
    attribution_artifacts = validate_attribution_artifacts(
        protocol,
        protocols_root=PROTOCOLS,
        longmem_case_ids=pilot["question_ids"],
        dolphin_case_ids=dolphin_split["development_ids"],
    )
    validate_retrieval_quality_protocol(
        protocol,
        split=question_split,
        pilot=pilot,
        dolphin_split=dolphin_split,
        route_probe=route_probe,
        for_pilot_run=True,
        external_root=output_root,
        repository_root=ROOT,
    )
    installed_product = _installed_product(
        str(protocol["paid_run_requirements"]["candidate_atmem_version"])
    )
    preflight_paid_runtime(
        protocol,
        methods=METHODS,
        require_live_reader=not args.preflight_only,
    )
    processor_preflight = preflight_reader_processor(protocol)
    expected_hardware = protocol["paid_run_requirements"]["hardware_profile"]
    hardware_profile = current_hardware_profile()
    if hardware_profile != expected_hardware:
        raise RuntimeError(
            "paid pilot hardware differs from the frozen protocol: "
            f"{hardware_profile}"
        )
    domains = _question_domains(data_root)
    missing_domains = sorted(set(pilot["question_ids"]) - set(domains))
    if missing_domains:
        raise RuntimeError(
            "pilot questions are absent from the pinned dataset: "
            + ", ".join(missing_domains)
        )
    data_preflight = preflight_pilot_data(
        data_root,
        pilot["question_ids"],
        dict(protocol["datasets"]["longmemeval_v2"]),
    )
    if (
        data_preflight.selected_input_manifest_sha256
        != pilot["selected_input_manifest_sha256"]
    ):
        raise RuntimeError(
            "selected official dataset media differs from the frozen pilot manifest"
        )
    verification = verify_installed_adapter(checkout)
    if args.preflight_only:
        print(json.dumps({
            "status": "ready",
            "installed_product": installed_product,
            "official_checkout": verification,
            "hardware_profile": hardware_profile,
            "data_preflight": data_preflight.report(),
            "reader_processor": processor_preflight,
            "attribution_artifacts": _attribution_summary(attribution_artifacts),
            "paid_egress_started": False,
        }, indent=2, sort_keys=True))
        return
    if not args.finalization_gate:
        raise RuntimeError(
            "paid pilot requires --finalization-gate"
        )
    cost_authorization_id = os.environ.get("ATMEM_COST_AUTHORIZATION_ID", "").strip()
    if not cost_authorization_id:
        raise RuntimeError("paid pilot requires ATMEM_COST_AUTHORIZATION_ID")
    gate = _load(Path(args.finalization_gate).expanduser().resolve())
    reader = dict(protocol["models"]["longmemeval_reader"])
    judge = dict(protocol["models"]["longmemeval_judge"])
    requirements = dict(protocol["paid_run_requirements"])
    prebuilt_root_value = os.environ.get("ATMEM_LME_PREBUILT_ROOT", "").strip()
    if not prebuilt_root_value:
        raise RuntimeError("paid pilot requires ATMEM_LME_PREBUILT_ROOT")
    gate_prebuilt_root = Path(prebuilt_root_value).expanduser().resolve()
    mem0_checkout_value = os.environ.get("ATMEM_MEM0_CHECKOUT", "").strip()
    if not mem0_checkout_value:
        raise RuntimeError("paid pilot requires ATMEM_MEM0_CHECKOUT")
    mem0_checkout = Path(mem0_checkout_value).expanduser().resolve()
    if not (mem0_checkout / "mem0").is_dir():
        raise RuntimeError(
            "ATMEM_MEM0_CHECKOUT must contain the pinned Mem0 source checkout"
        )
    expected_identity = {
        "gate_type": "longmemeval",
        "candidate_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip(),
        "candidate_artifact_sha256": installed_product["artifact_sha256"],
        "checkpoint_sha256": _tree_digest(gate_prebuilt_root),
        "provider": reader["provider"],
        "model": reader["model"],
        "model_revision": reader["revision"],
        "processor_sha256": canonical_digest(processor_preflight),
        "prompt_sha256": "sha256:" + requirements["reader_prompt_sha256"],
        "proxy_sha256": "sha256:" + hashlib.sha256(
            (ROOT / "research/production_benchmarks/runpod_reader_proxy.py").read_bytes()
        ).hexdigest(),
        "concurrency": int(requirements["reader_runtime_billing"]["max_num_seqs"]),
        "input_budget": int(reader["max_prompt_tokens"]),
        "output_budget": int(reader["max_completion_tokens"]),
        "sampling": {
            "temperature": reader["temperature"], "top_p": reader["top_p"],
            "top_k": reader["top_k"], "enable_thinking": reader["enable_thinking"],
        },
        "judge_provider": judge["provider"],
        "judge_model": judge["model"],
        "judge_revision": judge["revision"],
        "judge_prompt_sha256": "sha256:" + requirements["judge_prompt_sha256"],
        "probe_set_sha256": _expected_probe_set_sha256(),
        "run_config_sha256": "sha256:" + _canonical_digest({
            "protocol": protocol,
            "pilot": pilot,
            "question_split": question_split,
            "installed_product": installed_product,
            "official_checkout": verification,
            "processor": processor_preflight,
            "hardware_profile": hardware_profile,
            "methods": METHODS,
        }),
        "cost_authorization_id": cost_authorization_id,
        "runner_sha256": "sha256:" + _canonical_digest({
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                ROOT / "research/production_benchmarks/run_longmem_pilot.py",
                ROOT / "research/production_benchmarks/longmemeval_v2.py",
                ROOT / "research/production_benchmarks/adapters/longmemeval_atmem.py",
                ROOT / "research/production_benchmarks/adapters/longmemeval_verified.py",
            )
        }),
        "grader_runtime": {
            "provider": judge["provider"], "model": judge["model"],
            "revision": judge["revision"],
            "prompt_sha256": "sha256:" + requirements["judge_prompt_sha256"],
        },
        "agent_driver_target": "longmemeval-reader-proxy",
        "agent_driver_sha256": "sha256:" + hashlib.sha256(
            (ROOT / "research/production_benchmarks/runpod_reader_proxy.py").read_bytes()
        ).hexdigest(),
    }
    validate_finalization_gate(
        gate,
        expected_identity=expected_identity,
        expected_gate_type="longmemeval",
    )
    output_root.mkdir(parents=True, exist_ok=False)
    progress_path = output_root / "pilot-progress.json"
    cases: list[dict[str, Any]] = []
    progress = {
        "format": "atmem-longmemeval-v2-development-pilot-v1",
        "claim": "development-plumbing-and-directional-quality-only",
        "protocol_sha256": _canonical_digest(protocol),
        "pilot_sha256": _canonical_digest(pilot),
        "official_checkout": verification,
        "installed_product": installed_product,
        "data_preflight": data_preflight.report(),
        "reader_processor": processor_preflight,
        "hardware_profile": hardware_profile,
        "methods": list(METHODS),
        "attribution_artifacts": _attribution_summary(attribution_artifacts),
        "cases": cases,
    }
    _write_progress(progress_path, progress)
    requirements = dict(protocol["paid_run_requirements"])
    billing = dict(requirements["reader_runtime_billing"])
    pod_id = os.environ.get("ATMEM_RUNPOD_POD_ID", "").strip()
    reader_base_url = os.environ.get("ATMEM_READER_BASE_URL", "").strip()
    reader_api_key = os.environ.get("RUNPOD_READER_API_KEY", "").strip()
    billed_started_unix = float(os.environ.get("ATMEM_RUNPOD_BILLED_STARTED_UNIX", "0"))
    attempt = int(os.environ.get("ATMEM_BENCHMARK_ATTEMPT", "0"))
    if (
        not pod_id
        or not reader_base_url
        or not reader_api_key
        or billed_started_unix <= 0
        or attempt <= 0
    ):
        raise RuntimeError(
            "Runpod pilot requires the frozen pod id, URL, key, billing start and attempt"
        )
    pod_cleanup = {"required": True}

    def cleanup_runpod() -> None:
        if pod_cleanup["required"] and _terminate_runpod_pod(pod_id):
            pod_cleanup["required"] = False

    # This covers preflight/reservation failures that happen before the main
    # reader try/finally block. The regular finally below performs immediate
    # cleanup; this is the last-resort process-exit guard.
    atexit.register(cleanup_runpod)
    protocol_digest = _canonical_digest(protocol)
    authorization_digest = hashlib.sha256(
        cost_authorization_id.encode("utf-8")
    ).hexdigest()
    reader_ledger = DurableCostLedger(
        benchmark_root / "cost-ledgers" / authorization_digest / "longmem-reader-runtime-ledger.json",
        total_cap_usd=float(requirements["pilot_reader_cost_cap_usd"]),
    )
    reader_key = (
        f"longmem-pilot:{_canonical_digest(pilot)}:runpod-runtime:attempt-{attempt}"
    )
    elapsed_billed_seconds = max(0.0, time.time() - billed_started_unix)
    remaining_billed_seconds = max(
        0.0,
        float(billing["maximum_active_seconds"]) - elapsed_billed_seconds,
    )
    reader_maximum = (
        float(billing["usd_per_hour"])
        * remaining_billed_seconds
        / 3_600
    )
    if reader_maximum <= 0:
        raise RuntimeError("Runpod pod exceeded the frozen active-time limit")
    reader_ledger.reserve(
        reader_key,
        provider="runpod-pods",
        maximum_usd=reader_maximum,
        metadata={
            "protocol_sha256": protocol_digest,
            "pod_id": os.environ.get("ATMEM_RUNPOD_POD_ID"),
            "hardware_id": billing["hardware_id"],
            "billing_mode": billing["mode"],
            "attempt": attempt,
            "elapsed_billed_seconds_before_attempt": round(elapsed_billed_seconds, 3),
        },
    )
    evaluators = _question_evaluators(data_root)
    llm_evaluators = {"llm_abstention_checker", "llm_gotchas_checker"}
    work = [
        (question_id, method)
        for question_id in pilot["question_ids"]
        for method in METHODS
    ]
    non_llm_work = [item for item in work if evaluators[item[0]] not in llm_evaluators]
    llm_work = [item for item in work if evaluators[item[0]] in llm_evaluators]
    judge_gate = output_root / "openai-judge.gate"
    reader_proxy_url = ""
    prebuilt_root_value = os.environ.get("ATMEM_LME_PREBUILT_ROOT", "").strip()
    if not prebuilt_root_value:
        raise RuntimeError("pilot requires ATMEM_LME_PREBUILT_ROOT")
    prebuilt_root = Path(prebuilt_root_value).expanduser().resolve()
    prebuilt_memory = {
        (method, domain): prebuilt_root / method / domain / "memory_state"
        for method in SCORED_METHODS
        if method != "no-retrieval"
        for domain in ("web", "enterprise")
    }
    no_retrieval_memory = prebuilt_root / "no-retrieval" / "memory_state"
    cancellation_event = threading.Event()
    missing_prebuilt = [
        str(path) for path in prebuilt_memory.values()
        if not (path / "memory_config.json").is_file()
    ]
    if not (no_retrieval_memory / "memory_config.json").is_file():
        missing_prebuilt.append(str(no_retrieval_memory))
    if missing_prebuilt:
        raise RuntimeError(
            "pilot prebuilt AtMem memories are missing: " + ", ".join(missing_prebuilt)
        )

    def run_case(item: tuple[str, str], *, gated: bool) -> dict[str, Any]:
        question_id, method = item
        domain = domains.get(question_id)
        if domain is None:
            raise AssertionError(f"missing preflighted question domain: {question_id}")
        identity = {
            "reader_identity_sha256": _canonical_digest(
                protocol["models"]["longmemeval_reader"]
            ),
            "reader_prompt_sha256": "sha256:" + requirements["reader_prompt_sha256"],
        }
        try:
            result = run_official_pilot_case(
                checkout,
                data_root=data_root,
                output_root=output_root,
                question_id=question_id,
                domain=domain,
                method=method,
                protocol_path=protocol_path,
                question_split=question_split,
                pilot=pilot,
                dolphin_split=dolphin_split,
                route_probe=route_probe,
                environment={
                    "ATMEM_READER_BASE_URL": reader_proxy_url,
                    "ATMEM_COST_AUTHORIZATION_ID": cost_authorization_id,
                    **({
                        "ATMEM_MEM0_CHECKOUT": str(mem0_checkout),
                        "ATMEM_MEM0_STORAGE_PATH": str(
                            output_root / "runtime-mem0" / question_id
                        ),
                    } if method == "mem0-oss" else {}),
                    **({
                        "ATMEM_LME_REQUIREMENT_MANIFEST": str(
                            PROTOCOLS / "longmemeval-v2-requirements-5pct-v1.json"
                        ),
                    } if method == "verified-evidence" else {}),
                },
                confirmed_paid_run=True,
                data_preflight=data_preflight,
                shared_reader_runtime_reservation=True,
                judge_gate_file=judge_gate if gated else None,
                load_memory_dir=(
                    prebuilt_memory[(method, domain)]
                    if method in {"typed-local", "mem0-oss", "agentrunbook-r"}
                    else no_retrieval_memory if method == "no-retrieval" else None
                ),
                cancellation_event=cancellation_event,
                deadline_monotonic=deadline,
            )
            return {**result, **_case_score(Path(result["output_dir"])), **identity}
        except Exception as exc:
            lowered = str(exc).casefold()
            if isinstance(exc, TimeoutError) or "timeout" in lowered or "deadline" in lowered:
                error_type = "timeout"
            elif isinstance(exc, (json.JSONDecodeError, ValueError)) and any(
                token in lowered for token in ("json", "parse", "malformed")
            ):
                error_type = "parse_error"
            else:
                error_type = "provider_error"
            return {
                "format": "atmem-longmemeval-pilot-case-v1",
                "question_id": question_id,
                "domain": domain,
                "method": method,
                "output_dir": str(output_root / "runs" / question_id / method),
                "score": 0.0,
                "score_bool": False,
                "memory_context_token_count": 0,
                "memory_context_was_truncated": False,
                "memory_post_query_metadata": None,
                "response_parsed_boxed": None,
                "is_unknown": True,
                "openai_cost_usd": 0.0,
                "reader_cost_usd": None,
                "error_type": error_type,
                "error_class": type(exc).__name__,
                "error_message": str(exc),
                "actual_reason": "system_failure",
                **identity,
            }

    def run_batch(
        items: list[tuple[str, str]], *, max_workers: int, gated: bool
    ) -> list[dict[str, Any]]:
        """Run cases, durably checkpoint each success, and fail fast."""

        executor = ThreadPoolExecutor(max_workers=max_workers)
        futures = [executor.submit(run_case, item, gated=gated) for item in items]
        completed_cases: list[dict[str, Any]] = []
        try:
            for future in as_completed(futures):
                case = future.result()
                completed_cases.append(case)
                cases.append(case)
                _write_progress(progress_path, progress)
        except BaseException:
            cancellation_event.set()
            for future in futures:
                future.cancel()
            executor.shutdown(wait=True, cancel_futures=True)
            raise
        executor.shutdown(wait=True)
        return completed_cases

    try:
        probe = _probe_reader(reader_base_url, reader_api_key)
    except Exception:
        _terminate_runpod_pod(pod_id)
        raise
    if protocol["models"]["longmemeval_reader"]["model"] not in probe["models"]:
        raise RuntimeError("Runpod vLLM server does not expose the frozen reader model")
    terminated = False
    reader_proxy: subprocess.Popen[bytes] | None = None
    endpoint_receipt = output_root / "runpod-pod-runtime.json"
    try:
        reader_proxy_source = Path(__file__).with_name("runpod_reader_proxy.py")
        reader_proxy_ready = output_root / "reader-proxy-ready.json"
        proxy_environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "ATMEM_RUNPOD_UPSTREAM_URL": reader_base_url,
            "RUNPOD_READER_API_KEY": reader_api_key,
            "ATMEM_READER_REQUEST_MAX_BYTES": str(
                requirements["reader_request_max_bytes"]
            ),
        }
        reader_proxy = subprocess.Popen(
            [
                sys.executable,
                os.fspath(reader_proxy_source),
                "--ready-file",
                os.fspath(reader_proxy_ready),
            ],
            cwd=output_root,
            env=proxy_environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        reader_proxy_url = _wait_for_reader_proxy(reader_proxy, reader_proxy_ready)
        deadline = time.monotonic() + remaining_billed_seconds
        run_batch(non_llm_work, max_workers=2, gated=False)
        # Every LLM-judged case must reach the local gate before Runpod is
        # terminated. The remote vLLM server still enforces max_num_seqs=2.
        executor = ThreadPoolExecutor(max_workers=len(llm_work))
        llm_futures = [
            executor.submit(run_case, item, gated=True) for item in llm_work
        ]
        try:
            usage_paths = [
                output_root / "runs" / question_id / method / "judge-usage.json"
                for question_id, method in llm_work
            ]
            _wait_for_judge_gate(llm_futures, usage_paths, deadline=deadline)
            terminated = _terminate_runpod_pod(pod_id)
            if not terminated:
                raise RuntimeError("Runpod pod termination failed; manual action required")
            pod_cleanup["required"] = False
            active_seconds = time.time() - billed_started_unix
            reader_cost = active_seconds * float(billing["usd_per_hour"]) / 3_600
            reader_ledger.complete(reader_key, cost_usd=reader_cost)
            _write_progress(
                endpoint_receipt,
                {
                    "format": "atmem-runpod-pod-runtime-v1",
                    "pod_id": pod_id,
                    "cloud_type": billing["cloud_type"],
                    "hardware_id": billing["hardware_id"],
                    "container_image": billing["container_image"],
                    "model": protocol["models"]["longmemeval_reader"]["model"],
                    "model_revision": protocol["models"]["longmemeval_reader"]["revision"],
                    "active_seconds_local_observation": round(active_seconds, 3),
                    "usd_per_hour": float(billing["usd_per_hour"]),
                    "estimated_cost_usd": round(reader_cost, 9),
                    "provider_invoice_reconciled": False,
                    "pod_state_after_reader_phase": "terminated",
                    "reader_case_count": len(work),
                    "readiness_probe": probe,
                    "content_retained": False,
                },
            )
            _sound_reader_complete()
            print(
                "RUNPOD_READER_PHASE_COMPLETE pod=terminated "
                f"seconds={active_seconds:.3f} estimated_cost_usd={reader_cost:.6f}",
                flush=True,
            )
            judge_gate.write_text("reader phase complete; Runpod pod terminated\n", encoding="utf-8")
            for future in as_completed(llm_futures):
                case = future.result()
                cases.append(case)
                _write_progress(progress_path, progress)
        except BaseException:
            cancellation_event.set()
            for future in llm_futures:
                future.cancel()
            executor.shutdown(wait=True, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True)
    finally:
        cancellation_event.set()
        if reader_proxy is not None and reader_proxy.poll() is None:
            reader_proxy.terminate()
            try:
                reader_proxy.wait(timeout=5)
            except subprocess.TimeoutExpired:
                reader_proxy.kill()
                reader_proxy.wait(timeout=5)
        if not terminated:
            try:
                if _terminate_runpod_pod(pod_id):
                    pod_cleanup["required"] = False
            except Exception:
                pass
    progress["summary"] = {
        method: {
            "correct": sum(
                1 for case in cases
                if case["method"] == method and case["score_bool"]
            ),
            "total": sum(1 for case in cases if case["method"] == method),
            "reader_cost_usd": None,
            "openai_cost_usd": round(sum(
                float(case["openai_cost_usd"])
                for case in cases if case["method"] == method
            ), 9),
        }
        for method in METHODS
    }
    expected_pairs = {
        (question_id, method)
        for question_id in pilot["question_ids"] for method in METHODS
    }
    actual_pairs = {(row["question_id"], row["method"]) for row in cases}
    if actual_pairs != expected_pairs or len(cases) != len(expected_pairs):
        raise RuntimeError("LongMem run did not retain every frozen case/method outcome")
    progress["summary"]["reader_runtime"] = _load(endpoint_receipt)
    _write_progress(progress_path, progress)
    progress["matched_report"] = write_longmem(
        progress_path, output_root / "matched-results.json", methods=SCORED_METHODS
    )
    progress["controlled_reader_report"] = write_longmem_controls(
        progress_path, output_root / "controlled-reader-results.json"
    )
    _write_progress(progress_path, progress)
    print(json.dumps(progress["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
