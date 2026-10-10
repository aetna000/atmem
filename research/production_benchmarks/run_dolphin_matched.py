"""Run and aggregate the frozen AtMem/Mem0 DolphinBench development arms."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "research/production_benchmarks/run_dolphin_development.py"


def _arm_arguments(parser: argparse.ArgumentParser, name: str) -> None:
    parser.add_argument(f"--{name}-config", required=True)
    parser.add_argument(f"--{name}-checkpoint-root", required=True)
    parser.add_argument(f"--{name}-finalization-gate", required=True)
    parser.add_argument(f"--{name}-finalization-manifest", required=True)


def _evaluation_receipt(config_path: Path) -> Path:
    """Resolve the receipt from Dolphin's configured mutable run output."""
    configuration = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(configuration, dict) or not str(
        configuration.get("output") or ""
    ).strip():
        raise RuntimeError("DolphinBench config does not declare an output directory")
    output = Path(str(configuration["output"])).expanduser()
    if not output.is_absolute():
        output = config_path.parent / output
    return output.resolve() / "development-evaluation.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--confirm-paid-run", action="store_true")
    _arm_arguments(parser, "atmem")
    _arm_arguments(parser, "mem0")
    args = parser.parse_args()
    if not args.confirm_paid_run:
        raise SystemExit("refusing matched paid run without --confirm-paid-run")
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for name in ("atmem", "mem0"):
        checkpoint = Path(getattr(args, f"{name}_checkpoint_root")).expanduser().resolve()
        config_path = Path(getattr(args, f"{name}_config")).expanduser().resolve()
        command = [
            sys.executable, str(RUNNER), "--checkout", args.checkout,
            "--config", str(config_path),
            "--checkpoint-root", str(checkpoint),
            "--finalization-gate", getattr(args, f"{name}_finalization_gate"),
            "--finalization-manifest", getattr(args, f"{name}_finalization_manifest"),
            "--confirm-paid-run",
        ]
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode:
            raise RuntimeError(f"DolphinBench {name} arm failed with {completed.returncode}")
        result_path = _evaluation_receipt(config_path)
        if not result_path.is_file():
            raise RuntimeError(f"DolphinBench {name} arm produced no evaluation receipt")
        results.append(json.loads(result_path.read_text(encoding="utf-8")))
    if {row["tests"] for row in results} != {30} or len({
        tuple(row["development_ids"]) for row in results
    }) != 1:
        raise RuntimeError("matched DolphinBench arms did not use the same frozen tasks")
    report = {
        "format": "atmem-dolphinbench-matched-development-v1",
        "claim": "matched-development-30-of-600-not-an-official-score",
        "arms": results,
    }
    (output / "matched-results.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
