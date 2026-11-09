from dataclasses import replace

import pytest

from atmem.context_engine.contracts import ContextRequestV3
from atmem.context_engine.formation import FormationManager, SourceEpisode, SourcePart
from atmem.context_engine.profiles import prepare_feedback_profile
from atmem.contracts.feedback import RetrievalProfileCandidate
from atmem.feedback.store import FeedbackError
from atmem.rules.lifecycle import RuleLifecycle
from test_feedback_review import review_fixture


def test_real_v3_disabled_parity_shadow_returns_native_and_unqualified_cannot_activate(tmp_path, monkeypatch):
    f, memory, review, rule = review_fixture(tmp_path)
    try:
        manager = FormationManager(memory.store)
        text = b"The project destination is staging."
        source = manager.retain_source(SourceEpisode("episode", f.scope.authority_scope(),
            (SourcePart("part", 0, "text", "text/plain", text),)))
        generation = manager.begin_generation(f.scope.authority_scope(), profile_id="context-fast")
        source_range = manager.add_range(source, "part", 0, len(text))
        manager.add_unit(generation, kind="fact", ranges=(source_range,),
                         compact_value={"subject": "project", "relation": "destination", "value": "staging"})
        manager.verify_generation(generation)
        manager.activate_generation(generation)
        current = manager.active_generation(f.scope.authority_scope())
        request = ContextRequestV3("context", "request", f.scope.authority_scope(), "Where is the project destination?",
                                   "context-fast", "shadow", current["canonical_generation"])
        baseline = memory.prepare_context_v3(request)
        with pytest.raises(FeedbackError, match="denied"):
            prepare_feedback_profile(f.feedback, replace(f.session, credential="invalid-credential"*2), request)
        disabled = prepare_feedback_profile(f.feedback, f.session, request)
        assert disabled.context == baseline.context and disabled.selected_unit_ids == baseline.selected_unit_ids
        profile = RetrievalProfileCandidate("profile", f.scope, rule.sources, candidate_budget=20, context_bytes=1024, balanced_pools=True)
        review.propose_feedback_profile(f.feedback, f.session, profile, idempotency_key="profile")
        authorization = memory.issue_review_authorization(f.user["principal_id"], scopes=("procedure:review",))
        review.decide_feedback_profile(f.feedback, f.session, profile_id="profile", candidate_sha256=profile.content_digest,
                                       decision="approve", reason="bounded shadow", authorization=authorization)
        RuleLifecycle(f.feedback).transition(f.owner["token"], f.scope, artifact_id="profile", kind="profile",
                                             state="shadow", expected_generation=0)
        shadow = prepare_feedback_profile(f.feedback, f.session, request, profile_id="profile", mode="shadow")
        assert shadow.context == baseline.context and shadow.selected_unit_ids == baseline.selected_unit_ids
        with f.feedback.store.transaction(f.scope) as tx:
            retained = tx.list("profile_comparison")
            assert len(retained) == 1 and retained[0]["delivery"] == "not_confirmed"
            assert retained[0]["candidate"]["budget"]["context_bytes"] == 1024
        with pytest.raises(FeedbackError, match="profile_unavailable"):
            prepare_feedback_profile(f.feedback, f.session, request, profile_id="profile", mode="active")
        with pytest.raises(FeedbackError, match="denied"):
            prepare_feedback_profile(f.feedback, f.session, replace(request, scope=replace(request.scope, workspace_id="other")))
        from feedback_lifecycle_fixtures import VERSIONS, seed_trusted_test_receipt
        from atmem.context_engine.service import GovernanceViolation, StoredContextEngine
        # This tests a qualification consumer, not an efficacy result.
        key = seed_trusted_test_receipt(f, profile)
        RuleLifecycle(f.feedback).transition(f.owner["token"], f.scope, artifact_id="profile", kind="profile",
            state="active", expected_generation=1, qualification_id=key, versions=VERSIONS)
        active = prepare_feedback_profile(f.feedback, f.session, request, profile_id="profile", mode="active", versions=VERSIONS)
        assert active.budget.context_bytes == 1024 and set(active.selected_unit_ids) <= set(baseline.selected_unit_ids)
        original_select = StoredContextEngine.select
        def unavailable(self, *args):
            if self.candidate_budget == 20:
                raise TimeoutError("PRIVATE PROFILE CONTENT")
            return original_select(self, *args)
        monkeypatch.setattr(StoredContextEngine, "select", unavailable)
        fallback = prepare_feedback_profile(f.feedback, f.session, request, profile_id="profile", mode="active", versions=VERSIONS)
        assert fallback.context == baseline.context and fallback.budget.context_bytes == 1024
        assert "feedback_profile_native_fallback" in fallback.reason_codes
        with f.feedback.store.transaction(f.scope) as tx:
            failed = tx.list("profile_comparison")[-1]
            assert failed["effective"] == "native_fallback" and failed["candidate"] is None
            assert "PRIVATE PROFILE CONTENT" not in str(failed)
        def invalid(self, *args):
            raise GovernanceViolation("scope violation")
        monkeypatch.setattr(StoredContextEngine, "select", invalid)
        with pytest.raises(GovernanceViolation):
            prepare_feedback_profile(f.feedback, f.session, request, profile_id="profile", mode="active", versions=VERSIONS)
        monkeypatch.setattr(StoredContextEngine, "select", original_select)
        memory.forget_record("alice", profile.sources[0].source_id)
        with pytest.raises(FeedbackError, match="stale_source"):
            prepare_feedback_profile(f.feedback, f.session, request, profile_id="profile", mode="active", versions=VERSIONS)
    finally:
        memory.close()
