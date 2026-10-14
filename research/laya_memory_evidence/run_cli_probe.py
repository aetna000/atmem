"""Run a bounded, non-committing Codex CLI throughput/label-quality probe."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .label_dataset import _codex_labels


LANGUAGES = (
    "english", "chinese", "arabic", "french", "german", "spanish",
    "indonesian", "japanese", "korean", "portuguese", "russian",
)


def _sample(database: Path) -> list[dict]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in LANGUAGES)
        rows = connection.execute(
            f"""
            WITH ranked AS (
              SELECT c.candidate_id, c.authorized_input_json, c.language,
                     co.source_id, c.risk_tags_json, dm.cluster_id,
                     COUNT(*) OVER (PARTITION BY dm.cluster_id) AS cluster_size,
                     ROW_NUMBER() OVER (
                       PARTITION BY c.language,
                         CASE
                           WHEN c.risk_tags_json LIKE '%memory_intent%' THEN 'memory_intent'
                           WHEN c.risk_tags_json LIKE '%has_prior_user_turn%' THEN 'chronology'
                           ELSE 'representative'
                         END
                       -- candidate_id is a SHA-256-derived identifier, so this
                       -- is deterministic hash sampling rather than a length
                       -- extreme that over-selects one-character noise.
                       ORDER BY c.candidate_id
                     ) AS rn
              FROM candidate c
              JOIN conversation co USING(conversation_id)
              JOIN duplicate_member dm USING(candidate_id)
              WHERE c.eligibility='eligible' AND c.language IN ({placeholders})
            )
            SELECT * FROM ranked WHERE rn=1 ORDER BY language, candidate_id
            """,
            LANGUAGES,
        ).fetchall()
        lufy = connection.execute(
            """
            SELECT c.candidate_id, c.authorized_input_json, c.language,
                   co.source_id, c.risk_tags_json, dm.cluster_id,
                   (SELECT COUNT(*) FROM duplicate_member x WHERE x.cluster_id=dm.cluster_id)
                     AS cluster_size
            FROM candidate c JOIN conversation co USING(conversation_id)
            JOIN duplicate_member dm USING(candidate_id)
            WHERE co.source_id='lufy'
            ORDER BY c.candidate_id LIMIT 3
            """
        ).fetchall()
        selected = list(rows) + list(lufy)
        return [
            {
                "candidate_id": row["candidate_id"],
                "authorized_input": json.loads(row["authorized_input_json"]),
                "language": row["language"],
                "source_id": row["source_id"],
                "risk_tags": json.loads(row["risk_tags_json"]),
                "cluster_id": row["cluster_id"],
                "cluster_size": row["cluster_size"],
            }
            for row in selected
        ]
    finally:
        connection.close()


def run(database: Path, output: Path, model: str, timeout_seconds: int) -> dict:
    sample = _sample(database)
    labels, receipt = _codex_labels(sample, model=model, timeout_seconds=timeout_seconds)
    report = {
        "format": "atmem-codex-cli-probe-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "non_committing": True,
        "model": model,
        "rows": len(sample),
        "languages": dict(sorted(Counter(row["language"] for row in sample).items())),
        "sources": dict(sorted(Counter(row["source_id"] for row in sample).items())),
        "cluster_topologies": dict(sorted(Counter(
            "singleton" if row["cluster_size"] == 1 else "multi_member" for row in sample
        ).items())),
        "dispositions": dict(sorted(Counter(
            label["disposition"] for label in labels.values()
        ).items())),
        "classes": dict(sorted(Counter(
            label["memory_class"] for label in labels.values()
        ).items())),
        "receipt": receipt,
        "results": [
            {
                "candidate_id": row["candidate_id"],
                "language": row["language"],
                "source_id": row["source_id"],
                "risk_tags": row["risk_tags"],
                "cluster_size": row["cluster_size"],
                "label": labels[row["candidate_id"]],
            }
            for row in sample
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {key: value for key, value in report.items() if key != "results"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args()
    print(json.dumps(run(args.database, args.output, args.model, args.timeout_seconds), indent=2))


if __name__ == "__main__":
    main()
