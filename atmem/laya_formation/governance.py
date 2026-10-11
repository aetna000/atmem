"""Authority-first adapter for optional formation decision engines."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Mapping, Protocol

from atmem.contracts.models import AuthorityScope
from atmem.core.canonical import canonical_json, sha256_hex

from .contracts import (
    CalibrationBinding, DecisionReceiptV1, FormationDecisionRequest,
    FormationDecisionResponse, QuestionDefinitionV1,
)
from .packing import AuthorizedRange, PackingAdapter, pack_authorized_ranges


@dataclass(frozen=True, slots=True)
class SourceRangeSnapshot:
    range_id: str
    source_id: str
    start: int
    end: int
    text: str
    digest: str


@dataclass(frozen=True, slots=True)
class CandidateSnapshot:
    candidate_id: str
    generation_id: str
    lifecycle: str
    digest: str


@dataclass(frozen=True, slots=True)
class AuthoritySnapshot:
    scope: AuthorityScope
    generation_id: str
    canonical_generation: int
    source_ranges: Mapping[str, SourceRangeSnapshot]
    candidates: Mapping[str, CandidateSnapshot]
    policy_allowed: bool

    def digest(self) -> str:
        return "sha256:" + sha256_hex(canonical_json({
            "scope": self.scope.to_dict(), "generation_id": self.generation_id,
            "canonical_generation": self.canonical_generation,
            "source_ranges": {key: vars_like(value) for key, value in sorted(self.source_ranges.items())},
            "candidates": {key: vars_like(value) for key, value in sorted(self.candidates.items())},
            "policy_allowed": self.policy_allowed,
        }))


def vars_like(value: Any) -> dict[str, Any]:
    return {name: getattr(value, name) for name in value.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class FormationDecisionIntent:
    request_id: str
    scope: AuthorityScope
    generation_id: str
    canonical_generation: int
    question: QuestionDefinitionV1
    calibration: CalibrationBinding
    requested_range_ids: tuple[str, ...]
    requested_candidate_ids: tuple[str, ...]


class AuthorityGateway(Protocol):
    def load(self, intent: FormationDecisionIntent) -> AuthoritySnapshot: ...


class Spec040AuthorityGateway:
    """Reload authorized ranges/candidates from the owning Spec 040 SQLite state."""

    def __init__(self, store: Any, *, policy_check: Callable[[FormationDecisionIntent], bool]) -> None:
        self.store = store
        self.policy_check = policy_check

    def load(self, intent: FormationDecisionIntent) -> AuthoritySnapshot:
        generation = self.store._conn.execute(
            """SELECT generation_id, subject_id, agent_id, workspace_id, state,
                      canonical_generation
                 FROM context_view_generations WHERE generation_id=?""",
            (intent.generation_id,),
        ).fetchone()
        if generation is None or str(generation["state"]) not in {"building", "verified", "active"}:
            raise ValueError("formation generation is unavailable")
        scope = AuthorityScope(
            subject_id=str(generation["subject_id"]), agent_id=str(generation["agent_id"]),
            workspace_id=str(generation["workspace_id"]),
        )
        ranges: dict[str, SourceRangeSnapshot] = {}
        for identity in intent.requested_range_ids:
            row = self.store._conn.execute(
                """SELECT r.range_id, r.source_id, r.start_offset, r.end_offset,
                          r.source_sha256, p.content_bytes,
                          e.subject_id, e.agent_id, e.workspace_id
                     FROM context_source_ranges r
                     JOIN context_source_parts p
                       ON p.source_id=r.source_id AND p.part_id=r.part_id
                     JOIN context_source_episodes e ON e.source_id=r.source_id
                    WHERE r.range_id=?""",
                (identity,),
            ).fetchone()
            if row is None or (
                str(row["subject_id"]), str(row["agent_id"]), str(row["workspace_id"])
            ) != (scope.subject_id, scope.agent_id, scope.workspace_id):
                raise ValueError("source range is outside the generation scope")
            start, end = int(row["start_offset"]), int(row["end_offset"])
            text = bytes(row["content_bytes"])[start:end].decode("utf-8", errors="replace")
            digest = "sha256:" + sha256_hex(canonical_json([
                identity, row["source_id"], start, end, row["source_sha256"], text,
            ]))
            ranges[identity] = SourceRangeSnapshot(
                range_id=identity, source_id=str(row["source_id"]), start=start, end=end,
                text=text, digest=digest,
            )
        candidates: dict[str, CandidateSnapshot] = {}
        for identity in intent.requested_candidate_ids:
            row = self.store._conn.execute(
                """SELECT generation_id, unit_id, lifecycle, compact_sha256
                     FROM context_evidence_units
                    WHERE generation_id=? AND unit_id=?""",
                (intent.generation_id, identity),
            ).fetchone()
            if row is None:
                raise ValueError("candidate does not exist in the canonical generation")
            candidates[identity] = CandidateSnapshot(
                candidate_id=identity, generation_id=str(row["generation_id"]),
                lifecycle=str(row["lifecycle"]), digest=str(row["compact_sha256"]),
            )
        return AuthoritySnapshot(
            scope=scope, generation_id=str(generation["generation_id"]),
            canonical_generation=int(generation["canonical_generation"]),
            source_ranges=ranges, candidates=candidates,
            policy_allowed=bool(self.policy_check(intent)),
        )


class _BoundedCanonicalAdapter:
    """Dependency-free packer used only until T031 injects the exact Laya tokenizer."""

    def __init__(self, revision: str) -> None:
        self.revision = revision

    def head_token_count(self, question: Mapping[str, Any], head_max_len: int) -> tuple[int, int]:
        count = len(question.get("crit") or {})
        tokens = len(canonical_json(question).encode("utf-8"))
        if tokens > head_max_len:
            raise ValueError("the complete finite-choice head does not fit head_max_len")
        return tokens, count

    def serialize_and_encode_state(self, state: Mapping[str, Any]) -> tuple[str, list[int]]:
        serialized = canonical_json(state)
        return serialized, list(serialized.encode("utf-8"))


@dataclass(frozen=True, slots=True)
class GovernedDecisionResult:
    request: FormationDecisionRequest | None
    response: FormationDecisionResponse | None
    receipt: DecisionReceiptV1


class FormationGovernanceAdapter:
    def __init__(
        self, gateway: AuthorityGateway, *, tokenizer_revision: str,
        packing_adapter: PackingAdapter | None = None,
        model_repo: str = "atmem/atmem-laya-formation-model-v1",
        model_revision: str = "1698278c4b158fac30e4eb2fefd10ef8b8f873b3",
    ) -> None:
        self.gateway = gateway
        self.packer = packing_adapter or _BoundedCanonicalAdapter(tokenizer_revision)
        self.model_repo = model_repo
        self.model_revision = model_revision

    def _authorized(self, intent: FormationDecisionIntent, snapshot: AuthoritySnapshot) -> tuple[list[SourceRangeSnapshot], list[CandidateSnapshot]]:
        if intent.scope != snapshot.scope or intent.generation_id != snapshot.generation_id:
            raise ValueError("intent is outside the loaded authority scope")
        if intent.canonical_generation != snapshot.canonical_generation:
            raise ValueError("intent canonical generation is stale")
        ranges = []
        for identity in intent.requested_range_ids:
            if identity not in snapshot.source_ranges:
                raise ValueError("requested evidence range is not authorized")
            ranges.append(snapshot.source_ranges[identity])
        candidates = []
        for identity in intent.requested_candidate_ids:
            candidate = snapshot.candidates.get(identity)
            if candidate is None or candidate.generation_id != snapshot.generation_id or candidate.lifecycle != "active":
                raise ValueError("requested candidate is not active and authorized")
            candidates.append(candidate)
        return ranges, candidates

    def _request(self, intent: FormationDecisionIntent, snapshot: AuthoritySnapshot) -> FormationDecisionRequest:
        ranges, candidates = self._authorized(intent, snapshot)
        packed = pack_authorized_ranges(
            adapter=self.packer, question=intent.question.to_laya_internal(),
            ranges=[AuthorizedRange(
                range_id=row.range_id, source_id=row.source_id,
                start=row.start, end=row.end, text=row.text,
            ) for row in ranges],
            max_len=intent.question.max_len, head_max_len=intent.question.head_max_len,
            closing_tokens_reserved=intent.question.closing_tokens_reserved,
        )
        request = FormationDecisionRequest(
            request_id=intent.request_id, scope=snapshot.scope,
            generation_id=snapshot.generation_id,
            canonical_generation=snapshot.canonical_generation,
            question=intent.question, calibration=intent.calibration,
            packed_input=packed,
            authorized_range_digests={row.range_id: row.digest for row in ranges},
            candidate_digests={row.candidate_id: row.digest for row in candidates},
        )
        request.validate(); return request

    def _fallback_receipt(
        self, intent: FormationDecisionIntent, *, disposition: str, reason: str,
        request: FormationDecisionRequest | None = None,
    ) -> DecisionReceiptV1:
        if request is None:
            empty = self.packer.serialize_and_encode_state({"authorized_ranges": []})
            from .packing import PackedDecisionInput
            packed = PackedDecisionInput(
                format="atmem-laya-packed-decision-input-v1", packer_version="1.0.0",
                tokenizer_revision=intent.question.tokenizer_revision,
                state=empty[0], state_digest="sha256:" + sha256_hex(empty[0]),
                included_range_ids=(), lost_range_ids=(), head_tokens=0,
                state_tokens=len(empty[1]), max_len=512, head_max_len=192,
                closing_tokens_reserved=1, total_tokens=len(empty[1]) + 1, overflow=False,
            )
            request = FormationDecisionRequest(
                request_id=intent.request_id, scope=intent.scope,
                generation_id=intent.generation_id,
                canonical_generation=max(0, intent.canonical_generation),
                question=intent.question, calibration=intent.calibration,
                packed_input=packed, authorized_range_digests={}, candidate_digests={},
            )
        response = FormationDecisionResponse(
            request_id=intent.request_id, selected_choice_ids=(), calibrated_scores={},
            confidence=0.0, abstained=True, reason_code=reason,
        )
        return DecisionReceiptV1.from_decision(
            request, response, model_repo=self.model_repo, model_revision=self.model_revision,
            device="none", latency_ms=0.0, final_disposition=disposition,
        )

    def decide(
        self, intent: FormationDecisionIntent, *,
        engine: Callable[[FormationDecisionRequest], FormationDecisionResponse | Mapping[str, Any]],
        escalator: Callable[[FormationDecisionRequest, str], Any] | None = None,
    ) -> GovernedDecisionResult:
        try:
            before = self.gateway.load(intent)
            _ranges, _candidates = self._authorized(intent, before)
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            receipt = self._fallback_receipt(intent, disposition="authority_rejected", reason=f"authority:{type(exc).__name__}")
            return GovernedDecisionResult(None, None, receipt)
        if not before.policy_allowed:
            receipt = self._fallback_receipt(intent, disposition="policy_denied", reason="policy_denied")
            return GovernedDecisionResult(None, None, receipt)
        try:
            request = self._request(intent, before)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError, ImportError) as exc:
            receipt = self._fallback_receipt(
                intent, disposition="deterministic_fallback",
                reason=f"bounded_input:{type(exc).__name__}",
            )
            return GovernedDecisionResult(None, None, receipt)
        started = perf_counter()
        escalation_metadata: dict[str, Any] | None = None

        def run_escalation(reason: str) -> tuple[FormationDecisionResponse, str]:
            nonlocal escalation_metadata
            if escalator is None:
                response = FormationDecisionResponse(
                    request_id=request.request_id, selected_choice_ids=(), calibrated_scores={},
                    confidence=0.0, abstained=True, reason_code=reason,
                )
                return response, "deterministic_fallback" if reason == "input_overflow" else "review_required"
            value = escalator(request, reason)
            raw_response = getattr(value, "response", value)
            response = raw_response if isinstance(raw_response, FormationDecisionResponse) else FormationDecisionResponse.from_dict(raw_response)
            response.validate(request.question)
            escalation_metadata = {
                key: getattr(value, key, None)
                for key in ("provider", "model", "egress_class", "input_tokens", "output_tokens", "cost_usd")
            }
            disposition = str(getattr(value, "disposition", "escalated_proposal"))
            return response, disposition

        escalation_disposition: str | None = None
        try:
            if request.packed_input.overflow:
                response, escalation_disposition = run_escalation("input_overflow")
            else:
                raw = engine(request)
                response = raw if isinstance(raw, FormationDecisionResponse) else FormationDecisionResponse.from_dict(raw)
                if response.abstained:
                    response, escalation_disposition = run_escalation(response.reason_code)
            if response.request_id != request.request_id:
                raise ValueError("response request identity mismatch")
            response.validate(request.question)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError, ImportError):
            receipt = self._fallback_receipt(intent, disposition="invalid_model_output", reason="invalid_model_output", request=request)
            return GovernedDecisionResult(request, None, receipt)
        try:
            after = self.gateway.load(intent)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError):
            receipt = DecisionReceiptV1.from_decision(
                request, response, model_repo=self.model_repo, model_revision=self.model_revision,
                device="uncommitted", latency_ms=(perf_counter() - started) * 1000,
                final_disposition="authority_changed",
                escalation=escalation_metadata,
            )
            return GovernedDecisionResult(request, response, receipt)
        if before.digest() != after.digest():
            receipt = DecisionReceiptV1.from_decision(
                request, response, model_repo=self.model_repo, model_revision=self.model_revision,
                device="uncommitted", latency_ms=(perf_counter() - started) * 1000,
                final_disposition="authority_changed",
                escalation=escalation_metadata,
            )
            return GovernedDecisionResult(request, response, receipt)
        final_disposition = escalation_disposition or (
            "review_required" if response.abstained else "proposal_validated"
        )
        receipt = DecisionReceiptV1.from_decision(
            request, response, model_repo=self.model_repo, model_revision=self.model_revision,
            device="atbot" if escalation_metadata else "engine",
            latency_ms=(perf_counter() - started) * 1000,
            final_disposition=final_disposition, escalation=escalation_metadata,
        )
        return GovernedDecisionResult(request, response, receipt)
