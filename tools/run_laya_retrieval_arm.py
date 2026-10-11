#!/usr/bin/env python3
"""Run one fixed-pool retrieval arm from retained formation results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.laya_formation.retrieval_run import execute_retrieval_arm


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("arm")
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--formation-results-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = execute_retrieval_arm(
        args.packet_dir / "retrieval-packet.json",
        args.packet_dir / "retrieval-answer-key.json",
        args.formation_results_dir / f"{args.arm}.jsonl",
        args.formation_results_dir / f"{args.arm}-post-state.jsonl",
        args.output_dir / f"{args.arm}-retrieval.jsonl",
    )
    path = args.output_dir / f"{args.arm}-retrieval-summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
