"""Run the frozen two-arm LongMemEval-V2 development pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.production_benchmarks.longmemeval_v2 import (  # noqa: E402
    DatasetPreflight,
    current_hardware_profile,
    preflight_paid_runtime,
    preflight_selected_data,
    run_official_pilot_case,
    verify_installed_adapter,
)
from atmem.benchmark.contracts import validate_retrieval_quality_protocol  # noqa: E402


PROTOCOLS = ROOT / "benchmarks/retrieval_quality/protocols"
METHODS = ("no-retrieval", "typed-local")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    output_root.mkdir(parents=True, exist_ok=False)
    progress_path = output_root / "pilot-progress.json"
    cases: list[dict[str, Any]] = []
    progress = {
        "format": "atmem-longmemeval-v2-development-pilot-v1",
        "claim": "development-plumbing-and-directional-quality-only",
        "protocol_sha256": _canonical_digest(protocol),
        "pilot_sha256": _canonical_digest(pilot),
        "official_checkout": verification,
        "data_preflight": data_preflight.report(),
        "hardware_profile": hardware_profile,
        "methods": list(METHODS),
        "cases": cases,
    }
    _write_progress(progress_path, progress)
    for question_id in pilot["question_ids"]:
        domain = domains.get(question_id)
        if domain is None:  # guarded before output creation
            raise AssertionError(f"missing preflighted question domain: {question_id}")
        for method in METHODS:
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
            )
            score = _case_score(Path(result["output_dir"]))
            cases.append({**result, **score})
            _write_progress(progress_path, progress)
    progress["summary"] = {
        method: {
            "correct": sum(
                1 for case in cases
                if case["method"] == method and case["score_bool"]
            ),
            "total": sum(1 for case in cases if case["method"] == method),
            "hf_cost_usd": round(sum(
                float(case["hf_cost_usd"])
                for case in cases if case["method"] == method
            ), 9),
            "openai_cost_usd": round(sum(
                float(case["openai_cost_usd"])
                for case in cases if case["method"] == method
            ), 9),
        }
        for method in METHODS
    }
    _write_progress(progress_path, progress)
    print(json.dumps(progress["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
