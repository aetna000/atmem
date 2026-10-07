"""Evaluator-side controlled LongMem attribution helpers.

Gold requirements enter only this evaluation module.  They are never passed to
AtMem retrieval or stored in product memory.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Mapping

from atmem.benchmark.attribution import classify_longmem_outcome
from atmem.benchmark.contracts import canonical_digest


CONTROL_VARIANTS = ("product_context", "verified_minimal_evidence", "no_memory")


def build_control_messages(
    product_row: Mapping[str, Any],
    requirement_case: Mapping[str, Any],
    *,
    variant: str,
) -> list[dict[str, Any]]:
    """Build a controlled prompt while preserving question and media ordering."""
    if variant not in CONTROL_VARIANTS:
        raise ValueError("unknown controlled-reader variant")
    messages = deepcopy(product_row.get("prompt_messages"))
    if not isinstance(messages, list) or len(messages) != 2:
        raise ValueError("product row must retain the exact two-message reader prompt")
    user_content = messages[1].get("content")
    if not isinstance(user_content, list) or not user_content:
        raise ValueError("product reader prompt has no ordered user content")
    if variant == "product_context":
        return messages
    question_index = next((
        index for index, part in enumerate(user_content)
        if isinstance(part, dict)
        and part.get("type") == "text"
        and "### Question to answer:" in str(part.get("text") or "")
    ), None)
    if question_index is None:
        raise ValueError("reader prompt does not contain the frozen question block")
    question_and_media = user_content[question_index:]
    if variant == "verified_minimal_evidence":
        requirements = requirement_case.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            raise ValueError("verified control requires evaluator requirements")
        evidence = "\n\n".join(
            f"[{row['requirement_id']}] {row['verified_evidence_text']}"
            for row in requirements
        )
        intro = "### Memory context:\n" + evidence
    else:
        intro = "### Memory context:\n(empty)"
    messages[1]["content"] = [{"type": "text", "text": intro}, *question_and_media]
    return messages


def validate_controlled_reader_results(
    *,
    case_id: str,
    stages: Mapping[str, str],
    product_complete: bool,
    results: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if set(results) != set(CONTROL_VARIANTS):
        raise ValueError("controlled reader results must contain all three variants")
    identities = {str(row.get("reader_identity_sha256") or "") for row in results.values()}
    if len(identities) != 1 or "" in identities:
        raise ValueError("controlled inputs did not use one pinned reader identity")
    prompts = {str(row.get("reader_prompt_sha256") or "") for row in results.values()}
    if len(prompts) != 1 or "" in prompts:
        raise ValueError("controlled inputs did not use one pinned reader prompt")
    outcome = classify_longmem_outcome(
        stages=stages,
        product_complete=product_complete,
        product_reader=results["product_context"],
        verified_reader=results["verified_minimal_evidence"],
        no_memory_reader=results["no_memory"],
    )
    record = {
        "format": "atmem-longmemeval-controlled-attribution-v1",
        "case_id": case_id,
        "reader_identity_sha256": next(iter(identities)),
        "reader_prompt_sha256": next(iter(prompts)),
        "product_context_complete": product_complete,
        "terminal_outcome": outcome,
        "results": {name: dict(results[name]) for name in CONTROL_VARIANTS},
    }
    record["record_sha256"] = canonical_digest(record)
    return record


def execute_controlled_inputs(
    *,
    product_row: Mapping[str, Any],
    requirement_case: Mapping[str, Any],
    reader_identity_sha256: str,
    reader_prompt_sha256: str,
    call_reader,
    score_reader,
) -> dict[str, dict[str, Any]]:
    """Execute the two controls and normalize all three reader outcomes.

    ``call_reader`` and ``score_reader`` are injected so tests are no-cost and
    the paid runner can bind them to its already-finalized reader and grader.
    """
    if not reader_identity_sha256 or not reader_prompt_sha256:
        raise ValueError("controlled attribution requires pinned reader identities")
    results: dict[str, dict[str, Any]] = {}
    for variant in CONTROL_VARIANTS:
        messages = build_control_messages(
            product_row, requirement_case, variant=variant
        )
        if variant == "product_context":
            response = {
                "response_raw": product_row.get("response_raw"),
                "response_parsed_boxed": product_row.get("response_parsed_boxed"),
                "usage": product_row.get("usage"),
                "error_type": product_row.get("error_type"),
            }
        else:
            try:
                response = dict(call_reader(messages, variant))
            except TimeoutError:
                response = {"error_type": "timeout", "usage": None}
            except Exception as exc:  # preserved as a failed system outcome
                response = {
                    "error_type": "provider_error",
                    "error_class": type(exc).__name__,
                    "usage": None,
                }
        if response.get("error_type"):
            correct = False
        else:
            try:
                correct = bool(score_reader(response, variant))
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                response["error_type"] = "parse_error"
                response["error_class"] = type(exc).__name__
                correct = False
            except Exception as exc:
                response["error_type"] = "provider_error"
                response["error_class"] = type(exc).__name__
                correct = False
        results[variant] = {
            **response,
            "correct": correct,
            "reader_identity_sha256": reader_identity_sha256,
            "reader_prompt_sha256": reader_prompt_sha256,
            "messages_sha256": canonical_digest(messages),
        }
    return results
