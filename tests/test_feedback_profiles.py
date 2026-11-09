from dataclasses import replace

import pytest

from atmem.context_engine.contracts import ContextRequestV3
from atmem.context_engine.formation import FormationManager, SourceEpisode, SourcePart
from atmem.context_engine.profiles import prepare_feedback_profile
from atmem.contracts.feedback import RetrievalProfileCandidate
from atmem.feedback.store import FeedbackError
from atmem.rules.lifecycle import RuleLifecycle
from test_feedback_review import review_fixture


def test_real_v3_disabled_parity_shadow_returns_native_and_unqualified_cannot_activate(tmp_path):
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
    finally:
        memory.close()
