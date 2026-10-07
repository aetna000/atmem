"""Strict matched-arm aggregation for development benchmark evidence."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from statistics import median
from typing import Any, Iterable


def aggregate_longmem(cases: Iterable[dict[str, Any]], methods: Iterable[str]) -> dict:
    rows = list(cases)
    expected_methods = tuple(methods)
    by_method: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        method = str(row.get("method") or "")
        question_id = str(row.get("question_id") or "")
        if method not in expected_methods or not question_id:
            raise ValueError("LongMem result has an unknown method or question")
        if question_id in by_method[method]:
            raise ValueError("LongMem result contains a duplicate method/question")
        by_method[method][question_id] = row
    question_sets = {method: set(by_method[method]) for method in expected_methods}
    if not question_sets or len({frozenset(ids) for ids in question_sets.values()}) != 1:
        raise ValueError("LongMem arms are not matched on identical questions")
    question_ids = sorted(next(iter(question_sets.values())))
    if not question_ids:
        raise ValueError("LongMem matched report is empty")
    arms = {}
    for method in expected_methods:
        method_rows = list(by_method[method].values())
        correct = sum(bool(row.get("score_bool")) for row in method_rows)
        arms[method] = {
            "correct": correct,
            "total": len(method_rows),
            "accuracy": correct / len(method_rows),
            "median_context_tokens": median(
                int(row.get("memory_context_token_count") or 0) for row in method_rows
            ),
            "openai_cost_usd": round(sum(
                float(row.get("openai_cost_usd") or 0) for row in method_rows
            ), 9),
        }
    candidate = arms["typed-local"]
    comparisons = {
        method: {
            "absolute_accuracy_delta": candidate["accuracy"] - row["accuracy"],
            "passed_case_delta": candidate["correct"] - row["correct"],
        }
        for method, row in arms.items() if method != "typed-local"
    }
    return {
        "format": "atmem-longmemeval-matched-development-v1",
        "claim": "matched-development-sample-not-an-official-score",
        "question_ids": question_ids,
        "arms": arms,
        "atmem_comparisons": comparisons,
    }


def write_longmem(
    progress_path: str | Path, output_path: str | Path,
    *, methods: Iterable[str] | None = None,
) -> dict:
    progress = json.loads(Path(progress_path).read_text(encoding="utf-8"))
    selected = tuple(methods or progress.get("methods") or ())
    rows = [row for row in (progress.get("cases") or ()) if row.get("method") in selected]
    result = aggregate_longmem(rows, selected)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def aggregate_longmem_controls(cases: Iterable[dict[str, Any]]) -> dict:
    """Compare product, verified-evidence and no-memory reader outcomes."""
    method_to_variant = {
        "typed-local": "product_context",
        "verified-evidence": "verified_minimal_evidence",
        "no-retrieval": "no_memory",
    }
    by_case: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in cases:
        method = str(row.get("method") or "")
        if method not in method_to_variant:
            continue
        case_id = str(row.get("question_id") or "")
        variant = method_to_variant[method]
        if not case_id or variant in by_case[case_id]:
            raise ValueError("controlled reader results contain a missing or duplicate case")
        by_case[case_id][variant] = row
    results = []
    required = set(method_to_variant.values())
    for case_id in sorted(by_case):
        variants = by_case[case_id]
        if set(variants) != required:
            raise ValueError(f"controlled reader case is incomplete: {case_id}")
        identities = {str(row.get("reader_identity_sha256") or "") for row in variants.values()}
        prompts = {str(row.get("reader_prompt_sha256") or "") for row in variants.values()}
        if len(identities) != 1 or "" in identities or len(prompts) != 1 or "" in prompts:
            raise ValueError("controlled reader identity or prompt differs")
        product = variants["product_context"]
        verified = variants["verified_minimal_evidence"]
        no_memory = variants["no_memory"]
        metadata = dict(product.get("memory_post_query_metadata") or {})
        product_reported_complete = (
            dict(metadata.get("sufficiency") or {}).get("status") == "sufficient"
            and not product.get("memory_context_was_truncated")
        )
        if product.get("score_bool"):
            contrast = "product_answer_succeeded"
        elif verified.get("score_bool"):
            contrast = (
                "reader_use_or_noise_candidate" if product_reported_complete
                else "memory_pipeline_candidate"
            )
        else:
            contrast = "reader_capability_or_prompt_candidate"
        results.append({
            "case_id": case_id,
            "product_correct": bool(product.get("score_bool")),
            "verified_evidence_correct": bool(verified.get("score_bool")),
            "no_memory_correct": bool(no_memory.get("score_bool")),
            "product_reported_complete": product_reported_complete,
            "preliminary_contrast": contrast,
            "terminal_outcome": None,
            "terminal_outcome_pending": "eight_stage_requirement_ledger",
        })
    if not results:
        raise ValueError("controlled reader report is empty")
    return {
        "format": "atmem-longmemeval-controlled-reader-comparison-v1",
        "claim": "controlled-reader-contrast-not-terminal-attribution",
        "case_count": len(results),
        "all_failures_retained": True,
        "results": results,
    }


def write_longmem_controls(progress_path: str | Path, output_path: str | Path) -> dict:
    progress = json.loads(Path(progress_path).read_text(encoding="utf-8"))
    result = aggregate_longmem_controls(progress.get("cases") or ())
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
