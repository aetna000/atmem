from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED = (
    "synthetic-only",
    "no real user history",
    "not production-quality evidence",
    "12,000 scenarios",
    "60,000 decisions",
    "sealed_test",
    "99.75%",
    "Apache License 2.0",
    "AtMem remains the sole authority",
)
FORBIDDEN = (
    "TODO",
    "TBD",
    "real-user data",
    "proves production quality",
    "production-ready benchmark",
    "beats Jev",
)


def lint(text: str) -> None:
    missing = [phrase for phrase in REQUIRED if phrase not in text]
    forbidden = [phrase for phrase in FORBIDDEN if phrase in text]
    if missing:
        raise ValueError(f"dataset card is missing required wording: {missing}")
    if forbidden:
        raise ValueError(f"dataset card contains forbidden claim wording: {forbidden}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint the Spec 041 dataset card")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    lint(args.path.read_text(encoding="utf-8"))
    print(f"dataset card lint passed: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
