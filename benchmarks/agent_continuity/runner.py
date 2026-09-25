"""Run offline crash fixtures. Never presents smoke results as a product win."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import subprocess

from .faults import BARRIERS, trial
from .manifest import environment_stamp, file_digest
from .report import summarize


def expected_disposition(row: dict) -> str:
    if row["negative_control"]:
        return "invalid_effects"
    if row["capability"] == "N" and row["fault"] in {"after_intent", "in_flight", "after_commit", "after_response"}:
        return "blocked"
    if row["capability"] == "Q" and row["fault"] == "after_intent":
        return "blocked"
    return "completed"


def passes_smoke_cell(row: dict) -> bool:
    if row["disposition"] != expected_disposition(row):
        return False
    if row["fault"] and not row["fault_reached"]:
        return False
    if row["fault"] is None:
        runs = [event for event in row.get("events", []) if "resume" in event]
        if (row["fault_reached"] or "killed_worker_exitcode" in row or
                row.get("restart_to_terminal_ms") is not None or
                len(runs) != 1 or runs[0]["resume"]):
            return False
    oracle = row.get("oracle", {})
    return oracle.get("duplicate_effects") == (1 if row["negative_control"] else 0) and oracle.get("wrong_effects") == 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--historical-fixture", action="store_true",
                        help="explicitly run the old benchmark-owned recovery design, not a product evaluation")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--include-atmem", action="store_true")
    parser.add_argument("--capabilities", nargs="+", choices=["I", "Q", "N"], default=["I", "Q", "N"])
    parser.add_argument("--seed", type=int, default=20260925)
    args = parser.parse_args()
    if not args.historical_fixture:
        parser.error("This is the historical recovery fixture. Use --historical-fixture only to reproduce design tests; see retail_graph_qualification and installed product acceptance for current evidence.")
    if not 1 <= args.repetitions <= 100:
        parser.error("repetitions must be 1..100")
    args.output.mkdir(parents=True, exist_ok=False)
    schedule = [(capability, fault, atmem, False, repetition)
                for repetition in range(args.repetitions)
                for capability in args.capabilities
                for fault in (None, *BARRIERS)
                for atmem in ([False, True] if args.include_atmem else [False])]
    schedule = [(*row, False) for row in schedule]
    schedule += [("N", "after_commit", False, True, r, False) for r in range(args.repetitions)]
    schedule += [(capability, "in_flight", atmem, False, r, True)
                 for r in range(args.repetitions) for capability in args.capabilities
                 for atmem in ([False, True] if args.include_atmem else [False])]
    random.Random(args.seed).shuffle(schedule)
    source_root = Path(__file__).resolve().parents[2]
    frozen_environment = environment_stamp()
    manifest = {"evidence_level": "historical-recovery-design-fixture", "product_recovery_claims_allowed": False, "seed": args.seed, "schedule": schedule,
                "frozen_environment": frozen_environment,
                "python": platform.python_version(), "platform": platform.platform(),
                "packages": {name: importlib.metadata.version(name) for name in ("langgraph", "langgraph-checkpoint-sqlite", "atmem")},
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source_root, text=True).strip(),
                "source_status": subprocess.check_output(["git", "status", "--porcelain"], cwd=source_root, text=True).splitlines(),
                "harness_files": {str(p.relative_to(source_root)): file_digest(p) for p in Path(__file__).parent.rglob("*.py")}}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    rows = []
    with (args.output / "trials.jsonl").open("x") as output:
        for index, (capability, fault, atmem, naive, repetition, drop_request) in enumerate(schedule):
            if environment_stamp() != frozen_environment:
                raise SystemExit("Source or environment changed during run; partial output is not a qualification")
            row = trial(args.output / f"trial-{index:04}", capability=capability, fault=fault,
                        atmem=atmem, naive=naive, drop_request=drop_request)
            if environment_stamp() != frozen_environment:
                row["disposition"] = "infrastructure_failure"
                row["error"] = "source_or_environment_changed_during_trial"
            row["repetition"] = repetition
            rows.append(row)
            output.write(json.dumps(row, sort_keys=True) + "\n")
            output.flush()
            print(f"{index+1}/{len(schedule)} {row['arm']} {capability} {fault}: {row['disposition']}", flush=True)
    (args.output / "summary.json").write_text(json.dumps(summarize(rows), indent=2) + "\n")
    hashes = {p.name: file_digest(p) for p in args.output.iterdir() if p.is_file()}
    (args.output / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2) + "\n")
    if not all(passes_smoke_cell(r) for r in rows):
        raise SystemExit("Smoke suite contains unexpected failures; inspect trials.jsonl")


if __name__ == "__main__":
    main()
