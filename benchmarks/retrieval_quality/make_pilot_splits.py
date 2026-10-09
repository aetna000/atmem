"""Create metadata-only, answer-blind development pilot selections."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


LONGMEM_FORMAT = "atmem-longmemeval-v2-pilot-v1"
DOLPHIN_FORMAT = "atmem-dolphinbench-task-split-v1"
DEFAULT_SALT = "atmem-2.3.8-spec038-pilot-v1-20260928"


def _digest(salt: str, value: str) -> str:
    return hashlib.sha256(f"{salt}\0{value}".encode("utf-8")).hexdigest()


def _canonical_digest(value: dict[str, Any]) -> str:
    stable = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def longmem_pilot(
    questions: Path, split_path: Path, *, salt: str
) -> dict[str, Any]:
    rows = _read_jsonl(questions)
    split = json.loads(split_path.read_text(encoding="utf-8"))
    development = set(split["development_ids"])
    confirmation = set(split["confirmation_ids"])
    by_stratum: dict[str, list[str]] = {}
    for row in rows:
        question_id = str(row.get("id") or "")
        if question_id not in development:
            continue
        key = f"{row.get('domain')}:{row.get('question_type')}"
        by_stratum.setdefault(key, []).append(question_id)
    if set(by_stratum) != set(split["strata"]):
        raise ValueError("pilot question metadata does not cover every frozen stratum")
    selected_by_stratum = {
        key: min(ids, key=lambda value: (_digest(salt, value), value))
        for key, ids in sorted(by_stratum.items())
    }
    selected = sorted(selected_by_stratum.values())
    if len(selected) != 14 or set(selected) & confirmation:
        raise ValueError("LongMemEval pilot must contain 14 development-only IDs")
    payload: dict[str, Any] = {
        "format": LONGMEM_FORMAT,
        "dataset_revision": split["dataset_revision"],
        "question_split_sha256": split["split_sha256"],
        "salt": salt,
        "claim_class": "development_plumbing_and_cost_calibration",
        "selection_rule": "Select the lowest SHA-256(salt + NUL + question_id) development ID in each frozen domain-by-question_type stratum without reading answers.",
        "selected_by_stratum": selected_by_stratum,
        "question_ids": selected,
        "question_count": len(selected),
        "confirmation_overlap": 0,
    }
    payload["pilot_sha256"] = _canonical_digest(payload)
    return payload


def dolphin_split(tests_root: Path, *, source_commit: str, salt: str) -> dict[str, Any]:
    development: list[str] = []
    confirmation: list[str] = []
    counts: dict[str, dict[str, int]] = {}
    for persona_dir in sorted(path for path in tests_root.iterdir() if path.is_dir()):
        ids = sorted(path.stem for path in persona_dir.glob("[0-9][0-9][0-9].yaml"))
        if len(ids) != 200:
            continue
        ordered = sorted(ids, key=lambda value: (_digest(salt, f"{persona_dir.name}:{value}"), value))
        selected = set(ordered[:6])
        for value in ids:
            qualified = f"{persona_dir.name}:{value}"
            (development if value in selected else confirmation).append(qualified)
        counts[persona_dir.name] = {
            "total": len(ids),
            "development": len(selected),
            "confirmation": len(ids) - len(selected),
        }
    if len(counts) != 3 or len(development) != 18 or len(confirmation) != 582:
        raise ValueError("DolphinBench pilot requires three 200-task personas")
    payload: dict[str, Any] = {
        "format": DOLPHIN_FORMAT,
        "source_commit": source_commit,
        "salt": salt,
        "selection_rule": "Within each persona, order public task IDs by SHA-256(salt + NUL + persona:id); select six without reading task bodies, facts or grading checks.",
        "claim_class": "development_plumbing_and_cost_calibration",
        "personas": counts,
        "development_ids": sorted(development),
        "confirmation_ids": sorted(confirmation),
    }
    payload["split_sha256"] = _canonical_digest(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--longmem-questions", type=Path, required=True)
    parser.add_argument("--longmem-split", type=Path, required=True)
    parser.add_argument("--dolphin-tests", type=Path, required=True)
    parser.add_argument("--dolphin-commit", required=True)
    parser.add_argument("--salt", default=DEFAULT_SALT)
    parser.add_argument("--longmem-output", type=Path, required=True)
    parser.add_argument("--dolphin-output", type=Path, required=True)
    args = parser.parse_args()
    outputs = (
        (args.longmem_output, longmem_pilot(args.longmem_questions, args.longmem_split, salt=args.salt)),
        (args.dolphin_output, dolphin_split(args.dolphin_tests, source_commit=args.dolphin_commit, salt=args.salt)),
    )
    for path, payload in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
