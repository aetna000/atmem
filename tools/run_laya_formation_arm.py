#!/usr/bin/env python3
"""Run one immutable local formation arm and score it without answer access."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.laya_formation.adapters import (
    BASE_LAYA_MODEL,
    BASE_LAYA_REVISION,
    FINETUNED_LAYA_MODEL,
    FINETUNED_LAYA_REVISION,
    QWEN_MODEL,
    QWEN_REVISION,
    EscalatingChoiceAdapter,
    base_laya,
    deterministic_atmem,
    finetuned_laya,
    laya_agent_decision,
)
from benchmarks.laya_formation.contracts import ArmIdentity
from benchmarks.laya_formation.formation_run import (
    deterministic_decision,
    blocked_arm,
    load_frozen_cases,
    run_arm,
    score_arm,
)


def _identity(arm: str, *, device: str) -> ArmIdentity:
    common = dict(
        provider="local", hardware=f"{platform.system()}-{platform.machine()}-{device}",
        batching="one", maximum_calls=0, maximum_tokens=2_112,
        timeout_seconds=30, retries=0, remote_egress=False,
    )
    if arm == "deterministic-atmem":
        return ArmIdentity(
            arm=arm, model="atmem-deterministic-formation", revision="2.3.9b1",
            dtype="rules", **common,
        )
    if arm == "base-laya":
        return ArmIdentity(
            arm=arm, model=BASE_LAYA_MODEL, revision=BASE_LAYA_REVISION,
            dtype="float32", **common,
        )
    if arm == "finetuned-laya":
        return ArmIdentity(
            arm=arm, model=FINETUNED_LAYA_MODEL, revision=FINETUNED_LAYA_REVISION,
            dtype="float32", **common,
        )
    remote = {
        **common, "maximum_calls": 1, "remote_egress": True,
        "dtype": "bfloat16", "hardware": device,
    }
    if arm == "pinned-current-qwen":
        return ArmIdentity(
            arm=arm, model=QWEN_MODEL, revision=QWEN_REVISION,
            provider="self-hosted-vllm", **{key: value for key, value in remote.items() if key != "provider"},
        )
    if arm == "pinned-jev":
        return ArmIdentity(
            arm=arm, model="jev-1.13.0", revision="unresolved",
            provider="jev", **{key: value for key, value in remote.items() if key != "provider"},
        )
    return ArmIdentity(
        arm=arm, model=FINETUNED_LAYA_MODEL, revision=FINETUNED_LAYA_REVISION,
        provider="local-laya-plus-bounded-atbot", **{
            key: value for key, value in remote.items() if key not in {"provider", "dtype"}
        }, dtype="float32",
    )


def _laya_adapter(arm: str, model_dir: Path, device: str):
    from laya import Agent

    thresholds = None
    if arm == "finetuned-laya":
        from atmem.laya_formation.artifacts import LayaArtifactResolver
        from laya.calibrate import apply_calibration_payload

        bundle = LayaArtifactResolver().resolve(local_dir=model_dir)
        inventory = json.loads((bundle.root / "artifact-manifest.json").read_text())["inventory"]
        expected = {item["path"]: item["sha256"] for item in inventory}
        agent = Agent(str(bundle.root), device=device, expected_sha256=expected)
        apply_calibration_payload(agent, {
            "version": 1,
            "temperature": list(bundle.calibration.temperatures),
            "temperature_by_options": dict(bundle.calibration.temperature_by_options),
            "binning_map": None,
        })
        thresholds = bundle.calibration.thresholds
        return finetuned_laya(
            _identity(arm, device=device),
            laya_agent_decision(agent, abstention_thresholds=thresholds),
        )
    agent = Agent(str(model_dir), device=device)
    return base_laya(_identity(arm, device=device), laya_agent_decision(agent))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("arm", choices=(
        "deterministic-atmem", "base-laya", "finetuned-laya",
        "pinned-current-qwen", "pinned-jev", "finetuned-laya-with-atbot-escalation",
    ))
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--device", default="cpu", help="local device or explicit blocked-arm hardware identity")
    parser.add_argument("--blocked-code")
    args = parser.parse_args()
    cases = load_frozen_cases(
        args.packet_dir / "matched-packet.json",
        args.packet_dir / "matched-answer-key.json",
    )
    if args.blocked_code:
        if args.arm not in {"pinned-current-qwen", "pinned-jev"}:
            parser.error("--blocked-code is only valid for a remote arm")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        raw = args.output_dir / f"{args.arm}.jsonl"
        counts = blocked_arm(cases, _identity(args.arm, device=args.device), args.blocked_code, raw)
        post = args.output_dir / f"{args.arm}-post-state.jsonl"
        summary = score_arm(cases, raw, post)
        summary["run_counts"] = counts
        summary_path = args.output_dir / f"{args.arm}-summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    if args.arm == "deterministic-atmem":
        adapter = deterministic_atmem(_identity(args.arm, device=args.device), deterministic_decision)
    elif args.arm == "finetuned-laya-with-atbot-escalation":
        if args.model_dir is None:
            parser.error("--model-dir is required for the escalating arm")
        local = _laya_adapter("finetuned-laya", args.model_dir.resolve(), args.device)
        adapter = EscalatingChoiceAdapter(
            _identity(args.arm, device=args.device), local,
            lambda payload, timeout: (_ for _ in ()).throw(RuntimeError("escalation transport was not provisioned")),
        )
    else:
        if args.arm in {"pinned-current-qwen", "pinned-jev"}:
            parser.error("a remote arm requires its transport runner or --blocked-code")
        if args.model_dir is None:
            parser.error("--model-dir is required for a Laya arm")
        adapter = _laya_adapter(args.arm, args.model_dir.resolve(), args.device)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw = args.output_dir / f"{args.arm}.jsonl"
    post = args.output_dir / f"{args.arm}-post-state.jsonl"
    counts = run_arm(cases, adapter, raw)
    summary = score_arm(cases, raw, post)
    summary["run_counts"] = counts
    summary_path = args.output_dir / f"{args.arm}-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
