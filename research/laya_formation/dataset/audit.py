from __future__ import annotations

import base64
from collections import Counter
import hashlib
import random
from typing import Any, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from atmem.core.canonical import canonical_json

from .models import FormationScenarioV1, TypedDecisionExampleV1


HIGH_RISK_TAGS = ("sensitive", "credential", "private_scope", "cross_scope", "contradiction")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode()).hexdigest()


def build_blinded_audit_packet(
    scenarios: Iterable[FormationScenarioV1],
    examples: Iterable[TypedDecisionExampleV1],
    *,
    sample_size: int = 400,
    minimum_per_high_risk_tag: int = 60,
    seed: int = 410240,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if sample_size < minimum_per_high_risk_tag:
        raise ValueError("audit sample cannot satisfy its per-tag minimum")
    scenario_map = {row.scenario_id: row for row in scenarios if row.split != "sealed_test"}
    candidates = [row for row in examples if row.split != "sealed_test" and row.scenario_id in scenario_map]
    rng = random.Random(seed)
    rng.shuffle(candidates)
    selected: dict[str, TypedDecisionExampleV1] = {}
    for tag in HIGH_RISK_TAGS:
        tagged = [row for row in candidates if tag in scenario_map[row.scenario_id].safety_tags]
        for row in tagged:
            if sum(tag in scenario_map[item.scenario_id].safety_tags for item in selected.values()) >= minimum_per_high_risk_tag:
                break
            selected[row.example_id] = row
        if sum(tag in scenario_map[item.scenario_id].safety_tags for item in selected.values()) < minimum_per_high_risk_tag:
            raise ValueError(f"insufficient non-sealed audit coverage for {tag}")
    for row in candidates:
        if len(selected) >= sample_size:
            break
        selected[row.example_id] = row
    if len(selected) != sample_size:
        raise ValueError("insufficient non-sealed decisions for audit packet")
    ordered = sorted(selected.values(), key=lambda row: row.example_id)
    packet_rows = [
        {
            "example_id": row.example_id,
            "question_id": row.question_id,
            "authorized_input": row.authorized_input,
            "choice_ids": list(row.choice_ids),
            "safety_tags": list(scenario_map[row.scenario_id].safety_tags),
        }
        for row in ordered
    ]
    answer_rows = [
        {
            "example_id": row.example_id,
            "expected_choice_ids": list(row.expected_choice_ids),
            "oracle_receipt": row.oracle_receipt,
            "audit_rationale": row.audit_rationale,
        }
        for row in ordered
    ]
    tag_counts = Counter(tag for row in ordered for tag in scenario_map[row.scenario_id].safety_tags)
    packet = {
        "format": "atmem-laya-blinded-audit-packet-v1",
        "seed": seed,
        "sealed_rows": 0,
        "sample_size": len(packet_rows),
        "high_risk_tag_counts": dict(sorted(tag_counts.items())),
        "rows": packet_rows,
    }
    answer_key = {
        "format": "atmem-laya-audit-answer-key-v1",
        "independent_reviewer_required": True,
        "rows": answer_rows,
    }
    return packet, answer_key


def validate_audit_result(result: dict[str, Any]) -> None:
    if result.get("format") != "atmem-laya-audit-result-v1":
        raise ValueError("unsupported audit result")
    reviewed = result.get("reviewed")
    correct = result.get("correct")
    if not isinstance(reviewed, int) or reviewed < 400 or not isinstance(correct, int):
        raise ValueError("audit requires at least 400 reviewed rows")
    if correct / reviewed < 0.99:
        raise ValueError("audit target correctness is below 99 percent")
    if result.get("critical_findings") != 0:
        raise ValueError("critical audit findings block publication")
    if not result.get("reviewer") or not result.get("signed_at"):
        raise ValueError("audit result requires reviewer identity and signature time")


def build_review_template(packet: dict[str, Any]) -> dict[str, Any]:
    if packet.get("format") != "atmem-laya-blinded-audit-packet-v1":
        raise ValueError("unsupported audit packet")
    return {
        "format": "atmem-laya-audit-review-v1",
        "packet_sha256": _digest(packet),
        "reviewer": {
            "id": "",
            "kind": "human-or-independent-model",
            "independent_attestation": True,
            "answer_key_accessed": False,
        },
        "signed_at": "",
        "rows": [
            {
                "example_id": row["example_id"],
                "selected_choice_ids": [],
                "critical_findings": [],
            }
            for row in packet["rows"]
        ],
    }


def sign_audit_review(review: dict[str, Any], private_key_pem: bytes) -> dict[str, Any]:
    if "signature" in review:
        raise ValueError("review is already signed")
    private = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("audit review requires an Ed25519 private key")
    payload = canonical_json(review).encode()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        **review,
        "signature": {
            "algorithm": "ed25519",
            "public_key_base64": base64.b64encode(public).decode(),
            "signed_payload_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "value_base64": base64.b64encode(private.sign(payload)).decode(),
        },
    }


def verify_audit_review(review: dict[str, Any]) -> None:
    signature = review.get("signature")
    if not isinstance(signature, dict) or signature.get("algorithm") != "ed25519":
        raise ValueError("audit review requires an Ed25519 signature")
    unsigned = {key: value for key, value in review.items() if key != "signature"}
    payload = canonical_json(unsigned).encode()
    expected_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    if signature.get("signed_payload_sha256") != expected_digest:
        raise ValueError("audit review signed payload digest mismatch")
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(signature["public_key_base64"], validate=True))
        public.verify(base64.b64decode(signature["value_base64"], validate=True), payload)
    except (InvalidSignature, KeyError, TypeError, ValueError) as exc:
        raise ValueError("audit review signature verification failed") from exc


def score_audit_review(
    packet: dict[str, Any], answer_key: dict[str, Any], review: dict[str, Any]
) -> dict[str, Any]:
    verify_audit_review(review)
    if review.get("format") != "atmem-laya-audit-review-v1":
        raise ValueError("unsupported audit review")
    if review.get("packet_sha256") != _digest(packet):
        raise ValueError("review does not bind the supplied audit packet")
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, dict) or not reviewer.get("id"):
        raise ValueError("reviewer identity is required")
    if reviewer.get("independent_attestation") is not True or reviewer.get("answer_key_accessed") is not False:
        raise ValueError("reviewer independence attestation failed")
    packet_rows = {row["example_id"]: row for row in packet.get("rows", [])}
    answer_rows = {row["example_id"]: row for row in answer_key.get("rows", [])}
    review_rows = {row.get("example_id"): row for row in review.get("rows", [])}
    if len(review_rows) != len(review.get("rows", [])):
        raise ValueError("duplicate review example id")
    if set(packet_rows) != set(answer_rows) or set(packet_rows) != set(review_rows):
        raise ValueError("audit packet, answer key and review membership differ")
    correct = 0
    critical_findings = 0
    for example_id, row in review_rows.items():
        selected = row.get("selected_choice_ids")
        if not isinstance(selected, list) or len(selected) != 1:
            raise ValueError(f"audit row {example_id} requires exactly one selected choice")
        if not set(selected).issubset(packet_rows[example_id]["choice_ids"]):
            raise ValueError(f"audit row {example_id} selects an unknown choice")
        findings = row.get("critical_findings")
        if not isinstance(findings, list) or not all(isinstance(item, str) and item.strip() for item in findings):
            raise ValueError(f"audit row {example_id} has malformed critical findings")
        critical_findings += len(findings)
        correct += selected == answer_rows[example_id]["expected_choice_ids"]
    result = {
        "format": "atmem-laya-audit-result-v1",
        "packet_sha256": _digest(packet),
        "answer_key_sha256": _digest(answer_key),
        "review_sha256": _digest(review),
        "reviewed": len(review_rows),
        "correct": correct,
        "accuracy": correct / len(review_rows),
        "critical_findings": critical_findings,
        "reviewer": reviewer["id"],
        "reviewer_kind": reviewer.get("kind"),
        "signed_at": review.get("signed_at"),
        "signature": review["signature"],
    }
    validate_audit_result(result)
    return result
