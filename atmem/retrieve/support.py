"""Deterministic supporting-evidence aggregation over authorized candidates."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
import math
from typing import Any, Iterable, Mapping


SUPPORT_AGGREGATION_VERSION = "supporting-evidence-v1"
SUPPORT_BONUS_WEIGHT = 0.15
SUPPORT_PEER_LIMIT = 2


def aggregate_supporting_evidence(
    candidates: Iterable[Mapping[str, Any]],
    *,
    subject_id: str,
    workspace_id: str,
    agent_id: str,
) -> list[dict[str, Any]]:
    """Return aggregate-ranked candidates without raw session identifiers.

    Callers must pass only candidates that already cleared canonical authority,
    lifecycle, exclusion, and egress checks. ``source_session_id`` is consumed
    solely to construct an opaque, scope-bound group identity and is removed
    from every returned row.
    """
    prepared: list[dict[str, Any]] = []
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[str] = set()
    for original_rank, value in enumerate(candidates, start=1):
        record_id = str(value.get("record_id") or value.get("id") or "").strip()
        if not record_id:
            raise ValueError("supporting-evidence candidate requires record_id")
        if record_id in seen:
            raise ValueError("supporting-evidence candidates must be record-ID unique")
        seen.add(record_id)
        record_score = _bounded_score(value.get("score", 0.0))
        session_id = str(value.get("source_session_id") or "").strip()
        group_material = (
            f"session:{session_id}" if session_id else f"record:{record_id}"
        )
        group_id = _group_id(
            subject_id=subject_id,
            workspace_id=workspace_id,
            agent_id=agent_id,
            material=group_material,
        )
        row = {
            key: item
            for key, item in dict(value).items()
            if key != "source_session_id"
        }
        row.update(
            {
                "record_id": record_id,
                "_original_rank": original_rank,
                "_record_score": record_score,
                "_group_id": group_id,
            }
        )
        prepared.append(row)
        groups[group_id].append(row)

    result: list[dict[str, Any]] = []
    for row in prepared:
        all_peers = sorted(
            (
                float(peer["_record_score"])
                for peer in groups[str(row["_group_id"])]
                if peer["record_id"] != row["record_id"]
            ),
            reverse=True,
        )
        peers = all_peers[:SUPPORT_PEER_LIMIT]
        support_score = sum(peers) / len(peers) if peers else 0.0
        record_score = float(row["_record_score"])
        aggregate_score = (
            record_score
            if not peers
            else record_score
            + SUPPORT_BONUS_WEIGHT * support_score * (1.0 - record_score)
        )
        signals = dict(row.get("signals") or {})
        signals.update(
            {
                "support_aggregation_version": SUPPORT_AGGREGATION_VERSION,
                "record_score": _rounded(record_score),
                "support_score": _rounded(support_score),
                "aggregate_score": _rounded(min(1.0, aggregate_score)),
                "eligible_support_count": len(all_peers),
                "support_group_id": str(row["_group_id"]),
            }
        )
        clean = {
            key: item
            for key, item in row.items()
            if key not in {"_original_rank", "_record_score", "_group_id"}
        }
        clean["score"] = signals["aggregate_score"]
        clean["signals"] = signals
        clean["original_rank"] = int(row["_original_rank"])
        result.append(clean)

    result.sort(
        key=lambda row: (
            -float(row["score"]),
            int(row["original_rank"]),
            str(row["record_id"]),
        )
    )
    return result


def aggregation_signal_digest(candidates: Iterable[Mapping[str, Any]]) -> str:
    """Digest bounded aggregation signals without candidate content."""
    values = [
        {
            "record_id": str(row.get("record_id") or row.get("id") or ""),
            "signals": {
                key: (row.get("signals") or {}).get(key)
                for key in (
                    "support_aggregation_version",
                    "record_score",
                    "support_score",
                    "aggregate_score",
                    "eligible_support_count",
                    "support_group_id",
                )
            },
        }
        for row in candidates
    ]
    body = json.dumps(values, sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(body.encode('utf-8')).hexdigest()}"


def _bounded_score(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("supporting-evidence score must be a finite number")
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("supporting-evidence score must be a finite number") from exc
    if not math.isfinite(score):
        raise ValueError("supporting-evidence score must be a finite number")
    return min(1.0, max(0.0, score))


def _group_id(
    *, subject_id: str, workspace_id: str, agent_id: str, material: str
) -> str:
    body = json.dumps(
        {
            "version": SUPPORT_AGGREGATION_VERSION,
            "subject_id": str(subject_id),
            "workspace_id": str(workspace_id),
            "agent_id": str(agent_id),
            "material": material,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sgrp_{sha256(body.encode('utf-8')).hexdigest()}"


def _rounded(value: float) -> float:
    return round(float(value), 6)
