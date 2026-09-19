from __future__ import annotations

import argparse
from pathlib import Path

from .report import write_report
from .runner import DEFAULT_MODEL, run


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated AtMem × Jev research demo")
    parser.add_argument("--offline", action="store_true", help="do not call TypeSafe; use deterministic local judge")
    parser.add_argument("--seed", type=int, default=34)
    parser.add_argument("--cases", type=int, default=8)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=Path("research/jev_lab/results/jev-lab.html"))
    args = parser.parse_args()
    result = run(seed=args.seed, case_count=args.cases, offline=args.offline, model=args.model)
    write_report(result, args.output)
    print(f"mode={result['mode']} model={result['model']} cases={result['metrics']['baseline']['cases']}")
    print(f"baseline_mrr_at_5={result['metrics']['baseline']['mrr_at_5']} jev_mrr_at_5={result['metrics']['jev']['mrr_at_5']}")
    print(f"report={args.output} json={args.output.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
