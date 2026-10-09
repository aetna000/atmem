"""Create nested answer-blind five-percent benchmark development profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


LONGMEM_FORMAT = "atmem-longmemeval-v2-development-profile-v1"
DOLPHIN_FORMAT = "atmem-dolphinbench-development-profile-v1"
DEFAULT_SALT = "atmem-2.3.8-spec040-five-percent-v1-20261001"


def _digest(salt: str, value: str) -> str:
    return hashlib.sha256(f"{salt}\0{value}".encode()).hexdigest()


def _canonical_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def longmem_profile(
    *, split: dict[str, Any], historical: dict[str, Any], salt: str,
    selected_input_manifest_sha256: str,
) -> dict[str, Any]:
    development = {str(value) for value in split["development_ids"]}
    confirmation = {str(value) for value in split["confirmation_ids"]}
    historical_ids = {str(value) for value in historical["question_ids"]}
    if len(historical_ids) != 14 or not historical_ids <= development:
        raise ValueError("historical LongMem pilot is not a development-only 14-question set")
    remaining = sorted(
        development - historical_ids,
        key=lambda value: (_digest(salt, value), value),
    )
    selected = historical_ids | set(remaining[:9])
    if len(selected) != 23 or selected & confirmation:
        raise ValueError("LongMem five-percent selection is not development-only")
    payload: dict[str, Any] = {
        "format": LONGMEM_FORMAT,
        "dataset_revision": split["dataset_revision"],
        "question_split_sha256": split["split_sha256"],
        "salt": salt,
        "claim_class": "matched_five_percent_development",
        "selection_rule": (
            "Retain every historical 14-question pilot ID, then select the nine "
            "lowest SHA-256(salt + NUL + question_id) remaining frozen development "
            "IDs without reading questions, answers, evidence or grader output."
        ),
        "historical_pilot_sha256": historical["pilot_sha256"],
        "historical_question_ids": sorted(historical_ids),
        "question_ids": sorted(selected),
        "question_count": 23,
        "confirmation_overlap": 0,
        "selected_input_manifest_sha256": selected_input_manifest_sha256,
    }
    payload["profile_sha256"] = _canonical_digest(payload)
    return payload


def dolphin_profile(
    *, tests_root: Path, source_commit: str, historical: dict[str, Any], salt: str,
) -> dict[str, Any]:
    historical_ids = {str(value) for value in historical["development_ids"]}
    if len(historical_ids) != 18:
        raise ValueError("historical Dolphin pilot is not an 18-task set")
    development: set[str] = set()
    all_ids: set[str] = set()
    personas: dict[str, dict[str, int]] = {}
    for persona in ("alex", "morgan", "riley"):
        ids = {
            f"{persona}:{path.stem}"
            for path in (tests_root / persona).glob("[0-9][0-9][0-9].yaml")
        }
        if len(ids) != 200:
            raise ValueError(f"Dolphin persona {persona} does not contain 200 public IDs")
        historical_persona = historical_ids & ids
        if len(historical_persona) != 6:
            raise ValueError(f"historical Dolphin pilot does not contain six {persona} tasks")
        remaining = sorted(
            ids - historical_persona,
            key=lambda value: (_digest(salt, value), value),
        )
        selected = historical_persona | set(remaining[:4])
        development.update(selected)
        all_ids.update(ids)
        personas[persona] = {"total": 200, "development": 10, "confirmation": 190}
    payload: dict[str, Any] = {
        "format": DOLPHIN_FORMAT,
        "source_commit": source_commit,
        "salt": salt,
        "claim_class": "matched_five_percent_development",
        "selection_rule": (
            "Within each persona retain the historical six development IDs, then "
            "select the four lowest SHA-256(salt + NUL + persona:id) remaining "
            "public IDs without reading task bodies, facts or grading checks."
        ),
        "historical_split_sha256": historical["split_sha256"],
        "historical_development_ids": sorted(historical_ids),
        "personas": personas,
        "development_ids": sorted(development),
        "confirmation_ids": sorted(all_ids - development),
    }
    payload["profile_sha256"] = _canonical_digest(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--longmem-split", type=Path, required=True)
    parser.add_argument("--longmem-historical", type=Path, required=True)
    parser.add_argument("--longmem-selected-input-manifest-sha256", required=True)
    parser.add_argument("--dolphin-tests", type=Path, required=True)
    parser.add_argument("--dolphin-commit", required=True)
    parser.add_argument("--dolphin-historical", type=Path, required=True)
    parser.add_argument("--salt", default=DEFAULT_SALT)
    parser.add_argument("--longmem-output", type=Path, required=True)
    parser.add_argument("--dolphin-output", type=Path, required=True)
    args = parser.parse_args()
    longmem = longmem_profile(
        split=_load(args.longmem_split), historical=_load(args.longmem_historical),
        salt=args.salt,
        selected_input_manifest_sha256=args.longmem_selected_input_manifest_sha256,
    )
    dolphin = dolphin_profile(
        tests_root=args.dolphin_tests, source_commit=args.dolphin_commit,
        historical=_load(args.dolphin_historical), salt=args.salt,
    )
    for path, value in ((args.longmem_output, longmem), (args.dolphin_output, dolphin)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
