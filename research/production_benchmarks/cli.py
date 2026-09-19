from __future__ import annotations

import argparse
import json
from pathlib import Path

from .locomo import run_locomo


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AtMem production benchmark adapters")
    sub = parser.add_subparsers(dest="command", required=True)
    loco = sub.add_parser("locomo")
    loco.add_argument("--data", type=Path, required=True)
    loco.add_argument("--manifest", type=Path, default=Path("research/production_benchmarks/manifests/locomo.json"))
    loco.add_argument("--sample", type=int)
    loco.add_argument("--full-corpus", action="store_true")
    loco.add_argument("--allow-upstream-anomalies", action="store_true", help="run for diagnosis but force exploratory claim status")
    loco.add_argument("--jev", action="store_true", help="rerank AtMem candidates with Jev")
    loco.add_argument("--allow-egress", action="store_true", help="explicitly permit sending benchmark text to TypeSafe")
    loco.add_argument("--jev-batch-size", type=int, default=20)
    loco.add_argument("--jev-model", default="jev-1.13.0")
    loco.add_argument("--output", type=Path, required=True)
    loco.add_argument("--summary", type=Path)
    args = parser.parse_args()
    if args.command == "locomo":
        if args.full_corpus and args.sample:
            parser.error("--sample and --full-corpus are mutually exclusive")
        if args.jev and not args.allow_egress:
            parser.error("--jev requires explicit --allow-egress")
        result = run_locomo(args.data, manifest_path=args.manifest, sample=args.sample, full_corpus=args.full_corpus, allow_anomalies=args.allow_upstream_anomalies, use_jev=args.jev, jev_batch_size=args.jev_batch_size, jev_model=args.jev_model)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary_path = args.summary or args.output.with_suffix(".md")
        metrics = result["metrics"]
        summary_path.write_text(
            "# AtMem LoCoMo benchmark\n\n"
            f"Claim status: `{result['claim_status']}`\n\n"
            f"Dataset SHA-256: `{metrics['dataset_sha256']}`\n\n"
            "| Metric | Value |\n|---|---:|\n"
            f"| Questions | {metrics['questions']} |\n"
            f"| MRR@5 | {metrics['mrr_at_5']} |\n"
            f"| Recall@1 | {metrics['recall_at_1']} |\n"
            f"| Recall@5 | {metrics['recall_at_5']} |\n"
            f"| Recall@10 | {metrics['recall_at_10']} |\n"
            f"| p50 latency (ms) | {metrics['p50_latency_ms']} |\n"
            f"| p95 latency (ms) | {metrics['p95_latency_ms']} |\n"
            f"| Throughput (questions/s) | {metrics['throughput_records_per_second']} |\n"
            f"| Errors | {metrics['errors']} |\n"
            f"| Validation issues | {metrics['validation_issues']} |\n\n"
            "This is retrieval/evidence coverage, not answer-generation quality. "
            "Production-level claims require zero validation issues and all manifest gates.\n",
            encoding="utf-8",
        )
        print(f"benchmark=locomo claim_status={result['claim_status']} questions={result['metrics']['questions']} mrr_at_5={result['metrics']['mrr_at_5']}")
        if result.get("jev"):
            print(f"jev_mrr_at_5={result['jev']['metrics']['mrr_at_5']} jev_recall_at_5={result['jev']['metrics']['recall_at_5']} jev_batches={result['jev']['transport']['batches']} jev_errors={result['jev']['transport']['errors']}")
        print(f"output={args.output} summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
