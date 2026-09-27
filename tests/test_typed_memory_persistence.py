from __future__ import annotations

from dataclasses import replace

import pytest

from atmem import Memory
from atmem.contracts import AuthorityScope, SourceCaptureRequest
from atmem.core.canonical import sha256_hex
from atmem.extract import (
    AtomicFactPayload,
    DurableRulePayload,
    ExtractionProposal,
    MemoryClass,
    MemoryUnit,
    MemoryUnitKind,
    ProposalAction,
    ProposalEvidence,
)
from atmem.extract.review import ReviewPolicy, ReviewService


SCOPE = AuthorityScope("person-1", "agent-1", "workspace-1")
SOURCE = "I am 45 years old."


def typed_memory(path):
    return Memory(
        path,
        auto_vectors=False,
        allow_insecure_typed_development=True,
    )


def proposal(*, proposal_id: str = "proposal-1", unit_id: str = "unit-1"):
    evidence = (
        ProposalEvidence(
            source_id="source-1",
            source_sha256=f"sha256:{sha256_hex(SOURCE)}",
            start_offset=0,
            end_offset=len(SOURCE),
            excerpt_sha256=f"sha256:{sha256_hex(SOURCE)}",
        ),
    )
    unit = MemoryUnit(
        unit_id=unit_id,
        formation_id="formation-1",
        kind=MemoryUnitKind.ATOMIC_FACT,
        scope=SCOPE,
        payload=AtomicFactPayload("user", "age", "45"),
        evidence=evidence,
        confidence=1.0,
    )
    return ExtractionProposal(
        proposal_id=proposal_id,
        idempotency_key=f"key-{proposal_id}",
        scope=SCOPE,
        action=ProposalAction.ADD,
        memory_class=MemoryClass.DURABLE_FACT,
        confidence=1.0,
        reason_codes=("typed_structure",),
        evidence=evidence,
        fact=SOURCE,
        fact_key="user_age",
        unit=unit,
    )


def capture(memory: Memory, source_id: str = "source-1") -> None:
    memory.capture_source(
        SourceCaptureRequest(
            source_id=source_id,
            idempotency_key=f"capture-{source_id}",
            scope=SCOPE,
            message=SOURCE,
        )
    )


def test_typed_proposal_persists_source_once_and_survives_restart(tmp_path):
    path = tmp_path / "typed.db"
    memory = typed_memory(path)
    try:
        capture(memory)
        outcome = memory.submit_extraction_proposal(proposal(), source_text=SOURCE)
        assert outcome["review_state"] == "committed"
        record_id = outcome["record_ids"][0]
        record = memory.store.get_record(SCOPE.subject_id, record_id)
        assert record["raw"]["typed_unit"]["lifecycle"] == "active"
        stored = memory.store.get_typed_memory_unit(
            SCOPE.subject_id, SCOPE.workspace_id, "unit-1"
        )
        assert stored["record_id"] == record_id
        assert stored["unit"]["payload"] == {
            "subject": "user", "relation": "age", "value": "45", "polarity": "positive"
        }
        assert stored["evidence"][0]["source_id"] == "source-1"
        assert memory.store._conn.execute(
            "SELECT COUNT(*) AS count FROM protocol_sources"
        ).fetchone()["count"] == 1
        assert memory.store._conn.execute(
            "SELECT COUNT(*) AS count FROM episodes WHERE message = ?", (SOURCE,)
        ).fetchone()["count"] == 1
        committed_proposal = memory.store.get_memory_proposal("proposal-1")
        assert committed_proposal["proposal"]["redacted"] is True
        assert committed_proposal["fact_key"] is None
        captured = memory.store.get_protocol_source_by_id("source-1")
        assert "message" not in captured["request"]
    finally:
        memory.close()
    reopened = typed_memory(path)
    try:
        stored = reopened.store.get_typed_memory_unit(
            SCOPE.subject_id, SCOPE.workspace_id, "unit-1"
        )
        assert stored["lifecycle"] == "active"
        assert stored["unit"]["payload"]["value"] == "45"
    finally:
        reopened.close()


def test_typed_unit_lifecycle_and_source_deletion_follow_canonical_record(tmp_path):
    memory = typed_memory(tmp_path / "typed.db")
    try:
        capture(memory)
        outcome = memory.submit_extraction_proposal(proposal(), source_text=SOURCE)
        record_id = outcome["record_ids"][0]
        memory.forget_record(SCOPE.subject_id, record_id)
        stored = memory.store.get_typed_memory_unit(
            SCOPE.subject_id, SCOPE.workspace_id, "unit-1"
        )
        assert stored["lifecycle"] == "deleted"
        assert stored["unit"] is None
        source = memory.store.get_protocol_source_by_id("source-1")
        episode = memory.store._conn.execute(
            "SELECT message, raw FROM episodes WHERE id = ?", (source["episode_id"],)
        ).fetchone()
        assert episode["message"] == "[purged]"
        assert "45" not in episode["raw"]
        assert memory.store._conn.execute(
            "SELECT COUNT(*) AS count FROM record_search_terms WHERE record_id = ?",
            (record_id,),
        ).fetchone()["count"] == 0
        proposal_row = memory.store.get_memory_proposal("proposal-1")
        assert proposal_row["proposal"]["redacted"] is True
        assert "45" not in str(proposal_row["proposal"])
    finally:
        memory.close()


def test_typed_memory_class_mismatch_is_rejected_without_source_capture(tmp_path):
    memory = typed_memory(tmp_path / "typed.db")
    try:
        capture(memory)
        bad = replace(proposal(), memory_class=MemoryClass.PROCEDURE)
        outcome = memory.submit_extraction_proposal(bad, source_text=SOURCE)
        assert outcome["review_state"] == "rejected"
        assert "typed_unit_memory_class_mismatch" in outcome["reason_codes"]
        assert memory.store.get_protocol_source_by_id("source-1") is not None
        assert memory.store.get_typed_memory_unit(
            SCOPE.subject_id, SCOPE.workspace_id, "unit-1"
        ) is None
    finally:
        memory.close()


def test_shared_source_is_retained_until_last_typed_unit_is_deleted(tmp_path):
    memory = typed_memory(tmp_path / "typed.db")
    try:
        capture(memory)
        first = memory.submit_extraction_proposal(proposal(), source_text=SOURCE)
        second_proposal = proposal(proposal_id="proposal-2", unit_id="unit-2")
        second_proposal = replace(
            second_proposal,
            fact_key="user_age_statement",
            unit=replace(
                second_proposal.unit,
                payload=AtomicFactPayload("user", "age", "45 years old"),
            ),
        )
        second = memory.submit_extraction_proposal(second_proposal, source_text=SOURCE)
        memory.forget_record(SCOPE.subject_id, first["record_ids"][0])
        source = memory.store.get_protocol_source_by_id("source-1")
        episode = memory.store._conn.execute(
            "SELECT message FROM episodes WHERE id = ?", (source["episode_id"],)
        ).fetchone()
        assert episode["message"] == SOURCE
        memory.forget_record(SCOPE.subject_id, second["record_ids"][0])
        episode = memory.store._conn.execute(
            "SELECT message FROM episodes WHERE id = ?", (source["episode_id"],)
        ).fetchone()
        assert episode["message"] == "[purged]"
        assert memory.store._conn.execute(
            "SELECT COUNT(*) AS count FROM protocol_sources"
        ).fetchone()["count"] == 1
    finally:
        memory.close()


def test_purged_source_cannot_be_reactivated_and_new_source_can_reform(tmp_path):
    memory = typed_memory(tmp_path / "typed.db")
    try:
        capture(memory)
        first = memory.submit_extraction_proposal(proposal(), source_text=SOURCE)
        memory.forget_record(SCOPE.subject_id, first["record_ids"][0])
        with pytest.raises(ValueError, match="no longer retained"):
            memory.submit_extraction_proposal(
                proposal(proposal_id="proposal-2", unit_id="unit-2"),
                source_text=SOURCE,
            )
        capture(memory, "source-2")
        replacement = proposal(proposal_id="proposal-3", unit_id="unit-3")
        evidence = replace(replacement.evidence[0], source_id="source-2")
        replacement = replace(
            replacement,
            evidence=(evidence,),
            unit=replace(replacement.unit, evidence=(evidence,)),
        )
        outcome = memory.submit_extraction_proposal(replacement, source_text=SOURCE)
        assert outcome["review_state"] == "committed"
    finally:
        memory.close()


def test_duplicate_identity_is_a_deterministic_noop(tmp_path):
    memory = typed_memory(tmp_path / "typed.db")
    try:
        capture(memory)
        first = memory.submit_extraction_proposal(proposal(), source_text=SOURCE)
        duplicate = memory.submit_extraction_proposal(
            proposal(proposal_id="proposal-2", unit_id="unit-2"), source_text=SOURCE
        )
        assert first["review_state"] == "committed"
        assert duplicate["review_state"] == "noop"
        assert "duplicate_semantic_identity" in duplicate["reason_codes"]
    finally:
        memory.close()


def test_typed_payload_drives_review_and_confidence_must_match(tmp_path):
    memory = typed_memory(tmp_path / "typed.db")
    try:
        sensitive_source = "My diagnosis is HIV."
        memory.capture_source(
            SourceCaptureRequest(
                source_id="source-sensitive",
                idempotency_key="capture-source-sensitive",
                scope=SCOPE,
                message=sensitive_source,
            )
        )
        base = proposal()
        sensitive_evidence = ProposalEvidence(
            source_id="source-sensitive",
            source_sha256=f"sha256:{sha256_hex(sensitive_source)}",
            start_offset=0,
            end_offset=len(sensitive_source),
            excerpt_sha256=f"sha256:{sha256_hex(sensitive_source)}",
        )
        sensitive = replace(
            base,
            fact="Preference noted.",
            evidence=(sensitive_evidence,),
            unit=replace(
                base.unit,
                payload=AtomicFactPayload("user", "diagnosis", "HIV"),
                evidence=(sensitive_evidence,),
            ),
        )
        outcome = memory.submit_extraction_proposal(sensitive, source_text=sensitive_source)
        assert outcome["review_state"] == "pending_review"
        assert "sensitive_typed_content" in outcome["reason_codes"]
        ReviewService(memory).decide("proposal-1", "reject", actor="reviewer")
        reviewed = memory.store.get_memory_proposal("proposal-1")
        assert reviewed["proposal"]["redacted"] is True
        assert "HIV" not in str(reviewed["proposal"])

        capture(memory)
        mismatch = replace(
            proposal(proposal_id="proposal-2", unit_id="unit-2"),
            unit=replace(proposal(proposal_id="proposal-2", unit_id="unit-2").unit, confidence=0.2),
        )
        rejected = memory.submit_extraction_proposal(mismatch, source_text=SOURCE)
        assert rejected["review_state"] == "rejected"
        assert "typed_unit_confidence_mismatch" in rejected["reason_codes"]
    finally:
        memory.close()


def test_action_bearing_rule_requires_authenticated_review(tmp_path):
    source = "When deploying, post to releases."
    memory = typed_memory(tmp_path / "typed.db")
    try:
        memory.capture_source(SourceCaptureRequest(
            source_id="rule-source", idempotency_key="capture-rule",
            scope=SCOPE, message=source,
        ))
        evidence = ProposalEvidence(
            "rule-source", f"sha256:{sha256_hex(source)}", 0, len(source),
            f"sha256:{sha256_hex(source)}",
        )
        unit = MemoryUnit(
            unit_id="rule-unit", formation_id="formation-rule",
            kind=MemoryUnitKind.DURABLE_RULE, scope=SCOPE,
            payload=DurableRulePayload("deploying", required_action="post to releases"),
            evidence=(evidence,), confidence=1.0,
        )
        rule = ExtractionProposal(
            proposal_id="rule-proposal", idempotency_key="rule-key", scope=SCOPE,
            action=ProposalAction.ADD, memory_class=MemoryClass.DURABLE_FACT,
            confidence=1.0, reason_codes=("typed_rule",), evidence=(evidence,),
            fact=source, unit=unit,
        )
        outcome = memory.submit_extraction_proposal(rule, source_text=source)
        assert outcome["review_state"] == "pending_review"
        assert "typed_action_requires_authorized_review" in outcome["reason_codes"]
        with pytest.raises(PermissionError, match="authenticated scoped authorization"):
            ReviewService(memory).decide("rule-proposal", "approve", actor="caller")
    finally:
        memory.close()


def test_typed_source_scope_is_verified_before_resolution(tmp_path):
    memory = typed_memory(tmp_path / "typed.db")
    try:
        capture(memory)
        other = AuthorityScope("person-1", "agent-2", "workspace-2")
        base = proposal()
        forged = replace(base, scope=other, unit=replace(base.unit, scope=other))
        with pytest.raises(ValueError, match="not available in this authority scope"):
            memory.submit_extraction_proposal(forged, source_text=SOURCE)
    finally:
        memory.close()


def test_deleting_multi_source_unit_purges_every_unshared_source(tmp_path):
    memory = typed_memory(tmp_path / "typed.db")
    try:
        capture(memory)
        capture(memory, "source-2")
        base = proposal()
        second = replace(base.evidence[0], source_id="source-2")
        multi = replace(
            base,
            evidence=(base.evidence[0], second),
            unit=replace(base.unit, evidence=(base.evidence[0], second)),
        )
        outcome = memory.submit_extraction_proposal(multi, source_text=SOURCE)
        memory.forget_record(SCOPE.subject_id, outcome["record_ids"][0])
        for source_id in ("source-1", "source-2"):
            source = memory.store.get_protocol_source_by_id(source_id)
            assert source["result"]["retained"] is False
            episode = memory.store.get_episode(SCOPE.subject_id, source["episode_id"])
            assert episode["message"] == "[purged]"
    finally:
        memory.close()


def test_plaintext_household_refuses_typed_persistence_by_default(tmp_path):
    memory = Memory(tmp_path / "typed.db", auto_vectors=False)
    try:
        capture(memory)
        outcome = memory.submit_extraction_proposal(proposal(), source_text=SOURCE)
        assert outcome["review_state"] == "rejected"
        assert "typed_memory_requires_encrypted_household" in outcome["reason_codes"]
        assert not outcome["record_ids"]
    finally:
        memory.close()


def test_grounding_uses_each_retained_source_and_only_its_exact_span(tmp_path):
    memory = typed_memory(tmp_path / "typed.db")
    try:
        parts = {"source-subject": "I am discussing my age.", "source-value": "The value is 45."}
        evidence = []
        for source_id, body in parts.items():
            memory.capture_source(SourceCaptureRequest(
                source_id=source_id, idempotency_key=f"capture-{source_id}",
                scope=SCOPE, message=body,
            ))
            evidence.append(ProposalEvidence(
                source_id, f"sha256:{sha256_hex(body)}", 0, len(body),
                f"sha256:{sha256_hex(body)}",
            ))
        base = proposal()
        unit = replace(base.unit, evidence=tuple(evidence))
        item = replace(base, evidence=tuple(evidence), unit=unit)
        outcome = memory.submit_extraction_proposal(item, source_text="caller supplied text is ignored")
        assert outcome["review_state"] == "committed"

        narrow = replace(
            proposal(proposal_id="narrow-proposal", unit_id="narrow-unit"),
            evidence=(replace(evidence[1], start_offset=13, end_offset=15,
                              excerpt_sha256=f"sha256:{sha256_hex('45')}"),),
            unit=replace(
                base.unit, unit_id="narrow-unit",
                evidence=(replace(evidence[1], start_offset=13, end_offset=15,
                                  excerpt_sha256=f"sha256:{sha256_hex('45')}"),),
            ),
        )
        rejected = memory.submit_extraction_proposal(narrow, source_text=parts["source-value"])
        assert rejected["review_state"] == "rejected"
        assert "typed_subject_not_grounded_in_source" in rejected["reason_codes"]
    finally:
        memory.close()


def test_review_revalidates_source_and_custom_policy_cannot_bypass_action_review(tmp_path):
    class AllowEverything(ReviewPolicy):
        def requires_review(self, proposal):
            return ()

    source = "When deploying, post to releases."
    memory = Memory(
        tmp_path / "typed.db", auto_vectors=False,
        allow_insecure_typed_development=True,
        review_authorities=({
            "principal_id": "reviewer", "subject_id": SCOPE.subject_id,
            "agent_id": SCOPE.agent_id, "workspace_id": SCOPE.workspace_id,
            "scopes": ("procedure:review",),
        },),
    )
    try:
        memory.capture_source(SourceCaptureRequest(
            source_id="rule-source", idempotency_key="rule-capture", scope=SCOPE,
            message=source,
        ))
        evidence = ProposalEvidence(
            "rule-source", f"sha256:{sha256_hex(source)}", 0, len(source),
            f"sha256:{sha256_hex(source)}",
        )
        base = proposal()
        rule = replace(
            base, proposal_id="rule-review", idempotency_key="rule-review-key",
            evidence=(evidence,), fact=source,
            unit=MemoryUnit(
                unit_id="rule-review-unit", formation_id="rule-review-formation",
                kind=MemoryUnitKind.DURABLE_RULE, scope=SCOPE,
                payload=DurableRulePayload("deploying", required_action="post to releases"),
                evidence=(evidence,), confidence=1.0,
            ),
        )
        outcome = memory.submit_extraction_proposal(
            rule, source_text=source, review_policy=AllowEverything()
        )
        assert outcome["review_state"] == "pending_review"
        source_row = memory.store.get_protocol_source_by_id("rule-source")
        memory.store._conn.execute(
            "UPDATE episodes SET message = '[purged]' WHERE id = ?",
            (source_row["episode_id"],),
        )
        authorization = memory.issue_review_authorization(
            "reviewer", scopes=("procedure:review",)
        )
        reviewed = ReviewService(memory).decide(
            "rule-review", "approve", actor="reviewer", authorization=authorization
        )
        assert reviewed["review_state"] == "stale"
        assert "typed_evidence_no_longer_valid" in reviewed["reason_codes"]
        assert reviewed["typed_unit"] is None
    finally:
        memory.close()


def test_idempotent_replay_survives_source_deletion_and_noop_payload_is_redacted(tmp_path):
    memory = typed_memory(tmp_path / "typed.db")
    try:
        capture(memory)
        first = memory.submit_extraction_proposal(proposal(), source_text=SOURCE)
        replay = memory.submit_extraction_proposal(proposal(), source_text=SOURCE)
        assert replay["replayed"] is True
        duplicate = memory.submit_extraction_proposal(
            proposal(proposal_id="proposal-duplicate", unit_id="unit-duplicate"),
            source_text=SOURCE,
        )
        stored = memory.store.get_memory_proposal("proposal-duplicate")
        assert duplicate["review_state"] == "noop"
        assert stored["fact_key"] is None
        assert "45" not in str(stored["proposal"])
        memory.forget_record(SCOPE.subject_id, first["record_ids"][0])
        replay_after_delete = memory.submit_extraction_proposal(proposal(), source_text=SOURCE)
        assert replay_after_delete["replayed"] is True
    finally:
        memory.close()


def test_default_plaintext_rejection_does_not_store_typed_only_secret(tmp_path):
    path = tmp_path / "typed.db"
    memory = Memory(path, auto_vectors=False)
    try:
        capture(memory)
        base = proposal()
        typed_only = replace(
            base,
            unit=replace(base.unit, payload=AtomicFactPayload("user", "age", "45-TYPED-ONLY-SECRET")),
        )
        outcome = memory.submit_extraction_proposal(typed_only, source_text=SOURCE)
        assert outcome["review_state"] == "rejected"
    finally:
        memory.close()
    assert b"45-TYPED-ONLY-SECRET" not in path.read_bytes()
