"""Live Context Engine routing for the optional Laya formation profile.

The router is deliberately proposal-only.  Exact source retention and the
deterministic Context Engine formation transaction complete first; Laya then
classifies only those retained, authorized ranges.  Its decisions are retained
as children of that authoritative transaction and never mutate canonical state
directly.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from atmem.contracts.models import AuthorityScope
from atmem.core.canonical import canonical_json, sha256_hex

from .artifacts import LayaArtifactResolver
from .contracts import MODEL_HEAD_MAX_LEN, MODEL_MAX_LEN, QuestionDefinitionV1
from .escalation import AtBotFormationEscalator, EscalationPolicy
from .governance import (
    AuthoritySnapshot,
    CandidateSnapshot,
    FormationDecisionIntent,
    FormationGovernanceAdapter,
    SourceRangeSnapshot,
    Spec040AuthorityGateway,
)
from .runtime import LayaDecisionEngine
from .runtime import LayaTypedDecisionEngineV2
from .formation_v2 import FormationPlanV2, revalidate_ruling
from .selective_v3 import build_joint_choice_v3, evaluate_joint_choice_v3
from .setup import LayaProfileManager


class ProtocolAuthorityGateway:
    """Reload V2 captured-source and record authority for ordinary live formation."""

    def __init__(
        self, store: Any, *, scope: AuthorityScope, source_id: str, text: str,
        range_id: str,
    ) -> None:
        self.store = store
        self.scope = scope
        self.source_id = source_id
        self.text = text
        self.range_id = range_id

    def load(self, intent: FormationDecisionIntent) -> AuthoritySnapshot:
        source = self.store.get_protocol_source_by_id(self.source_id)
        if source is None or (
            str(source["subject_id"]), str(source["agent_id"]),
            str(source["workspace_id"]),
        ) != (
            self.scope.subject_id, self.scope.agent_id, self.scope.workspace_id,
        ):
            raise ValueError("captured source is outside the authority scope")
        expected_sha = "sha256:" + sha256_hex(self.text)
        if str(source["source_sha256"]) != expected_sha:
            raise ValueError("captured source bytes changed after authorization")
        source_range = SourceRangeSnapshot(
            range_id=self.range_id,
            source_id=self.source_id,
            start=0,
            end=len(self.text),
            text=self.text,
            digest="sha256:" + sha256_hex(canonical_json([
                self.range_id, self.source_id, 0, len(self.text), expected_sha,
                self.text,
            ])),
            source_type=str((source.get("request") or {}).get("source_type") or "user_message"),
            binding_assurance=str(
                (source.get("request") or {}).get("binding_assurance")
                or "host_authenticated"
            ),
        )
        candidates: dict[str, CandidateSnapshot] = {}
        for candidate_id in intent.requested_candidate_ids:
            row = self.store.get_record(self.scope.subject_id, candidate_id)
            if row is None:
                raise ValueError("candidate no longer exists")
            raw_scope = dict((row.get("raw") or {}).get("authority_scope") or {})
            if raw_scope and (
                str(raw_scope.get("subject_id")) != self.scope.subject_id
                or str(raw_scope.get("agent_id")) != self.scope.agent_id
                or str(raw_scope.get("workspace_id")) != self.scope.workspace_id
            ):
                raise ValueError("candidate is outside the authority scope")
            candidates[candidate_id] = CandidateSnapshot(
                candidate_id=candidate_id,
                generation_id=intent.generation_id,
                lifecycle=str(row.get("status") or "missing"),
                digest="sha256:" + sha256_hex(canonical_json({
                    "id": candidate_id,
                    "status": row.get("status"),
                    "generation": row.get("generation"),
                    "content": row.get("content"),
                })),
                kind="fact",
                content={
                    "text": str(row.get("content") or ""),
                    "fact_key": row.get("fact_key"),
                },
            )
        return AuthoritySnapshot(
            scope=self.scope,
            generation_id=intent.generation_id,
            canonical_generation=self.store.record_generation(self.scope.subject_id),
            source_ranges={self.range_id: source_range},
            candidates=candidates,
            policy_allowed=True,
        )


class FormationProfileRouter:
    """Resolve one active profile and execute bounded live decisions lazily."""

    def __init__(
        self,
        *,
        profile_manager: LayaProfileManager | None = None,
        resolver: LayaArtifactResolver | None = None,
        engine_factory: Callable[..., Any] = LayaDecisionEngine,
        escalator_factory: Callable[..., Any] = AtBotFormationEscalator,
        v2_engine_factory: Callable[[Any], Any] | None = None,
    ) -> None:
        self.profile_manager = profile_manager or LayaProfileManager()
        self.resolver = resolver or LayaArtifactResolver()
        self.engine_factory = engine_factory
        self.escalator_factory = escalator_factory
        self.v2_engine_factory = v2_engine_factory
        self._engine: Any | None = None
        self._engine_identity: tuple[str, str, str] | None = None

    def uses_v2_semantic_authority(self) -> bool:
        profile = self.profile_manager.active_profile()
        return bool(
            profile is not None
            and profile.get("profile") in {
                "laya-formation-v2", "laya-formation-selective-v3",
            }
        )

    def _decide_protocol_transition_v3(
        self, *, profile: Mapping[str, Any], store: Any, scope: AuthorityScope,
        source_id: str, text: str,
        retrieved_records: tuple[Mapping[str, Any], ...],
    ) -> dict[str, Any]:
        """Delegate only the bounded STORE/DO_NOT_STORE ambiguity to Laya."""

        generation = int(store.record_generation(scope.subject_id))
        normalized = " ".join(text.casefold().split())
        if any(
            " ".join(str(row.get("content") or "").casefold().split()) == normalized
            for row in retrieved_records
            if str(row.get("status") or "") == "active"
        ):
            return {
                "format": "atmem-live-formation-transition-v3",
                "profile": "deterministic", "active": False,
                "authority_result": "DETERMINISTIC", "ruling": None,
                "model_calls": 0, "reason_code": "deterministic_exact_duplicate",
            }
        bundle, legacy_engine = self._engine_for(profile)
        typed_engine = self._typed_v2_engine(legacy_engine)
        source_digest = "sha256:" + sha256_hex(text)
        observation = {
            "id": source_id, "content": text, "speaker_role": "user",
            "source_digest": source_digest,
        }
        memories = []
        for rank, row in enumerate(retrieved_records):
            if str(row.get("status") or "") != "active":
                continue
            authority = dict((row.get("raw") or {}).get("authority_scope") or {})
            if authority and (
                authority.get("subject_id"), authority.get("agent_id"),
                authority.get("workspace_id"),
            ) != (scope.subject_id, scope.agent_id, scope.workspace_id):
                continue
            content = str(row.get("content") or "")
            digest = "sha256:" + sha256_hex(content)
            memories.append({
                "id": str(row["id"]), "content": content, "lifecycle": "active",
                "source_digest": digest, "content_digest": digest,
                "retrieval_score": float(row.get("retrieval_score", 1.0 / (rank + 1))),
                "memory_class": "unknown",
            })
        request_id = "formation_v3_" + sha256_hex(canonical_json([
            source_id, generation, bundle.revision,
        ]))[:32]
        scope_id = "scope_" + sha256_hex(canonical_json(scope.to_dict()))[:32]
        choice = build_joint_choice_v3(
            request_id=request_id, scope_id=scope_id,
            canonical_generation=generation, observation=observation,
            retrieved_memories=memories,
            allowed_operations=("STORE_NEW", "DO_NOT_STORE"),
        )
        result = evaluate_joint_choice_v3(
            typed_engine, choice,
            confidence_threshold=float(profile.get("confidence_threshold", 0.8)),
        )
        observed_generation = int(store.record_generation(scope.subject_id))
        authorized = (
            result.operation in {"STORE_NEW", "DO_NOT_STORE"}
            and result.disposition == "model_delegated"
            and observed_generation == generation
        )
        return {
            "format": "atmem-live-formation-transition-v3",
            "profile": "laya-formation-selective-v3", "active": True,
            "model_repo": bundle.repo_id, "model_revision": bundle.revision,
            "authority_result": "AUTHORIZED_PROPOSAL" if authorized else "REVIEW",
            "ruling": result.to_dict(), "model_calls": result.model_calls,
            "previous_generation": generation,
            "observed_generation": observed_generation,
            "reason_code": (
                "governance_revalidation_passed" if authorized
                else result.reason_code
            ),
        }

    def _typed_v2_engine(self, engine: Any) -> Any:
        if self.v2_engine_factory is not None:
            return self.v2_engine_factory(engine)
        return LayaTypedDecisionEngineV2(
            engine.agent, packing_adapter=engine.packing_adapter,
        )

    def decide_protocol_transition_v2(
        self, *, store: Any, scope: AuthorityScope, source_id: str, text: str,
        retrieved_records: tuple[Mapping[str, Any], ...],
    ) -> dict[str, Any]:
        """Return one governed V2 ruling; never fall back semantically."""

        profile = self.profile_manager.active_profile()
        generation = int(store.record_generation(scope.subject_id))
        if profile is None:
            return {
                "format": "atmem-live-formation-transition-v2",
                "profile": "deterministic", "active": False,
                "authority_result": "DETERMINISTIC", "ruling": None,
                "question_receipts": [], "reason_code": "laya_profile_inactive",
            }
        if profile.get("profile") == "laya-formation-selective-v3":
            try:
                return self._decide_protocol_transition_v3(
                    profile=profile, store=store, scope=scope,
                    source_id=source_id, text=text,
                    retrieved_records=retrieved_records,
                )
            except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                return {
                    "format": "atmem-live-formation-transition-v3",
                    "profile": "laya-formation-selective-v3", "active": True,
                    "authority_result": "REVIEW", "ruling": None,
                    "model_calls": 0,
                    "reason_code": f"laya_runtime_{type(exc).__name__}",
                }
        try:
            bundle, legacy_engine = self._engine_for(profile)
            typed_engine = self._typed_v2_engine(legacy_engine)
            typed_escalation_receipts: list[dict[str, Any]] = []
            escalator = self._escalator(profile)
            if escalator is not None and hasattr(escalator, "decide_typed"):
                primary_engine = typed_engine

                def typed_engine(request: Mapping[str, Any]) -> Mapping[str, Any]:
                    response = primary_engine(request)
                    if (
                        response.get("type") == "choice"
                        and float(response.get("confidence") or 0.0) < 0.5
                    ):
                        escalated, escalation_receipt = escalator.decide_typed(
                            request, response, "calibrated_low_confidence",
                        )
                        typed_escalation_receipts.append(escalation_receipt)
                        if escalated is not None:
                            return escalated
                    return response
            source_digest = "sha256:" + sha256_hex(text)
            observation = {
                "id": source_id, "content": text, "speaker_role": "user",
                "source_digest": source_digest,
            }
            memories: list[dict[str, Any]] = []
            target_rows: list[dict[str, Any]] = []
            for rank, row in enumerate(retrieved_records):
                authority = dict((row.get("raw") or {}).get("authority_scope") or {})
                if authority and (
                    authority.get("subject_id"), authority.get("agent_id"),
                    authority.get("workspace_id"),
                ) != (scope.subject_id, scope.agent_id, scope.workspace_id):
                    continue
                if str(row.get("status") or "") != "active":
                    continue
                content = str(row.get("content") or "")
                digest = "sha256:" + sha256_hex(content)
                raw = row.get("raw") or {}
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except (TypeError, ValueError):
                        raw = {}
                memories.append({
                    "id": str(row["id"]), "content": content,
                    "lifecycle": "active", "source_digest": digest,
                    "content_digest": digest,
                    "memory_class": str(raw.get("memory_class") or "unknown"),
                    "retrieval_score": float(row.get("retrieval_score", 1.0 / (rank + 1))),
                })
                target_rows.append(dict(row))
            scope_id = "scope_" + sha256_hex(canonical_json(scope.to_dict()))[:32]
            ruling, question_receipts = FormationPlanV2().evaluate(
                typed_engine, scope_id=scope_id,
                canonical_generation=generation, observation=observation,
                retrieved_memories=memories,
            )
            receipt = revalidate_ruling(
                ruling, request_id="formation_" + sha256_hex(canonical_json([
                    source_id, generation, bundle.revision,
                ]))[:32],
                classifier=f"{bundle.repo_id}@{bundle.revision}",
                expected_generation=generation,
                observed_generation=int(store.record_generation(scope.subject_id)),
                allowed_target_ids=[row["id"] for row in memories],
                policy_allowed=True,
            )
            return {
                "format": "atmem-live-formation-transition-v2",
                "active": True,
                "profile": (
                    "laya-escalation"
                    if bool((profile.get("escalation") or {}).get("enabled"))
                    else "laya"
                ),
                "model_repo": bundle.repo_id, "model_revision": bundle.revision,
                "authority_result": receipt.authority_result,
                "ruling": ruling.to_dict(), "receipt": receipt.to_dict(),
                "question_receipts": list(question_receipts),
                "escalation_receipts": typed_escalation_receipts,
                "authorized_target_records": target_rows,
                "reason_code": receipt.authority_reason,
            }
        except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return {
                "format": "atmem-live-formation-transition-v2",
                "active": True,
                "profile": (
                    "laya-escalation"
                    if bool((profile.get("escalation") or {}).get("enabled"))
                    else "laya"
                ),
                "authority_result": "REVIEW", "ruling": None,
                "question_receipts": [],
                "reason_code": f"laya_runtime_{type(exc).__name__}",
            }

    def _engine_for(self, profile: Mapping[str, Any]) -> tuple[Any, Any]:
        bundle = self.resolver.verify(Path(str(profile["model_dir"])))
        identity = (bundle.revision, bundle.model_sha256, str(profile["device"]))
        if self._engine is None or self._engine_identity != identity:
            self.close()
            self._engine = self.engine_factory(bundle, device=str(profile["device"]))
            self._engine_identity = identity
        return bundle, self._engine

    @staticmethod
    def _question(bundle: Any, engine: Any, question_id: str) -> QuestionDefinitionV1:
        value = bundle.questions[question_id]
        question = QuestionDefinitionV1(
            question_id=question_id,
            semantic_version="1.0.0",
            kind="choice",
            instructions=str(value["instructions"]),
            choice_ids=tuple(str(item) for item in value["choice_ids"]),
            allow_abstain=True,
            tokenizer_revision=str(engine.packing_adapter.revision),
            max_len=MODEL_MAX_LEN,
            head_max_len=MODEL_HEAD_MAX_LEN,
            closing_tokens_reserved=1,
            overflow_policy="whole-authorized-ranges-or-review",
        )
        question.validate()
        return question

    @staticmethod
    def _authorized_inputs(
        store: Any, source_id: str, generation_id: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...], int, AuthorityScope]:
        generation = store._conn.execute(
            "SELECT subject_id, agent_id, workspace_id, canonical_generation, state "
            "FROM context_view_generations WHERE generation_id=?",
            (generation_id,),
        ).fetchone()
        if generation is None or str(generation["state"]) != "building":
            raise ValueError("live formation requires the current building generation")
        ranges = store._conn.execute(
            "SELECT range_id FROM context_source_ranges WHERE source_id=? "
            "ORDER BY part_id, start_offset, end_offset, range_id",
            (source_id,),
        ).fetchall()
        if not ranges:
            raise ValueError("live formation has no retained source ranges")
        candidates = store._conn.execute(
            """SELECT unit_id FROM context_evidence_units
               WHERE generation_id=? AND lifecycle='active'
               ORDER BY created_at, unit_id LIMIT 64""",
            (generation_id,),
        ).fetchall()
        scope = AuthorityScope(
            subject_id=str(generation["subject_id"]),
            agent_id=str(generation["agent_id"]),
            workspace_id=str(generation["workspace_id"]),
        )
        return (
            tuple(str(row["range_id"]) for row in ranges),
            tuple(str(row["unit_id"]) for row in candidates),
            int(generation["canonical_generation"]),
            scope,
        )

    def _escalator(self, profile: Mapping[str, Any]) -> Any | None:
        value = dict(profile.get("escalation") or {})
        if not value.get("enabled"):
            return None
        policy = EscalationPolicy(
            enabled=True,
            max_calls=int(value.get("max_calls", 1)),
            max_input_tokens=int(value.get("max_input_tokens", 2_048)),
            max_output_tokens=int(value.get("max_output_tokens", 128)),
            timeout_seconds=float(value.get("timeout_seconds", 15.0)),
            retries=int(value.get("retries", 0)),
            remote_egress_allowed=bool(value.get("remote_egress_allowed", False)),
            max_cost_usd=float(value.get("max_cost_usd", 0.0)),
        )
        return self.escalator_factory(policy=policy)

    def _run_decisions(
        self, *, profile: Mapping[str, Any], bundle: Any, engine: Any,
        gateway: Any, source_identity: str, generation_id: str,
        generation: int, scope: AuthorityScope, range_ids: tuple[str, ...],
        candidate_ids: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        adapter = FormationGovernanceAdapter(
            gateway,
            tokenizer_revision=str(engine.packing_adapter.revision),
            packing_adapter=engine.packing_adapter,
            model_repo=bundle.repo_id,
            model_revision=bundle.revision,
        )
        escalator = self._escalator(profile)
        decisions: list[dict[str, Any]] = []
        for question_id in sorted(bundle.questions):
            question = self._question(bundle, engine, question_id)
            request_id = "laya_" + sha256_hex(canonical_json([
                source_identity, generation_id, generation, question_id,
                bundle.revision, bundle.calibration_digest,
            ]))[:32]
            result = adapter.decide(
                FormationDecisionIntent(
                    request_id=request_id,
                    scope=scope,
                    generation_id=generation_id,
                    canonical_generation=generation,
                    question=question,
                    calibration=bundle.calibration,
                    requested_range_ids=range_ids,
                    requested_candidate_ids=candidate_ids,
                ),
                engine=engine,
                escalator=escalator,
            )
            receipt = result.receipt
            if receipt.final_disposition in {"proposal_validated", "escalated_proposal"}:
                receipt = replace(
                    receipt,
                    final_disposition="proposal_retained_deterministic_authority",
                    authorizes_mutation=False,
                )
            decisions.append({
                "question_id": question_id,
                "selected_choice_ids": (
                    list(result.response.selected_choice_ids)
                    if result.response is not None else []
                ),
                "receipt": receipt.to_dict(),
            })
        return decisions

    def decide_source(
        self, *, store: Any, source_id: str, generation_id: str,
    ) -> dict[str, Any]:
        """Run all artifact-bound questions or return a deterministic fallback."""

        profile = self.profile_manager.active_profile()
        if profile is None:
            return {
                "format": "atmem-live-formation-intelligence-v1",
                "profile": "deterministic",
                "active": False,
                "fallback": False,
                "reason_code": "laya_profile_inactive",
                "decisions": [],
            }
        try:
            bundle, engine = self._engine_for(profile)
            range_ids, candidate_ids, generation, scope = self._authorized_inputs(
                store, source_id, generation_id
            )
            gateway = Spec040AuthorityGateway(
                store,
                policy_check=lambda intent: (
                    intent.scope == scope
                    and intent.generation_id == generation_id
                    and intent.canonical_generation == generation
                ),
            )
            decisions = self._run_decisions(
                profile=profile, bundle=bundle, engine=engine, gateway=gateway,
                source_identity=source_id, generation_id=generation_id,
                generation=generation, scope=scope, range_ids=range_ids,
                candidate_ids=candidate_ids,
            )
            return {
                "format": "atmem-live-formation-intelligence-v1",
                "profile": "laya-formation-v1",
                "active": True,
                "fallback": all(not row["selected_choice_ids"] for row in decisions),
                "reason_code": "bounded_laya_decisions_completed",
                "model_repo": bundle.repo_id,
                "model_revision": bundle.revision,
                "decisions": decisions,
            }
        except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return {
                "format": "atmem-live-formation-intelligence-v1",
                "profile": "deterministic",
                "active": True,
                "fallback": True,
                "reason_code": f"laya_runtime_{type(exc).__name__}",
                "decisions": [],
            }

    def decide_protocol_source(
        self, *, store: Any, scope: AuthorityScope, source_id: str, text: str,
    ) -> dict[str, Any]:
        """Run Laya for the ordinary V2 formation entry point after capture."""
        profile = self.profile_manager.active_profile()
        if profile is None:
            return {
                "format": "atmem-live-formation-intelligence-v1",
                "profile": "deterministic", "active": False, "fallback": False,
                "reason_code": "laya_profile_inactive", "decisions": [],
            }
        try:
            bundle, engine = self._engine_for(profile)
            generation = int(store.record_generation(scope.subject_id))
            generation_id = f"records:{scope.subject_id}:{generation}"
            range_id = "range_" + sha256_hex(canonical_json([
                source_id, 0, len(text), "protocol-source-v1",
            ]))[:32]
            records = [
                row for row in store.list_records(scope.subject_id, statuses=("active",))
                if not (row.get("raw") or {}).get("authority_scope")
                or dict((row.get("raw") or {}).get("authority_scope") or {}).get("workspace_id")
                == scope.workspace_id
            ][:64]
            candidate_ids = tuple(str(row["id"]) for row in records)
            gateway = ProtocolAuthorityGateway(
                store, scope=scope, source_id=source_id, text=text, range_id=range_id,
            )
            decisions = self._run_decisions(
                profile=profile, bundle=bundle, engine=engine, gateway=gateway,
                source_identity=source_id, generation_id=generation_id,
                generation=generation, scope=scope, range_ids=(range_id,),
                candidate_ids=candidate_ids,
            )
            return {
                "format": "atmem-live-formation-intelligence-v1",
                "profile": "laya-formation-v1", "active": True,
                "fallback": all(not row["selected_choice_ids"] for row in decisions),
                "reason_code": "bounded_laya_decisions_completed",
                "model_repo": bundle.repo_id, "model_revision": bundle.revision,
                "decisions": decisions,
            }
        except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return {
                "format": "atmem-live-formation-intelligence-v1",
                "profile": "deterministic", "active": True, "fallback": True,
                "reason_code": f"laya_runtime_{type(exc).__name__}",
                "decisions": [],
            }

    def close(self) -> None:
        if self._engine is not None:
            close = getattr(self._engine, "close", None)
            if callable(close):
                close()
        self._engine = None
        self._engine_identity = None

