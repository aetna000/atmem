from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import subprocess
import time
from typing import Any, Iterable, Sequence

from research.laya_formation.training.contracts import (
    CROSS_BACKEND_TOLERANCE,
    FORMAT_CALIBRATION,
    FORMAT_MANIFEST,
    FORMAT_METRICS,
    SAME_BACKEND_TOLERANCE,
    assert_finite,
    calibration_power,
    canonical_digest,
    class_distribution,
    collapse_report,
    secret_findings,
    truncation_report,
    validate_manifest,
    write_json,
)
from research.laya_formation.training.smoke import (
    _verify_base_files,
    sha256_file,
)
from research.laya_memory_evidence.training_view import (
    V3_QUESTION_IDS,
    V2_QUESTION_IDS,
    option_ids as memory_option_ids,
    question_definitions,
    to_laya_rows as to_memory_evidence_laya_rows,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_rows(path: Path, expected_split: str) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    accepted = {expected_split}
    if expected_split == "test":
        accepted.add("sealed_test")
    wrong = sorted({row["partition"] for row in rows} - accepted)
    if wrong:
        raise ValueError(f"{path} contains unexpected splits: {wrong}")
    return rows


def _macro_f1(expected: Sequence[str], predicted: Sequence[str]) -> float:
    labels = sorted(set(expected) | set(predicted))
    scores = []
    for label in labels:
        tp = sum(e == label and p == label for e, p in zip(expected, predicted))
        fp = sum(e != label and p == label for e, p in zip(expected, predicted))
        fn = sum(e == label and p != label for e, p in zip(expected, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def _labels(rows: Sequence[dict[str, Any]], records: Sequence[tuple]) -> tuple[list[str], list[str]]:
    import numpy as np

    expected, predicted = [], []
    for row, (_qtype, logits, target, count) in zip(rows, records):
        choices = memory_option_ids(row)
        gold = int(np.asarray(target[:count]).argmax())
        pred = int(np.asarray(logits[:count]).argmax())
        qid = row["request"]["question"]["question_id"]
        expected.append(f"{qid}:{choices[gold]}")
        predicted.append(f"{qid}:{choices[pred]}")
    return expected, predicted


def _truncation_rows(train: Any, tok: Any, items: Sequence[dict[str, Any]],
                     source_rows: Sequence[dict[str, Any]], max_len: int,
                     head_max_len: int) -> list[dict[str, Any]]:
    records = []
    for item, source in zip(items, source_rows):
        _ids, _markers, stats = train.build_sequence(
            tok, None, item["q"], max_len, head_max_len,
            state_ids=item["state_ids"], return_truncation_stats=True,
        )
        records.append({"example_id": source["transition_id"], **stats})
    return records


def _inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(root).as_posix(), "size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(root.rglob("*")) if path.is_file()
    ]


def _versions() -> dict[str, str]:
    values = {}
    for name in ("laya", "torch", "transformers", "safetensors", "huggingface-hub", "numpy"):
        values[name] = importlib.metadata.version(name)
    return values


def _question_digest(rows: Sequence[dict[str, Any]]) -> str:
    return canonical_digest(question_definitions(rows))


def _hard_target(row: dict[str, Any]) -> str:
    # V3 option IDs are deliberately opaque and position-dependent. Balance on
    # the adjudicated semantic operation, never on an accidental option index.
    if row.get("expected_operation"):
        return str(row["expected_operation"])
    response = row["expected_response"]
    if response["type"] == "choice":
        return str(response["choice"])
    if response["type"] == "noul":
        return "true" if float(response["noul"]) >= 0.5 else "false"
    return str(int(float(response["score"])))


def _balance_training_rows(
    rows: Sequence[dict[str, Any]], *, seed: int, maximum_repeat: int = 8,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Bound class imbalance by resampling only authentic training examples."""

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        question_id = str(row["request"]["question"]["question_id"])
        grouped.setdefault(question_id, {}).setdefault(_hard_target(row), []).append(row)
    rng = random.Random(seed)
    balanced: list[dict[str, Any]] = []
    report: dict[str, Any] = {}
    for question_id, classes in sorted(grouped.items()):
        largest = max(len(items) for items in classes.values())
        sampled_counts: dict[str, int] = {}
        for label, items in sorted(classes.items()):
            target = min(largest, len(items) * maximum_repeat)
            selected = list(items)
            while len(selected) < target:
                selected.append(items[rng.randrange(len(items))])
            rng.shuffle(selected)
            balanced.extend(selected)
            sampled_counts[label] = len(selected)
        report[question_id] = {
            "original": {label: len(items) for label, items in sorted(classes.items())},
            "sampled": sampled_counts, "maximum_repeat": maximum_repeat,
        }
    rng.shuffle(balanced)
    return balanced, report


def _semantic_operation_coverage(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    trajectories: dict[str, set[str]] = {}
    for row in rows:
        operation = str(row.get("expected_operation") or _hard_target(row))
        trajectories.setdefault(operation, set()).add(str(row["trajectory_id"]))
    counts = {key: len(value) for key, value in sorted(trajectories.items())}
    underpowered = {
        key: value for key, value in counts.items()
        if key not in {"REVIEW"} and value < 100
    }
    return {
        "minimum_distinct_trajectories_per_operation": 100,
        "distinct_trajectory_counts": counts,
        "underpowered_operations": underpowered,
        "sufficient": not underpowered,
    }


def _metric_report(run_id: str, objective: str, split: str, history: Sequence[float],
                   rows: Sequence[dict[str, Any]], records: Sequence[tuple],
                   truncation: dict[str, Any], train: Any) -> dict[str, Any]:
    evaluation = train.evaluate_records(records)
    expected, predicted = _labels(rows, records)
    report = {
        "format": FORMAT_METRICS,
        "run_id": run_id,
        "objective": objective,
        "split": split,
        "loss_history": list(history),
        "accuracy": evaluation["accuracy"],
        "macro_f1": _macro_f1(expected, predicted),
        "nll": evaluation["loss"],
        "brier": evaluation["brier"],
        "ece": evaluation["ece"],
        "class_distribution": class_distribution(expected),
        "collapse": {
            **collapse_report(expected, predicted),
            "laya_stats": train.collapse_stats(records),
            "laya_warning": train.prior_collapse_message(records),
        },
        "truncation": truncation,
        "nonfinite": False,
    }
    assert_finite(history, label="training loss")
    assert_finite(
        [report[name] for name in ("accuracy", "macro_f1", "nll", "brier", "ece")],
        label=f"{split} metrics",
    )
    return report


def run(root: Path, output: Path, objective: str, device_name: str, micro_batch: int,
        grad_accum: int, epochs: int, code_revision: str,
        research_only: bool = False) -> dict[str, Any]:
    import torch
    import laya
    import laya.train as train
    from huggingface_hub import snapshot_download
    from laya.calibrate import fit_abstention_thresholds, fit_temperature_map

    if objective not in {"soft-ce", "rlcd"}:
        raise ValueError("objective must be soft-ce or rlcd")
    if laya.__version__ != "0.4.2":
        raise RuntimeError(f"Laya version mismatch: {laya.__version__}")
    sources = json.loads((Path(__file__).parents[1] / "sources.json").read_text(encoding="utf-8"))
    local_dataset_manifest = root / "manifest.json"
    if not local_dataset_manifest.is_file():
        raise ValueError(
            "training requires a finalized authentic-conversation manifest; "
            "the superseded Hugging Face v1 fallback is disabled"
        )
    dataset_metadata = json.loads(local_dataset_manifest.read_text(encoding="utf-8"))
    if dataset_metadata.get("format") not in {
        "atmem-stateful-memory-transitions-manifest-v2",
        "atmem-stateful-memory-transitions-manifest-v3",
    }:
        raise ValueError(
            "training is blocked: isolated-label manifests are superseded; "
            "a verified stateful memory-transition v2 manifest is required"
        )
    if dataset_metadata.get("synthetic_conversation_rows") != 0 or dataset_metadata.get("locomo_rows") != 0:
        raise ValueError("training dataset contains a prohibited source class")
    dataset_revision = str(
        dataset_metadata.get("manifest_digest")
        or canonical_digest(dataset_metadata)
    )
    dataset_manifest_sha = sha256_file(local_dataset_manifest)
    dataset_repo = str(
        dataset_metadata.get("repo_id")
        or "atmem/stateful-memory-transitions-10pct-v2"
    )
    base = {
        "repo_id": sources["laya"]["hub_repo"],
        "revision": sources["laya"]["hub_revision"],
    }
    base_dir = Path(snapshot_download(
        repo_id=base["repo_id"], revision=base["revision"],
        allow_patterns=[
            "README.md", "config.json", "rl_agent_config.json", "model.safetensors",
            "tokenizer/*", "encoder/*",
        ],
    ))
    _verify_base_files(base_dir, sources)

    paths = {
        name: root / "records" / f"decisions-{name}.jsonl"
        for name in ("train", "validation", "calibration")
    }
    rows = {name: _read_rows(path, name) for name, path in paths.items()}
    question_ids = {
        row["request"]["question"]["question_id"]
        for split_rows in rows.values() for row in split_rows
    }
    required_question_ids = {
        "formation.context_sufficient.v2", "formation.is_durable.v2",
        "formation.memory_class.v2", "formation.operation.v2",
    }
    if question_ids <= set(V2_QUESTION_IDS) and required_question_ids <= question_ids:
        row_converter = to_memory_evidence_laya_rows
        dataset_schema = "stateful-memory-transition-v2"
    elif question_ids == set(V3_QUESTION_IDS):
        row_converter = to_memory_evidence_laya_rows
        dataset_schema = "stateful-memory-transition-selective-v3"
    else:
        raise ValueError(
            "only the authentic memory-understanding question schema is training-eligible; "
            f"found {sorted(question_ids)}"
        )
    all_nonsealed_rows = rows["train"] + rows["validation"] + rows["calibration"]
    definitions = question_definitions(all_nonsealed_rows)
    question_digest = canonical_digest(definitions)
    split_digests = {name: sha256_file(path) for name, path in paths.items()}
    seed = 410239
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    device = train.resolve_device(device_name)
    if device.type != "cuda" and not research_only:
        raise RuntimeError("release-eligible training requires CUDA")
    # PyTorch's memory-efficient CUDA attention backward is explicitly
    # nondeterministic on this profile. Fail closed and force the math SDPA
    # implementation so a repeated seed is a meaningful control.
    # RLCD's ordered-score reward uses CUDA cumsum. PyTorch 2.5 has no
    # deterministic CUDA kernel for that operation, so strict mode would abort
    # before the first optimizer update. Keep deterministic algorithms enabled
    # and record the narrow warn-only exception for RLCD; soft-CE remains strict.
    # MPS currently lacks deterministic scatter-reduce backward. Research-only
    # Apple runs record the warning; release-eligible CUDA soft-CE stays strict.
    deterministic_warn_only = objective == "rlcd" or device.type == "mps"
    torch.use_deterministic_algorithms(True, warn_only=deterministic_warn_only)
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_mem_efficient_sdp(False)
        torch.backends.cuda.enable_math_sdp(True)

    model, tok, base_cfg = train.load_checkpoint(str(base_dir))
    model.to(device)
    max_len = int(base_cfg.get("max_len", 1024))
    head_max_len = int(base_cfg.get("head_max_len", 256))
    if (max_len, head_max_len) != (1024, 256):
        raise RuntimeError(
            f"multilingual base limits differ from the frozen profile: {(max_len, head_max_len)}"
        )
    items = {}
    skipped = {}
    truncation = {}
    for name in ("train", "validation", "calibration"):
        laya_rows = row_converter(rows[name])
        raw_items, skipped[name] = train.items_from_rows(
            tok, laya_rows, max_len, head_max_len,
        )
        if skipped[name] or len(raw_items) != len(rows[name]):
            raise RuntimeError(f"{name} preprocessing skipped rows: {skipped[name]}")
        records = _truncation_rows(
            train, tok, raw_items, rows[name], max_len, head_max_len,
        )
        keep = [index for index, record in enumerate(records) if not record["truncated"]]
        report = truncation_report(records)
        report.update({
            "policy": "exclude-before-optimization-and-evaluation",
            "retained_items": len(keep), "post_filter_truncated_items": 0,
        })
        truncation[name] = report
        rows[name] = [rows[name][index] for index in keep]
        items[name] = [raw_items[index] for index in keep]
    semantic_coverage = _semantic_operation_coverage(rows["train"])
    if dataset_schema == "stateful-memory-transition-selective-v3":
        required = set(dataset_metadata.get("learned_operations") or ())
        missing = required - set(semantic_coverage["distinct_trajectory_counts"])
        if missing:
            semantic_coverage["missing_operations"] = sorted(missing)
            semantic_coverage["sufficient"] = False
        if (
            not semantic_coverage["sufficient"]
            or any(report["truncated_items"] for report in truncation.values())
        ) and not research_only:
            raise RuntimeError(
                "V3 data is not release-eligible after exact packing: "
                f"coverage={semantic_coverage}, truncation={truncation}"
            )
    rows["train"], training_sampling = _balance_training_rows(
        rows["train"], seed=seed,
    )
    train_rows = row_converter(rows["train"])
    items["train"], train_skipped = train.items_from_rows(
        tok, train_rows, max_len, head_max_len,
    )
    if train_skipped or len(items["train"]) != len(rows["train"]):
        raise RuntimeError(f"balanced train preprocessing skipped rows: {train_skipped}")
    calibration_counts = Counter(
        row["request"]["question"]["question_id"]
        for row in rows["calibration"]
    )
    power = calibration_power(calibration_counts)
    if dataset_schema == "stateful-memory-transition-selective-v3":
        question_count_sufficient = bool(power["sufficient"])
        packing_overflow_counts = {
            name: int(report["truncated_items"])
            for name, report in truncation.items()
        }
        power.update({
            "question_count_sufficient": question_count_sufficient,
            "semantic_operation_coverage": semantic_coverage,
            "packing_overflow_counts": packing_overflow_counts,
            "sufficient": (
                question_count_sufficient
                and bool(semantic_coverage["sufficient"])
                and not any(packing_overflow_counts.values())
            ),
        })
    if not power["sufficient"] and not research_only:
        raise RuntimeError(
            "calibration underpowered before paid optimization: "
            f"{power['underpowered_questions']}"
        )

    run_id = f"{objective}-{seed}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    output = output / run_id
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "question-definitions.json", definitions)
    base_validation_records = train.calibration_records(
        model, tok, items["validation"], device, max_len, head_max_len, batch_size=micro_batch
    )
    base_metrics = _metric_report(
        run_id, objective, "validation", [], rows["validation"], base_validation_records,
        truncation["validation"], train,
    )
    write_json(output / "base-validation-metrics.json", base_metrics)

    config = train.TrainConfig(
        epochs=epochs, micro_batch=micro_batch, grad_accum=grad_accum,
        encoder_lr=2.5e-5, head_lr=1e-4, min_lr=1e-6,
        weight_decay=0.01, grad_clip=1.0, loss=objective,
        rl_samples=4, sigma_start=0.4, sigma_end=0.1,
        w_sph=0.75, w_rps=1.0, freeze_encoder=False,
        seed=seed, max_len=max_len, head_max_len=head_max_len,
        # Upstream RLCD's Gaussian log-density term can overflow the initial
        # fp16 GradScaler step on current CUDA/PyTorch, advancing the scheduler
        # without an optimizer update. Keep the CE control on AMP, but run RLCD
        # in fp32 so every scheduled update is actually applied.
        amp=(objective == "soft-ce"), gradient_checkpointing=True, log_every=250,
    )
    epoch_checkpoints = []

    def checkpoint(epoch: int, mean_loss: float) -> None:
        path = output / "checkpoints" / f"epoch-{epoch + 1}"
        train.save_checkpoint(model, tok, base_cfg, str(path))
        epoch_checkpoints.append({
            "epoch": epoch + 1, "mean_loss": mean_loss,
            "path": path.relative_to(output).as_posix(),
            "model_sha256": sha256_file(path / "model.safetensors"),
        })

    started = time.perf_counter()
    history = train.train_model(
        model, tok, items["train"], config, device, max_len, head_max_len,
        on_epoch_end=checkpoint,
    )
    train_seconds = time.perf_counter() - started
    assert_finite(history, label="training loss")

    validation_records = train.calibration_records(
        model, tok, items["validation"], device, max_len, head_max_len, batch_size=micro_batch
    )
    validation_metrics = _metric_report(
        run_id, objective, "validation", history, rows["validation"], validation_records,
        truncation["validation"], train,
    )
    write_json(output / "validation-metrics.json", validation_metrics)

    calibration_records = train.calibration_records(
        model, tok, items["calibration"], device, max_len, head_max_len, batch_size=micro_batch
    )
    calibration_metrics = _metric_report(
        run_id, objective, "calibration", history, rows["calibration"], calibration_records,
        truncation["calibration"], train,
    )
    final_model = output / "model"
    train.save_checkpoint(model, tok, base_cfg, str(final_model))
    model_digest = sha256_file(final_model / "model.safetensors")
    calibration_bundle = None
    if power["sufficient"]:
        fitted = fit_temperature_map(calibration_records, compute_ece=True, seed=seed)
        thresholds = fit_abstention_thresholds(
            calibration_records, fitted["temperature"], fitted["temperature_by_options"],
            target_error=0.10, min_bucket_n=100, conservative=True,
        )
        calibration_bundle = {
            "format": FORMAT_CALIBRATION,
            "model_digest": model_digest,
            "dataset_revision": dataset_revision,
            "questions_digest": question_digest,
            "split_digest": split_digests["calibration"],
            "method": "per-question-temperature-and-abstention-v1",
            "temperatures": {
                "by_type": fitted["temperature"],
                "by_option_bucket": fitted["temperature_by_options"],
            },
            "thresholds": thresholds,
            "sample_counts": power,
            "reliability": {"fit_report": fitted["report"], "metrics": calibration_metrics},
            "selection_procedure": {
                "target_error": 0.10, "minimum_bucket_items": 100,
                "conservative_pseudo_error": True, "sealed_test_opened": False,
            },
            "created_at": _utc_now(),
        }
        calibration_bundle["digest"] = canonical_digest(calibration_bundle)
        write_json(output / "calibration-bundle.json", calibration_bundle)
    write_json(output / "calibration-power.json", power)
    write_json(output / "calibration-metrics.json", calibration_metrics)

    hardware = {"platform": platform.platform(), "device": str(device)}
    if device.type == "cuda":
        hardware.update({
            "gpu_name": torch.cuda.get_device_name(device),
            "gpu_memory_bytes": torch.cuda.get_device_properties(device).total_memory,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
        })
    elif device.type == "mps":
        hardware.update({"gpu_name": "Apple Metal Performance Shaders"})
    manifest = {
        "format": FORMAT_MANIFEST,
        "run_id": run_id,
        "created_at": _utc_now(),
        "code_revision": code_revision,
        "base_model": {"repo_id": base["repo_id"], "revision": base["revision"]},
        "laya": {"repo_id": sources["laya"]["source_repo"], "revision": sources["laya"]["source_revision"]},
        "dataset": {
            "repo_id": dataset_repo, "revision": dataset_revision,
            "manifest_sha256": dataset_manifest_sha,
            "schema": dataset_schema,
        },
        "questions_digest": question_digest,
        "environment": _versions(),
        "objective": objective,
        "hyperparameters": {
            **config.__dict__, "train_seconds": train_seconds,
            "research_only": research_only, "calibration_power": power,
            "deterministic_algorithms": True,
            "deterministic_warn_only": deterministic_warn_only,
        },
        "training_sampling": training_sampling,
        "semantic_operation_coverage": semantic_coverage,
        "seeds": {"python": seed, "torch": seed, "cuda": seed, "calibration": seed},
        "split_digests": split_digests,
        "hardware": hardware,
        "checkpoints": epoch_checkpoints,
        "metrics": {
            "base_validation": "base-validation-metrics.json",
            "validation": "validation-metrics.json",
            "calibration": "calibration-metrics.json",
        },
        "calibration": (
            {"path": "calibration-bundle.json", "digest": calibration_bundle["digest"]}
            if calibration_bundle is not None else None
        ),
        "export_inventory": [],
        "parent_run": None,
        "reproducibility_tolerances": {
            "same_backend": dict(SAME_BACKEND_TOLERANCE),
            "cross_backend": dict(CROSS_BACKEND_TOLERANCE),
        },
    }
    manifest["export_inventory"] = _inventory(final_model)
    validate_manifest(manifest)
    if secret_findings([base_metrics, validation_metrics, calibration_bundle, manifest]):
        raise RuntimeError("secret-like material detected in retained JSON artifacts")
    write_json(output / "training-manifest.json", manifest)
    return {"run_id": run_id, "output": str(output), "manifest": manifest}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train one frozen AtMem Laya objective")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--objective", choices=("soft-ce", "rlcd"), required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--micro-batch", type=int, default=8)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--research-only", action="store_true")
    args = parser.parse_args(argv)
    result = run(
        args.root.resolve(), args.output.resolve(), args.objective, args.device,
        args.micro_batch, args.grad_accum, args.epochs, args.code_revision,
        args.research_only,
    )
    print(json.dumps({"run_id": result["run_id"], "output": result["output"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
