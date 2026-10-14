"""Matched Mac replay of deterministic AtMem and a research-only Laya V2 model.

This runner deliberately bypasses production artifact activation.  It exists to
measure a research checkpoint on the same host, corpus, retrieval path, and
AtMem mutation path as the deterministic arm without presenting an
uncalibrated checkpoint as releasable.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import platform
from pathlib import Path
import statistics
import sqlite3
import sys
from time import perf_counter
from typing import Any, Mapping

from atmem.core.canonical import canonical_json, sha256_hex
from atmem import Memory
from atmem.contracts import AuthorityScope
from atmem.laya_formation.formation_v2 import FormationPlanV2, revalidate_ruling
from atmem.laya_formation.integration import FormationProfileRouter
from atmem.laya_formation.runtime import LayaTypedDecisionEngineV2
from research.laya_formation.openclaw_corpus import EXPECTED_COUNTS, validate_corpus
from research.laya_formation.run_openclaw_ab import InactiveProfile, _request


@dataclass(frozen=True)
class _Identity:
    repo_id: str
    revision: str


class ResearchV2Router:
    """V2 semantic router limited to this offline benchmark process."""

    def __init__(
        self, model_dir: Path, device: str, threshold: float, *,
        repo_id: str = "atmem/laya-memory-decision-v2",
        revision: str | None = None,
    ) -> None:
        from laya import Agent

        manifest_path = model_dir / "artifact-manifest.json"
        training_path = model_dir / "training-manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        training = json.loads(training_path.read_text()) if training_path.is_file() else {}
        tokenizer_revision = str(
            (training.get("base_model") or {}).get("revision")
            or revision or "local-unversioned"
        )
        self.identity = _Identity(
            repo_id=repo_id,
            revision=str(revision or manifest.get("digest") or "local-unversioned"),
        )
        self.agent = Agent(str(model_dir), device=device)
        self.engine = LayaTypedDecisionEngineV2(
            self.agent, tokenizer_revision=tokenizer_revision,
        )
        self.plan = FormationPlanV2(choice_confidence_threshold=threshold)

    def uses_v2_semantic_authority(self) -> bool:
        return True

    def decide_protocol_transition_v2(
        self, *, store: Any, scope: Any, source_id: str, text: str,
        retrieved_records: tuple[Mapping[str, Any], ...],
    ) -> dict[str, Any]:
        generation = int(store.record_generation(scope.subject_id))
        memories: list[dict[str, Any]] = []
        target_rows: list[dict[str, Any]] = []
        for rank, original in enumerate(retrieved_records):
            row = dict(original)
            raw = row.get("raw") or {}
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except (TypeError, ValueError):
                    raw = {}
            authority = dict(raw.get("authority_scope") or {})
            if authority and (
                authority.get("subject_id"), authority.get("agent_id"),
                authority.get("workspace_id"),
            ) != (scope.subject_id, scope.agent_id, scope.workspace_id):
                continue
            if str(row.get("status") or "active") != "active":
                continue
            content = str(row.get("content") or "")
            digest = "sha256:" + sha256_hex(content)
            memories.append({
                "id": str(row["id"]), "content": content,
                "lifecycle": "active", "source_digest": digest,
                "content_digest": digest,
                "memory_class": str(raw.get("memory_class") or "unknown"),
                "retrieval_score": float(row.get("retrieval_score", 1.0 / (rank + 1))),
            })
            target_rows.append(row)
        scope_id = "scope_" + sha256_hex(canonical_json(scope.to_dict()))[:32]
        try:
            ruling, question_receipts = self.plan.evaluate(
                self.engine, scope_id=scope_id,
                canonical_generation=generation,
                observation={
                    "id": source_id, "content": text, "speaker_role": "user",
                    "source_digest": "sha256:" + sha256_hex(text),
                },
                retrieved_memories=memories,
            )
            request_id = "research_" + sha256_hex(canonical_json([
                source_id, generation, self.identity.revision,
            ]))[:32]
            receipt = revalidate_ruling(
                ruling, request_id=request_id,
                classifier=f"{self.identity.repo_id}@{self.identity.revision}",
                expected_generation=generation,
                observed_generation=int(store.record_generation(scope.subject_id)),
                allowed_target_ids=[row["id"] for row in memories],
                policy_allowed=True,
            )
            return {
                "format": "atmem-live-formation-transition-v2",
                "active": True, "profile": "laya-research-v2",
                "model_repo": self.identity.repo_id,
                "model_revision": self.identity.revision,
                "authority_result": receipt.authority_result,
                "ruling": ruling.to_dict(), "receipt": receipt.to_dict(),
                "question_receipts": list(question_receipts),
                "authorized_target_records": target_rows,
                "reason_code": receipt.authority_reason,
            }
        except Exception as exc:
            return {
                "format": "atmem-live-formation-transition-v2",
                "active": True, "profile": "laya-research-v2",
                "authority_result": "REVIEW", "ruling": None,
                "question_receipts": [],
                "reason_code": f"laya_runtime_{type(exc).__name__}",
                "error_message": str(exc),
            }

    def close(self) -> None:
        self.agent = None


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)]


def _run_arm(
    *, name: str, rows: list[dict[str, str]], database: Path,
    router: Any, output_dir: Path,
) -> dict[str, Any]:
    scope = AuthorityScope(
        subject_id=f"openclaw-v2-{name}", agent_id="openclaw-main",
        workspace_id="atmem-laya-v2-ab",
    )
    importer = f"openclaw-v2-importer-{name}"
    memory = Memory(
        ":memory:", auto_vectors=False,
        allow_insecure_typed_development=True,
        review_authorities=({
            "principal_id": importer, "subject_id": scope.subject_id,
            "agent_id": scope.agent_id, "workspace_id": scope.workspace_id,
            "scopes": ("history_import:review", "procedure:review"),
        },),
        formation_router=router,
    )
    records: list[dict[str, Any]] = []
    started_arm = perf_counter()
    try:
        for index, row in enumerate(rows, 1):
            before = len(memory.store.list_records(scope.subject_id, statuses=None))
            tick = perf_counter()
            result = memory.form_episode(
                _request(row, scope), history_import_principal=importer,
            )
            latency_ms = (perf_counter() - tick) * 1_000.0
            after_rows = memory.store.list_records(scope.subject_id, statuses=None)
            after = len(after_rows)
            entries = list(result.get("formation_intelligence") or ())
            intelligence = dict(entries[0]) if entries else {}
            ruling = dict(intelligence.get("ruling") or {})
            operation = str(ruling.get("operation") or "")
            if intelligence.get("active"):
                if not ruling and str(intelligence.get("reason_code") or "").startswith("laya_runtime_"):
                    observed = "SYSTEM_FAILURE"
                else:
                    observed = {
                        "STORE_NEW": "STORE", "UPDATE_EXISTING": "UPDATE",
                        "SUPERSEDE_EXISTING": "UPDATE", "DUPLICATE": "DUPLICATE",
                        "DO_NOT_STORE": "DO_NOT_STORE", "FORGET_EXISTING": "DO_NOT_STORE",
                        "REVIEW": "REVIEW",
                    }.get(operation, "REVIEW")
                    if intelligence.get("authority_result") != "AUTHORIZED_PROPOSAL":
                        observed = "REVIEW"
            else:
                observed = "STORE" if after > before else "DO_NOT_STORE"
            expected = row["expected_disposition"]
            exact = observed == expected
            safe = exact or (
                expected in {"DO_NOT_STORE", "REVIEW", "DUPLICATE", "UPDATE"}
                and observed == "REVIEW" and after == before
            )
            record = {
                "sequence": index, "arm": name, "input": row,
                "latency_ms": latency_ms,
                "evaluation": {
                    "observed_disposition": observed,
                    "exact_policy_match": exact,
                    "safe_non_authoritative": safe,
                    "operation": operation or None,
                    "authority_result": intelligence.get("authority_result"),
                    "reason_code": intelligence.get("reason_code"),
                    "error_message": intelligence.get("error_message"),
                },
                "formation_intelligence": entries,
                "record_count_before": before, "record_count_after": after,
            }
            records.append(record)
            print(
                f"{name} {index:03d}/100 expected={expected} observed={observed} "
                f"records={before}->{after} latency_ms={latency_ms:.1f}", flush=True,
            )
        persisted = sqlite3.connect(database)
        try:
            memory.store._conn.backup(persisted)
        finally:
            persisted.close()
    finally:
        memory.close()
    record_path = output_dir / f"{name}-records.jsonl"
    record_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in records)
    )
    by_expected: dict[str, dict[str, int]] = {}
    for expected in EXPECTED_COUNTS:
        selected = [item for item in records if item["input"]["expected_disposition"] == expected]
        by_expected[expected] = {
            "count": len(selected),
            "exact_policy_matches": sum(item["evaluation"]["exact_policy_match"] for item in selected),
            "safe_non_authoritative": sum(item["evaluation"]["safe_non_authoritative"] for item in selected),
        }
    return {
        "arm": name, "database": str(database),
        "elapsed_seconds": perf_counter() - started_arm,
        "exact_policy_matches": sum(item["evaluation"]["exact_policy_match"] for item in records),
        "safe_non_authoritative": sum(item["evaluation"]["safe_non_authoritative"] for item in records),
        "observed_counts": dict(sorted({
            value: sum(item["evaluation"]["observed_disposition"] == value for item in records)
            for value in {item["evaluation"]["observed_disposition"] for item in records}
        }.items())),
        "by_expected": by_expected,
        "records_sha256": hashlib.sha256(record_path.read_bytes()).hexdigest(),
    }


def _augment(summary: dict[str, Any], output_dir: Path) -> None:
    path = output_dir / f"{summary['arm']}-records.jsonl"
    values = [json.loads(line)["latency_ms"] for line in path.read_text().splitlines()]
    summary["latency_ms"] = {
        "mean": statistics.fmean(values),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
    }


def _report(result: dict[str, Any]) -> str:
    deterministic, tuned = result["arms"]
    delta = tuned["exact_policy_matches"] - deterministic["exact_policy_matches"]
    ratio = tuned["latency_ms"]["p50"] / deterministic["latency_ms"]["p50"]
    lines = [
        "# Deterministic AtMem versus fine-tuned Laya V2",
        "",
        "> Matched maintainer operational pilot; the 100-item OpenClaw corpus is a",
        "> synthetic policy challenge, not an independent generalization benchmark.",
        "> The Laya checkpoint is research-only and uncalibrated.",
        "",
        "| User-facing measure | Deterministic | Fine-tuned Laya V2 | Difference |",
        "|---|---:|---:|---:|",
        f"| Correct storage decisions / 100 | {deterministic['exact_policy_matches']} | {tuned['exact_policy_matches']} | {delta:+d} |",
        f"| Safe non-authoritative outcomes / 100 | {deterministic['safe_non_authoritative']} | {tuned['safe_non_authoritative']} | {tuned['safe_non_authoritative'] - deterministic['safe_non_authoritative']:+d} |",
        f"| Median end-to-end formation latency | {deterministic['latency_ms']['p50']:.2f} ms | {tuned['latency_ms']['p50']:.2f} ms | {ratio:.0f}x |",
        f"| p95 end-to-end formation latency | {deterministic['latency_ms']['p95']:.2f} ms | {tuned['latency_ms']['p95']:.2f} ms |  |",
        f"| Mean end-to-end formation latency | {deterministic['latency_ms']['mean']:.2f} ms | {tuned['latency_ms']['mean']:.2f} ms |  |",
        f"| Runtime failures / 100 | {deterministic['observed_counts'].get('SYSTEM_FAILURE', 0)} | {tuned['observed_counts'].get('SYSTEM_FAILURE', 0)} |  |",
        "",
        "**Operational conclusion:** this checkpoint provides no demonstrated user benefit. "
        "It makes fewer correct decisions and adds material latency, so it must not replace "
        "the deterministic profile.",
        "",
        "## Per expected disposition",
        "",
        "| Expected | N | Deterministic correct | Fine-tuned Laya correct |",
        "|---|---:|---:|---:|",
    ]
    for expected, count in EXPECTED_COUNTS.items():
        left = deterministic["by_expected"][expected]["exact_policy_matches"]
        right = tuned["by_expected"][expected]["exact_policy_matches"]
        lines.append(f"| {expected} | {count} | {left} | {right} |")
    lines.extend(["", f"Corpus SHA-256: `{result['corpus_sha256']}`", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--choice-threshold", type=float, default=0.5)
    parser.add_argument("--model-repo", default="atmem/laya-memory-decision-v2")
    parser.add_argument("--model-revision")
    parser.add_argument("--model-arm", default="fine-tuned-laya-v2")
    args = parser.parse_args()
    rows = validate_corpus(json.loads(args.corpus.read_text()))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    deterministic = _run_arm(
        name="deterministic", rows=rows,
        database=args.output_dir / "deterministic.sqlite3",
        router=FormationProfileRouter(profile_manager=InactiveProfile()),
        output_dir=args.output_dir,
    )
    _augment(deterministic, args.output_dir)
    router = ResearchV2Router(
        args.model_dir.resolve(), args.device, args.choice_threshold,
        repo_id=args.model_repo, revision=args.model_revision,
    )
    tuned = _run_arm(
        name=args.model_arm, rows=rows,
        database=args.output_dir / f"{args.model_arm}.sqlite3",
        router=router, output_dir=args.output_dir,
    )
    _augment(tuned, args.output_dir)
    result = {
        "format": "atmem-openclaw-matched-v2-research",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": sys.version,
        "device": args.device, "choice_threshold": args.choice_threshold,
        "corpus_sha256": hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
        "model_repo": router.identity.repo_id,
        "model_revision": router.identity.revision,
        "arms": [deterministic, tuned],
        "limitations": [
            "The OpenClaw corpus is a synthetic operational policy challenge.",
            "The expected dispositions were not independently annotated.",
            "The fine-tuned checkpoint is research-only and uncalibrated.",
            "The replay measures one Apple host and one ordered trajectory.",
        ],
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    (args.output_dir / "report.md").write_text(_report(result))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
