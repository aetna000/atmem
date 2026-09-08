#!/usr/bin/env python3
"""Blocking invariant gate. Pytest produces the assertion evidence."""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atmem.invariants import AssertionResult, build_report, load_registry, write_report

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--report",default="invariant-report.json"); parser.add_argument("--skip-tests",action="store_true"); args=parser.parse_args()
    if args.skip_tests: print("invariant suite may not be skipped",file=sys.stderr); return 2
    command=[sys.executable,"-m","pytest","-q","tests/invariants"]
    completed=subprocess.run(command,check=False)
    results=[AssertionResult(i.assertions[0],"base",True,completed.returncode==0,f"tests/invariants/{i.invariant_id.lower()}") for i in load_registry().invariants]
    report=build_report(load_registry(),results); write_report(args.report,report)
    if completed.returncode or report["blocking"]:
        for row in report["verdicts"]:
            if row["status"]=="unproven": print(f"{row['invariant_id']}: {row['guarantee']} | {row['owning_spec']} | {row['missing_assertions']} | {row['evidence']}",file=sys.stderr)
        return 1
    return 0
if __name__=="__main__": raise SystemExit(main())
