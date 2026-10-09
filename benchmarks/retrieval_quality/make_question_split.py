"""Create a metadata-only, precommitted LongMemEval-V2 question split."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any


FORMAT = "atmem-longmemeval-v2-question-split-v1"
DEFAULT_SALT = "atmem-2.3.8-spec038-split-v1-20260927"
FORCED_DEVELOPMENT = frozenset(
    {
        "ff311d07", "f3496ca5", "14a823df", "41a18e5c", "07ffeedf",
        "15e5efa6", "631667c9", "d3300354", "c738b934", "07ab3723",
    }
)


def _digest(salt: str, question_id: str) -> str:
    return hashlib.sha256(f"{salt}\0{question_id}".encode("utf-8")).hexdigest()


def build_split(
    rows: list[dict[str, Any]],
    *,
    salt: str,
    development_fraction: float,
    questions_sha256: str,
) -> dict[str, Any]:
    if not 0.0 < development_fraction < 1.0:
        raise ValueError("development_fraction must be between zero and one")
    strata: dict[tuple[str, str], list[str]] = defaultdict(list)
    seen: set[str] = set()
    for row in rows:
        question_id = str(row.get("id") or "").strip()
        domain = str(row.get("domain") or "").strip()
        question_type = str(row.get("question_type") or "").strip()
        if not question_id or question_id in seen or not domain or not question_type:
            raise ValueError("question metadata requires unique id, domain and question_type")
        seen.add(question_id)
        strata[(domain, question_type)].append(question_id)
    missing = sorted(FORCED_DEVELOPMENT - seen)
    if missing:
        raise ValueError(f"forced development IDs absent from dataset: {missing}")

    development: list[str] = []
    confirmation: list[str] = []
    counts: dict[str, dict[str, int]] = {}
    for (domain, question_type), ids in sorted(strata.items()):
        ordered = sorted(ids, key=lambda value: (_digest(salt, value), value))
        target = max(1, min(len(ordered) - 1, round(len(ordered) * development_fraction)))
        forced = [value for value in ordered if value in FORCED_DEVELOPMENT]
        remaining = [value for value in ordered if value not in FORCED_DEVELOPMENT]
        selected = set(forced + remaining[: max(0, target - len(forced))])
        key = f"{domain}:{question_type}"
        counts[key] = {"total": len(ordered), "development": len(selected), "confirmation": len(ordered) - len(selected)}
        for value in ordered:
            (development if value in selected else confirmation).append(value)

    payload = {
        "format": FORMAT,
        "dataset": "xiaowu0162/longmemeval-v2",
        "dataset_revision": "f152293e235517d504809563c833d7190b8c713b",
        "questions_sha256": questions_sha256,
        "salt": salt,
        "rule": "Within each domain and question_type, order SHA-256(salt + NUL + id); select 30% for development, forcing every previously inspected dev10 id into development.",
        "development_fraction": development_fraction,
        "strata": counts,
        "development_ids": sorted(development),
        "confirmation_ids": sorted(confirmation),
    }
    stable = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["split_sha256"] = hashlib.sha256(stable.encode("utf-8")).hexdigest()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("questions", type=Path)
    parser.add_argument("--salt", default=DEFAULT_SALT)
    parser.add_argument("--development-fraction", type=float, default=0.30)
    args = parser.parse_args()
    source_bytes = args.questions.read_bytes()
    rows = [json.loads(line) for line in source_bytes.decode("utf-8").splitlines() if line.strip()]
    print(
        json.dumps(
            build_split(
                rows,
                salt=args.salt,
                development_fraction=args.development_fraction,
                questions_sha256=hashlib.sha256(source_bytes).hexdigest(),
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
