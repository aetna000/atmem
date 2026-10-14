"""Restart-safe database worker for authenticated Codex/Claude CLI labeling."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid
from typing import Any, Callable

from . import label_dataset
from .workdb import initialize, transaction


TARGET_SHARES = {
    "english": 0.50,
    "chinese": 0.20,
    "arabic": 0.05,
    "french": 0.05,
    "german": 0.05,
    "spanish": 0.05,
    "indonesian": 0.01,
    "japanese": 0.01,
    "korean": 0.01,
    "portuguese": 0.01,
    "russian": 0.01,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _candidate_rows(
    connection: sqlite3.Connection, candidate_ids: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    where = ""
    parameters: list[str] = []
    if candidate_ids is not None:
        if not candidate_ids:
            return {}
        where = "AND c.candidate_id IN (" + ",".join("?" for _ in candidate_ids) + ")"
        parameters = candidate_ids
    rows = connection.execute(
        f"""
        SELECT c.candidate_id, c.authorized_input_json, c.language,
               c.risk_tags_json, dm.cluster_id
        FROM candidate c
        JOIN duplicate_member dm ON dm.candidate_id = c.candidate_id
        WHERE c.eligibility = 'eligible'
        {where}
        ORDER BY dm.cluster_id, c.candidate_id
        """,
        parameters,
    )
    return {
        row[0]: {
            "candidate_id": row[0],
            "authorized_input": json.loads(row[1]),
            "language": row[2],
            "risk_tags": json.loads(row[3]),
            "cluster_id": row[4],
        }
        for row in rows
    }


def _language_quotas(connection: sqlite3.Connection, target_rows: int) -> dict[str, int]:
    available = dict(connection.execute(
        "SELECT language, COUNT(*) FROM candidate WHERE eligibility='eligible' GROUP BY language"
    ).fetchall())
    quotas = {language: round(target_rows * share) for language, share in TARGET_SHARES.items()}
    remainder_target = target_rows - sum(quotas.values())
    total_other = sum(
        count for language, count in available.items() if language not in TARGET_SHARES
    )
    if total_other < remainder_target:
        raise ValueError("not enough remaining-language candidates for requested distribution")
    # The frozen requirement fixes the remaining languages collectively at 5%,
    # not an impossible fractional quota for every low-resource language.
    quotas["__other__"] = remainder_target
    missing = {language: quota - available.get(language, 0) for language, quota in quotas.items()
               if language != "__other__" and available.get(language, 0) < quota}
    if missing:
        raise ValueError(f"language targets exceed available candidates: {missing}")
    if sum(quotas.values()) != target_rows:
        raise AssertionError("language quota rounding did not preserve target size")
    return quotas


def select_cluster_preserving_candidates(
    connection: sqlite3.Connection, target_rows: int | None,
    *, max_component_rows: int | None = None,
    max_component_tokens: int | None = None,
) -> tuple[list[tuple[str, list[tuple[str, int, str]]]], dict[str, int]]:
    """Choose exact language quotas without splitting any duplicate component."""

    clusters: dict[str, list[tuple[str, int, str]]] = {}
    canonicals: dict[str, str] = {}
    conversations: dict[str, set[str]] = {}
    candidate_priority: dict[str, tuple[int, int, int]] = {}
    for row in connection.execute(
        """
        SELECT dm.cluster_id, c.candidate_id, length(c.authorized_input_json), c.language,
               dc.canonical_candidate_id, c.source_split_key, co.source_id,
               c.risk_tags_json
        FROM candidate c JOIN duplicate_member dm ON dm.candidate_id=c.candidate_id
        JOIN duplicate_cluster dc ON dc.cluster_id=dm.cluster_id
        JOIN conversation co ON co.conversation_id=c.conversation_id
        WHERE c.eligibility='eligible' ORDER BY dm.cluster_id, c.candidate_id
        """
    ):
        clusters.setdefault(row[0], []).append((row[1], max(1, int(row[2] / 3.2)), row[3]))
        canonicals[row[0]] = row[4]
        conversations.setdefault(row[5], set()).add(row[0])
        tags = json.loads(row[7])
        candidate_priority[row[1]] = (
            0 if row[6] == "lufy" else 1,
            0 if "selection:memory_intent" in tags else
            1 if "has_prior_user_turn" in tags else 2,
            max(1, int(row[2] / 3.2)),
        )
    parent = {cluster_id: cluster_id for cluster_id in clusters}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        left, right = find(left), find(right)
        if left != right:
            if right < left:
                left, right = right, left
            parent[right] = left

    for cluster_ids in conversations.values():
        ordered_ids = sorted(cluster_ids)
        for cluster_id in ordered_ids[1:]:
            union(ordered_ids[0], cluster_id)
    component_clusters: dict[str, list[str]] = {}
    for cluster_id in clusters:
        component_clusters.setdefault(find(cluster_id), []).append(cluster_id)
    components = {
        "+".join(sorted(cluster_ids)): [
            member for cluster_id in sorted(cluster_ids) for member in clusters[cluster_id]
        ]
        for cluster_ids in component_clusters.values()
    }
    component_canonicals = {
        "+".join(sorted(cluster_ids)): [canonicals[cluster_id] for cluster_id in cluster_ids]
        for cluster_ids in component_clusters.values()
    }
    if target_rows is None:
        selected = sorted(components.items())
        counts: dict[str, int] = {}
        for component_id, members in components.items():
            for canonical in component_canonicals[component_id]:
                language = next(language for candidate_id, _tokens, language in members
                                if candidate_id == canonical)
                counts[language] = counts.get(language, 0) + 1
        return selected, counts
    quotas = _language_quotas(connection, target_rows)
    counts = {language: 0 for language in quotas}
    actual_counts: dict[str, int] = {}

    def quota_bucket(language: str) -> str:
        return language if language in TARGET_SHARES else "__other__"
    selected: list[tuple[str, list[tuple[str, int, str]]]] = []
    # Retain duplicate evidence first, but count only the canonical representative
    # toward the public corpus; cross-scope replicas remain review context.
    def component_order(item: tuple[str, list[tuple[str, int, str]]]) -> tuple[Any, ...]:
        component_id, members = item
        canonical_languages = [
            next(language for candidate_id, _tokens, language in members
                 if candidate_id == canonical)
            for canonical in component_canonicals[component_id]
        ]
        # Allocate scarce "all remaining" languages first. Otherwise a mixed
        # conversation component can become impossible to add after a dominant
        # language has already reached its quota.
        scarcity = min(quotas[quota_bucket(language)] for language in canonical_languages)
        canonical_priority = min(
            candidate_priority[candidate_id]
            for candidate_id in component_canonicals[component_id]
        )
        return (scarcity, *canonical_priority[:2], len(members), canonical_priority[2], component_id)

    ordered = sorted(components.items(), key=component_order)
    for component_id, members in ordered:
        if max_component_rows is not None and len(members) > max_component_rows:
            continue
        if (max_component_tokens is not None
                and sum(item[1] for item in members) > max_component_tokens):
            continue
        additions: dict[str, int] = {}
        actual_additions: dict[str, int] = {}
        for canonical in component_canonicals[component_id]:
            language = next(language for candidate_id, _tokens, language in members
                            if candidate_id == canonical)
            bucket = quota_bucket(language)
            additions[bucket] = additions.get(bucket, 0) + 1
            actual_additions[language] = actual_additions.get(language, 0) + 1
        if all(counts.get(language, 0) + amount <= quotas.get(language, 0)
               for language, amount in additions.items()):
            selected.append((component_id, members))
            for language, amount in additions.items():
                counts[language] += amount
            for language, amount in actual_additions.items():
                actual_counts[language] = actual_counts.get(language, 0) + amount
        if sum(counts.values()) == target_rows:
            break
    if counts != quotas:
        deficits = {language: quotas[language] - counts.get(language, 0)
                    for language in quotas if counts.get(language, 0) != quotas[language]}
        raise RuntimeError(f"cluster-preserving selection could not meet exact quotas: {deficits}")
    return sorted(selected), actual_counts


def build_first_pass_queue(
    database: Path,
    judge: str,
    *,
    target_tokens: int = 24_000,
    max_rows: int = 80,
    row_limit: int | None = None,
) -> dict[str, Any]:
    if judge not in {"codex", "claude"}:
        raise ValueError("unknown judge")
    if target_tokens < 1_000 or max_rows < 1:
        raise ValueError("unsafe packet limits")
    connection = initialize(database)
    try:
        selected_clusters, language_counts = select_cluster_preserving_candidates(
            connection, row_limit, max_component_rows=max_rows,
            max_component_tokens=target_tokens,
        )
        packets: list[tuple[str, list[str], int]] = []
        current_ids: list[str] = []
        current_clusters: list[str] = []
        current_tokens = 0
        selected = 0
        for cluster_id, members in selected_clusters:
            member_tokens = sum(item[1] for item in members)
            if current_ids and (
                current_tokens + member_tokens > target_tokens
                or len(current_ids) + len(members) > max_rows
            ):
                packets.append(("+".join(current_clusters), current_ids, current_tokens))
                current_ids, current_clusters, current_tokens = [], [], 0
            current_clusters.append(cluster_id)
            current_ids.extend(item[0] for item in members)
            current_tokens += member_tokens
            selected += len(members)
        if current_ids:
            packets.append(("+".join(current_clusters), current_ids, current_tokens))
        with transaction(connection):
            for cluster_key, candidate_ids, token_estimate in packets:
                connection.execute(
                    """INSERT OR IGNORE INTO work_queue(
                        judge, pass_kind, cluster_key, candidate_ids_json,
                        token_estimate, state, attempts
                    ) VALUES (?, 'first_pass', ?, ?, ?, 'pending', 0)""",
                    (judge, cluster_key, _canonical(candidate_ids), token_estimate),
                )
        return {
            "packets": len(packets),
            "judge_candidates": selected,
            "public_canonical_candidates": sum(language_counts.values()),
            "languages": language_counts,
        }
    finally:
        connection.close()


def _ensure_run(connection: sqlite3.Connection, judge: str, model: str, cli_version: str) -> str:
    existing = connection.execute(
        "SELECT run_id FROM judge_run WHERE judge=? AND pass_kind='first_pass' AND pass_number=1",
        (judge,),
    ).fetchone()
    if existing:
        return existing[0]
    run_id = f"{judge}-first-pass-{uuid.uuid4().hex[:16]}"
    connection.execute(
        "INSERT INTO judge_run VALUES (?, ?, ?, ?, ?, ?, 'first_pass', 1, 'running', ?, NULL, NULL)",
        (
            run_id, judge, cli_version, model,
            _digest(label_dataset.SYSTEM), _digest(label_dataset.BATCH_SCHEMA), _now(),
        ),
    )
    return run_id


def _lease(connection: sqlite3.Connection, judge: str, owner: str) -> sqlite3.Row | None:
    now = _now()
    expired = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    row = connection.execute(
        """
        SELECT * FROM work_queue
        WHERE judge=? AND pass_kind='first_pass'
          AND attempts < 3
          AND (state='pending' OR state='failed' OR (state='leased' AND lease_expires_at < ?))
        ORDER BY work_id LIMIT 1
        """,
        (judge, now),
    ).fetchone()
    if row is None:
        return None
    connection.execute(
        """UPDATE work_queue SET state='leased', lease_owner=?, lease_expires_at=?,
                                  attempts=attempts+1, last_error=NULL WHERE work_id=?""",
        (owner, (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"), row["work_id"]),
    )
    return connection.execute("SELECT * FROM work_queue WHERE work_id=?", (row["work_id"],)).fetchone()


def split_exhausted_packets(database: Path, judge: str) -> dict[str, int]:
    """Archive a refused packet receipt and retry its intact components separately."""

    connection = initialize(database)
    split_packets = replacement_packets = unsplittable_packets = 0
    try:
        with transaction(connection):
            run = connection.execute(
                "SELECT run_id FROM judge_run WHERE judge=? AND pass_kind='first_pass' AND pass_number=1",
                (judge,),
            ).fetchone()
            if run is None:
                return {"split_packets": 0, "replacement_packets": 0, "unsplittable_packets": 0}
            failed = connection.execute(
                """SELECT * FROM work_queue WHERE judge=? AND pass_kind='first_pass'
                   AND state='failed' AND attempts>=3 ORDER BY work_id""",
                (judge,),
            ).fetchall()
            for work in failed:
                candidate_ids = json.loads(work["candidate_ids_json"])
                placeholders = ",".join("?" for _ in candidate_ids)
                rows = connection.execute(
                    f"""SELECT c.candidate_id, dm.cluster_id, c.source_split_key,
                                max(1, CAST(length(c.authorized_input_json)/3.2 AS INTEGER))
                         FROM candidate c JOIN duplicate_member dm USING(candidate_id)
                         WHERE c.candidate_id IN ({placeholders})""",
                    candidate_ids,
                ).fetchall()
                parent = {row[1]: row[1] for row in rows}

                def find(value: str) -> str:
                    while parent[value] != value:
                        parent[value] = parent[parent[value]]
                        value = parent[value]
                    return value

                by_conversation: dict[str, list[str]] = {}
                for _candidate_id, cluster_id, conversation, _tokens in rows:
                    by_conversation.setdefault(conversation, []).append(cluster_id)
                for cluster_ids in by_conversation.values():
                    first = find(cluster_ids[0])
                    for cluster_id in cluster_ids[1:]:
                        other = find(cluster_id)
                        if first != other:
                            parent[other] = first
                groups: dict[str, list[tuple[str, int]]] = {}
                for candidate_id, cluster_id, _conversation, tokens in rows:
                    groups.setdefault(find(cluster_id), []).append((candidate_id, tokens))
                if len(groups) <= 1:
                    unsplittable_packets += 1
                    continue
                failure = {
                    "work_id": work["work_id"], "attempts": work["attempts"],
                    "candidate_ids": candidate_ids, "error": work["last_error"],
                    "recovery": "split_intact_components",
                }
                receipt_id = f"query-{uuid.uuid4().hex}"
                connection.execute(
                    "INSERT INTO query_receipt VALUES (?, ?, NULL, 'cli_failure', ?, ?, ?, ?)",
                    (receipt_id, run[0], _canonical(failure), _canonical(candidate_ids),
                     _digest(failure), _now()),
                )
                connection.execute("DELETE FROM work_queue WHERE work_id=?", (work["work_id"],))
                for index, members in enumerate(sorted(groups.values())):
                    ids = sorted(item[0] for item in members)
                    token_estimate = sum(item[1] for item in members)
                    key = f"recovery:{work['work_id']}:{index}:{_digest(ids)[7:23]}"
                    connection.execute(
                        """INSERT INTO work_queue(
                            judge, pass_kind, cluster_key, candidate_ids_json,
                            token_estimate, state, attempts
                        ) VALUES (?, 'first_pass', ?, ?, ?, 'pending', 0)""",
                        (judge, key, _canonical(ids), token_estimate),
                    )
                    replacement_packets += 1
                split_packets += 1
        return {
            "split_packets": split_packets,
            "replacement_packets": replacement_packets,
            "unsplittable_packets": unsplittable_packets,
        }
    finally:
        connection.close()


def run_worker(
    database: Path,
    judge: str,
    model: str,
    *,
    max_packets: int | None = None,
    timeout_seconds: int = 1_800,
    labeler: Callable[..., tuple[dict[str, dict[str, Any]], dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    cli_version = "codex-cli-0.162.1" if judge == "codex" else "claude-code-2.1.281"
    if labeler is None:
        labeler = label_dataset._codex_labels if judge == "codex" else label_dataset._claude_labels
    connection = initialize(database)
    owner = f"{judge}-{uuid.uuid4().hex[:12]}"
    completed = failed = labeled = 0
    try:
        with transaction(connection):
            run_id = _ensure_run(connection, judge, model, cli_version)
        while max_packets is None or completed + failed < max_packets:
            with transaction(connection):
                work = _lease(connection, judge, owner)
            if work is None:
                break
            candidate_ids = json.loads(work["candidate_ids_json"])
            candidates = _candidate_rows(connection, candidate_ids)
            batch = [candidates[candidate_id] for candidate_id in candidate_ids]
            started = time.monotonic()
            try:
                labels, receipt = labeler(batch, model=model, timeout_seconds=timeout_seconds)
                receipt_id = f"query-{uuid.uuid4().hex}"
                query_core = {
                    "work_id": work["work_id"], "candidate_ids": candidate_ids,
                    "cluster_key": work["cluster_key"], "token_estimate": work["token_estimate"],
                }
                with transaction(connection):
                    connection.execute(
                        "INSERT INTO query_receipt VALUES (?, ?, NULL, 'work_packet', ?, ?, ?, ?)",
                        (receipt_id, run_id, _canonical(query_core), _canonical(candidate_ids),
                         _digest(query_core), _now()),
                    )
                    for candidate_id in candidate_ids:
                        decision = labels[candidate_id]
                        decision_digest = _digest(decision)
                        connection.execute(
                            """INSERT INTO judgment(
                                candidate_id, run_id, judge, pass_kind, pass_number,
                                prior_judgment_id, disposition, memory_class, decision_json,
                                decision_digest, change_reason, query_receipt_ids_json,
                                output_digest, confidence, validation_state, created_at
                            ) VALUES (?, ?, ?, 'first_pass', 1, NULL, ?, ?, ?, ?, NULL, ?, ?, ?, 'valid', ?)""",
                            (
                                candidate_id, run_id, judge, decision["disposition"],
                                decision["memory_class"], _canonical(decision), decision_digest,
                                _canonical([receipt_id]), receipt["output_sha256"],
                                float(decision["confidence"]), _now(),
                            ),
                        )
                    connection.execute(
                        "UPDATE work_queue SET state='complete', lease_owner=NULL, lease_expires_at=NULL WHERE work_id=?",
                        (work["work_id"],),
                    )
                completed += 1
                labeled += len(candidate_ids)
            except Exception as exc:
                with transaction(connection):
                    connection.execute(
                        """UPDATE work_queue SET state='failed', lease_owner=NULL,
                           lease_expires_at=NULL, last_error=? WHERE work_id=?""",
                        (str(exc)[-1000:], work["work_id"]),
                    )
                failed += 1
                if failed >= 3 and completed == 0:
                    raise
            finally:
                _ = time.monotonic() - started
        remaining = connection.execute(
            "SELECT COUNT(*) FROM work_queue WHERE judge=? AND pass_kind='first_pass' AND state!='complete'",
            (judge,),
        ).fetchone()[0]
        if remaining == 0:
            with transaction(connection):
                connection.execute(
                    """UPDATE judge_run SET status='complete', completed_at=?, run_digest=?
                       WHERE run_id=? AND status='running'""",
                    (_now(), _digest({"labeled_rows": connection.execute(
                        "SELECT COUNT(*) FROM judgment WHERE run_id=?", (run_id,)
                    ).fetchone()[0]}), run_id),
                )
        return {"judge": judge, "completed_packets": completed, "failed_packets": failed,
                "labeled_rows": labeled, "remaining_packets": remaining}
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--judge", choices=("codex", "claude"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--build-queue", action="store_true")
    parser.add_argument("--target-tokens", type=int, default=24_000)
    parser.add_argument("--max-rows", type=int, default=80)
    parser.add_argument("--row-limit", type=int)
    parser.add_argument("--max-packets", type=int)
    parser.add_argument("--timeout-seconds", type=int, default=1_800)
    args = parser.parse_args()
    if args.build_queue:
        print(json.dumps(build_first_pass_queue(
            args.database, args.judge, target_tokens=args.target_tokens,
            max_rows=args.max_rows, row_limit=args.row_limit,
        ), indent=2))
    print(json.dumps(run_worker(
        args.database, args.judge, args.model,
        max_packets=args.max_packets, timeout_seconds=args.timeout_seconds,
    ), indent=2))


if __name__ == "__main__":
    main()
