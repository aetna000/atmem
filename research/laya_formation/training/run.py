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

from research.laya_formation.dataset.training_view import iter_training_rows
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
    QUESTION_INSTRUCTIONS,
    _verify_base_files,
    sha256_file,
    to_laya_rows,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_rows(path: Path, expected_split: str) -> list[dict[str, Any]]:
    rows = list(iter_training_rows([path]))
    wrong = sorted({row["split"] for row in rows} - {expected_split})
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
        choices = row["choice_ids"]
        gold = int(np.asarray(target[:count]).argmax())
        pred = int(np.asarray(logits[:count]).argmax())
        qid = row["question_id"]
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
        records.append({"example_id": source["example_id"], **stats})
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
    definitions = {}
    for row in rows:
        definitions[row["question_id"]] = {
            "instructions": QUESTION_INSTRUCTIONS[row["question_id"]],
            "choice_ids": row["choice_ids"],
        }
    return canonical_digest(definitions)


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
        grad_accum: int, epochs: int, code_revision: str) -> dict[str, Any]:
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
    dataset_revision = "4436089b38cbe3a5374aaaa92c4c77703cdbf668"
    dataset_manifest_sha = "d67d371c8c1d6de85a0293cded5aa5b3f7d078e92197130ce1f9edef68e863d4"
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
        name: root / "data" / f"decisions-{name}.jsonl"
        for name in ("train", "validation", "calibration")
    }
    rows = {name: _read_rows(path, name) for name, path in paths.items()}
    question_digest = _question_digest(rows["train"] + rows["validation"] + rows["calibration"])
    split_digests = {name: sha256_file(path) for name, path in paths.items()}
    seed = 410239
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    device = train.resolve_device(device_name)
    if device.type != "cuda":
        raise RuntimeError("the paid training profile requires CUDA")
    # PyTorch's memory-efficient CUDA attention backward is explicitly
    # nondeterministic on this profile. Fail closed and force the math SDPA
    # implementation so a repeated seed is a meaningful control.
    torch.use_deterministic_algorithms(True, warn_only=False)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)

    model, tok, base_cfg = train.load_checkpoint(str(base_dir))
    model.to(device)
    max_len, head_max_len = 512, 192
    items = {}
    skipped = {}
    truncation = {}
    for name in ("train", "validation", "calibration"):
        laya_rows = to_laya_rows(rows[name])
        items[name], skipped[name] = train.items_from_rows(tok, laya_rows, max_len, head_max_len)
        if skipped[name] or len(items[name]) != len(rows[name]):
            raise RuntimeError(f"{name} preprocessing skipped rows: {skipped[name]}")
        truncation[name] = truncation_report(
            _truncation_rows(train, tok, items[name], rows[name], max_len, head_max_len)
        )

    run_id = f"{objective}-{seed}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    output = output / run_id
    output.mkdir(parents=True, exist_ok=False)
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
    fitted = fit_temperature_map(calibration_records, compute_ece=True, seed=seed)
    thresholds = fit_abstention_thresholds(
        calibration_records, fitted["temperature"], fitted["temperature_by_options"],
        target_error=0.10, min_bucket_n=100, conservative=True,
    )
    calibration_metrics = _metric_report(
        run_id, objective, "calibration", history, rows["calibration"], calibration_records,
        truncation["calibration"], train,
    )
    counts = Counter(row["question_id"] for row in rows["calibration"])
    power = calibration_power(counts)
    if not power["sufficient"]:
        raise RuntimeError(f"calibration underpowered: {power['underpowered_questions']}")

    final_model = output / "model"
    train.save_checkpoint(model, tok, base_cfg, str(final_model))
    model_digest = sha256_file(final_model / "model.safetensors")
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
    write_json(output / "calibration-metrics.json", calibration_metrics)

    hardware = {
        "platform": platform.platform(), "device": str(device),
        "gpu_name": torch.cuda.get_device_name(device),
        "gpu_memory_bytes": torch.cuda.get_device_properties(device).total_memory,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
    }
    manifest = {
        "format": FORMAT_MANIFEST,
        "run_id": run_id,
        "created_at": _utc_now(),
        "code_revision": code_revision,
        "base_model": {"repo_id": base["repo_id"], "revision": base["revision"]},
        "laya": {"repo_id": sources["laya"]["source_repo"], "revision": sources["laya"]["source_revision"]},
        "dataset": {
            "repo_id": "atmem/atmem-laya-formation-v1", "revision": dataset_revision,
            "manifest_sha256": dataset_manifest_sha,
        },
        "questions_digest": question_digest,
        "environment": _versions(),
        "objective": objective,
        "hyperparameters": {**config.__dict__, "train_seconds": train_seconds},
        "seeds": {"python": seed, "torch": seed, "cuda": seed, "calibration": seed},
        "split_digests": split_digests,
        "hardware": hardware,
        "checkpoints": epoch_checkpoints,
        "metrics": {
            "base_validation": "base-validation-metrics.json",
            "validation": "validation-metrics.json",
            "calibration": "calibration-metrics.json",
        },
        "calibration": {"path": "calibration-bundle.json", "digest": calibration_bundle["digest"]},
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
    args = parser.parse_args(argv)
    result = run(
        args.root.resolve(), args.output.resolve(), args.objective, args.device,
        args.micro_batch, args.grad_accum, args.epochs, args.code_revision,
    )
    print(json.dumps({"run_id": result["run_id"], "output": result["output"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
