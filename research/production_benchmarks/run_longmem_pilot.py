"""Run the frozen two-arm LongMemEval-V2 development pilot."""

from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from research.production_benchmarks.longmemeval_v2 import (  # noqa: E402
    DatasetPreflight,
    current_hardware_profile,
    preflight_paid_runtime,
    preflight_selected_data,
    run_official_pilot_case,
    verify_installed_adapter,
)
from atmem.benchmark.contracts import validate_retrieval_quality_protocol  # noqa: E402
from research.production_benchmarks.cost_ledger import DurableCostLedger  # noqa: E402


PROTOCOLS = ROOT / "benchmarks/retrieval_quality/protocols"
METHODS = ("no-retrieval", "typed-local")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _installed_product(expected_version: str) -> dict[str, str]:
    from importlib.metadata import version
    import atmem

    module = Path(atmem.__file__).resolve()
    if module.is_relative_to(ROOT) or "site-packages" not in module.parts:
        raise RuntimeError(
            "paid pilot requires an installed AtMem wheel outside the checkout"
        )
    installed_version = version("atmem")
    if installed_version != expected_version:
        raise RuntimeError(
            f"paid pilot requires AtMem {expected_version}; found {installed_version}"
        )
    return {"version": installed_version, "module": str(module)}


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


def _wait_for_judge_gate(
    futures: list[Future[dict[str, Any]]],
    usage_paths: list[Path],
    *,
    deadline: float,
) -> None:
    while True:
        failed = [future.exception() for future in futures if future.done()]
        if failed:
            raise RuntimeError("reader phase failed before the judge gate") from failed[0]
        waiting = 0
        for path in usage_paths:
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
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--confirm-paid-run", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if not args.confirm_paid_run:
        raise SystemExit("refusing paid pilot without --confirm-paid-run")
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
    pilot = _load(PROTOCOLS / "longmemeval-v2-pilot-v1.json")
    dolphin_split = _load(PROTOCOLS / "dolphinbench-task-split-v1.json")
    route_probe = _load(PROTOCOLS / "provider-route-probe-v1.json")
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
    preflight_paid_runtime(protocol, methods=METHODS)
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
            "paid_egress_started": False,
        }, indent=2, sort_keys=True))
        return
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
        "hardware_profile": hardware_profile,
        "methods": list(METHODS),
        "cases": cases,
    }
    _write_progress(progress_path, progress)
    requirements = dict(protocol["paid_run_requirements"])
    billing = dict(requirements["huggingface_reader_billing"])
    protocol_digest = _canonical_digest(protocol)
    hf_ledger = DurableCostLedger(
        benchmark_root / "cost-ledgers" / protocol_digest / "longmem-hf-runtime-ledger.json",
        total_cap_usd=float(requirements["pilot_hf_cost_cap_usd"]),
    )
    hf_key = f"longmem-pilot:{_canonical_digest(pilot)}:hf-endpoint-runtime"
    hf_maximum = (
        float(billing["usd_per_hour"])
        * float(billing["maximum_active_seconds"])
        / 3_600
    )
    hf_ledger.reserve(
        hf_key,
        provider="huggingface-inference-endpoints",
        maximum_usd=hf_maximum,
        metadata={
            "endpoint_name": billing["endpoint_name"],
            "namespace": billing["namespace"],
            "billing_mode": billing["mode"],
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

    def run_case(item: tuple[str, str], *, gated: bool) -> dict[str, Any]:
        question_id, method = item
        domain = domains.get(question_id)
        if domain is None:
            raise AssertionError(f"missing preflighted question domain: {question_id}")
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
            confirmed_paid_run=True,
            data_preflight=data_preflight,
            shared_hf_runtime_reservation=True,
            judge_gate_file=judge_gate if gated else None,
        )
        return {**result, **_case_score(Path(result["output_dir"]))}

    from huggingface_hub import get_inference_endpoint

    endpoint = get_inference_endpoint(
        str(billing["endpoint_name"]),
        namespace=str(billing["namespace"]),
        token=os.environ["HF_TOKEN"],
    )
    endpoint.fetch()
    if str(endpoint.status) != "paused":
        raise RuntimeError(
            "dedicated endpoint must be paused before the metered batch starts"
        )
    active_started = time.monotonic()
    paused = False
    endpoint_receipt = output_root / "hf-endpoint-runtime.json"
    try:
        endpoint.resume(running_ok=True).wait(timeout=900, refresh_every=5)
        deadline = active_started + float(billing["maximum_active_seconds"])
        with ThreadPoolExecutor(max_workers=6) as executor:
            for future in as_completed(
                [executor.submit(run_case, item, gated=False) for item in non_llm_work]
            ):
                cases.append(future.result())
                _write_progress(progress_path, progress)
        with ThreadPoolExecutor(max_workers=len(llm_work)) as executor:
            llm_futures = [
                executor.submit(run_case, item, gated=True) for item in llm_work
            ]
            usage_paths = [
                output_root / "runs" / question_id / method / "judge-usage.json"
                for question_id, method in llm_work
            ]
            _wait_for_judge_gate(llm_futures, usage_paths, deadline=deadline)
            endpoint.pause()
            paused = True
            active_seconds = time.monotonic() - active_started
            hf_cost = active_seconds * float(billing["usd_per_hour"]) / 3_600
            hf_ledger.complete(hf_key, cost_usd=hf_cost)
            _write_progress(
                endpoint_receipt,
                {
                    "format": "atmem-hf-endpoint-runtime-v1",
                    "endpoint_name": billing["endpoint_name"],
                    "namespace": billing["namespace"],
                    "model": protocol["models"]["longmemeval_reader"]["model"],
                    "model_revision": protocol["models"]["longmemeval_reader"]["revision"],
                    "active_seconds_local_observation": round(active_seconds, 3),
                    "usd_per_hour": float(billing["usd_per_hour"]),
                    "estimated_cost_usd": round(hf_cost, 9),
                    "provider_invoice_reconciled": False,
                    "endpoint_state_after_reader_phase": "paused",
                    "reader_case_count": len(work),
                    "content_retained": False,
                },
            )
            _sound_reader_complete()
            print(
                "HF_READER_PHASE_COMPLETE endpoint=paused "
                f"seconds={active_seconds:.3f} estimated_cost_usd={hf_cost:.6f}",
                flush=True,
            )
            judge_gate.write_text("reader phase complete; HF endpoint paused\n", encoding="utf-8")
            for future in as_completed(llm_futures):
                cases.append(future.result())
                _write_progress(progress_path, progress)
    finally:
        if not paused:
            try:
                endpoint.pause()
            except Exception:
                pass
    progress["summary"] = {
        method: {
            "correct": sum(
                1 for case in cases
                if case["method"] == method and case["score_bool"]
            ),
            "total": sum(1 for case in cases if case["method"] == method),
            "hf_cost_usd": None,
            "openai_cost_usd": round(sum(
                float(case["openai_cost_usd"])
                for case in cases if case["method"] == method
            ), 9),
        }
        for method in METHODS
    }
    progress["summary"]["hf_endpoint_runtime"] = _load(endpoint_receipt)
    _write_progress(progress_path, progress)
    print(json.dumps(progress["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
