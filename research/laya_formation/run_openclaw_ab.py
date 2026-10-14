"""Replay one frozen OpenClaw corpus through deterministic and Laya formation.

The output is an operational product record.  It is deliberately labelled as
such and must not be presented as an independent or held-out benchmark.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import sqlite3
import sys
from time import perf_counter
from typing import Any

from atmem import Memory
from atmem.contracts import AuthorityScope, EpisodeIngestRequest, EpisodePart
from atmem.core.canonical import sha256_hex
from atmem.laya_formation.artifacts import LayaArtifactResolver
from atmem.laya_formation.integration import FormationProfileRouter

from research.laya_formation.openclaw_corpus import EXPECTED_COUNTS, validate_corpus


class InactiveProfile:
    def active_profile(self) -> None:
        return None


class FixedProfile:
    def __init__(self, model_dir: Path, device: str) -> None:
        self.model_dir = model_dir
        self.device = device

    def active_profile(self) -> dict[str, Any]:
        return {
            "profile": "laya-formation-v1",
            "model_dir": str(self.model_dir),
            "device": self.device,
            "active": True,
            "verified": True,
            "escalation": {"enabled": False},
        }


class DiagnosticThresholdResolver:
    """In-memory calibration override for diagnosis; never a release artifact."""

    def __init__(self, threshold: float) -> None:
        self.base = LayaArtifactResolver()
        self.threshold = float(threshold)

    def verify(self, root: Path):
        bundle = self.base.verify(root)
        payload = {
            "parent": bundle.calibration.calibration_digest,
            "thresholds": {"choice:3-5": self.threshold},
            "purpose": "diagnostic-only-openclaw-ab",
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        calibration = replace(
            bundle.calibration,
            calibration_digest=digest,
            thresholds={"choice:3-5": self.threshold},
        )
        return replace(
            bundle, calibration=calibration, calibration_digest=digest,
        )


def _request(row: dict[str, str], scope: AuthorityScope) -> EpisodeIngestRequest:
    text = row["text"]
    return EpisodeIngestRequest(
        episode_id=row["id"],
        idempotency_key=f"openclaw-ab-{row['id']}",
        scope=scope,
        parts=(EpisodePart(
            part_id=f"{row['id']}-part",
            ordinal=0,
            kind="text",
            source_type="user_message",
            content=text,
            content_sha256="sha256:" + sha256_hex(text),
        ),),
        binding_method="host_asserted",
        binding_assurance="host_asserted",
        session_id=row["id"],
        turn_id=f"turn-{row['id']}",
        source_observation_granularity="sentence",
    )


def _pieces(memory: Memory, generation_id: str, episode_id: str) -> list[dict[str, Any]]:
    rows = memory.store._conn.execute(
        """SELECT e.source_id, r.range_id, r.part_id, r.start_offset, r.end_offset,
                  p.content_bytes, u.unit_id, u.kind AS deterministic_kind,
                  u.lifecycle, u.compact_json,
                  GROUP_CONCAT(v.kind, ',') AS active_views
             FROM context_source_episodes e
             JOIN context_source_ranges r USING(source_id)
             JOIN context_source_parts p
               ON p.source_id=r.source_id AND p.part_id=r.part_id
             JOIN context_unit_ranges ur USING(range_id)
             JOIN context_evidence_units u
               ON u.generation_id=ur.generation_id AND u.unit_id=ur.unit_id
             LEFT JOIN context_unit_views v
               ON v.generation_id=u.generation_id AND v.unit_id=u.unit_id
            WHERE e.legacy_episode_id=? AND u.generation_id=?
            GROUP BY e.source_id, r.range_id, r.part_id, r.start_offset, r.end_offset,
                     p.content_bytes, u.unit_id, u.kind, u.lifecycle, u.compact_json
            ORDER BY r.start_offset, u.unit_id""",
        (episode_id, generation_id),
    ).fetchall()
    pieces: list[dict[str, Any]] = []
    for row in rows:
        body = bytes(row["content_bytes"])
        start, end = int(row["start_offset"]), int(row["end_offset"])
        pieces.append({
            "source_id": str(row["source_id"]),
            "range_id": str(row["range_id"]),
            "part_id": str(row["part_id"]),
            "start": start,
            "end": end,
            "exact_text": body[start:end].decode("utf-8", errors="replace"),
            "unit_id": str(row["unit_id"]),
            "deterministic_kind": str(row["deterministic_kind"]),
            "active_views": sorted(str(row["active_views"] or "").split(",")),
            "lifecycle": str(row["lifecycle"]),
            "compact": json.loads(str(row["compact_json"])),
        })
    return pieces


def _decision_map(intelligence: dict[str, Any]) -> dict[str, str | None]:
    return {
        str(row["question_id"]): (
            str(row["selected_choice_ids"][0])
            if row.get("selected_choice_ids") else None
        )
        for row in intelligence.get("decisions") or ()
    }


def _safe_outcome(row: dict[str, str], result: dict[str, Any], pieces: list[dict[str, Any]]) -> dict[str, Any]:
    intelligence = dict(result.get("formation_intelligence") or {})
    if intelligence.get("format") == "atmem-live-formation-transition-v2":
        ruling = dict(intelligence.get("ruling") or {})
        operation = str(ruling.get("operation") or "REVIEW")
        observed = {
            "STORE_NEW": "STORE",
            "UPDATE_EXISTING": "UPDATE",
            "SUPERSEDE_EXISTING": "UPDATE",
            "DUPLICATE": "DUPLICATE",
            "DO_NOT_STORE": "DO_NOT_STORE",
            "FORGET_EXISTING": "DO_NOT_STORE",
            "REVIEW": "REVIEW",
        }.get(operation, "REVIEW")
        if intelligence.get("authority_result") != "AUTHORIZED_PROPOSAL":
            observed = "REVIEW"
        expected = row["expected_disposition"]
        exact_match = observed == expected
        views = {
            view for piece in pieces for view in piece["active_views"] if view
        }
        semantic = sorted(views - {"raw_state"})
        safe = exact_match
        if expected in {"DO_NOT_STORE", "REVIEW", "DUPLICATE", "UPDATE"}:
            safe = observed in {expected, "REVIEW"} and not semantic
        return {
            "observed_disposition": observed,
            "exact_policy_match": exact_match,
            "safe_non_authoritative": safe,
            "semantic_views": semantic,
            "all_views": sorted(views),
            "authority_status": intelligence.get("authority_result"),
            "authority_reason": intelligence.get("reason_code"),
            "decisions": {"operation": operation},
        }
    decisions = _decision_map(intelligence)
    authority = dict(intelligence.get("authority_disposition") or {})
    views = {view for piece in pieces for view in piece["active_views"] if view}
    semantic = sorted(views - {"raw_state"})
    expected = row["expected_disposition"]
    status = str(authority.get("status") or "deterministic_only")
    operation = decisions.get("operation")
    memory_class = decisions.get("memory_class")
    useful = decisions.get("retrieval_usefulness")
    if status == "review_required":
        observed = "REVIEW"
    elif operation == "UPDATE":
        observed = "UPDATE"
    elif operation == "NOOP":
        observed = "DUPLICATE"
    elif (
        operation == "REJECT" or memory_class == "non_memory"
        or useful in {"NOT_USEFUL", "INSUFFICIENT_EVIDENCE"}
        or not semantic
    ):
        observed = "DO_NOT_STORE"
    else:
        observed = "STORE"
    exact_match = observed == expected
    safe = exact_match
    if expected in {"DO_NOT_STORE", "REVIEW", "DUPLICATE", "UPDATE"}:
        safe = observed in {expected, "REVIEW"} and not semantic
    return {
        "observed_disposition": observed,
        "exact_policy_match": exact_match,
        "safe_non_authoritative": safe,
        "semantic_views": semantic,
        "all_views": sorted(views),
        "authority_status": status,
        "authority_reason": authority.get("reason_code"),
        "decisions": decisions,
    }


def run_arm(
    *, name: str, rows: list[dict[str, str]], database: Path,
    router: FormationProfileRouter, output_dir: Path,
) -> dict[str, Any]:
    scope = AuthorityScope(
        subject_id=f"openclaw-ab-{name}",
        agent_id="openclaw-main",
        workspace_id="atmem-laya-ab",
    )
    importer = f"openclaw-ab-importer-{name}"
    memory = Memory(
        ":memory:",
        auto_vectors=False,
        allow_insecure_typed_development=True,
        review_authorities=({
            "principal_id": importer,
            "subject_id": scope.subject_id,
            "agent_id": scope.agent_id,
            "workspace_id": scope.workspace_id,
            "scopes": ("history_import:review",),
        },),
        formation_router=router,
    )
    records: list[dict[str, Any]] = []
    arm_started = perf_counter()
    try:
        for index, row in enumerate(rows, 1):
            started = perf_counter()
            result = memory.form_context_episode(
                _request(row, scope), history_import_principal=importer,
            )
            latency_ms = (perf_counter() - started) * 1_000
            generation_id = str(result["generation_id"])
            pieces = _pieces(memory, generation_id, row["id"])
            outcome = _safe_outcome(row, result, pieces)
            records.append({
                "sequence": index,
                "arm": name,
                "input": row,
                "latency_ms": latency_ms,
                "formation": result,
                "memory_pieces": pieces,
                "evaluation": outcome,
            })
            print(
                f"{name} {index:03d}/100 expected={row['expected_disposition']} "
                f"observed={outcome['observed_disposition']} "
                f"views={','.join(outcome['all_views']) or 'none'} "
                f"latency_ms={latency_ms:.1f}",
                flush=True,
            )
        frozen = memory.freeze_context_engine(scope)
        audit_events = memory.store.list_audit_events(scope.subject_id)
        persisted = sqlite3.connect(database)
        try:
            memory.store._conn.backup(persisted)
        finally:
            persisted.close()
    finally:
        memory.close()
    jsonl = output_dir / f"{name}-records.jsonl"
    jsonl.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    observed = Counter(record["evaluation"]["observed_disposition"] for record in records)
    expected_by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        expected_by_class[record["input"]["expected_disposition"]].append(record)
    summary = {
        "arm": name,
        "database": str(database),
        "elapsed_seconds": perf_counter() - arm_started,
        "mean_latency_ms": sum(record["latency_ms"] for record in records) / len(records),
        "observed_counts": dict(sorted(observed.items())),
        "exact_policy_matches": sum(record["evaluation"]["exact_policy_match"] for record in records),
        "safe_non_authoritative": sum(record["evaluation"]["safe_non_authoritative"] for record in records),
        "by_expected": {
            key: {
                "count": len(values),
                "exact_policy_matches": sum(v["evaluation"]["exact_policy_match"] for v in values),
                "safe_non_authoritative": sum(v["evaluation"]["safe_non_authoritative"] for v in values),
                "semantic_view_count": sum(bool(v["evaluation"]["semantic_views"]) for v in values),
            }
            for key, values in sorted(expected_by_class.items())
        },
        "generation": frozen,
        "audit_event_count": len(audit_events),
        "formation_decision_audit_events": sum(
            event["event_type"] == "memory.formation_decision_recorded"
            for event in audit_events
        ),
        "records_sha256": hashlib.sha256(jsonl.read_bytes()).hexdigest(),
    }
    return summary


def _report(summary: dict[str, Any]) -> str:
    arms = {arm["arm"]: arm for arm in summary["arms"]}
    lines = [
        "# OpenClaw 100-memory AtMem/Laya operational A/B",
        "",
        "> This is a maintainer-run operational pilot over a frozen synthetic "
        "policy challenge set produced by the configured OpenClaw agent. It is "
        "not an independent, held-out, or statistically powered benchmark.",
        "",
        f"Corpus SHA-256: `{summary['corpus_sha256']}`  ",
        f"Model revision: `{summary['model_revision']}`  ",
        f"Host: `{summary['platform']}`",
        "",
        "| Measure | Deterministic | Laya active |",
        "|---|---:|---:|",
        f"| Exact policy matches / 100 | {arms['deterministic']['exact_policy_matches']} | {arms['laya']['exact_policy_matches']} |",
        f"| Safe non-authoritative outcomes / 100 | {arms['deterministic']['safe_non_authoritative']} | {arms['laya']['safe_non_authoritative']} |",
        f"| Mean formation latency (ms) | {arms['deterministic']['mean_latency_ms']:.1f} | {arms['laya']['mean_latency_ms']:.1f} |",
        f"| Formation decision audit events | {arms['deterministic']['formation_decision_audit_events']} | {arms['laya']['formation_decision_audit_events']} |",
        "",
        "## Per expected disposition",
        "",
        "| Expected | N | Deterministic exact | Laya exact | Deterministic semantic | Laya semantic |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for expected, count in EXPECTED_COUNTS.items():
        left = arms["deterministic"]["by_expected"][expected]
        right = arms["laya"]["by_expected"][expected]
        lines.append(
            f"| {expected} | {count} | {left['exact_policy_matches']} | "
            f"{right['exact_policy_matches']} | {left['semantic_view_count']} | "
            f"{right['semantic_view_count']} |"
        )
    lines.extend([
        "",
        "## Evidence files",
        "",
        "- `corpus.json`: exact frozen inputs and expected policy dispositions.",
        "- `deterministic-records.jsonl`: every deterministic memory piece and receipt.",
        "- `laya-records.jsonl`: every Laya decision, confidence receipt, final authority disposition, and memory piece.",
        "- `summary.json`: machine-readable aggregate and artifact hashes.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--diagnostic-threshold", type=float)
    args = parser.parse_args()
    rows = validate_corpus(json.loads(args.corpus.read_text(encoding="utf-8")))
    model_dir = args.model_dir.resolve()
    bundle = LayaArtifactResolver().verify(model_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    deterministic = run_arm(
        name="deterministic",
        rows=rows,
        database=args.output_dir / "deterministic.sqlite3",
        router=FormationProfileRouter(profile_manager=InactiveProfile()),
        output_dir=args.output_dir,
    )
    resolver = (
        DiagnosticThresholdResolver(args.diagnostic_threshold)
        if args.diagnostic_threshold is not None else LayaArtifactResolver()
    )
    laya = run_arm(
        name="laya",
        rows=rows,
        database=args.output_dir / "laya.sqlite3",
        router=FormationProfileRouter(
            profile_manager=FixedProfile(model_dir, args.device),
            resolver=resolver,
        ),
        output_dir=args.output_dir,
    )
    canonical_corpus = args.corpus.read_bytes()
    summary = {
        "format": "atmem-openclaw-laya-operational-ab-v1",
        "claim_class": "maintainer_operational_pilot",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "corpus_sha256": hashlib.sha256(canonical_corpus).hexdigest(),
        "model_repo": bundle.repo_id,
        "model_revision": bundle.revision,
        "model_sha256": bundle.model_sha256,
        "device_requested": args.device,
        "diagnostic_threshold_override": args.diagnostic_threshold,
        "arms": [deterministic, laya],
        "limitations": [
            "The corpus was generated by the configured OpenClaw agent and is synthetic.",
            "Expected dispositions are policy expectations, not independently annotated ground truth.",
            "This single ordered replay does not estimate generalization or statistical significance.",
            "Deterministic and Laya arms share code and differ only by the selected formation profile.",
        ],
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "report.md").write_text(_report(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
