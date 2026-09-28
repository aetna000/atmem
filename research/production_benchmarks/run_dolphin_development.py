"""Run the frozen 18-task DolphinBench development slice, not a submission."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from research.production_benchmarks.dolphinbench import evaluate_development  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--confirm-paid-run", action="store_true")
    args = parser.parse_args()
    if not args.confirm_paid_run:
        raise SystemExit("refusing paid DolphinBench development run without confirmation")
    checkout = Path(args.checkout).expanduser().resolve()
    config = Path(args.config).expanduser().resolve()
    if not config.is_file():
        raise SystemExit(f"DolphinBench config does not exist: {config}")
    if str(checkout) not in sys.path:
        sys.path.insert(0, str(checkout))

    from harness import runner as official_runner

    original = official_runner.Runner.evaluate

    def selected_evaluate(instance) -> None:
        result = evaluate_development(instance, checkout)
        print(
            f"Completed {result['tests']} frozen development tasks; "
            "this is not an official 600-task score."
        )

    official_runner.Runner.evaluate = selected_evaluate
    try:
        return int(official_runner.main([
            "evaluate",
            "--config", str(config),
            "--confirm-paid-calls",
        ]))
    finally:
        official_runner.Runner.evaluate = original


if __name__ == "__main__":
    raise SystemExit(main())
