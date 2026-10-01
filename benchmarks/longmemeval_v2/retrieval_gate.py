#!/usr/bin/env python3
"""Run a reader-free LongMemEval-V2 evidence gate against one AtMem database.

The expected answer is never supplied to retrieval.  It is consulted only
after context assembly to report a deliberately conservative literal coverage
signal alongside the complete candidates, provenance, and timing evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import uuid

from atmem import Memory
from atmem.contracts import (
    AuthorityScope,
    ContextRequestV2,
    RecallRequest,
    RetrievalBudget,
)


def _question_text(question: object) -> str:
    if isinstance(question, str):
        return question
    if isinstance(question, dict) and isinstance(question.get("text"), str):
        return str(question["text"])
    raise ValueError("question must be text or an object containing text")


def _literal_coverage(answer: object, context: str) -> bool | None:
    if not isinstance(answer, str) or not answer.strip():
        return None
    values = [part.strip().lower() for part in answer.replace(";", ",").split(",")]
    values = [value for value in values if value]
    return bool(values) and all(value in context.lower() for value in values)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--candidate-limit", type=int, default=200)
    parser.add_argument("--context-bytes", type=int, default=32_768)
    args = parser.parse_args()

    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    if not isinstance(questions, list):
        raise ValueError("questions file must contain a JSON array")
    scope = AuthorityScope(
        "longmemeval-public", "longmemeval-v2", f"{args.domain}-small"
    )
    memory = Memory(args.database, retain_query_text=False, auto_vectors=False)
    rows: list[dict[str, object]] = []
    try:
        for question in questions:
            query = _question_text(question["question"])
            request_id = f"gate-{uuid.uuid4().hex}"
            started = time.perf_counter()
            candidates = memory.eligible_candidates(RecallRequest(
                request_id=request_id,
                scope=scope,
                query=query,
                limit=args.limit,
                candidate_limit=args.candidate_limit,
                signals=("lexical", "graph"),
                retrieval_strategy="core-rrf-v1",
            ))
            nominated_at = time.perf_counter()
            package = memory.prepare_context_v2(ContextRequestV2(
                context_id=f"context-{request_id}",
                candidate_set_id=candidates.candidate_set_id,
                scope=scope,
                query=query,
                budget=RetrievalBudget(context_bytes=args.context_bytes),
            ))
            finished = time.perf_counter()
            rows.append({
                "id": question.get("id"),
                "question_type": question.get("question_type"),
                "query": query,
                "expected_answer": question.get("answer"),
                "literal_answer_in_context": _literal_coverage(
                    question.get("answer"), package.context
                ),
                "nomination_seconds": nominated_at - started,
                "assembly_seconds": finished - nominated_at,
                "total_seconds": finished - started,
                "context_bytes": len(package.context.encode("utf-8")),
                "candidates": [candidate.to_dict() for candidate in candidates.candidates],
                "context_package": package.to_dict(),
            })
    finally:
        memory.close()

    payload = {
        "format": "atmem-longmemeval-retrieval-gate-v1",
        "database": str(args.database),
        "domain": args.domain,
        "question_count": len(rows),
        "literal_coverage_count": sum(
            row["literal_answer_in_context"] is True for row in rows
        ),
        "mean_total_seconds": (
            sum(float(row["total_seconds"]) for row in rows) / len(rows)
            if rows else 0.0
        ),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(args.output),
        "question_count": payload["question_count"],
        "literal_coverage_count": payload["literal_coverage_count"],
        "mean_total_seconds": payload["mean_total_seconds"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
