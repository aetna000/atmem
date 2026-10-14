"""Import immutable authentic conversation candidates into the work database."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterator

from .build_dataset import MANIFEST_FORMAT
from .workdb import initialize, integrity_report, transaction


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def _source_method(source: str) -> tuple[str, str]:
    if source == "wildchat-1m":
        return (
            "organic public human-to-assistant production conversations",
            "WildChat-1M collection methodology and source metadata",
        )
    if source == "lufy":
        return (
            "controlled longitudinal human-to-assistant study conversations",
            "LUFY study protocol and participant-authored turns",
        )
    raise ValueError(f"unreviewed source: {source}")


def import_candidates(database: Path, corpus_root: Path) -> dict[str, Any]:
    manifest_path = corpus_root / "manifest.json"
    candidates_path = corpus_root / "candidates.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != MANIFEST_FORMAT:
        raise ValueError("candidate corpus is not an authentic-conversation manifest")
    if manifest.get("generated_or_translated_conversations") != 0:
        raise ValueError("generated or translated conversations are forbidden")
    if manifest.get("unlabeled") is not True:
        raise ValueError("source import expects immutable unlabeled candidates")

    connection = initialize(database)
    created_at = _utc_now()
    inserted = {"sources": 0, "conversations": 0, "turns": 0, "candidates": 0}
    seen_rows = 0
    try:
        with transaction(connection):
            for source_id, source in sorted(manifest["source_revisions"].items()):
                if source_id == "lufy" and not source.get("included"):
                    continue
                method, evidence = _source_method(source_id)
                before = connection.total_changes
                connection.execute(
                    "INSERT OR IGNORE INTO source_dataset VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (source_id, source["repo_id"], source["revision"], source["license"],
                     method, evidence, manifest["files"]["candidates.jsonl"]["sha256"], created_at),
                )
                inserted["sources"] += connection.total_changes - before

            for row in _rows(candidates_path):
                seen_rows += 1
                provenance = row["provenance"]
                source_id = provenance["source"]
                group_id = provenance["group_id"]
                conversation_id = "conv-" + hashlib.sha256(
                    f"{source_id}\0{group_id}".encode("utf-8")
                ).hexdigest()[:32]
                scope_key = f"{source_id}:{group_id}"
                turns = row["authorized_input"]["turns"]
                conversation_digest = _digest_text(_canonical(turns))
                before = connection.total_changes
                connection.execute(
                    "INSERT OR IGNORE INTO conversation VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (conversation_id, source_id, group_id, None, None, scope_key,
                     provenance["language"], None, conversation_digest),
                )
                inserted["conversations"] += connection.total_changes - before

                local_to_global: dict[str, str] = {}
                for window_order, turn in enumerate(turns):
                    global_turn_id = f"{conversation_id}:{turn['turn_id']}"
                    local_to_global[turn["turn_id"]] = global_turn_id
                    match = re.fullmatch(r"t(\d+)", turn["turn_id"])
                    order = int(match.group(1)) if match else window_order
                    before = connection.total_changes
                    connection.execute(
                        "INSERT OR IGNORE INTO turn VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (global_turn_id, conversation_id, order, turn["role"], turn["content"],
                         f"{provenance['record_id']}#{turn['turn_id']}",
                         _digest_text(turn["content"]), None),
                    )
                    inserted["turns"] += connection.total_changes - before

                candidate_turn_id = local_to_global[row["authorized_input"]["candidate_turn_id"]]
                risk_tags = [
                    "selection:" + str(provenance.get("selection_stratum", "unspecified"))
                ]
                if row["authorized_input"].get("prior_user_turn_ids"):
                    risk_tags.append("has_prior_user_turn")
                before = connection.total_changes
                connection.execute(
                    "INSERT OR IGNORE INTO candidate VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (row["candidate_id"], conversation_id, candidate_turn_id, scope_key,
                     _canonical(row["authorized_input"]), row["input_digest"],
                     provenance["language"], _canonical(sorted(risk_tags)), "eligible", None,
                     f"{source_id}:{group_id}", created_at),
                )
                inserted["candidates"] += connection.total_changes - before
        if seen_rows != manifest["rows"]:
            raise ValueError(f"manifest declares {manifest['rows']} rows but read {seen_rows}")
        report = integrity_report(connection)
        if report["integrity"] != "ok" or report["foreign_key_errors"]:
            raise RuntimeError(f"work database integrity failed: {report}")
        return {"read": seen_rows, "inserted": inserted, "database": str(database), "integrity": report}
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(import_candidates(args.database, args.corpus_root), indent=2))


if __name__ == "__main__":
    main()
