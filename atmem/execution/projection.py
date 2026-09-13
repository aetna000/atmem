"""Bounded projections over authenticated execution evidence."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from atmem.execution.status import classify_execution


def execution_projection(
    events: Iterable[Mapping[str, Any]], *, subject_id: str, execution_id: str
) -> dict[str, Any]:
    """Project one execution without guessing missing parent/retry links."""

    selected: list[dict[str, Any]] = []
    all_execution_ids: set[str] = set()
    for raw in events:
        body = dict(raw.get("body") or raw)
        if body.get("subject_id") != subject_id:
            continue
        candidate = str(body.get("execution_id") or body.get("run_id") or "")
        if candidate:
            all_execution_ids.add(candidate)
        if candidate == execution_id:
            selected.append({**dict(raw), "body": body})
    selected.sort(
        key=lambda row: (
            int((row.get("body") or {}).get("producer_sequence") or 0),
            int(row.get("sequence") or 0),
        )
    )
    if not selected:
        raise LookupError("execution not found")
    parents: set[str] = set()
    retries: set[str] = set()
    producers: dict[tuple[str, str], list[int]] = defaultdict(list)
    gaps: list[dict[str, Any]] = []
    for row in selected:
        body = row["body"]
        if body.get("parent_execution_id"):
            parents.add(str(body["parent_execution_id"]))
        if body.get("retry_of_attempt_id"):
            retries.add(str(body["retry_of_attempt_id"]))
        producer = body.get("producer_instance_id")
        epoch = body.get("producer_epoch")
        sequence = body.get("producer_sequence")
        if producer and epoch and isinstance(sequence, int):
            producers[(str(producer), str(epoch))].append(sequence)
    for (producer, epoch), sequences in producers.items():
        ordered = sorted(set(sequences))
        for previous, current in zip(ordered, ordered[1:]):
            if current > previous + 1:
                gaps.append(
                    {
                        "reason": "missing_producer_sequence",
                        "producer_instance_id": producer,
                        "producer_epoch": epoch,
                        "first_sequence": previous + 1,
                        "last_sequence": current - 1,
                    }
                )
    return {
        "format": "atmem-execution-projection-v1",
        "subject_id": subject_id,
        "execution_id": execution_id,
        "events": selected,
        "event_count": len(selected),
        "status": classify_execution(selected),
        "parent_execution_ids": sorted(parents),
        "orphan_parent_ids": sorted(parents - all_execution_ids),
        "retry_of_attempt_ids": sorted(retries),
        "coverage_gaps": gaps,
        "ordering": "producer_sequence_then_ingest_sequence",
        "cross_producer_ordering": "incomparable_without_explicit_dependency",
    }
