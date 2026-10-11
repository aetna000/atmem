from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .audit import build_review_template, score_audit_review, sign_audit_review


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare, sign or score a blinded Spec 041 dataset audit")
    commands = parser.add_subparsers(dest="command", required=True)
    template = commands.add_parser("template")
    template.add_argument("--packet", type=Path, required=True)
    template.add_argument("--output", type=Path, required=True)
    sign = commands.add_parser("sign")
    sign.add_argument("--review", type=Path, required=True)
    sign.add_argument("--private-key", type=Path, required=True)
    sign.add_argument("--output", type=Path, required=True)
    score = commands.add_parser("score")
    score.add_argument("--packet", type=Path, required=True)
    score.add_argument("--answer-key", type=Path, required=True)
    score.add_argument("--review", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "template":
        value = build_review_template(_read(args.packet))
    elif args.command == "sign":
        value = sign_audit_review(_read(args.review), args.private_key.read_bytes())
    else:
        value = score_audit_review(_read(args.packet), _read(args.answer_key), _read(args.review))
    _write(args.output, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
