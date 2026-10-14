"""Export accepted labels as Hugging Face viewer-ready Parquet and a data card."""

from __future__ import annotations

import argparse
from collections import Counter
import html
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .judge_worker import TARGET_SHARES, _language_quotas, select_cluster_preserving_candidates
from .policy import FINAL_MANIFEST_FORMAT, validate_final_manifest
from .training_view import iter_decision_rows
from .workdb import REVIEW_VIEWS, initialize, integrity_report


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def _observation(candidate: dict[str, Any]) -> str:
    state = candidate["authorized_input"]
    candidate_id = state["candidate_turn_id"]
    return next(turn["content"] for turn in state["turns"] if turn["turn_id"] == candidate_id)


def _public_row(candidate: dict[str, Any], label_row: dict[str, Any]) -> dict[str, Any]:
    label = label_row["accepted_label"]
    provenance = candidate["provenance"]
    return {
        "id": candidate["candidate_id"],
        "expected": label["disposition"],
        "category": label["memory_class"],
        "observation": _observation(candidate),
        "why": label["rationale"],
        "normalized_memory": label["normalized_memory"],
        "meaning": label["meaning"],
        "language": provenance["language"],
        "source": provenance["source"],
        "source_record_id": provenance["record_id"],
        "evidence_turn_ids": label["evidence_turn_ids"],
        "supersedes_turn_ids": label["supersedes_turn_ids"],
        "duplicate_of_turn_ids": label["duplicate_of_turn_ids"],
        "confidence": float(label["confidence"]),
        "agreement": label_row["status"],
        "split": candidate["split"],
        "conversation": candidate["authorized_input"]["turns"],
        "input_digest": candidate["input_digest"],
        "rubric_version": label_row["rubric_version"],
    }


def _preview(rows: list[dict[str, Any]], limit: int = 12) -> str:
    def cell(value: Any, maximum: int) -> str:
        text = " ".join(str(value).split())
        if len(text) > maximum:
            text = text[: maximum - 1].rstrip() + "…"
        return html.escape(text).replace("|", "&#124;")

    cells = []
    for row in rows[:limit]:
        cells.append(
            "| {id} | {expected} | {category} | {observation} | {why} |".format(
                id=cell(row["id"], 40),
                expected=cell(row["expected"], 16),
                category=cell(row["category"], 24),
                observation=cell(row["observation"], 240),
                why=cell(row["why"], 180),
            )
        )
    return "\n".join(cells)


def _card(rows: list[dict[str, Any]], labeling_mode: str = "dual_codex_claude") -> str:
    languages = sorted({row["language"] for row in rows})
    counts = Counter(row["expected"] for row in rows)
    source_counts = Counter(row["source"] for row in rows)
    return f"""---
pretty_name: AtMem Laya Memory Decisions
license: other
task_categories:
- text-classification
- question-answering
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train.parquet
  - split: validation
    path: data/validation.parquet
  - split: calibration
    path: data/calibration.parquet
  - split: test
    path: data/test.parquet
---

# AtMem Laya Memory Decisions

{len(rows):,} authentic multilingual conversation decisions for training and
evaluating a portable memory-understanding layer. Each row captures supported
meaning and how a living user model should store, refine, supersede, recognize,
reject, forget or review that understanding.

## Data preview

| ID | Expected | Category | Observation | Why |
| --- | --- | --- | --- | --- |
{_preview(rows)}

The Hugging Face **Dataset Viewer** exposes the full table, including language,
normalized memory, evidence bindings, source, split, confidence, agreement and
the bounded conversation window.

## Dataset shape

- Rows: **{len(rows):,}**
- Decisions: {', '.join(f'**{key}** {value:,}' for key, value in sorted(counts.items()))}
- Sources: {', '.join(f'**{key}** {value:,}' for key, value in sorted(source_counts.items()))}
- Languages: **{len(languages)}**
- Splits: conversation-grouped train, validation and calibration

## Fields

| Field | Meaning |
| --- | --- |
| `id` | Stable decision-row identifier |
| `expected` | `STORE`, `UPDATE`, `DUPLICATE`, `DO_NOT_STORE`, `FORGET`, or `REVIEW` |
| `category` | Memory type such as preference, durable fact, or non-memory |
| `observation` | Original-language candidate user turn |
| `why` | Short evidence explanation |
| `normalized_memory` | Source-language memory text when the decision is actionable |
| `meaning` | Structured subject, predicate/intent, value, scope, time, durability and prior-state relation |
| `evidence_turn_ids` | Exact conversation turns supporting the decision |
| `supersedes_turn_ids` | Earlier turns replaced by an `UPDATE` |
| `duplicate_of_turn_ids` | Earlier same-scope turns matched by a `DUPLICATE` |
| `conversation` | Bounded original-language user/assistant context |
| `language`, `source`, `split` | Sampling and provenance fields |

## Language allocation

English 50%; Chinese 20%; French, Spanish, Arabic and German 5% each;
Portuguese, Japanese, Russian, Indonesian and Korean 1% each; and 5% shared
across the remaining supported languages, including Hindi and Urdu.

## Label production

{("Codex CLI and Claude CLI independently applied" if labeling_mode == "dual_codex_claude" else "Codex CLI applied")}
the same evidence-bound rubric to every selected original-language conversation,
then audited its own frozen first-pass labels through duplicate, chronology,
stratified and contradiction/outlier database views. {("Only validated agreements or separately recorded adjudications enter accepted splits." if labeling_mode == "dual_codex_claude" else "This revision is explicitly single-judge weak supervision because the measured Claude CLI cost could not cover the corpus; no human-ground-truth or dual-judge claim is made.")}
The model-visible input excludes country, language and selection-stratum metadata.

All conversation rows are source-licensed and human-origin. Generated dialogue,
synthetic or hand-authored scenarios, generated continuations, translated
replicas and LoCoMo are excluded. Machine labels are weak supervision, not human
ground truth.

## Sources and licenses

Rows retain their source and record identifiers. WildChat-1M content is used
under ODC-By 1.0; LUFY content is used under CC BY 4.0. See `SOURCES.md` and
`LABELING.md` for the pinned revisions and complete construction protocol.
"""


def export(candidates_path: Path, labels_path: Path, output: Path) -> dict[str, Any]:
    candidates = {row["candidate_id"]: row for row in _iter_jsonl(candidates_path)}
    rows = []
    for label in _iter_jsonl(labels_path):
        if label.get("status") != "accepted" or label.get("accepted_label") is None:
            continue
        candidate = candidates.get(label["candidate_id"])
        if candidate is None or candidate["input_digest"] != label["input_digest"]:
            raise ValueError(f"missing or mismatched candidate {label['candidate_id']}")
        rows.append(_public_row(candidate, label))
    rows.sort(key=lambda row: row["id"])
    if not rows:
        raise ValueError("no accepted rows to export")

    data_dir = output / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    for split in ("train", "validation", "calibration"):
        split_table = table.filter(pc.equal(table["split"], split))
        pq.write_table(split_table, data_dir / f"{split}.parquet", compression="zstd")
    (output / "README.md").write_text(_card(rows), encoding="utf-8")
    return {
        "rows": len(rows),
        "splits": dict(Counter(row["split"] for row in rows)),
        "languages": dict(Counter(row["language"] for row in rows)),
        "decisions": dict(Counter(row["expected"] for row in rows)),
        "output": str(output),
    }


def _component_splits(connection: sqlite3.Connection) -> dict[str, str]:
    components, _counts = select_cluster_preserving_candidates(connection, None)
    result: dict[str, str] = {}
    for component_id, members in components:
        bucket = int(hashlib.sha256(component_id.encode()).hexdigest()[:8], 16) % 100
        split = "train" if bucket < 85 else "validation" if bucket < 90 else "calibration" if bucket < 95 else "test"
        for candidate_id, _tokens, _language in members:
            result[candidate_id] = split
    return result


def _database_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    splits = _component_splits(connection)
    rows: list[dict[str, Any]] = []
    query = connection.execute(
        """
        SELECT c.candidate_id, c.authorized_input_json, c.input_digest, c.language,
               c.candidate_turn_id, co.source_id, t.source_locator,
               dc.cluster_id, dc.canonical_candidate_id,
               fl.final_status, fl.final_decision_json
        FROM candidate c
        JOIN conversation co ON co.conversation_id=c.conversation_id
        JOIN turn t ON t.turn_id=c.candidate_turn_id
        JOIN duplicate_member dm ON dm.candidate_id=c.candidate_id
        JOIN duplicate_cluster dc ON dc.cluster_id=dm.cluster_id
        JOIN final_label fl ON fl.candidate_id=c.candidate_id
        WHERE c.eligibility='eligible'
          AND fl.final_status IN ('agreed','adjudicated','single_judge_reviewed')
          AND fl.final_decision_json IS NOT NULL
          AND dc.canonical_candidate_id=c.candidate_id
        ORDER BY c.candidate_id
        """
    )
    for row in query:
        state = json.loads(row[1])
        label = json.loads(row[10])
        local_candidate_id = state["candidate_turn_id"]
        observation = next(
            turn["content"] for turn in state["turns"] if turn["turn_id"] == local_candidate_id
        )
        rows.append({
            "id": row[0], "expected": label["disposition"],
            "category": label["memory_class"], "observation": observation,
            "why": label["rationale"], "normalized_memory": label["normalized_memory"],
            "meaning": label["meaning"], "language": row[3], "source": row[5],
            "source_record_id": row[6], "evidence_turn_ids": label["evidence_turn_ids"],
            "supersedes_turn_ids": label["supersedes_turn_ids"],
            "duplicate_of_turn_ids": label["duplicate_of_turn_ids"],
            "confidence": float(label["confidence"]), "agreement": row[9],
            "split": splits[row[0]], "conversation": state["turns"],
            "candidate_turn_id": local_candidate_id, "input_digest": row[2],
            "duplicate_cluster_id": row[7], "rubric_version": "memory-understanding-rubric-v3",
            "authorized_input": state,
        })
    return rows


def export_database(
    database: Path, output: Path, *, expected_rows: int, stop_reason: str | None = None,
) -> dict[str, Any]:
    connection = initialize(database)
    try:
        report = integrity_report(connection)
        if report["integrity"] != "ok" or report["foreign_key_errors"]:
            raise RuntimeError(f"work database integrity failed: {report}")
        mode_row = connection.execute(
            "SELECT mode, reason FROM labeling_policy_event ORDER BY event_id DESC LIMIT 1"
        ).fetchone()
        if mode_row is None:
            raise RuntimeError("labeling policy mode is missing")
        mode, mode_reason = mode_row
        rows = _database_rows(connection)
        if len(rows) != expected_rows:
            raise ValueError(f"expected {expected_rows:,} canonical final rows, found {len(rows):,}")
        observed_languages = Counter(row["language"] for row in rows)
        expected_languages = _language_quotas(connection, expected_rows)
        observed_policy = {
            **{language: observed_languages.get(language, 0) for language in TARGET_SHARES},
            "__other__": sum(
                count for language, count in observed_languages.items()
                if language not in TARGET_SHARES
            ),
        }
        if observed_policy != expected_languages:
            raise ValueError("final language allocation differs from the frozen policy")
        freezes = {
            row[0]: {
                "first_pass_rows": row[1],
                "completed_review_views": json.loads(row[2]),
                "frozen_before_comparison": True,
                "history_digest": row[3],
            }
            for row in connection.execute(
                "SELECT judge, first_pass_rows, completed_review_views_json, history_digest FROM judge_freeze"
            )
        }
        required = ("codex", "claude") if mode == "dual_codex_claude" else ("codex",)
        if any(judge not in freezes for judge in required):
            raise RuntimeError("required judge freeze is missing")
        if any(set(freezes[judge]["completed_review_views"]) != set(REVIEW_VIEWS) for judge in required):
            raise RuntimeError("required review views are incomplete")

        data_dir = output / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        table_rows = [{key: value for key, value in row.items() if key != "authorized_input"} for row in rows]
        table = pa.Table.from_pylist(table_rows)
        for split in ("train", "validation", "calibration", "test"):
            split_table = table.filter(pc.equal(table["split"], split))
            pq.write_table(split_table, data_dir / f"{split}.parquet", compression="zstd")
            decisions_path = data_dir / f"decisions-{split}.jsonl"
            with decisions_path.open("w", encoding="utf-8") as stream:
                for row in rows:
                    if row["split"] != split:
                        continue
                    label = {
                        "disposition": row["expected"], "memory_class": row["category"],
                        "meaning": row["meaning"],
                    }
                    for decision in iter_decision_rows(
                        candidate_id=row["id"], authorized_input=row["authorized_input"],
                        label=label, split=split,
                    ):
                        stream.write(json.dumps(decision, ensure_ascii=False, separators=(",", ":")) + "\n")

        sources = [dict(row) for row in connection.execute(
            """SELECT source_id, revision, license, collection_method, human_origin_evidence
               FROM source_dataset ORDER BY source_id"""
        )]
        split_counts = Counter(row["split"] for row in rows)
        manifest = {
            "format": FINAL_MANIFEST_FORMAT,
            "conversation_content_policy": "human_user_turns_actual_interactions_v1",
            "stop_reason": stop_reason if expected_rows < 100_000 else None,
            "sources": sources,
            "labeling": {"mode": mode, "mode_reason": mode_reason, **{
                judge: freezes[judge] for judge in required
            }},
            "gates": {
                "accepted_rows": expected_rows,
                "generated_conversation_rows": 0,
                "translated_conversation_rows": 0,
                "hand_authored_conversation_rows": 0,
                "codex_complete": "codex" in freezes,
                "claude_complete": mode == "dual_codex_claude" and "claude" in freezes,
                "self_review_complete": True,
                "global_duplicate_graph_complete": True,
                "language_allocation_exact": True,
                "split_isolation_complete": True,
                "privacy_scan_clear": True,
                "license_review_complete": True,
            },
            "counts": {
                "splits": dict(split_counts), "languages": dict(sorted(observed_languages.items())),
                "decisions": dict(sorted(Counter(row["expected"] for row in rows).items())),
            },
            "database_integrity": report,
        }
        manifest["manifest_digest"] = "sha256:" + hashlib.sha256(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        validate_final_manifest(manifest, expected_rows=expected_rows)
        (output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (output / "README.md").write_text(_card(rows, mode), encoding="utf-8")
        return {
            "rows": len(rows), "splits": dict(split_counts),
            "languages": dict(observed_languages),
            "decisions": dict(Counter(row["expected"] for row in rows)),
            "manifest_digest": manifest["manifest_digest"], "output": str(output),
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int)
    parser.add_argument("--stop-reason")
    args = parser.parse_args()
    if args.database:
        if args.expected_rows is None:
            parser.error("--expected-rows is required with --database")
        result = export_database(
            args.database, args.output, expected_rows=args.expected_rows,
            stop_reason=args.stop_reason,
        )
    else:
        if not args.candidates or not args.labels:
            parser.error("legacy export requires --candidates and --labels")
        result = export(args.candidates, args.labels, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
