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
    AuthorityScope, RetrievalBudget,
)
from atmem.context_engine.contracts import ContextRequestV3
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
    synonyms = {
        "cc": "copy", "copied": "copy", "outside": "external",
        "emails": "email", "threads": "thread", "calculation": "calculate",
        "calculated": "calculate", "chose": "choose", "chosen": "choose",
        "selected": "choose", "target": "choose", "personal": "private",
        "completed": "finish", "finished": "finish",
    }
    values = set()
    for raw in _normalized(value).split():
        token = synonyms.get(raw, raw)
        if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        if token not in STOP:
            values.add(token)
    return values


def _source_session_ids(requirement: dict) -> tuple[str, ...]:
    return tuple(sorted({
        ref.partition(":")[2]
        for ref in requirement.get("source_refs") or ()
        if isinstance(ref, str) and ref.startswith("session:")
        and ref.partition(":")[2]
    }))


def _select_removal_requirement(case: dict, task_text: str) -> tuple[dict, dict]:
    """Freeze the most request-aligned removable fact without product output."""
    query_tokens = _tokens(task_text)
    candidates = []
    for requirement in case["requirements"]:
        if requirement.get("removal_applicable") is not True:
            continue
        expected = _tokens(str(requirement.get("expected") or ""))
        overlap = len(query_tokens & expected)
        candidates.append((
            overlap / max(1, len(expected)), overlap,
            str(requirement["requirement_id"]), requirement,
        ))
    if not candidates:
        raise RuntimeError("case has no removal-applicable requirement")
    candidates.sort(key=lambda row: (-row[0], -row[1], row[2]))
    ratio, overlap, requirement_id, requirement = candidates[0]
    return requirement, {
        "method": "query_aligned_requirement_v1",
        "requirement_id": requirement_id,
        "overlap_tokens": overlap,
        "expected_token_coverage": ratio,
        "product_output_observed": False,
    }


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


def _is_source_statement(record: dict) -> bool:
    unit = ((record.get("raw") or {}).get("typed_unit") or {})
    payload = unit.get("payload") or {}
    return (
        unit.get("kind") == "environment_state"
        and payload.get("entity") == "source episode"
        and payload.get("relation") == "source statement"
    )


def _atomic_removal_records(
    records: list[dict], requirement: dict, case_requirements: list[dict]
) -> tuple[list[dict], str | None]:
    """Select a minimal evaluator-matched unit set or fail without deleting.

    Provenance narrows selection to the immutable source session. Evaluator
    wording may then identify minimal source-statement units, but never enters
    retrieval or the product database. A fact may span adjacent atomic clauses;
    every selected clause must be exclusive to that one requirement. Units that
    also materially match another requirement remain non-atomic failures.
    """
    candidates = _matching_records(records, requirement)
    statements = [row for row in candidates if _is_source_statement(row)]
    if not statements:
        return [], "non_atomic_removal_target" if candidates else "removal_target_unrepresented"
    expected_tokens = _tokens(str(requirement.get("expected") or ""))
    scored = []
    for row in statements:
        content_tokens = _tokens(str(row.get("content") or ""))
        score = (
            len(expected_tokens & content_tokens) / len(expected_tokens)
            if expected_tokens else 0.0
        )
        scored.append((score, str(row.get("id") or ""), row))
    scored.sort(key=lambda item: (-item[0], item[1]))
    if not scored or scored[0][0] <= 0:
        return [], "non_atomic_removal_target"
    source_sessions = set(_source_session_ids(requirement))
    exclusive: list[tuple[float, str, dict, set[str]]] = []
    for score, unit_id, row in scored:
        selected_tokens = _tokens(str(row.get("content") or ""))
        overlaps_other = False
        for other in case_requirements:
            if other is requirement or not (
                source_sessions & set(_source_session_ids(other))
            ):
                continue
            other_tokens = _tokens(str(other.get("expected") or ""))
            if (
                other_tokens
                and len(other_tokens & selected_tokens) / len(other_tokens) >= 0.60
            ):
                overlaps_other = True
                break
        if not overlaps_other:
            exclusive.append((score, unit_id, row, selected_tokens))
    if not exclusive:
        return [], "non_atomic_removal_target"
    selected_rows: list[dict] = []
    covered: set[str] = set()
    for _score, _unit_id, row, tokens in exclusive:
        gain = (tokens & expected_tokens) - covered
        if not gain:
            continue
        selected_rows.append(row)
        covered.update(tokens & expected_tokens)
        if len(covered) / len(expected_tokens) >= 0.80 or len(selected_rows) >= 4:
            break
    if not selected_rows:
        return [], "non_atomic_removal_target"
    # If several candidates contribute exactly the same coverage, choosing one
    # would make the control depend on an arbitrary unit ID.
    if len(selected_rows) == 1 and len(exclusive) > 1:
        first_coverage = exclusive[0][3] & expected_tokens
        second_coverage = exclusive[1][3] & expected_tokens
        if first_coverage == second_coverage:
            return [], "non_atomic_removal_target"
    return selected_rows, None


def _gate_blocks_removed_requirement(gate: dict, requirement: dict) -> bool:
    """Require a product-named need that matches the removed fact.

    Generic slot names are deliberately insufficient. Evaluator-only expected
    text is used here only to verify the product receipt after the run; it is
    never passed into planning, retrieval, or the action gate.
    """
    expected = _tokens(str(requirement.get("expected") or ""))
    if gate.get("outcome") != "blocked_missing_requirement" or not expected:
        return False
    descriptions = [
        " ".join(str(obligation.get(key) or "") for key in (
            "entity", "relation_or_action", "temporal_target", "applicability",
        ))
        for obligation in gate.get("missing_obligations") or ()
    ]
    for description in (*descriptions, " ".join(descriptions)):
        overlap = expected & _tokens(description)
        if len(overlap) >= 3 or (
            len(overlap) >= 2 and len(overlap) / len(expected) >= 0.10
        ):
            return True
    return False


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
    generation = memory.context_generation(scope)
    return memory.prepare_context_v3(ContextRequestV3(
        context_id=f"context-{request_id}",
        request_id=request_id,
        scope=scope,
        query=query,
        profile_id="context-fast",
        mode="active",
        generation=int(generation["canonical_generation"]),
        budget=RetrievalBudget(context_bytes=int(options.get("context_bytes", 32_000))),
    ))


def run_restored_gate_precheck(
    *, checkpoint_root: Path, checkout: Path, manifest: dict,
    output_root: Path, options: dict,
) -> dict:
    """Prove complete checkpoints open every gate without invoking a model."""
    rows = []
    memories: dict[str, Memory] = {}
    try:
        for case in manifest["cases"]:
            case_id = str(case["case_id"])
            persona, item = case_id.split(":", 1)
            memory = memories.get(persona)
            if memory is None:
                memory = Memory(
                    checkpoint_root / "atmem-personas" / f"{persona}.db",
                    retain_query_text=False, auto_vectors=False,
                )
                memories[persona] = memory
            spec = yaml.safe_load(
                (checkout / "tests" / persona / f"{item}.yaml").read_text()
            )
            request = SimpleNamespace(
                persona=persona,
                interaction_id=item,
                dated_message=(
                    f"[{spec['narrative_anchor_date']}] {spec['test'].strip()}"
                ),
            )
            package = _recall(
                memory, persona, request.dated_message, options=options
            )
            gate = build_pre_action_gate_receipt(request, package)
            rows.append({
                "case_id": case_id,
                "outcome": gate["outcome"],
                "missing_requirement_ids": gate["missing_requirement_ids"],
                "context_sha256": "sha256:" + hashlib.sha256(
                    package.context.encode()
                ).hexdigest(),
                "model_invoked": False,
                "tool_calls": 0,
            })
    finally:
        for memory in memories.values():
            memory.close()
    report = {
        "format": "atmem-dolphin-restored-gate-precheck-v1",
        "case_count": len(rows),
        "gate_open": sum(row["outcome"] == "gate_open" for row in rows),
        "all_failures_retained": True,
        "model_invocations": 0,
        "results": rows,
    }
    _write(output_root / "restored-gate-precheck.json", report)
    return report


def run_removals(*, checkpoint_root: Path, checkout: Path, manifest: dict,
                 output_root: Path, options: dict) -> dict:
    results = []
    scratch = output_root / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    for case in manifest["cases"]:
        case_id = str(case["case_id"])
        persona, item = case_id.split(":", 1)
        spec = yaml.safe_load(
            (checkout / "tests" / persona / f"{item}.yaml").read_text()
        )
        requirement, requirement_selection = _select_removal_requirement(
            case, str(spec["test"])
        )
        scope = AuthorityScope(
            subject_id=f"dolphin:{persona}",
            agent_id="dolphin-agent",
            workspace_id=f"dolphin:{persona}",
        )
        requirement_id = str(requirement["requirement_id"])
        source = checkpoint_root / "atmem-personas" / f"{persona}.db"
        clone = scratch / f"{persona}-{item}.db"
        _clone_household(source, clone)
        memory: Memory | None = None
        try:
            memory = Memory(clone, retain_query_text=False, auto_vectors=False)
            source_session_ids = _source_session_ids(requirement)
            matches, selection_failure = _atomic_removal_records(
                memory.list_context_observations(
                    scope,
                    source_session_ids=source_session_ids,
                ),
                requirement, list(case["requirements"])
            )
            if not matches:
                results.append({
                    "case_id": case_id,
                    "removed_requirement_id": requirement_id,
                    "outcome": "control_failed",
                    "actual_reason": selection_failure,
                    "model_invoked": False,
                    "tool_calls": 0,
                    "error_type": None,
                    "deleted_record_ids": [],
                    "source_session_ids": list(source_session_ids),
                    "selection_method": "atomic_source_statement",
                    "requirement_selection": requirement_selection,
                })
                continue
            deleted = []
            for record in matches:
                result = memory.forget_context_observation(
                    scope, str(record["id"]), actor="benchmark-evaluator"
                )
                deleted.extend(result["unit_ids"])
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
                "product_missing_obligation_ids": gate["missing_requirement_ids"],
                "product_missing_obligations": gate.get("missing_obligations") or [],
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
                "selection_method": "atomic_source_statement",
                "requirement_selection": requirement_selection,
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
    run_restored_gate_precheck(
        checkpoint_root=args.checkpoint_root.resolve(),
        checkout=args.dolphin_checkout.resolve(), manifest=manifest,
        output_root=args.output_root.resolve(), options=options,
    )
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
