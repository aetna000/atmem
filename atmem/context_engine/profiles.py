"""Explicit Context Engine V3 profile and activation state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class EngineProfile:
    profile_id: str
    deterministic: bool
    navigation: bool
    model_required: bool


LEGACY_CONTROL = EngineProfile("legacy-control", True, False, False)
CONTEXT_FAST = EngineProfile("context-fast", True, False, False)
CONTEXT_NAVIGATE = EngineProfile("context-navigate", False, True, True)
PROFILES = {item.profile_id: item for item in (LEGACY_CONTROL, CONTEXT_FAST, CONTEXT_NAVIGATE)}


def prepare_feedback_profile(feedback, session, request, *, profile_id=None, mode="disabled", versions=None):
    """Explicit application extension; ordinary prepare_context_v3 is unchanged.

    Shadow returns native context and retains the alternative only as evidence.
    Active mode requires a current accepted qualification and fails closed on
    invalid authority/policy; it never silently widens access or enables a model.
    """
    from dataclasses import replace
    import uuid
    from atmem.feedback.store import FeedbackError
    from atmem.rules.lifecycle import RuleLifecycle
    from atmem.context_engine.formation import FormationManager
    from atmem.context_engine.service import StoredContextEngine

    if mode not in ("disabled", "shadow", "active"):
        raise ValueError("explicit supported profile mode required")
    if feedback.memory is None or request.scope != session.scope.authority_scope():
        raise FeedbackError("denied")
    if mode == "disabled":
        return feedback.memory.prepare_context_v3(request)
    with feedback.memory.store.transaction(), feedback._authorized(session, "read") as (tx, principal):
        states = RuleLifecycle(feedback).current(tx, kind="profile", versions=versions or {})
        selected = next(((state, profile) for state, profile in states if profile.profile_id == profile_id), None)
        if selected is None or selected[0]["state"] != mode:
            raise FeedbackError("profile_unavailable")
        state, profile = selected
        generation = FormationManager(feedback.memory.store).active_generation(request.scope)
        if generation is None:
            raise FeedbackError("missing_evidence")
        bounded = replace(request, budget=replace(request.budget, context_bytes=min(request.budget.context_bytes, profile.context_bytes)))
        engine = StoredContextEngine(feedback.memory.store, generation_id=generation["generation_id"],
                                     candidate_budget=profile.candidate_budget, balanced_pools=profile.balanced_pools)
        candidate = feedback.memory.prepare_context_v3(bounded, engine=engine)
        native = feedback.memory.prepare_context_v3(request) if mode == "shadow" else None
        tx.put("profile_comparison", "profile-check-"+uuid.uuid4().hex,
               {"profile_id": profile_id, "candidate_sha256": profile.content_digest, "generation": state["generation"],
                "mode": mode, "candidate": candidate.to_dict(), "native": native.to_dict() if native else None,
                "actor_id": principal.principal_id, "delivery": "not_confirmed"}, expected_revision=0)
        return native if native is not None else candidate


@dataclass(frozen=True, slots=True)
class EngineProfileState:
    format: ClassVar[str] = "atmem-context-engine-profile-state-v1"
    active_profile: str
    shadow_profile: str | None
    shadow_sample_rate: float
    generation: int
    qualified_profiles: tuple[str, ...] = ("legacy-control",)

    def __post_init__(self) -> None:
        if self.active_profile not in PROFILES:
            raise ValueError("unknown active context-engine profile")
        if self.shadow_profile is not None and self.shadow_profile not in PROFILES:
            raise ValueError("unknown shadow context-engine profile")
        if self.shadow_profile == self.active_profile:
            raise ValueError("active and shadow profiles must differ")
        if not 0.0 <= self.shadow_sample_rate <= 1.0:
            raise ValueError("shadow sample rate must be within [0, 1]")
        if self.shadow_profile is None and self.shadow_sample_rate != 0.0:
            raise ValueError("shadow sampling requires a shadow profile")
        if self.generation < 0:
            raise ValueError("profile generation cannot be negative")
        if any(profile not in PROFILES for profile in self.qualified_profiles):
            raise ValueError("qualified profile list contains an unknown profile")
        if self.active_profile not in self.qualified_profiles:
            raise ValueError("active profile must be locally qualified")

    def to_dict(self) -> dict[str, Any]:
        return {"format": self.format, **asdict(self)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EngineProfileState":
        fields = set(cls.__dataclass_fields__) - {"format"}
        extras = set(value) - fields - {"format"}
        if extras or value.get("format") != cls.format:
            raise ValueError("malformed context-engine profile state")
        payload = {name: value[name] for name in fields}
        payload["qualified_profiles"] = tuple(payload["qualified_profiles"])
        return cls(**payload)


def initial_profile_state(
    *, fresh_install: bool, context_fast_qualified: bool, generation: int = 0
) -> EngineProfileState:
    qualified = (
        ("legacy-control", "context-fast")
        if context_fast_qualified
        else ("legacy-control",)
    )
    if fresh_install and context_fast_qualified:
        return EngineProfileState(
            active_profile="context-fast",
            shadow_profile=None,
            shadow_sample_rate=0.0,
            generation=generation,
            qualified_profiles=qualified,
        )
    return EngineProfileState(
        active_profile="legacy-control",
        shadow_profile="context-fast",
        shadow_sample_rate=0.1,
        generation=generation,
        qualified_profiles=qualified,
    )


class ProfileStateStore(Protocol):
    def get_context_engine_profile_state(self, migration_id: str) -> dict[str, Any] | None: ...
    def set_context_engine_profile_state(
        self, migration_id: str, value: dict[str, Any]
    ) -> None: ...


def load_profile_state(store: ProfileStateStore, migration_id: str) -> EngineProfileState | None:
    value = store.get_context_engine_profile_state(migration_id)
    return EngineProfileState.from_dict(value) if value is not None else None


def save_profile_state(
    store: ProfileStateStore, migration_id: str, state: EngineProfileState
) -> None:
    store.set_context_engine_profile_state(migration_id, state.to_dict())
