from __future__ import annotations

import json
from pathlib import Path

from atmem import Memory
from atmem.context_engine.formation import FormationManager, SourceEpisode, SourcePart
from atmem.contracts import (
    AuthorityScope, EpisodeIngestRequest, EpisodePart, SourceCaptureRequest,
)
from atmem.core.canonical import sha256_hex
from atmem.laya_formation.artifacts import ArtifactBundle
from atmem.laya_formation.contracts import (
    CalibrationBinding, FormationDecisionResponse, SUPPORTED_QUESTIONS_DIGEST,
)
from atmem.laya_formation.integration import FormationProfileRouter
from atmem.store.sqlite import SQLiteStore


SCOPE = AuthorityScope("formation-user", "formation-agent", "formation-workspace")


class ExactPacker:
    revision = "tokenizer-revision"

    def head_token_count(self, question, head_max_len):
        return 8, len(question["crit"])

    def serialize_and_encode_state(self, state):
        value = json.dumps(state, sort_keys=True, separators=(",", ":"))
        return value, list(value.encode())


def calibration() -> CalibrationBinding:
    return CalibrationBinding(
        model_sha256="f" * 64,
        questions_digest=SUPPORTED_QUESTIONS_DIGEST,
        calibration_digest="b165d4b7d554cdbda5a889baf7059c3f43ba2774d68754e4fa3aeb63f5f0e067",
        method="per-question-temperature-and-abstention-v1",
        temperatures=(1.0, 1.0, 1.0),
        temperature_by_options={"choice:3-5": 1.0},
        thresholds={"choice:3-5": 0.5},
    )


QUESTIONS = {
    "operation": {"instructions": "Choose the operation.", "choice_ids": ["ADD", "UPDATE", "SUPERSEDE", "NOOP", "REJECT"]},
    "memory_class": {"instructions": "Choose the memory class.", "choice_ids": ["durable_fact", "temporary_state", "episode", "procedure", "non_memory"]},
    "evidence_support": {"instructions": "Choose evidence support.", "choice_ids": ["SUPPORTED", "AMBIGUOUS", "UNSUPPORTED"]},
    "target_selection": {"instructions": "Choose the target.", "choice_ids": ["target:active", "target:none", "REVIEW"]},
    "retrieval_usefulness": {"instructions": "Choose usefulness.", "choice_ids": ["USEFUL", "NOT_USEFUL", "INSUFFICIENT_EVIDENCE"]},
}


def bundle(root: Path) -> ArtifactBundle:
    value = calibration()
    return ArtifactBundle(
        root=root,
        repo_id="atmem/atmem-laya-formation-model-v1",
        revision="1" * 40,
        model_sha256=value.model_sha256,
        questions_digest=value.questions_digest,
        calibration_digest=value.calibration_digest,
        export_digest="e" * 64,
        calibration=value,
        questions=QUESTIONS,
    )


class Profile:
    def __init__(self, active=True): self.active = active

    def active_profile(self):
        if not self.active:
            return None
        return {
            "active": True,
            "verified": True,
            "model_dir": "/verified/model",
            "device": "cpu",
            "escalation": {"enabled": False},
        }


class Resolver:
    def __init__(self, value): self.value = value
    def verify(self, _root): return self.value


class Engine:
    def __init__(self, value, *, device):
        self.bundle = value
        self.device = device
        self.packing_adapter = ExactPacker()
        self.calls = []

    def __call__(self, request):
        self.calls.append(request)
        selected = request.question.choice_ids[0]
        scores = {choice: float(choice == selected) for choice in request.question.choice_ids}
        return FormationDecisionResponse(
            request_id=request.request_id,
            selected_choice_ids=(selected,),
            calibrated_scores=scores,
            confidence=1.0,
            abstained=False,
            reason_code="test_choice",
        )

    def close(self): pass


def formed_store():
    store = SQLiteStore(":memory:")
    manager = FormationManager(store)
    source_id = manager.retain_source(SourceEpisode(
        episode_id="episode-1",
        scope=SCOPE,
        parts=(SourcePart("part-1", 0, "text", "text/plain", b"I prefer blue."),),
    ))
    generation_id = manager.begin_generation(SCOPE, profile_id="context-fast")
    manager.form_source(source_id, generation_id, range_granularity="sentence")
    return store, source_id, generation_id


def test_inactive_profile_is_byte_safe_deterministic_route(tmp_path: Path) -> None:
    store, source_id, generation_id = formed_store()
    try:
        router = FormationProfileRouter(
            profile_manager=Profile(False),
            resolver=Resolver(bundle(tmp_path)),
            engine_factory=Engine,
        )
        result = router.decide_source(
            store=store, source_id=source_id, generation_id=generation_id
        )
        assert result["profile"] == "deterministic"
        assert result["active"] is False
        assert result["decisions"] == []
    finally:
        store.close()


def test_active_profile_runs_all_bound_questions_and_retains_non_authoritative_receipts(tmp_path: Path) -> None:
    store, source_id, generation_id = formed_store()
    engines = []

    def make_engine(value, *, device):
        engine = Engine(value, device=device)
        engines.append(engine)
        return engine

    try:
        router = FormationProfileRouter(
            profile_manager=Profile(True),
            resolver=Resolver(bundle(tmp_path)),
            engine_factory=make_engine,
        )
        result = router.decide_source(
            store=store, source_id=source_id, generation_id=generation_id
        )
        assert result["active"] is True and result["fallback"] is False
        assert {row["question_id"] for row in result["decisions"]} == set(QUESTIONS)
        assert len(engines[0].calls) == 5
        for row in result["decisions"]:
            receipt = row["receipt"]
            assert receipt["authorizes_mutation"] is False
            assert receipt["final_disposition"] == "proposal_retained_deterministic_authority"
            assert receipt["included_range_ids"]
            assert receipt["request_digest"].startswith("sha256:")
    finally:
        store.close()


def test_active_profile_runs_on_ordinary_captured_source(tmp_path: Path) -> None:
    memory = Memory(":memory:", auto_vectors=False)
    engines = []

    def make_engine(value, *, device):
        engine = Engine(value, device=device)
        engines.append(engine)
        return engine

    try:
        text = "I prefer blue."
        source_id = "protocol-source-1"
        memory.capture_source(SourceCaptureRequest(
            source_id=source_id,
            idempotency_key="protocol-key-1",
            scope=SCOPE,
            message=text,
            source_type="user_message",
        ))
        router = FormationProfileRouter(
            profile_manager=Profile(True),
            resolver=Resolver(bundle(tmp_path)),
            engine_factory=make_engine,
        )

        result = router.decide_protocol_source(
            store=memory.store, scope=SCOPE, source_id=source_id, text=text,
        )

        assert result["active"] is True
        assert result["fallback"] is False
        assert len(engines[0].calls) == 5
        assert all(
            row["receipt"]["authorizes_mutation"] is False
            for row in result["decisions"]
        )
    finally:
        memory.close()


def test_authority_applies_only_consistent_source_grounded_view_classification() -> None:
    store, source_id, generation_id = formed_store()
    try:
        manager = FormationManager(store)
        decisions = (
            {"question_id": "operation", "selected_choice_ids": ["ADD"]},
            {"question_id": "memory_class", "selected_choice_ids": ["durable_fact"]},
            {"question_id": "evidence_support", "selected_choice_ids": ["SUPPORTED"]},
            {"question_id": "target_selection", "selected_choice_ids": ["target:none"]},
            {"question_id": "retrieval_usefulness", "selected_choice_ids": ["USEFUL"]},
        )
        result = manager.apply_laya_decisions(source_id, generation_id, decisions)
        assert result["status"] == "authorized_mutation_committed"
        assert result["authorized_views"] == ("fact", "raw_state")
        views = {
            str(row["kind"])
            for row in store._conn.execute(
                "SELECT kind FROM context_unit_views WHERE generation_id=?",
                (generation_id,),
            ).fetchall()
        }
        assert views == {"fact", "raw_state"}

        ambiguous = tuple(
            {**row, "selected_choice_ids": ["AMBIGUOUS"]}
            if row["question_id"] == "evidence_support" else row
            for row in decisions
        )
        blocked = manager.apply_laya_decisions(source_id, generation_id, ambiguous)
        assert blocked["status"] == "review_required"
        assert blocked["authorizes_mutation"] is False
        assert blocked["policy_withheld_semantic_views"] is True
        assert {
            str(row["kind"])
            for row in store._conn.execute(
                "SELECT kind FROM context_unit_views WHERE generation_id=?",
                (generation_id,),
            ).fetchall()
        } == {"raw_state"}

        abstained = tuple(
            {**row, "selected_choice_ids": []}
            if row["question_id"] == "operation" else row
            for row in decisions
        )
        withheld = manager.apply_laya_decisions(
            source_id, generation_id, abstained
        )
        assert withheld["reason_code"] == "incomplete_or_abstained_decision_set"
        assert withheld["authorized_views"] == ("raw_state",)
    finally:
        store.close()


class LiveRouter:
    def __init__(self): self.calls = []

    def decide_source(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "format": "atmem-live-formation-intelligence-v1",
            "profile": "laya-formation-v1",
            "active": True,
            "fallback": False,
            "reason_code": "bounded_laya_decisions_completed",
            "decisions": [{
                "question_id": "operation",
                "selected_choice_ids": ["ADD"],
                "receipt": {
                    "format": "atmem-formation-decision-receipt-v1",
                    "request_id": "request-1",
                    "authorizes_mutation": False,
                    "final_disposition": "proposal_retained_deterministic_authority",
                },
            }],
        }

    def decide_protocol_source(self, **kwargs):
        return self.decide_source(**kwargs)


def test_live_context_formation_invokes_router_and_audits_decision() -> None:
    router = LiveRouter()
    memory = Memory(
        ":memory:", auto_vectors=False, allow_insecure_typed_development=True,
        review_authorities=({
            "principal_id": "importer", "subject_id": SCOPE.subject_id,
            "agent_id": SCOPE.agent_id, "workspace_id": SCOPE.workspace_id,
            "scopes": ("history_import:review",),
        },),
        formation_router=router,
    )
    try:
        text = "I prefer blue."
        request = EpisodeIngestRequest(
            episode_id="live-episode",
            idempotency_key="live-key",
            scope=SCOPE,
            parts=(EpisodePart(
                part_id="part-1", ordinal=0, kind="text",
                source_type="user_message", content=text,
                content_sha256="sha256:" + sha256_hex(text),
            ),),
            binding_method="host_asserted",
            binding_assurance="host_asserted",
            source_observation_granularity="sentence",
        )
        result = memory.form_context_episode(
            request, history_import_principal="importer"
        )
        assert router.calls
        assert result["formation_intelligence"]["profile"] == "laya-formation-v1"
        events = memory.store.list_audit_events(SCOPE.subject_id)
        recorded = [row for row in events if row["event_type"] == "memory.formation_decision_recorded"]
        assert len(recorded) == 1
        assert recorded[0]["payload"]["receipt"]["authorizes_mutation"] is False
    finally:
        memory.close()


def test_ordinary_form_episode_invokes_selected_profile_and_returns_receipts() -> None:
    router = LiveRouter()
    memory = Memory(
        ":memory:", auto_vectors=False, allow_insecure_typed_development=True,
        formation_router=router,
    )
    try:
        text = "I prefer blue."
        request = EpisodeIngestRequest(
            episode_id="ordinary-live-episode",
            idempotency_key="ordinary-live-key",
            scope=SCOPE,
            parts=(EpisodePart(
                part_id="part-1", ordinal=0, kind="text",
                source_type="user_message", content=text,
                content_sha256="sha256:" + sha256_hex(text),
            ),),
        )

        result = memory.form_episode(request)

        assert len(router.calls) == 1
        assert result["formation_intelligence"][0]["active"] is True
        assert result["formation_intelligence"][0]["decisions"][0][
            "selected_choice_ids"
        ] == ["ADD"]
        events = memory.store.list_audit_events(SCOPE.subject_id)
        assert any(
            row["event_type"] == "memory.formation_decision_recorded"
            for row in events
        )
    finally:
        memory.close()


def test_active_profile_runtime_failure_keeps_deterministic_result(tmp_path: Path) -> None:
    store, source_id, generation_id = formed_store()

    class BrokenResolver:
        def verify(self, _root): raise OSError("model unavailable")

    try:
        result = FormationProfileRouter(
            profile_manager=Profile(True), resolver=BrokenResolver(),
        ).decide_source(store=store, source_id=source_id, generation_id=generation_id)
        assert result["active"] is True
        assert result["fallback"] is True
        assert result["profile"] == "deterministic"
        assert result["reason_code"] == "laya_runtime_OSError"
    finally:
        store.close()


def test_v2_active_path_never_runs_deterministic_semantic_reconciliation() -> None:
    class V2Router:
        def __init__(self): self.calls = 0

        def decide_protocol_transition_v2(self, **kwargs):
            self.calls += 1
            assert kwargs["retrieved_records"] == ()
            return {
                "format": "atmem-live-formation-transition-v2",
                "profile": "laya-formation-v2", "active": True,
                "authority_result": "AUTHORIZED_PROPOSAL",
                "reason_code": "governance_revalidation_passed",
                "authorized_target_records": [], "question_receipts": [],
                "ruling": {
                    "format": "atmem-formation-ruling-v2",
                    "operation": "STORE_NEW", "memory_class": "preference",
                    "target_memory_id": None,
                    "operation_probability": 0.93, "target_probability": None,
                    "context_sufficient_probability": 0.98,
                    "durable_probability": 0.96, "future_utility_score": 3.8,
                    "review_required": False, "review_reason": None,
                    "plan_version": "memory-formation-plan-v2",
                },
            }

    router = V2Router()
    memory = Memory(
        ":memory:", auto_vectors=False, allow_insecure_typed_development=True,
        formation_router=router,
    )
    try:
        def forbidden(_proposal):
            raise AssertionError("deterministic semantic classifier ran in Laya mode")

        memory._reconcile_typed_proposal = forbidden
        text = "My preferred colour is blue."
        result = memory.form_episode(EpisodeIngestRequest(
            episode_id="v2-live-episode", idempotency_key="v2-live-key",
            scope=SCOPE,
            parts=(EpisodePart(
                part_id="part-1", ordinal=0, kind="text",
                source_type="user_message", content=text,
                content_sha256="sha256:" + sha256_hex(text),
            ),),
        ))
        assert router.calls == 1
        assert result["outcomes"][0]["review_state"] == "committed"
        assert "laya_v2_semantic_ruling" in result["outcomes"][0]["reason_codes"]
        events = memory.store.list_audit_events(SCOPE.subject_id)
        assert any(
            row["event_type"] == "memory.formation_transition_recorded"
            for row in events
        )
    finally:
        memory.close()


def test_legacy_remember_converges_on_v2_without_double_classification() -> None:
    class V2Router:
        def __init__(self):
            self.calls = 0

        def uses_v2_semantic_authority(self):
            return True

        def decide_protocol_transition_v2(self, **kwargs):
            self.calls += 1
            return {
                "format": "atmem-live-formation-transition-v2",
                "profile": "laya-formation-v2", "active": True,
                "authority_result": "AUTHORIZED_PROPOSAL",
                "reason_code": "governance_revalidation_passed",
                "authorized_target_records": [], "question_receipts": [],
                "ruling": {
                    "format": "atmem-formation-ruling-v2",
                    "operation": "STORE_NEW", "memory_class": "preference",
                    "target_memory_id": None, "operation_probability": 1.0,
                    "target_probability": None,
                    "context_sufficient_probability": 1.0,
                    "durable_probability": 1.0, "future_utility_score": 4.0,
                    "review_required": False, "review_reason": None,
                    "plan_version": "memory-formation-plan-v2",
                },
            }

    router = V2Router()
    memory = Memory(
        ":memory:", auto_vectors=False, allow_insecure_typed_development=True,
        formation_router=router,
    )
    try:
        memory._reconcile_typed_proposal = lambda _proposal: (_ for _ in ()).throw(
            AssertionError("deterministic semantic classifier ran in Laya mode")
        )
        result = memory.remember(
            SCOPE.subject_id, "I prefer compact status reports.",
            raw={"agent_id": SCOPE.agent_id, "workspace_id": SCOPE.workspace_id},
        )
        assert router.calls == 1
        assert result["records"]
        assert result["formation_intelligence"][0]["profile"] == "laya-formation-v2"
    finally:
        memory.close()


def test_force_flag_cannot_bypass_selected_v2_semantic_authority() -> None:
    class ReviewRouter:
        def __init__(self):
            self.calls = 0

        def uses_v2_semantic_authority(self):
            return True

        def decide_protocol_transition_v2(self, **_kwargs):
            self.calls += 1
            return {
                "format": "atmem-live-formation-transition-v2",
                "profile": "laya", "active": True,
                "authority_result": "REVIEW", "ruling": None,
                "question_receipts": [], "reason_code": "model_unavailable",
            }

    router = ReviewRouter()
    memory = Memory(
        ":memory:", auto_vectors=False, allow_insecure_typed_development=True,
        formation_router=router,
    )
    try:
        result = memory.remember(
            SCOPE.subject_id, "I prefer compact status reports.", force=True,
            raw={"agent_id": SCOPE.agent_id, "workspace_id": SCOPE.workspace_id},
        )
        assert router.calls == 1
        assert result["records"] == []
        assert result["formation_intelligence"][0]["authority_result"] == "REVIEW"
    finally:
        memory.close()


def test_v2_runtime_failure_is_active_review_not_deterministic_fallback(tmp_path: Path) -> None:
    class V2Profile(Profile):
        def active_profile(self):
            value = super().active_profile()
            return {**value, "profile": "laya-formation-v2"}

    class BrokenResolver:
        def verify(self, _root):
            raise OSError("model unavailable")

    memory = Memory(":memory:", auto_vectors=False)
    try:
        text = "I prefer blue."
        source_id = "protocol-source-v2-failure"
        memory.capture_source(SourceCaptureRequest(
            source_id=source_id, idempotency_key="protocol-v2-failure",
            scope=SCOPE, message=text, source_type="user_message",
        ))
        result = FormationProfileRouter(
            profile_manager=V2Profile(True), resolver=BrokenResolver(),
        ).decide_protocol_transition_v2(
            store=memory.store, scope=SCOPE, source_id=source_id, text=text,
            retrieved_records=(),
        )
        assert result["active"] is True
        assert result["authority_result"] == "REVIEW"
        assert result["profile"] == "laya"
    finally:
        memory.close()


def test_selective_v3_delegates_one_binary_call_and_atmem_applies_store(tmp_path: Path) -> None:
    class V3Profile(Profile):
        def active_profile(self):
            value = super().active_profile()
            return {
                **value, "profile": "laya-formation-selective-v3",
                "confidence_threshold": 0.8,
            }

    typed_calls = []

    def typed_factory(_engine):
        def decide(request):
            typed_calls.append(request)
            options = [item["id"] for item in request["question"]["options"]]
            return {
                "format": "laya-choice-response-v2", "schema_version": "2.0.0",
                "request_id": request["request_id"],
                "question_id": request["question"]["question_id"],
                "type": "choice", "choice": options[0],
                "probabilities": {item: float(item == options[0]) for item in options},
                "confidence": 1.0,
            }
        return decide

    memory = Memory(
        ":memory:", auto_vectors=False, allow_insecure_typed_development=True,
        formation_router=FormationProfileRouter(
            profile_manager=V3Profile(True), resolver=Resolver(bundle(tmp_path)),
            engine_factory=Engine, v2_engine_factory=typed_factory,
        ),
    )
    try:
        result = memory.remember(
            SCOPE.subject_id, "My preferred status format is compact.",
            raw={"agent_id": SCOPE.agent_id, "workspace_id": SCOPE.workspace_id},
        )
        assert len(typed_calls) == 1
        assert len(typed_calls[0]["question"]["options"]) == 2
        assert result["records"]
        intelligence = result["formation_intelligence"][0]
        assert intelligence["format"] == "atmem-live-formation-transition-v3"
        assert intelligence["ruling"]["operation"] == "STORE_NEW"
        assert intelligence["model_calls"] == 1
    finally:
        memory.close()


def test_selective_v3_exact_duplicate_stays_deterministic_without_model_load(tmp_path: Path) -> None:
    class V3Profile(Profile):
        def active_profile(self):
            return {**super().active_profile(), "profile": "laya-formation-selective-v3"}

    class MustNotResolve:
        def verify(self, _root):
            raise AssertionError("model must remain lazy on deterministic fast path")

    memory = Memory(":memory:", auto_vectors=False)
    try:
        result = FormationProfileRouter(
            profile_manager=V3Profile(True), resolver=MustNotResolve(),
        ).decide_protocol_transition_v2(
            store=memory.store, scope=SCOPE, source_id="source-v3",
            text="  I PREFER BLUE. ",
            retrieved_records=({
                "id": "memory-1", "content": "I prefer blue.", "status": "active",
                "raw": {"authority_scope": SCOPE.to_dict()},
            },),
        )
        assert result["active"] is False
        assert result["model_calls"] == 0
        assert result["reason_code"] == "deterministic_exact_duplicate"
    finally:
        memory.close()
