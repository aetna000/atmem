#!/usr/bin/env python3
"""Run evaluator-only Dolphin removal controls without invoking a model.

One load-bearing fact is removed from a disposable clone for every frozen task.
The original checkpoint is never modified.  Positive controls are finalized
later from paid-run gate receipts, so an always-blocking gate cannot pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from types import SimpleNamespace
import uuid

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.append(str(ROOT))

from atmem import Memory
from atmem.benchmark.attribution import (
    ACTION_GATE_PAIR_FORMAT,
    assess_dolphin_action_gate_pair,
)
from atmem.contracts import (
    AuthorityScope,
    ContextRequestV2,
    RecallRequest,
    RetrievalBudget,
)
from research.production_benchmarks.dolphinbench import build_pre_action_gate_receipt
from research.production_benchmarks.installed_product import installed_atmem_identity


STOP = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "to", "was", "with",
})


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _tokens(value: str) -> set[str]:
    return {token for token in _normalized(value).split() if token not in STOP}


def _source_session_ids(requirement: dict) -> tuple[str, ...]:
    return tuple(sorted({
        ref.partition(":")[2]
        for ref in requirement.get("source_refs") or ()
        if isinstance(ref, str) and ref.startswith("session:")
        and ref.partition(":")[2]
    }))


def _matching_records(records: list[dict], requirement: dict) -> list[dict]:
    """Resolve the removable unit from frozen provenance, never answer text.

    The official registry expresses a normalized fact that is often not a
    verbatim substring of the user-authored source.  Session references are
    evaluator-only provenance and select the represented source unit without
    influencing retrieval.  Lexical matching is permitted only for manifests
    that genuinely lack a source-session reference.
    """
    source_sessions = set(_source_session_ids(requirement))
    if source_sessions:
        return [
            record for record in records
            if str(record.get("source_session_id") or "") in source_sessions
        ]
    statement = str(requirement["expected"])
    expected = _normalized(statement)
    expected_tokens = _tokens(statement)
    if not expected_tokens:
        raise RuntimeError("removal requirement has no discriminating tokens")
    matches = []
    for record in records:
        content = str(record.get("content") or "")
        normalized = _normalized(content)
        overlap = len(expected_tokens & _tokens(content)) / len(expected_tokens)
        if expected in normalized or normalized in expected or overlap >= 0.80:
            matches.append(record)
    return matches


def _gate_blocks_removed_requirement(gate: dict, requirement: dict) -> bool:
    """Require semantic obligation linkage, not merely any closed gate."""
    expected = set(requirement.get("expected_obligation_slots") or ())
    missing = set(gate.get("missing_requirement_ids") or ())
    return (
        gate.get("outcome") == "blocked_missing_requirement"
        and bool(expected)
        and bool(expected & missing)
    )


def _clone_household(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    policy = Path(f"{source}.encryption.json")
    if not policy.is_file():
        raise RuntimeError(f"encrypted household policy is missing: {policy}")
    shutil.copy2(policy, Path(f"{destination}.encryption.json"))


def _recall(memory: Memory, persona: str, query: str, *, options: dict) -> object:
    scope = AuthorityScope(
        subject_id=f"dolphin:{persona}",
        agent_id="dolphin-agent",
        workspace_id=f"dolphin:{persona}",
    )
    request_id = f"dolphin-removal-{uuid.uuid4().hex}"
    candidates = memory.eligible_candidates(RecallRequest(
        request_id=request_id,
        scope=scope,
        query=query,
        limit=int(options.get("memory_limit", 20)),
        candidate_limit=int(options.get("candidate_limit", 200)),
        retrieval_strategy="core-rrf-v1",
    ))
    return memory.prepare_context_v2(ContextRequestV2(
        context_id=f"context-{request_id}",
        candidate_set_id=candidates.candidate_set_id,
        scope=scope,
        query=query,
        budget=RetrievalBudget(context_bytes=int(options.get("context_bytes", 32_000))),
    ))


def run_removals(*, checkpoint_root: Path, checkout: Path, manifest: dict,
                 output_root: Path, options: dict) -> dict:
    results = []
    scratch = output_root / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    for case in manifest["cases"]:
        case_id = str(case["case_id"])
        persona, item = case_id.split(":", 1)
        requirement = next(
            row for row in case["requirements"] if row.get("removal_applicable") is True
        )
        requirement_id = str(requirement["requirement_id"])
        source = checkpoint_root / "atmem-personas" / f"{persona}.db"
        clone = scratch / f"{persona}-{item}.db"
        _clone_household(source, clone)
        subject = f"dolphin:{persona}"
        memory: Memory | None = None
        try:
            memory = Memory(clone, retain_query_text=False, auto_vectors=False)
            source_session_ids = _source_session_ids(requirement)
            matches = _matching_records(memory.list(subject), requirement)
            if not matches:
                results.append({
                    "case_id": case_id,
                    "removed_requirement_id": requirement_id,
                    "outcome": "control_failed",
                    "actual_reason": "removal_target_unrepresented",
                    "model_invoked": False,
                    "tool_calls": 0,
                    "error_type": None,
                    "deleted_record_ids": [],
                    "source_session_ids": list(source_session_ids),
                    "selection_method": (
                        "source_session_provenance" if source_session_ids
                        else "conservative_lexical_fallback"
                    ),
                })
                continue
            deleted = []
            for record in matches:
                result = memory.forget_record(subject, str(record["id"]), actor="benchmark-evaluator")
                deleted.extend(result["record_ids"])
            spec = yaml.safe_load((checkout / "tests" / persona / f"{item}.yaml").read_text())
            request = SimpleNamespace(
                persona=persona,
                interaction_id=item,
                dated_message=f"[{spec['narrative_anchor_date']}] {spec['test'].strip()}",
            )
            package = _recall(memory, persona, request.dated_message, options=options)
            gate = build_pre_action_gate_receipt(request, package)
            removed_slots = set(requirement["expected_obligation_slots"])
            blocked = _gate_blocks_removed_requirement(gate, requirement)
            results.append({
                "case_id": case_id,
                "removed_requirement_id": requirement_id,
                "outcome": gate["outcome"] if blocked else "control_failed",
                "missing_requirement_id": requirement_id if blocked else None,
                "product_missing_slots": gate["missing_requirement_ids"],
                "actual_reason": (
                    "missing_requirement" if blocked
                    else "unmatched_missing_obligation"
                    if gate["outcome"] == "blocked_missing_requirement"
                    else "gate_open_after_removal"
                ),
                "model_invoked": False,
                "tool_calls": 0,
                "error_type": None,
                "deleted_record_ids": deleted,
                "source_session_ids": list(source_session_ids),
                "selection_method": (
                    "source_session_provenance" if source_session_ids
                    else "conservative_lexical_fallback"
                ),
                "expected_obligation_slots": sorted(removed_slots),
                "context_sha256": "sha256:" + hashlib.sha256(package.context.encode()).hexdigest(),
            })
        except Exception as exc:
            results.append({
                "case_id": case_id,
                "removed_requirement_id": requirement_id,
                "outcome": "control_failed",
                "actual_reason": "control_system_failure",
                "model_invoked": False,
                "tool_calls": 0,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            })
        finally:
            if memory is not None:
                memory.close()
            clone.unlink(missing_ok=True)
            Path(f"{clone}.encryption.json").unlink(missing_ok=True)
    report = {
        "format": "atmem-dolphin-removal-controls-v1",
        "case_count": len(results),
        "all_failures_retained": True,
        "model_invocations": 0,
        "results": results,
    }
    _write(output_root / "removal-controls.json", report)
    return report


def pair_positive_controls(*, removal_report: dict, manifest: dict,
                           gate_root: Path, output_root: Path) -> dict:
    cases = {str(row["case_id"]): row for row in manifest["cases"]}
    pairs = []
    for removal in removal_report["results"]:
        case_id = str(removal["case_id"])
        persona, item = case_id.split(":", 1)
        gate_path = gate_root / persona / f"{item}.json"
        if not gate_path.is_file():
            positive = {
                "gate_open": False, "model_invoked": False, "tool_calls": 0,
                "expected_tool_call_observed": False,
                "error_type": "missing_positive_receipt",
            }
        else:
            gate = _load(gate_path)
            expected = {
                str(row["expected"])
                for row in cases[case_id]["requirements"]
                if "required_action" in row["classes"]
            }
            observed = set(gate.get("observed_tool_names") or ())
            positive = {
                "gate_open": gate.get("outcome") == "gate_open",
                "model_invoked": gate.get("model_invoked") is True,
                "tool_calls": int(gate.get("tool_calls") or 0),
                "expected_tool_call_observed": bool(expected & observed),
                "expected_tool_calls": sorted(expected),
                "observed_tool_calls": sorted(observed),
                "error_type": gate.get("error_type"),
            }
        pair = {
            "format": ACTION_GATE_PAIR_FORMAT,
            "case_id": case_id,
            "removed_requirement_id": removal["removed_requirement_id"],
            "removal": removal,
            "restored": positive,
        }
        assessment = assess_dolphin_action_gate_pair(pair)
        pair.update(assessment)
        pairs.append(pair)
    report = {
        "format": "atmem-dolphin-action-gate-controls-v1",
        "case_count": len(pairs),
        "passed": sum(row["passed"] for row in pairs),
        "all_failures_retained": True,
        "pairs": pairs,
    }
    _write(output_root / "action-gate-controls.json", report)
    return report


def main() -> None:
    installed_atmem_identity()
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-root", required=True, type=Path)
    parser.add_argument("--dolphin-checkout", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--adapter-options", type=Path)
    parser.add_argument("--positive-gate-root", type=Path)
    args = parser.parse_args()
    manifest = _load(args.manifest.resolve())
    options = _load(args.adapter_options.resolve()) if args.adapter_options else {}
    removal = run_removals(
        checkpoint_root=args.checkpoint_root.resolve(),
        checkout=args.dolphin_checkout.resolve(), manifest=manifest,
        output_root=args.output_root.resolve(), options=options,
    )
    if args.positive_gate_root:
        pair_positive_controls(
            removal_report=removal, manifest=manifest,
            gate_root=args.positive_gate_root.resolve(),
            output_root=args.output_root.resolve(),
        )


if __name__ == "__main__":
    main()
