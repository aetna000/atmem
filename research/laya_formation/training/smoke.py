from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import time
from typing import Any, Iterable

from research.laya_formation.dataset.training_view import iter_training_rows


WORKLOAD_PATH = Path(__file__).with_name("smoke-workload.json")
QUESTION_INSTRUCTIONS = {
    "operation": "Choose the only permitted memory formation operation.",
    "memory_class": "Classify the proposed memory using the finite policy classes.",
    "evidence_support": "Classify whether authorized evidence supports the proposal.",
    "target_selection": "Choose the authorized canonical target or review outcome.",
    "retrieval_usefulness": "Classify future retrieval usefulness from the authorized evidence.",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_workload(path: Path = WORKLOAD_PATH) -> dict[str, Any]:
    workload = json.loads(path.read_text(encoding="utf-8"))
    if workload.get("format") != "atmem-laya-smoke-workload-v1":
        raise ValueError("unknown smoke workload format")
    objectives = workload["training"]["objectives"]
    if objectives != ["soft-ce", "rlcd"]:
        raise ValueError("the fixed smoke must exercise soft-ce and rlcd in that order")
    if workload["training"]["freeze_encoder"] is not False:
        raise ValueError("the representative smoke must train the encoder")
    return workload


def choose_rows(paths: Iterable[Path], count: int) -> list[dict[str, Any]]:
    """Select deterministically while interleaving all five decision questions."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in iter_training_rows(paths):
        buckets[row["question_id"]].append(row)
        if sum(len(rows) for rows in buckets.values()) >= count * len(QUESTION_INSTRUCTIONS):
            break
    unknown = sorted(set(buckets) - set(QUESTION_INSTRUCTIONS))
    if unknown:
        raise ValueError(f"unknown question ids: {unknown}")
    chosen: list[dict[str, Any]] = []
    offset = 0
    names = list(QUESTION_INSTRUCTIONS)
    while len(chosen) < count:
        advanced = False
        for name in names:
            if offset < len(buckets[name]) and len(chosen) < count:
                chosen.append(buckets[name][offset])
                advanced = True
        if not advanced:
            raise ValueError("not enough rows for the fixed stratified smoke sample")
        offset += 1
    return chosen


def to_laya_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for row in rows:
        qid = row["question_id"]
        choices = row["choice_ids"]
        expected = row["expected_choice_ids"]
        if len(expected) != 1:
            raise ValueError("the v1 smoke supports exactly one oracle choice per question")
        converted.append({
            "state": row["authorized_input"],
            "questions": {
                qid: {
                    "type": "choice",
                    "instructions": QUESTION_INSTRUCTIONS[qid],
                    "criteria": {choice: choice.replace("_", " ").lower() for choice in choices},
                }
            },
            "expected": {qid: expected[0]},
        })
    return converted


def evaluate_viability(evidence: dict[str, Any], limits: dict[str, float]) -> dict[str, Any]:
    reasons = []
    if evidence.get("error"):
        reasons.append("execution_error")
    if evidence.get("nonfinite"):
        reasons.append("nonfinite")
    if not evidence.get("resume_verified"):
        reasons.append("resume_failed")
    if not evidence.get("safetensors_reload_verified"):
        reasons.append("safetensors_reload_failed")
    headroom = evidence.get("memory_headroom_fraction")
    if headroom is None or headroom < limits["minimum_memory_headroom_fraction"]:
        reasons.append("memory_headroom_below_20_percent")
    ratio = evidence.get("free_to_projected_storage_ratio")
    if ratio is None or ratio < limits["minimum_free_to_projected_storage_ratio"]:
        reasons.append("storage_below_3x_projected_peak")
    hours = evidence.get("projected_both_objectives_hours")
    if hours is None or hours > limits["maximum_projected_both_objectives_hours"]:
        reasons.append("projected_runtime_over_48_hours")
    return {"state": "viable" if not reasons else "infeasible", "reason_codes": reasons}


def _device_memory(torch: Any, device: Any) -> tuple[int | None, int | None]:
    if device.type == "cuda":
        free, total = torch.cuda.mem_get_info(device)
        return int(total - free), int(total)
    if (
        device.type == "mps"
        and hasattr(torch.mps, "driver_allocated_memory")
        and hasattr(torch.mps, "recommended_max_memory")
    ):
        used = int(torch.mps.driver_allocated_memory())
        total = int(torch.mps.recommended_max_memory())
        return used, total
    try:
        import psutil
        memory = psutil.virtual_memory()
        return int(memory.total - memory.available), int(memory.total)
    except ImportError:
        return None, None


def _package_versions() -> dict[str, str]:
    result = {}
    for name in ("laya", "torch", "transformers", "safetensors", "huggingface-hub", "numpy"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "missing"
    return result


def _empty_device_cache(torch: Any, device: Any) -> None:
    if device.type == "cuda":
        torch.cuda.empty_cache()
    elif device.type == "mps" and hasattr(torch.mps, "empty_cache"):
        torch.mps.empty_cache()


def _verify_base_files(model_dir: Path, source_lock: dict[str, Any]) -> None:
    for relative, expected in source_lock["laya"]["files"].items():
        path = model_dir / relative
        if path.stat().st_size != expected["size"] or sha256_file(path) != expected["sha256"]:
            raise RuntimeError(f"pinned base-model file mismatch: {relative}")


def _normalized_probabilities(records: Iterable[tuple[Any, Any, Any, Any]]) -> list[list[float]]:
    import numpy as np

    probabilities = []
    for _qtype, logits, _target, count in records:
        values = np.asarray(logits[:count], dtype=float)
        shifted = values - values.max()
        exp = np.exp(shifted)
        probabilities.append((exp / exp.sum()).tolist())
    return probabilities


def _one_step(torch: Any, train: Any, model: Any, tok: Any, item: dict[str, Any],
              optimizer: Any, device: Any, cfg: dict[str, Any], objective: str) -> float:
    model.train()
    encoded = train.encode_item(tok, item, cfg["max_len"], cfg["head_max_len"])
    batch = train.collate_items([[encoded]], tok.pad_token_id)
    optimizer.zero_grad(set_to_none=True)
    logits = train._forward(model, batch, device, amp=device.type == "cuda", detach_encoder=False)
    mask = batch["marker_mask"].to(device)
    target = batch["target"].to(device)
    if objective == "rlcd":
        loss = train.rlcd_loss(
            logits, target, mask, batch["qtype"].to(device), 0.25,
            cfg["rl_samples"], 0.75, 1.0,
        )
    else:
        loss = train.soft_ce_loss(logits, target, mask)
    if not torch.isfinite(loss):
        raise FloatingPointError("nonfinite smoke loss")
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), cfg["gradient_clip"])
    optimizer.step()
    return float(loss.detach().cpu())


def _optimizer(model: Any, torch: Any, cfg: dict[str, Any]) -> Any:
    return torch.optim.AdamW([
        {"params": [p for n, p in model.named_parameters() if n.startswith("encoder.")], "lr": cfg["encoder_lr"]},
        {"params": [p for n, p in model.named_parameters() if not n.startswith("encoder.")], "lr": cfg["head_lr"]},
    ], weight_decay=cfg["weight_decay"])


def _save_resume_state(torch: Any, train: Any, model: Any, tok: Any, base_cfg: dict[str, Any],
                       optimizer: Any, path: Path, seed: int) -> None:
    train.save_checkpoint(model, tok, base_cfg, str(path / "model"))
    _save_optimizer_state(torch, optimizer, path, seed)


def _save_optimizer_state(torch: Any, optimizer: Any, path: Path, seed: int) -> None:
    from safetensors.torch import save_file

    path.mkdir(parents=True, exist_ok=True)
    state_dict = optimizer.state_dict()
    tensors = {}
    scalars: dict[str, dict[str, Any]] = {}
    for parameter_id, values in state_dict["state"].items():
        for name, value in values.items():
            key = f"{parameter_id}.{name}"
            if torch.is_tensor(value):
                tensors[key] = value.detach().cpu().contiguous()
            else:
                scalars.setdefault(str(parameter_id), {})[name] = value
    save_file(tensors, path / "optimizer.safetensors")
    (path / "optimizer.json").write_text(json.dumps({
        "format": "atmem-laya-adamw-checkpoint-v1",
        "seed": seed,
        "param_groups": state_dict["param_groups"],
        "scalars": scalars,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_optimizer_state(path: Path) -> dict[str, Any]:
    from safetensors.torch import load_file

    metadata = json.loads((path / "optimizer.json").read_text(encoding="utf-8"))
    if metadata.get("format") != "atmem-laya-adamw-checkpoint-v1":
        raise ValueError("unknown optimizer checkpoint format")
    state: dict[int, dict[str, Any]] = defaultdict(dict)
    for key, value in load_file(path / "optimizer.safetensors", device="cpu").items():
        parameter_id, name = key.split(".", 1)
        state[int(parameter_id)][name] = value
    for parameter_id, values in metadata.get("scalars", {}).items():
        state[int(parameter_id)].update(values)
    return {"state": dict(state), "param_groups": metadata["param_groups"]}


def _run_objective(torch: Any, train: Any, base_dir: Path, rows: list[dict[str, Any]],
                   calibration_rows: list[dict[str, Any]],
                   objective: str, device: Any, cfg: dict[str, Any], output: Path,
                   seed: int) -> dict[str, Any]:
    torch.manual_seed(seed)
    random.seed(seed)
    model, tok, base_cfg = train.load_checkpoint(str(base_dir))
    model.to(device)
    items, skipped = train.items_from_rows(tok, rows, cfg["max_len"], cfg["head_max_len"])
    if skipped or len(items) != len(rows):
        raise RuntimeError(f"smoke preprocessing skipped rows: {skipped}")
    calibration_items, calibration_skipped = train.items_from_rows(
        tok, calibration_rows, cfg["max_len"], cfg["head_max_len"]
    )
    if calibration_skipped or len(calibration_items) != len(calibration_rows):
        raise RuntimeError(f"smoke calibration preprocessing skipped rows: {calibration_skipped}")
    optimizer = _optimizer(model, torch, cfg)
    first_started = time.perf_counter()
    first_loss = _one_step(torch, train, model, tok, items[0], optimizer, device, cfg, objective)
    first_elapsed = time.perf_counter() - first_started
    checkpoint = output / objective / "resume"
    checkpoint.mkdir(parents=True, exist_ok=True)
    _save_resume_state(torch, train, model, tok, base_cfg, optimizer, checkpoint, seed)
    # Normalize the uninterrupted branch through the exact fp16 Safetensors checkpoint
    # that the fresh-process branch will load; otherwise fp32 in-memory weights and the
    # serialized fp16 checkpoint would not be a fair resume comparison.
    model, tok, _ = train.load_checkpoint(str(checkpoint / "model"))
    model.to(device)
    optimizer = _optimizer(model, torch, cfg)
    optimizer.load_state_dict(_load_optimizer_state(checkpoint))
    second_seed = seed + 1000
    torch.manual_seed(second_seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(second_seed)
    second_started = time.perf_counter()
    second_loss = _one_step(torch, train, model, tok, items[1], optimizer, device, cfg, objective)
    second_elapsed = time.perf_counter() - second_started
    elapsed = first_elapsed + second_elapsed
    reference_records = train.calibration_records(
        model, tok, items[:4], device, cfg["max_len"], cfg["head_max_len"], batch_size=1
    )
    reference_probabilities = _normalized_probabilities(reference_records)

    request = {
        "base": str(checkpoint / "model"), "optimizer": str(checkpoint),
        "rows": rows, "objective": objective, "device": str(device), "training": cfg,
        "second_seed": second_seed,
        "result": str(checkpoint / "resumed-result.json"),
    }
    request_path = checkpoint / "resume-request.json"
    # Choice-option mapping order is semantic in Laya. Never sort nested JSON keys here:
    # doing so would reorder `criteria` in the restarted process and invalidate parity.
    request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")
    subprocess.run([
        sys.executable, "-m", "research.laya_formation.training.smoke",
        "--resume-request", str(request_path),
    ], check=True)
    resumed = json.loads(Path(request["result"]).read_text(encoding="utf-8"))
    resume_deltas = [
        abs(left - right)
        for expected, actual in zip(reference_probabilities, resumed["probabilities"])
        for left, right in zip(expected, actual)
    ]
    resume_agreement = sum(
        max(range(len(left)), key=left.__getitem__) == max(range(len(right)), key=right.__getitem__)
        for left, right in zip(reference_probabilities, resumed["probabilities"])
    ) / len(reference_probabilities)
    resume_verified = (
        abs(second_loss - resumed["loss"]) <= 1e-4
        and max(resume_deltas, default=0.0) <= 1e-4
        and resume_agreement == 1.0
    )

    isolated_calibration_records = train.calibration_records(
        model, tok, calibration_items, device, cfg["max_len"], cfg["head_max_len"], batch_size=1
    )
    from laya.calibrate import fit_temperature_map
    calibration = fit_temperature_map(isolated_calibration_records, compute_ece=False, seed=seed)

    exported = output / objective / "exported"
    train.save_checkpoint(model, tok, base_cfg, str(exported))
    del model, optimizer
    _empty_device_cache(torch, device)
    # Establish the retained reference from the serialized dtype, then compare a
    # second clean load. The in-memory optimizer model is fp32 while upstream's
    # portable checkpoint is fp16, so comparing those would conflate export
    # quantization with reload reproducibility.
    reference_model, reference_tok, _ = train.load_checkpoint(str(exported))
    reference_model.to(device)
    original_records = train.calibration_records(
        reference_model, reference_tok, items[:4], device,
        cfg["max_len"], cfg["head_max_len"], batch_size=1,
    )
    del reference_model
    _empty_device_cache(torch, device)
    reloaded, reload_tok, _ = train.load_checkpoint(str(exported))
    reloaded.to(device)
    reload_records = train.calibration_records(reloaded, reload_tok, items[:4], device, cfg["max_len"], cfg["head_max_len"], batch_size=1)
    original_probabilities = _normalized_probabilities(original_records)
    reload_probabilities = _normalized_probabilities(reload_records)
    agreements, max_delta = 0, 0.0
    for left, right in zip(original_probabilities, reload_probabilities):
        agreements += int(max(range(len(left)), key=left.__getitem__) == max(range(len(right)), key=right.__getitem__))
        max_delta = max(max_delta, max(abs(a - b) for a, b in zip(left, right)))
    return {
        "objective": objective,
        "losses": [first_loss, second_loss],
        "elapsed_seconds": elapsed,
        "seconds_per_step": elapsed / 2,
        "resume_loss": resumed["loss"],
        "resume_verified": resume_verified,
        "resume_choice_agreement": resume_agreement,
        "resume_max_probability_delta": max(resume_deltas, default=0.0),
        "reload_choice_agreement": agreements / len(original_records),
        "reload_max_score_delta": max_delta,
        "calibration_items": len(isolated_calibration_records),
        "calibration_finite": all(math.isfinite(float(value)) for value in calibration["temperature"]),
        "export_bytes": sum(p.stat().st_size for p in exported.rglob("*") if p.is_file()),
    }


def _resume(request_path: Path) -> int:
    import torch
    import laya.train as train

    request = json.loads(request_path.read_text(encoding="utf-8"))
    device = train.resolve_device(request["device"])
    model, tok, _ = train.load_checkpoint(request["base"])
    model.to(device)
    cfg = request["training"]
    items, skipped = train.items_from_rows(tok, request["rows"], cfg["max_len"], cfg["head_max_len"])
    if skipped:
        raise RuntimeError(f"resume preprocessing skipped rows: {skipped}")
    optimizer = _optimizer(model, torch, cfg)
    optimizer.load_state_dict(_load_optimizer_state(Path(request["optimizer"])))
    torch.manual_seed(request["second_seed"])
    if device.type == "cuda":
        torch.cuda.manual_seed_all(request["second_seed"])
    loss = _one_step(torch, train, model, tok, items[1], optimizer, device, cfg, request["objective"])
    records = train.calibration_records(
        model, tok, items[:4], device, cfg["max_len"], cfg["head_max_len"], batch_size=1
    )
    Path(request["result"]).write_text(json.dumps({
        "loss": loss, "probabilities": _normalized_probabilities(records),
    }, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def run(root: Path, output: Path, requested_device: str, workload_path: Path) -> dict[str, Any]:
    import torch
    import laya
    import laya.train as train
    from huggingface_hub import snapshot_download

    workload = load_workload(workload_path)
    if laya.__version__ != "0.4.2":
        raise RuntimeError(f"Laya version mismatch: {laya.__version__}")
    source_lock = json.loads((Path(__file__).parents[1] / "sources.json").read_text(encoding="utf-8"))
    base = workload["base_model"]
    cache = root / "training" / "base-model"
    cache.mkdir(parents=True, exist_ok=True)
    base_dir = Path(snapshot_download(
        base["repo_id"], revision=base["revision"], local_dir=cache,
        allow_patterns=[
            "README.md", "config.json", "rl_agent_config.json", "model.safetensors",
            "tokenizer/*", "encoder/*",
        ],
    ))
    _verify_base_files(base_dir, source_lock)
    device = train.resolve_device(requested_device)
    seed = workload["seed"]
    train_rows = to_laya_rows(choose_rows([root / workload["dataset"]["train_path"]], workload["sample"]["train_items"]))
    calibration_rows = to_laya_rows(choose_rows(
        [root / workload["dataset"]["calibration_path"]], workload["sample"]["calibration_items"]
    ))
    output.mkdir(parents=True, exist_ok=True)
    used_before, total_memory = _device_memory(torch, device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    results = []
    error = None
    try:
        for index, objective in enumerate(workload["training"]["objectives"]):
            results.append(_run_objective(
                torch, train, base_dir, train_rows, calibration_rows, objective,
                device, workload["training"], output, seed + index,
            ))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    used_after, _ = _device_memory(torch, device)
    if device.type == "cuda":
        peak_used = int(torch.cuda.max_memory_reserved(device))
    else:
        peak_used = max(value for value in (used_before, used_after) if value is not None) if total_memory else None
    headroom = max(0.0, (total_memory - peak_used) / total_memory) if total_memory and peak_used is not None else None
    free_storage = shutil.disk_usage(root).free
    measured_run_storage = sum(
        path.stat().st_size for path in output.rglob("*")
        if path.is_file() and not path.name.startswith("._")
    )
    projected_storage = max(
        measured_run_storage,
        max((row["export_bytes"] for row in results), default=0) * 3,
    )
    ratio = free_storage / projected_storage if projected_storage else None
    full_steps = workload["dataset"]["full_train_items"] * workload["training"]["full_epochs"]
    projected_hours = sum(row["seconds_per_step"] * full_steps for row in results) / 3600 if len(results) == 2 else None
    reload_ok = bool(results) and all(
        row["reload_choice_agreement"] >= workload["viability"]["reload_choice_agreement"]
        and row["reload_max_score_delta"] <= workload["viability"]["reload_score_absolute_tolerance"]
        and row["calibration_finite"]
        for row in results
    )
    evidence = {
        "error": error,
        "nonfinite": any(not all(math.isfinite(v) for v in row["losses"]) for row in results),
        "resume_verified": len(results) == 2 and all(row["resume_verified"] for row in results),
        "safetensors_reload_verified": reload_ok,
        "peak_memory_bytes": peak_used,
        "total_memory_bytes": total_memory,
        "memory_headroom_fraction": headroom,
        "free_storage_bytes": free_storage,
        "projected_peak_run_storage_bytes": projected_storage,
        "free_to_projected_storage_ratio": ratio,
        "projected_both_objectives_hours": projected_hours,
    }
    receipt = {
        "format": "atmem-laya-compute-smoke-receipt-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "workload_sha256": sha256_file(workload_path),
        "workload": workload,
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "python": platform.python_version()},
        "packages": _package_versions(),
        "device": str(device),
        "objectives": results,
        "evidence": evidence,
        "decision": evaluate_viability(evidence, workload["viability"]),
    }
    receipt_path = output / "smoke-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the fixed Spec 041 Laya compute smoke")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--workload", type=Path, default=WORKLOAD_PATH)
    parser.add_argument("--resume-request", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.resume_request:
        return _resume(args.resume_request)
    if args.root is None or args.output is None:
        parser.error("--root and --output are required")
    receipt = run(args.root.resolve(), args.output.resolve(), args.device, args.workload.resolve())
    print(json.dumps({"decision": receipt["decision"], "receipt": str(args.output / "smoke-receipt.json")}, sort_keys=True))
    return 0 if receipt["decision"]["state"] == "viable" else 2


if __name__ == "__main__":
    raise SystemExit(main())
