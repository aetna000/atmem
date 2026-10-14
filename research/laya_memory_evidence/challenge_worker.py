"""Adjudicate authentic challenge transitions against the frozen scoped state."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable

from atmem import Memory
from atmem.contracts import AuthorityScope, RecallRequest
from atmem.core.canonical import canonical_json

from .baseline_worker import (
    BATCH_SCHEMA, SYSTEM, _packets, _state, _validate_decisions,
    decisions_agree,
)
from .label_dataset import _claude_structured, _codex_structured


FORMAT = "atmem-challenge-adjudication-v2"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def _migrate(connection: sqlite3.Connection) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS challenge_judgment(
      transition_id TEXT NOT NULL REFERENCES challenge(transition_id),
      authority TEXT NOT NULL,
      pass_kind TEXT NOT NULL CHECK(pass_kind IN ('first','verification','adjudication')),
      decision_json TEXT NOT NULL CHECK(json_valid(decision_json)),
      input_digest TEXT NOT NULL,
      receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
      decision_digest TEXT NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY(transition_id,authority,pass_kind)
    ) STRICT;
    CREATE TABLE IF NOT EXISTS challenge_adjudication(
      transition_id TEXT PRIMARY KEY REFERENCES challenge(transition_id),
      authority TEXT NOT NULL,
      expected_json TEXT NOT NULL CHECK(json_valid(expected_json)),
      pre_state_digest TEXT NOT NULL,
      expected_post_state_digest TEXT NOT NULL,
      accepted INTEGER NOT NULL CHECK(accepted IN (0,1)),
      receipt_digest TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL
    ) STRICT;
    CREATE TABLE IF NOT EXISTS challenge_retrieval(
      transition_id TEXT PRIMARY KEY REFERENCES challenge(transition_id),
      retrieval_json TEXT NOT NULL CHECK(json_valid(retrieval_json)),
      receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
      retrieval_digest TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL
    ) STRICT;
    CREATE TABLE IF NOT EXISTS challenge_failed_attempt(
      transition_id TEXT NOT NULL REFERENCES challenge(transition_id),
      authority TEXT NOT NULL,
      attempt INTEGER NOT NULL CHECK(attempt > 0),
      judgments_json TEXT NOT NULL CHECK(json_valid(judgments_json)),
      adjudication_json TEXT NOT NULL CHECK(json_valid(adjudication_json)),
      reason TEXT NOT NULL,
      archived_at TEXT NOT NULL,
      PRIMARY KEY(transition_id,authority,attempt)
    ) STRICT;
    """)
    connection.commit()


def archive_and_reset_invalid(
    work_db: Path, *, partition: str, authority: str,
) -> dict[str, int]:
    """Archive and reset only finalized technical validation failures.

    Accepted semantic judgments are deliberately ineligible.  The complete
    failed decision/receipt trail remains in the work database so a smaller
    packet retry is auditable rather than an overwrite.
    """

    connection = sqlite3.connect(work_db)
    connection.row_factory = sqlite3.Row
    _migrate(connection)
    rows = connection.execute(
        """SELECT a.*,c.status FROM challenge_adjudication a
           JOIN challenge c ON c.transition_id=a.transition_id
           WHERE c.split_family=? AND a.authority=? AND a.accepted=0
           ORDER BY a.transition_id""",
        (partition, authority),
    ).fetchall()
    reset = 0
    try:
        with connection:
            for row in rows:
                expected = json.loads(row["expected_json"])
                if "judge_output_validation_failed" not in set(
                    expected.get("reason_codes") or ()
                ):
                    continue
                judgments = connection.execute(
                    """SELECT pass_kind,decision_json,input_digest,receipt_json,
                              decision_digest,created_at
                       FROM challenge_judgment
                       WHERE transition_id=? AND authority=?
                       ORDER BY pass_kind""",
                    (row["transition_id"], authority),
                ).fetchall()
                archived = [dict(item) for item in judgments]
                attempt = int(connection.execute(
                    """SELECT COALESCE(MAX(attempt),0)+1
                       FROM challenge_failed_attempt
                       WHERE transition_id=? AND authority=?""",
                    (row["transition_id"], authority),
                ).fetchone()[0])
                adjudication = {
                    key: row[key] for key in (
                        "expected_json", "pre_state_digest",
                        "expected_post_state_digest", "accepted",
                        "receipt_digest", "created_at",
                    )
                }
                connection.execute(
                    "INSERT INTO challenge_failed_attempt VALUES (?,?,?,?,?,?,?)",
                    (
                        row["transition_id"], authority, attempt,
                        canonical_json(archived), canonical_json(adjudication),
                        "judge_output_validation_failed", _now(),
                    ),
                )
                connection.execute(
                    "DELETE FROM challenge_adjudication WHERE transition_id=?",
                    (row["transition_id"],),
                )
                connection.execute(
                    "DELETE FROM challenge_judgment WHERE transition_id=? AND authority=?",
                    (row["transition_id"], authority),
                )
                connection.execute(
                    "UPDATE challenge SET status='ready' WHERE transition_id=?",
                    (row["transition_id"],),
                )
                reset += 1
        return {"archived": reset, "reset": reset}
    finally:
        connection.close()


def _rows(
    connection: sqlite3.Connection, *, partition: str, authority: str,
    pass_kind: str, limit: int,
) -> list[sqlite3.Row]:
    return connection.execute(
        """SELECT c.transition_id AS observation_id,c.* FROM challenge c
           WHERE c.split_family=? AND c.status IN ('blocked_on_baseline','ready')
             AND NOT EXISTS (
               SELECT 1 FROM baseline_observation b
               WHERE b.group_id=c.group_id AND b.status='awaiting_adjudication'
             )
             AND NOT EXISTS (
               SELECT 1 FROM challenge_judgment j
               WHERE j.transition_id=c.transition_id
                 AND j.authority=? AND j.pass_kind=?
             )
             AND (
               ? != 'verification' OR EXISTS (
                 SELECT 1 FROM challenge_judgment first_pass
                 WHERE first_pass.transition_id=c.transition_id
                   AND first_pass.authority=? AND first_pass.pass_kind='first'
               )
             )
           ORDER BY c.transition_id LIMIT ?""",
        (partition, authority, pass_kind, pass_kind, authority, limit),
    ).fetchall()


def _retrieve(memory: Memory, row: sqlite3.Row) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the production governed retriever once and freeze its bounded output."""

    scope = AuthorityScope(
        subject_id=str(row["scope_id"]),
        # The baseline replay materialized every authentic source into this
        # fixed opaque authority envelope.  Reuse it exactly so governed
        # retrieval cannot silently filter all candidates as cross-workspace.
        agent_id="baseline-agent",
        workspace_id="baseline-workspace",
    )
    request = RecallRequest(
        request_id="retrieval_" + _sha(row["transition_id"])[7:39],
        scope=scope,
        query=str(row["content"]),
        limit=8,
        candidate_limit=64,
        min_score=0.0,
        egress_class="local",
    )
    candidate_set = memory.eligible_candidates(request)
    record_ids = [candidate.record_id for candidate in candidate_set.candidates]
    records = memory.store.get_records(scope.subject_id, record_ids)
    retrieved: list[dict[str, Any]] = []
    for candidate in candidate_set.candidates:
        record = records.get(candidate.record_id) or {}
        raw = record.get("raw") or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                raw = {}
        retrieved.append({
            "id": candidate.record_id,
            "content": candidate.content,
            "status": str(record.get("status") or "active"),
            "generation": int(record.get("generation") or 0),
            "memory_class": str(raw.get("memory_class") or "unknown"),
            "retrieval_score": float(candidate.score),
        })
    receipt = {
        "format": "atmem-frozen-retrieval-receipt-v2",
        "request_id": request.request_id,
        "candidate_set_id": candidate_set.candidate_set_id,
        "candidate_digest": candidate_set.candidate_digest,
        "canonical_generation": candidate_set.generation,
        "requested_top_k": request.limit,
        "returned_count": len(retrieved),
        "complete": True,
        "truncated": False,
        "retriever_revision": "atmem-eligible-candidates-v1",
    }
    return retrieved, receipt


def _ensure_retrievals(
    connection: sqlite3.Connection, memory: Memory, rows: list[sqlite3.Row],
) -> None:
    for row in rows:
        existing = connection.execute(
            "SELECT 1 FROM challenge_retrieval WHERE transition_id=?",
            (row["transition_id"],),
        ).fetchone()
        if existing is not None:
            continue
        retrieved, receipt = _retrieve(memory, row)
        digest = _sha({
            "transition_id": row["transition_id"],
            "retrieved_memories": retrieved,
            "receipt": receipt,
        })
        with connection:
            connection.execute(
                "INSERT INTO challenge_retrieval VALUES (?,?,?,?,?)",
                (
                    row["transition_id"], canonical_json(retrieved),
                    canonical_json(receipt), digest, _now(),
                ),
            )


def _inputs(
    connection: sqlite3.Connection, memory: Memory, rows: list[sqlite3.Row],
) -> list[dict[str, Any]]:
    _ensure_retrievals(connection, memory, rows)
    result = []
    for row in rows:
        frozen = connection.execute(
            "SELECT retrieval_json FROM challenge_retrieval WHERE transition_id=?",
            (row["transition_id"],),
        ).fetchone()
        if frozen is None:
            raise RuntimeError("challenge retrieval was not frozen")
        memories = json.loads(str(frozen["retrieval_json"]))
        result.append({
            "observation_id": row["transition_id"],
            "observation": {"role": "user", "content": row["content"]},
            "current_memories": memories,
            "allowed_operations": [
                "STORE_NEW", "UPDATE_EXISTING", "SUPERSEDE_EXISTING",
                "DUPLICATE", "DO_NOT_STORE", "FORGET_EXISTING", "REVIEW",
            ],
        })
    return result


def _call(
    authority: str, prompt: str, schema: dict[str, Any], *, model: str,
    timeout_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if authority == "codex":
        return _codex_structured(
            prompt, schema, model=model, timeout_seconds=timeout_seconds,
        )
    if authority == "claude":
        return _claude_structured(
            prompt, schema, model=model, timeout_seconds=timeout_seconds,
        )
    raise ValueError("authority must be codex or claude")


def _judge_validated(
    authority: str, rows: list[sqlite3.Row], inputs: list[dict[str, Any]], *,
    model: str, timeout_seconds: int, system: str = SYSTEM,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        prompt = system + "\n\nINPUT:\n" + canonical_json({"items": inputs})
        payload, receipt = _call(
            authority, prompt, BATCH_SCHEMA, model=model,
            timeout_seconds=timeout_seconds,
        )
        return _validate_decisions(rows, inputs, payload), receipt
    except (RuntimeError, ValueError) as exc:
        if len(rows) <= 1:
            return [{
                "observation_id": rows[0]["transition_id"],
                "operation": "REVIEW", "memory_class": "non_memory",
                "target_memory_id": None, "context_sufficient": False,
                "durable": False, "future_utility_level": 0,
                "evidence_memory_ids": [],
                "reason_codes": ["judge_output_validation_failed"],
            }], {
                "authority": authority, "model": model,
                "validation_failed": True, "error_type": type(exc).__name__,
                "error_message": str(exc)[-500:],
            }
        middle = len(rows) // 2
        left, left_receipt = _judge_validated(
            authority, rows[:middle], inputs[:middle], model=model,
            timeout_seconds=timeout_seconds, system=system,
        )
        right, right_receipt = _judge_validated(
            authority, rows[middle:], inputs[middle:], model=model,
            timeout_seconds=timeout_seconds, system=system,
        )
        return left + right, {
            "authority": authority, "model": model, "packet_split": True,
            "child_receipt_digests": [_sha(left_receipt), _sha(right_receipt)],
            "validation_failure_count": sum(
                int(item.get("validation_failure_count", item.get("validation_failed", False)))
                for item in (left_receipt, right_receipt)
            ),
        }


def run_pass(
    work_db: Path, atmem_db: Path, *, partition: str, authority: str,
    pass_kind: str, model: str, batch_size: int, row_limit: int | None,
    timeout_seconds: int, workers: int = 1,
) -> dict[str, Any]:
    connection = sqlite3.connect(work_db)
    connection.row_factory = sqlite3.Row
    _migrate(connection)
    memory = Memory(atmem_db, auto_vectors=False, allow_insecure_typed_development=True)
    completed = 0
    try:
        while row_limit is None or completed < row_limit:
            capacity = batch_size * max(1, workers)
            take = capacity if row_limit is None else min(capacity, row_limit - completed)
            rows = _rows(
                connection, partition=partition, authority=authority,
                pass_kind=pass_kind, limit=take,
            )
            if not rows:
                break
            inputs = _inputs(connection, memory, rows)
            packets = _packets(rows, inputs, batch_size=batch_size)
            with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
                judged = list(executor.map(
                    lambda packet: _judge_validated(
                        authority, packet[0], packet[1], model=model,
                        timeout_seconds=timeout_seconds,
                    ),
                    packets,
                ))
            decisions = [decision for packet, _receipt in judged for decision in packet]
            row_receipts = [
                receipt for (packet_rows, _packet_inputs), (_decisions, receipt)
                in zip(packets, judged) for _ in packet_rows
            ]
            with connection:
                for row, judge_input, decision, receipt in zip(
                    rows, inputs, decisions, row_receipts,
                ):
                    connection.execute(
                        "INSERT INTO challenge_judgment VALUES (?,?,?,?,?,?,?,?)",
                        (
                            row["transition_id"], authority, pass_kind,
                            canonical_json(decision), _sha(judge_input),
                            canonical_json(receipt), _sha(decision), _now(),
                        ),
                    )
            completed += len(rows)
    finally:
        memory.close()
        connection.close()
    return {"partition": partition, "authority": authority, "completed": completed}


RESOLUTION_SYSTEM = SYSTEM + """

This is a disagreement adjudication pass. Each input includes two
candidate_decisions from independent passes. Re-evaluate the authentic
observation and authorized current state, then return one final decision for
every supervised field. Do not vote mechanically."""


def resolve_disagreements(
    work_db: Path, atmem_db: Path, *, partition: str, authority: str,
    model: str, batch_size: int, timeout_seconds: int, workers: int = 1,
) -> dict[str, int]:
    connection = sqlite3.connect(work_db)
    connection.row_factory = sqlite3.Row
    _migrate(connection)
    memory = Memory(atmem_db, auto_vectors=False, allow_insecure_typed_development=True)
    try:
        candidates = connection.execute(
            """SELECT c.transition_id AS observation_id,c.* FROM challenge c
               WHERE c.split_family=? AND c.status IN ('blocked_on_baseline','ready')
                 AND (SELECT COUNT(*) FROM challenge_judgment j
                      WHERE j.transition_id=c.transition_id AND j.authority=?
                        AND j.pass_kind IN ('first','verification'))=2
                 AND NOT EXISTS (
                   SELECT 1 FROM challenge_judgment j
                   WHERE j.transition_id=c.transition_id AND j.authority=?
                     AND j.pass_kind='adjudication'
                 ) ORDER BY c.transition_id""",
            (partition, authority, authority),
        ).fetchall()
        rows: list[sqlite3.Row] = []
        inputs: list[dict[str, Any]] = []
        for row in candidates:
            values = connection.execute(
                "SELECT pass_kind,decision_json FROM challenge_judgment WHERE transition_id=? AND authority=?",
                (row["transition_id"], authority),
            ).fetchall()
            decisions = {item["pass_kind"]: json.loads(item["decision_json"]) for item in values}
            if decisions_agree(decisions["first"], decisions["verification"]):
                continue
            judge_input = _inputs(connection, memory, [row])[0]
            judge_input["candidate_decisions"] = [decisions["first"], decisions["verification"]]
            rows.append(row)
            inputs.append(judge_input)
        completed = 0
        for offset in range(0, len(rows), batch_size * max(1, workers)):
            batch_rows = rows[offset:offset + batch_size * max(1, workers)]
            batch_inputs = inputs[offset:offset + batch_size * max(1, workers)]
            packets = _packets(batch_rows, batch_inputs, batch_size=batch_size)
            with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
                judged = list(executor.map(
                    lambda packet: _judge_validated(
                        authority, packet[0], packet[1], model=model,
                        timeout_seconds=timeout_seconds, system=RESOLUTION_SYSTEM,
                    ), packets,
                ))
            decisions = [decision for packet, _receipt in judged for decision in packet]
            receipts = [
                receipt for (packet_rows, _packet_inputs), (_decisions, receipt)
                in zip(packets, judged) for _ in packet_rows
            ]
            with connection:
                for row, judge_input, decision, receipt in zip(
                    batch_rows, batch_inputs, decisions, receipts,
                ):
                    connection.execute(
                        "INSERT INTO challenge_judgment VALUES (?,?,?,?,?,?,?,?)",
                        (row["transition_id"], authority, "adjudication",
                         canonical_json(decision), _sha(judge_input),
                         canonical_json(receipt), _sha(decision), _now()),
                    )
            completed += len(batch_rows)
        return {"completed": completed}
    finally:
        memory.close()
        connection.close()


def _post_state_digest(state: list[dict[str, Any]], decision: dict[str, Any], content: str) -> str:
    after = [dict(row) for row in state]
    operation = decision["operation"]
    target = decision["target_memory_id"]
    if operation == "STORE_NEW":
        after.append({
            "id": "expected:" + _sha(content)[7:31], "content": content,
            "status": "active", "generation": 0,
            "memory_class": decision["memory_class"],
        })
    elif operation in {"UPDATE_EXISTING", "SUPERSEDE_EXISTING"}:
        after = [row for row in after if row["id"] != target]
        after.append({
            "id": "expected:" + _sha([target, content])[7:31],
            "content": content, "status": "active", "generation": 0,
            "memory_class": decision["memory_class"],
        })
    elif operation == "FORGET_EXISTING":
        after = [row for row in after if row["id"] != target]
    return _sha(sorted(after, key=lambda row: row["id"]))


def finalize(work_db: Path, atmem_db: Path, *, partition: str, authority: str) -> dict[str, int]:
    connection = sqlite3.connect(work_db)
    connection.row_factory = sqlite3.Row
    _migrate(connection)
    memory = Memory(atmem_db, auto_vectors=False, allow_insecure_typed_development=True)
    accepted = rejected = 0
    try:
        rows = connection.execute(
            "SELECT c.* FROM challenge c WHERE c.split_family=? AND c.status IN ('blocked_on_baseline','ready') ORDER BY c.transition_id",
            (partition,),
        ).fetchall()
        for row in rows:
            judgments = connection.execute(
                "SELECT pass_kind,decision_json FROM challenge_judgment WHERE transition_id=? AND authority=? ORDER BY pass_kind",
                (row["transition_id"], authority),
            ).fetchall()
            if len(judgments) < 2:
                continue
            decisions = {
                item["pass_kind"]: json.loads(item["decision_json"])
                for item in judgments
            }
            first, verification = decisions["first"], decisions["verification"]
            agreed = decisions_agree(first, verification)
            if not agreed and "adjudication" not in decisions:
                continue
            expected = first if agreed else decisions["adjudication"]
            valid_label = "judge_output_validation_failed" not in set(
                expected.get("reason_codes") or ()
            )
            state = _state(memory, row["scope_id"])
            before = _sha(state)
            after = _post_state_digest(state, expected, row["content"])
            core = {
                "format": FORMAT, "transition_id": row["transition_id"],
                "partition": partition, "authority": authority,
                "expected": expected, "pre_state_digest": before,
                "expected_post_state_digest": after, "accepted": valid_label,
            }
            digest = _sha(core)
            with connection:
                connection.execute(
                    "INSERT INTO challenge_adjudication VALUES (?,?,?,?,?,?,?,?)",
                    (
                        row["transition_id"], authority, canonical_json(expected),
                        before, after, int(valid_label), digest, _now(),
                    ),
                )
                connection.execute(
                    "UPDATE challenge SET status=? WHERE transition_id=?",
                    ("adjudicated", row["transition_id"]),
                )
            accepted += int(valid_label)
            rejected += int(not valid_label)
    finally:
        memory.close()
        connection.close()
    return {"accepted": accepted, "rejected": rejected}


def pipeline(
    work_db: Path, atmem_db: Path, *, partition: str, authority: str,
    model: str, batch_size: int, row_limit: int | None, timeout_seconds: int,
    workers: int = 1,
) -> dict[str, int]:
    first_total = verification_total = accepted = rejected = 0
    while row_limit is None or first_total < row_limit:
        capacity = batch_size * max(1, workers)
        take = capacity if row_limit is None else min(capacity, row_limit - first_total)
        pending = run_pass(
            work_db, atmem_db, partition=partition, authority=authority,
            pass_kind="verification", model=model, batch_size=batch_size,
            row_limit=take, timeout_seconds=timeout_seconds, workers=workers,
        )
        if pending["completed"]:
            resolve_disagreements(
                work_db, atmem_db, partition=partition, authority=authority,
                model=model, batch_size=batch_size,
                timeout_seconds=timeout_seconds, workers=workers,
            )
            result = finalize(
                work_db, atmem_db, partition=partition, authority=authority,
            )
            verification_total += pending["completed"]
            accepted += result["accepted"]
            rejected += result["rejected"]
            print(json.dumps({
                "event": "challenge_packet_resumed", "partition": partition,
                "authority": authority, "first": first_total,
                "verification": verification_total, "accepted": accepted,
                "rejected": rejected,
            }, sort_keys=True), flush=True)
            continue
        first = run_pass(
            work_db, atmem_db, partition=partition, authority=authority,
            pass_kind="first", model=model, batch_size=batch_size, row_limit=take,
            timeout_seconds=timeout_seconds, workers=workers,
        )
        if not first["completed"]:
            break
        verification = run_pass(
            work_db, atmem_db, partition=partition, authority=authority,
            pass_kind="verification", model=model, batch_size=batch_size,
            row_limit=first["completed"], timeout_seconds=timeout_seconds,
            workers=workers,
        )
        if verification["completed"] != first["completed"]:
            raise RuntimeError("verification did not cover the complete packet")
        resolve_disagreements(
            work_db, atmem_db, partition=partition, authority=authority,
            model=model, batch_size=batch_size,
            timeout_seconds=timeout_seconds, workers=workers,
        )
        result = finalize(
            work_db, atmem_db, partition=partition, authority=authority,
        )
        first_total += first["completed"]
        verification_total += verification["completed"]
        accepted += result["accepted"]
        rejected += result["rejected"]
        print(json.dumps({
            "event": "challenge_packet_completed", "partition": partition,
            "authority": authority, "first": first_total,
            "verification": verification_total, "accepted": accepted,
            "rejected": rejected,
        }, sort_keys=True), flush=True)
    return {
        "first": first_total, "verification": verification_total,
        "accepted": accepted, "rejected": rejected,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-db", type=Path, required=True)
    parser.add_argument("--atmem-db", type=Path, required=True)
    parser.add_argument("--partition", required=True)
    parser.add_argument("--authority", choices=("codex", "claude"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--row-limit", type=int)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--retry-invalid", action="store_true",
        help="Archive and retry only finalized technical validation failures",
    )
    args = parser.parse_args()
    if args.retry_invalid:
        archived = archive_and_reset_invalid(
            args.work_db, partition=args.partition, authority=args.authority,
        )
        print(json.dumps({"event": "invalid_attempts_archived", **archived}, sort_keys=True))
    result = pipeline(
        args.work_db, args.atmem_db, partition=args.partition,
        authority=args.authority, model=args.model, batch_size=args.batch_size,
        row_limit=args.row_limit, timeout_seconds=args.timeout_seconds,
        workers=args.workers,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
