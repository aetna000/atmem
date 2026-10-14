"""Extract and validate a frozen 100-observation OpenClaw memory corpus.

This helper intentionally reads the persisted OpenClaw transcript rather than
asking the model to regenerate its answer.  That preserves the exact corpus,
run identity, and token-use evidence used by the operational A/B replay.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any


EXPECTED_COUNTS = {
    "STORE": 25,
    "UPDATE": 15,
    "DUPLICATE": 10,
    "DO_NOT_STORE": 20,
    "REVIEW": 30,
}
EXPECTED_FIELDS = {
    "id", "category", "text", "query", "expected_disposition", "rationale",
}


def _assistant_text(database: Path, session_id: str) -> tuple[str, dict[str, Any]]:
    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            "SELECT seq, event_json FROM transcript_events "
            "WHERE session_id=? ORDER BY seq",
            (session_id,),
        ).fetchall()
    finally:
        connection.close()
    for seq, raw in reversed(rows):
        event = json.loads(raw)
        message = event.get("message") or {}
        if message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content, {"seq": seq, "message": message}
        if isinstance(content, list):
            text = "".join(
                str(block.get("text") or "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
            if text:
                return text, {"seq": seq, "message": message}
    raise ValueError("no assistant text was found in the selected OpenClaw session")


def validate_corpus(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) != 100:
        raise ValueError("corpus must contain exactly 100 observations")
    expected_ids = [f"M{index:03d}" for index in range(1, 101)]
    actual_ids: list[str] = []
    normalized: list[dict[str, str]] = []
    for row in value:
        if not isinstance(row, dict) or set(row) != EXPECTED_FIELDS:
            raise ValueError("every corpus row must contain the exact required fields")
        item = {key: str(row[key]).strip() for key in EXPECTED_FIELDS}
        if not all(item.values()):
            raise ValueError("corpus fields cannot be empty")
        actual_ids.append(item["id"])
        normalized.append(item)
    if actual_ids != expected_ids:
        raise ValueError("corpus IDs must be consecutive M001 through M100")
    counts = Counter(row["expected_disposition"] for row in normalized)
    if dict(counts) != EXPECTED_COUNTS:
        raise ValueError(f"unexpected disposition balance: {dict(counts)}")
    return normalized


def _markdown(rows: list[dict[str, str]], metadata: dict[str, Any]) -> str:
    lines = [
        "# Frozen OpenClaw 100-memory operational corpus",
        "",
        "This corpus is an operational policy challenge set, not an independent "
        "scientific benchmark. It was generated once by the configured OpenClaw "
        "agent, frozen before either A/B arm ran, and validated mechanically.",
        "",
        f"- OpenClaw session: `{metadata['session_key']}`",
        f"- Session ID: `{metadata['session_id']}`",
        f"- Run ID: `{metadata['run_id']}`",
        f"- Provider/model: `{metadata['provider']}/{metadata['model']}`",
        f"- Corpus SHA-256: `{metadata['corpus_sha256']}`",
        "- Balance: 25 STORE, 15 UPDATE, 10 DUPLICATE, 20 DO_NOT_STORE, 30 REVIEW",
        "",
        "| ID | Expected | Category | Observation | Why |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        cells = [
            row["id"], row["expected_disposition"], row["category"],
            row["text"], row["rationale"],
        ]
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    return "\n".join(lines) + "\n"


def extract(database: Path, session_id: str, output_dir: Path) -> dict[str, Any]:
    text, event = _assistant_text(database, session_id)
    rows = validate_corpus(json.loads(text))
    canonical = json.dumps(rows, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    message = event["message"]
    metadata = {
        "format": "atmem-openclaw-memory-corpus-v1",
        "session_key": "agent:main:atmem-laya-100-corpus-20261012",
        "session_id": session_id,
        "run_id": "dc3ff697-91b7-43ea-b8bf-d7216a6a4e4c",
        "provider": message.get("provider"),
        "model": message.get("model"),
        "usage": message.get("usage"),
        "stop_reason": message.get("stopReason"),
        "corpus_sha256": digest,
        "counts": EXPECTED_COUNTS,
        "transcript_database": str(database),
        "transcript_event_seq": event["seq"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "corpus.json").write_text(canonical, encoding="utf-8")
    (output_dir / "corpus-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "corpus.md").write_text(_markdown(rows, metadata), encoding="utf-8")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    metadata = extract(args.database.expanduser(), args.session_id, args.output_dir)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
