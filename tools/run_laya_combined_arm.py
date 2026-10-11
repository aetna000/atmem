#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.laya_formation.combined_run import execute_combined_arm


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("arm")
    parser.add_argument("--formation-packet-dir", type=Path, required=True)
    parser.add_argument("--retrieval-packet-dir", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = execute_combined_arm(
        args.formation_packet_dir / "matched-packet.json",
        args.formation_packet_dir / "matched-answer-key.json",
        args.retrieval_packet_dir / "retrieval-packet.json",
        args.retrieval_packet_dir / "retrieval-answer-key.json",
        args.results_dir / f"{args.arm}.jsonl",
        args.results_dir / f"{args.arm}-post-state.jsonl",
        args.results_dir / f"{args.arm}-retrieval.jsonl",
        args.results_dir / f"{args.arm}-combined.jsonl",
    )
    path = args.results_dir / f"{args.arm}-combined-summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
