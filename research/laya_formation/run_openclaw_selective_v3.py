"""Matched replay for deterministic, base Laya, and selective tuned Laya V3.

This is an operational product diagnostic on the frozen 100-item corpus.  It
does not open or tune against the stateful dataset's sealed scientific test.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import sys
from typing import Any, Mapping

from laya import Agent

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.laya_formation.integration import FormationProfileRouter
from atmem.laya_formation.runtime import LayaTypedDecisionEngineV2
from atmem.laya_formation.selective_v3 import (
    build_joint_choice_v3,
    evaluate_joint_choice_v3,
)
from research.laya_formation.openclaw_corpus import EXPECTED_COUNTS, validate_corpus
from research.laya_formation.run_openclaw_ab import InactiveProfile
from research.laya_formation.run_openclaw_v2_research import _augment, _run_arm


class ResearchSelectiveV3Router:
    """Offline-only two-action router using the production V3 wire contract."""

    def __init__(
        self, model_dir: Path, *, device: str, threshold: float,
        identity: str,
    ) -> None:
        self.identity = identity
        self.agent = Agent(str(model_dir), device=device)
        self.engine = LayaTypedDecisionEngineV2(
            self.agent, tokenizer_revision=identity,
        )
        self.threshold = float(threshold)

    def uses_v2_semantic_authority(self) -> bool:
        return True

    def decide_protocol_transition_v2(
        self, *, store: Any, scope: Any, source_id: str, text: str,
        retrieved_records: tuple[Mapping[str, Any], ...],
    ) -> dict[str, Any]:
        generation = int(store.record_generation(scope.subject_id))
        memories = []
        for rank, original in enumerate(retrieved_records):
            row = dict(original)
            if str(row.get("status") or "active") != "active":
                continue
            content = str(row.get("content") or "")
            digest = "sha256:" + sha256_hex(content)
            memories.append({
                "id": str(row["id"]), "content": content,
                "lifecycle": "active", "source_digest": digest,
                "content_digest": digest, "memory_class": "unknown",
                "retrieval_score": float(row.get("retrieval_score", 1.0 / (rank + 1))),
            })
        request_id = "openclaw_v3_" + sha256_hex(canonical_json([
            source_id, generation, self.identity,
        ]))[:32]
        bundle = build_joint_choice_v3(
            request_id=request_id,
            scope_id="scope_" + sha256_hex(canonical_json(scope.to_dict()))[:32],
            canonical_generation=generation,
            observation={
                "id": source_id, "content": text, "speaker_role": "user",
                "source_digest": "sha256:" + sha256_hex(text),
            },
            retrieved_memories=memories,
            allowed_operations=("STORE_NEW", "DO_NOT_STORE"),
        )
        result = evaluate_joint_choice_v3(
            self.engine, bundle, confidence_threshold=self.threshold,
        )
        authorized = (
            result.disposition == "model_delegated"
            and result.operation in {"STORE_NEW", "DO_NOT_STORE"}
            and int(store.record_generation(scope.subject_id)) == generation
        )
        return {
            "format": "atmem-live-formation-transition-v3",
            "profile": "laya-selective-v3-research", "active": True,
            "authority_result": "AUTHORIZED_PROPOSAL" if authorized else "REVIEW",
            "ruling": result.to_dict(), "model_calls": result.model_calls,
            "reason_code": (
                "governance_revalidation_passed" if authorized else result.reason_code
            ),
        }

    def close(self) -> None:
        self.agent = None


def _report(result: dict[str, Any]) -> str:
    arms = result["arms"]
    lines = [
        "# Selective Laya V3 matched operational comparison", "",
        "> Frozen 100-item operational corpus; this is not an independent scientific benchmark.",
        "",
        "| Measure | Deterministic | Original Laya | Fine-tuned selective Laya |",
        "|---|---:|---:|---:|",
        f"| Correct / 100 | {arms[0]['exact_policy_matches']} | {arms[1]['exact_policy_matches']} | {arms[2]['exact_policy_matches']} |",
        f"| Safe / 100 | {arms[0]['safe_non_authoritative']} | {arms[1]['safe_non_authoritative']} | {arms[2]['safe_non_authoritative']} |",
        f"| Median latency (ms) | {arms[0]['latency_ms']['p50']:.2f} | {arms[1]['latency_ms']['p50']:.2f} | {arms[2]['latency_ms']['p50']:.2f} |",
        f"| p95 latency (ms) | {arms[0]['latency_ms']['p95']:.2f} | {arms[1]['latency_ms']['p95']:.2f} | {arms[2]['latency_ms']['p95']:.2f} |",
        f"| Runtime failures | {arms[0]['observed_counts'].get('SYSTEM_FAILURE', 0)} | {arms[1]['observed_counts'].get('SYSTEM_FAILURE', 0)} | {arms[2]['observed_counts'].get('SYSTEM_FAILURE', 0)} |",
        "", "## Per expected disposition", "",
        "| Expected | N | Deterministic | Original Laya | Fine-tuned Laya |",
        "|---|---:|---:|---:|---:|",
    ]
    for expected, count in EXPECTED_COUNTS.items():
        values = [arm["by_expected"][expected]["exact_policy_matches"] for arm in arms]
        lines.append(f"| {expected} | {count} | {values[0]} | {values[1]} | {values[2]} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--tuned-model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    rows = validate_corpus(json.loads(args.corpus.read_text()))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    configurations = [
        ("deterministic", FormationProfileRouter(profile_manager=InactiveProfile())),
        ("original-laya-selective-v3", ResearchSelectiveV3Router(
            args.base_model, device=args.device, threshold=args.threshold,
            identity="original-laya-multilingual",
        )),
        ("fine-tuned-laya-selective-v3", ResearchSelectiveV3Router(
            args.tuned_model, device=args.device, threshold=args.threshold,
            identity="fine-tuned-selective-v3",
        )),
    ]
    arms = []
    for name, router in configurations:
        arm = _run_arm(
            name=name, rows=rows,
            database=args.output_dir / f"{name}.sqlite3",
            router=router, output_dir=args.output_dir,
        )
        _augment(arm, args.output_dir)
        arms.append(arm)
        close = getattr(router, "close", None)
        if callable(close):
            close()
    result = {
        "format": "atmem-openclaw-selective-v3-research",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": sys.version,
        "device": args.device, "threshold": args.threshold,
        "corpus_sha256": hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
        "arms": arms,
        "limitations": [
            "Operational corpus, not an independent generalization benchmark.",
            "The two-action specialist does not learn relational transitions.",
            "The authentic STORE_NEW training class is below the activation minimum.",
        ],
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    (args.output_dir / "comparison.md").write_text(_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
