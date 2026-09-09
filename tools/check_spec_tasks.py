#!/usr/bin/env python3
"""Read-only Spec Kit task inventory preserving feature-local suffix IDs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


TASK = re.compile(r"^- \[( |x|X)\] \[(T[0-9]{3,}[a-z]*)\](?:\s|$)")
CHECKBOX = re.compile(r"^- \[[ xX]\]")


def parse_tasks(text: str, source: str) -> list[dict[str, object]]:
    rows = []
    seen = set()
    for number, line in enumerate(text.splitlines(), 1):
        if not CHECKBOX.match(line):
            continue
        match = TASK.match(line)
        if match is None:
            raise ValueError(f"{source}:{number}: invalid task row")
        task_id = match[2]
        if task_id in seen:
            raise ValueError(f"{source}:{number}: duplicate task ID {task_id}")
        seen.add(task_id)
        rows.append({
            "id": task_id,
            "completed": match[1].lower() == "x",
            "rollup": line[match.end():].startswith("[ROLLUP:"),
        })
    return rows


def inventory(root: Path) -> dict[str, object]:
    files = sorted(root.glob("*/tasks.md"))
    if not files:
        raise ValueError(f"{root}: no feature task files")
    features = []
    for path in files:
        rows = parse_tasks(path.read_text(encoding="utf-8"), str(path))
        features.append({"feature": path.parent.name, "tasks": rows})
    rows = [row for feature in features for row in feature["tasks"]]
    unchecked = [row for row in rows if not row["completed"]]
    return {
        "feature_count": len(features),
        "task_count": len(rows),
        "completed": len(rows) - len(unchecked),
        "unchecked": len(unchecked),
        "unchecked_rollups": sum(bool(row["rollup"]) for row in unchecked),
        "actionable_unchecked": sum(not row["rollup"] for row in unchecked),
        "features": features,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "specs")
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    try:
        result = inventory(args.root)
    except (OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}))
        return 1
    if not args.details:
        result.pop("features")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
