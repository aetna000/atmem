"""Fail-closed policy for authentic-conversation training artifacts."""

from __future__ import annotations

from typing import Any


FINAL_MANIFEST_FORMAT = "atmem-authentic-memory-decisions-manifest-v1"
REQUIRED_REVIEW_VIEWS = frozenset({
    "duplicate_clusters",
    "scope_chronology",
    "stratified",
    "contradiction_outliers",
})
FORBIDDEN_SOURCE_MARKERS = ("locomo", "synthetic", "generated", "fictional", "translated")


def validate_final_manifest(
    manifest: dict[str, Any], *, expected_rows: int | None = None,
    minimum_rows: int = 20_000, target_rows: int = 100_000,
) -> None:
    if manifest.get("format") != FINAL_MANIFEST_FORMAT:
        raise ValueError("only the finalized authentic memory-decisions manifest is eligible")
    if not isinstance(manifest.get("manifest_digest"), str) or not manifest["manifest_digest"]:
        raise ValueError("final manifest digest is missing")

    gates = manifest.get("gates", {})
    accepted_rows = gates.get("accepted_rows")
    if not isinstance(accepted_rows, int) or not minimum_rows <= accepted_rows <= target_rows:
        raise ValueError(
            f"accepted rows must be between {minimum_rows:,} and {target_rows:,}"
        )
    if expected_rows is not None and accepted_rows != expected_rows:
        raise ValueError(f"manifest contains {accepted_rows:,} rows, expected {expected_rows:,}")
    if accepted_rows < target_rows and not manifest.get("stop_reason"):
        raise ValueError("a corpus below the target requires an evidence-bound stop reason")
    expected = {
        "generated_conversation_rows": 0,
        "translated_conversation_rows": 0,
        "hand_authored_conversation_rows": 0,
        "codex_complete": True,
        "self_review_complete": True,
        "global_duplicate_graph_complete": True,
        "language_allocation_exact": True,
        "split_isolation_complete": True,
        "privacy_scan_clear": True,
        "license_review_complete": True,
    }
    failures = {
        key: {"expected": value, "actual": gates.get(key)}
        for key, value in expected.items() if gates.get(key) != value
    }
    if failures:
        raise ValueError(f"authentic dataset gates failed: {failures}")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("source provenance inventory is missing")
    for source in sources:
        required = ("source_id", "revision", "license", "collection_method", "human_origin_evidence")
        if any(not source.get(field) for field in required):
            raise ValueError("source provenance is incomplete")
        identity = " ".join(str(source.get(field, "")) for field in required).casefold()
        if any(marker in identity for marker in FORBIDDEN_SOURCE_MARKERS):
            raise ValueError("forbidden generated/synthetic/translated source marker")

    labeling = manifest.get("labeling", {})
    mode = labeling.get("mode")
    if mode not in {"dual_codex_claude", "codex_only_credit_exhausted"}:
        raise ValueError("unknown labeling mode")
    required_judges = ("codex", "claude") if mode == "dual_codex_claude" else ("codex",)
    if gates.get("claude_complete") is not (mode == "dual_codex_claude"):
        raise ValueError("Claude completion gate does not match labeling mode")
    for judge in required_judges:
        record = labeling.get(judge, {})
        if record.get("first_pass_rows") < accepted_rows:
            raise ValueError(f"{judge} first-pass coverage is incomplete")
        if set(record.get("completed_review_views", ())) != REQUIRED_REVIEW_VIEWS:
            raise ValueError(f"{judge} self-review coverage is incomplete")
        if record.get("frozen_before_comparison") is not True:
            raise ValueError(f"{judge} was not frozen before comparison")

    if manifest.get("conversation_content_policy") != "human_user_turns_actual_interactions_v1":
        raise ValueError("authentic human-origin conversation policy is not bound")
