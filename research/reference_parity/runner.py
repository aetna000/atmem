"""Reader-free reference runner with evaluator-owned scoring."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Protocol

from .contracts import CaseEvidenceResult
from .normalizer import normalize_evidence


class EvidenceAdapter(Protocol):
    system: str

    def run_case(self, case: Mapping[str, Any]) -> CaseEvidenceResult: ...


def _gold_ranges(case: Mapping[str, Any]) -> set[tuple[str, int, int]]:
    return {
        (item.source_id, item.start, item.end)
        for item in normalize_evidence(case["minimal_evidence"], case["sources"])
    }


def score_case(case: Mapping[str, Any], result: CaseEvidenceResult) -> dict[str, Any]:
    gold = _gold_ranges(case)
    selected = set(result.selected_ranges)
    forbidden = set(result.forbidden_source_ids)
    leaked = sorted({source_id for source_id, _, _ in selected} & forbidden)
    covered = len(gold & selected)
    evidence_complete = gold <= selected
    status_correct = result.status == case["expected_status"]
    if result.status in {"sufficient", "conflicted", "contradicted"}:
        status_correct = status_correct and evidence_complete
    return {
        **result.to_dict(),
        "gold_range_count": len(gold),
        "covered_gold_range_count": covered,
        "evidence_recall": covered / len(gold) if gold else 1.0,
        "complete_evidence": evidence_complete,
        "typed_status_correct": status_correct,
        "unauthorized_source_ids": leaked,
    }


def run(adapter: EvidenceAdapter, corpus: Mapping[str, Any]) -> dict[str, Any]:
    materialized_cases = []
    budget = int(corpus.get("selection_budget_sources", 2))
    distractors = list(corpus.get("global_distractors", []))
    for original in corpus["cases"]:
        case = {**original, "sources": [*original["sources"], *distractors]}
        result = adapter.run_case(case)
        result = replace(result, selected_ranges=result.selected_ranges[:budget])
        materialized_cases.append(score_case(case, result))
    cases = materialized_cases
    holdout = [case for case in cases if case["split"] == "holdout"]
    errors = [case for case in cases if case["error"]]
    aggregate = {
        "case_count": len(cases),
        "error_count": len(errors),
        "evidence_recall": sum(case["evidence_recall"] for case in cases) / len(cases),
        "typed_status_accuracy": sum(case["typed_status_correct"] for case in cases) / len(cases),
        "unauthorized_exposure_count": sum(bool(case["unauthorized_source_ids"]) for case in cases),
        "median_latency_ms": median(case["elapsed_ms"] for case in cases),
        "holdout_evidence_recall": (
            sum(case["evidence_recall"] for case in holdout) / len(holdout)
            if holdout
            else None
        ),
        "holdout_typed_status_accuracy": (
            sum(case["typed_status_correct"] for case in holdout) / len(holdout)
            if holdout
            else None
        ),
    }
    return {
        "format": "atmem-reader-free-reference-run-v1",
        "system": adapter.system,
        "corpus_sha256": "sha256:" + hashlib.sha256(
            json.dumps(corpus, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "aggregate": aggregate,
        "cases": cases,
    }


def load_corpus(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if value.get("format") != "atmem-neutral-minimal-evidence-v1":
        raise ValueError("unsupported reference corpus")
    return value
