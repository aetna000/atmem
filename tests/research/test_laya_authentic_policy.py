import copy

import pytest

from research.laya_memory_evidence.policy import (
    FINAL_MANIFEST_FORMAT,
    REQUIRED_REVIEW_VIEWS,
    validate_final_manifest,
)


def _manifest():
    judge = {
        "first_pass_rows": 100_000,
        "completed_review_views": sorted(REQUIRED_REVIEW_VIEWS),
        "frozen_before_comparison": True,
    }
    return {
        "format": FINAL_MANIFEST_FORMAT,
        "manifest_digest": "sha256:valid",
        "conversation_content_policy": "human_user_turns_actual_interactions_v1",
        "gates": {
            "accepted_rows": 100_000,
            "generated_conversation_rows": 0,
            "translated_conversation_rows": 0,
            "hand_authored_conversation_rows": 0,
            "codex_complete": True,
            "claude_complete": True,
            "self_review_complete": True,
            "global_duplicate_graph_complete": True,
            "language_allocation_exact": True,
            "split_isolation_complete": True,
            "privacy_scan_clear": True,
            "license_review_complete": True,
        },
        "sources": [{
            "source_id": "real-public-conversations",
            "revision": "immutable-revision",
            "license": "reviewed-license",
            "collection_method": "organic human assistant conversations",
            "human_origin_evidence": "dataset collection methodology",
        }],
        "labeling": {
            "mode": "dual_codex_claude",
            "codex": copy.deepcopy(judge),
            "claude": copy.deepcopy(judge),
        },
    }


def test_accepts_complete_authentic_manifest():
    validate_final_manifest(_manifest())


def test_accepts_disclosed_codex_only_fallback():
    manifest = _manifest()
    manifest["labeling"]["mode"] = "codex_only_credit_exhausted"
    del manifest["labeling"]["claude"]
    manifest["gates"]["claude_complete"] = False
    validate_final_manifest(manifest)


@pytest.mark.parametrize("field", [
    "generated_conversation_rows",
    "translated_conversation_rows",
    "hand_authored_conversation_rows",
])
def test_rejects_any_non_authentic_conversation_content(field):
    manifest = _manifest()
    manifest["gates"][field] = 1
    with pytest.raises(ValueError, match="authentic dataset gates failed"):
        validate_final_manifest(manifest)


def test_rejects_locomo_even_when_counts_claim_zero():
    manifest = _manifest()
    manifest["sources"][0]["source_id"] = "LoCoMo"
    with pytest.raises(ValueError, match="forbidden"):
        validate_final_manifest(manifest)


def test_rejects_missing_judge_review_view():
    manifest = _manifest()
    manifest["labeling"]["claude"]["completed_review_views"].remove("scope_chronology")
    with pytest.raises(ValueError, match="self-review"):
        validate_final_manifest(manifest)
