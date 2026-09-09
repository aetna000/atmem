"""Session bindings: the key, the generation, and the single answer.

Spec 007 Amendment A, T061 and T065.

The tests that matter here are the ones that would pass under a *weaker*
design. Exact scope alone does not separate two conversations in the same
subject/agent/workspace, and a lifetime alone cannot notice a reset that
happens inside it. Both are asserted explicitly, so the session generation is
proven load-bearing rather than assumed to be.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import BindingResolution, EvidenceRef, HostSessionIdentity
from atmem.store.sqlite import SQLiteStore
from atmem.task_state.binding import BindingError, ResolvedTask, SessionBindingService
from atmem.task_state.profiles import GENERAL_V1


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
OTHER_SCOPE = AuthorityScope("subject-1", "agent-2", "workspace-1")


class FakeClock:
    """Deterministic and injectable; lifetime edges are otherwise untestable."""

    def __init__(self) -> None:
        self.moment = datetime(2026, 9, 5, 9, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.moment

    def advance(self, **delta) -> None:
        self.moment += timedelta(**delta)


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def store(tmp_path) -> SQLiteStore:
    store = SQLiteStore(str(tmp_path / "bindings.db"))
    yield store
    store.close()


@pytest.fixture()
def service(store, clock) -> SessionBindingService:
    return SessionBindingService(store, clock)


def identity(session_key: str = "session-1", epoch: str = "epoch-1") -> HostSessionIdentity:
    return HostSessionIdentity("openclaw", session_key, epoch)


# --- the uniqueness key -----------------------------------------------------


def test_at_most_one_active_binding_per_key(service) -> None:
    service.register(SCOPE, identity(), task_id="migrate", actor="op", reason="r")
    with pytest.raises(BindingError) as caught:
        service.register(SCOPE, identity(), task_id="docs", actor="op", reason="r")
    assert caught.value.reason_code == "binding_already_active"


def test_retargeting_is_refused_as_an_update(service) -> None:
    """Repointing a session must be a revoke and a register, never an upsert.

    Each half then carries its own authority, reason and evidence, so a
    conversation silently changing what it points at is not expressible.
    """
    first = service.register(SCOPE, identity(), task_id="migrate", actor="op", reason="r")
    with pytest.raises(BindingError):
        service.register(SCOPE, identity(), task_id="docs", actor="op", reason="r")

    service.revoke(SCOPE, binding_id=first.binding_id, actor="op", reason="switching")
    service.register(SCOPE, identity(), task_id="docs", actor="op", reason="r")
    assert service.resolve(SCOPE, identity=identity()).task_id == "docs"


def test_bindings_are_many_to_one(service) -> None:
    """Several conversations may drive one task; uniqueness is per key, not per task."""
    service.register(SCOPE, identity("session-1"), task_id="migrate", actor="op", reason="r")
    service.register(SCOPE, identity("session-2"), task_id="migrate", actor="op", reason="r")
    assert service.resolve(SCOPE, identity=identity("session-1")).task_id == "migrate"
    assert service.resolve(SCOPE, identity=identity("session-2")).task_id == "migrate"


def test_a_binding_is_invisible_outside_its_exact_scope(service) -> None:
    service.register(SCOPE, identity(), task_id="migrate", actor="op", reason="r")
    resolved = service.resolve(OTHER_SCOPE, identity=identity())
    assert resolved.resolution is BindingResolution.NONE
    assert resolved.task_id is None


def test_revocation_is_recorded_not_deleted(service) -> None:
    binding = service.register(SCOPE, identity(), task_id="migrate", actor="op", reason="r")
    service.revoke(SCOPE, binding_id=binding.binding_id, actor="op", reason="finished")

    assert service.list(SCOPE) == []
    history = service.list(SCOPE, include_revoked=True)
    assert len(history) == 1
    assert history[0]["revoked_reason"] == "finished"


def test_revoking_an_unknown_binding_is_non_disclosing(service) -> None:
    """A binding in another scope and one that never existed answer alike."""
    binding = service.register(SCOPE, identity(), task_id="migrate", actor="op", reason="r")
    with pytest.raises(BindingError) as other_scope:
        service.revoke(OTHER_SCOPE, binding_id=binding.binding_id, actor="op", reason="x")
    with pytest.raises(BindingError) as never_existed:
        service.revoke(SCOPE, binding_id="binding-nope", actor="op", reason="x")
    assert other_scope.value.reason_code == never_existed.value.reason_code
    assert str(other_scope.value) == str(never_existed.value)


def test_registration_records_evidence(service) -> None:
    binding = service.register(
        SCOPE, identity(), task_id="migrate", actor="op", reason="r",
        evidence=(EvidenceRef("operator_request", "req-1"),),
    )
    assert binding.evidence[0].reference_id == "req-1"
    assert service.list(SCOPE)[0]["evidence"][0]["reference_id"] == "req-1"


# --- the session generation is load-bearing ---------------------------------


def test_exact_scope_alone_does_not_stop_a_recycled_key(service, store) -> None:
    """The negative control for the whole FR-052 design.

    Everything except the generation is identical here -- same subject, agent,
    workspace, host and session key. If the generation were not part of the
    key, this new conversation would silently inherit the old task. The store
    lookup is exercised directly so the point cannot be hidden by resolver
    logic.
    """
    service.register(SCOPE, identity(epoch="epoch-1"), task_id="migrate", actor="op", reason="r")

    same_but_for_generation = dict(
        subject_id=SCOPE.subject_id,
        agent_id=SCOPE.agent_id,
        workspace_id=SCOPE.workspace_id,
        host_type="openclaw",
        session_key="session-1",
    )
    assert store.find_active_session_binding(
        **same_but_for_generation, session_epoch="epoch-1"
    ) is not None
    assert store.find_active_session_binding(
        **same_but_for_generation, session_epoch="epoch-2"
    ) is None


def test_a_recycled_session_key_withholds_as_stale_not_as_absent(service) -> None:
    """Distinguishable on purpose: it tells an operator to re-confirm."""
    service.register(SCOPE, identity(epoch="epoch-1"), task_id="migrate", actor="op", reason="r")
    resolved = service.resolve(SCOPE, identity=identity(epoch="epoch-2"))
    assert resolved.resolution is BindingResolution.STALE_SESSION
    assert resolved.reason_code == "task_binding_stale_session"
    assert resolved.task_id is None


def test_a_never_bound_session_withholds_as_absent(service) -> None:
    resolved = service.resolve(SCOPE, identity=identity("session-unknown"))
    assert resolved.resolution is BindingResolution.NONE
    assert resolved.reason_code == "task_context_selection_required"


def test_recovery_from_a_stale_session_requires_explicit_re_registration(service) -> None:
    service.register(SCOPE, identity(epoch="epoch-1"), task_id="migrate", actor="op", reason="r")
    assert not service.resolve(SCOPE, identity=identity(epoch="epoch-2")).resolution.delivers

    service.register(SCOPE, identity(epoch="epoch-2"), task_id="migrate", actor="op", reason="r")
    assert service.resolve(SCOPE, identity=identity(epoch="epoch-2")).task_id == "migrate"


# --- the lifetime is supplemental, never a substitute -----------------------


def test_a_reset_inside_the_lifetime_still_withholds(service, clock) -> None:
    """The case a TTL provably cannot cover, and the reason it is not the mechanism.

    The binding is nowhere near expiry. Only the generation catches this.
    """
    service.register(
        SCOPE, identity(epoch="epoch-1"), task_id="migrate", actor="op",
        reason="r", profile=GENERAL_V1,
    )
    clock.advance(minutes=1)
    resolved = service.resolve(SCOPE, identity=identity(epoch="epoch-2"))
    assert resolved.reason_code == "task_binding_stale_session"


def test_the_lifetime_expires_a_binding_that_was_never_reset(service, clock) -> None:
    service.register(
        SCOPE, identity(), task_id="migrate", actor="op", reason="r", profile=GENERAL_V1
    )
    clock.advance(hours=11)
    assert service.resolve(SCOPE, identity=identity()).task_id == "migrate"

    clock.advance(hours=2)  # past the general-v1 twelve-hour lifetime
    resolved = service.resolve(SCOPE, identity=identity())
    assert resolved.resolution is BindingResolution.STALE_SESSION
    assert resolved.task_id is None


def test_a_profile_without_a_lifetime_binds_without_expiry(service, clock) -> None:
    service.register(SCOPE, identity(), task_id="migrate", actor="op", reason="r", profile=None)
    clock.advance(days=30)
    assert service.resolve(SCOPE, identity=identity()).task_id == "migrate"


# --- the resolution matrix (T065) -------------------------------------------


@pytest.mark.parametrize(
    "explicit,bound,expected,reason",
    [
        (None, None, BindingResolution.NONE, "task_context_selection_required"),
        (None, "migrate", BindingResolution.BOUND, None),
        ("migrate", None, BindingResolution.EXPLICIT, None),
        ("migrate", "migrate", BindingResolution.EXPLICIT, None),
        ("docs", "migrate", BindingResolution.CONFLICT, "task_binding_conflict"),
    ],
)
def test_the_resolution_matrix(service, explicit, bound, expected, reason) -> None:
    """Explicit, then binding, then withhold. Disagreement picks neither."""
    if bound:
        service.register(SCOPE, identity(), task_id=bound, actor="op", reason="r")
    resolved = service.resolve(SCOPE, identity=identity(), explicit_task_id=explicit)
    assert resolved.resolution is expected
    assert resolved.reason_code == reason
    assert (resolved.task_id is not None) is expected.delivers


def test_disagreement_prefers_neither_source(service) -> None:
    """Preferring either would hide a real misconfiguration.

    Taking the explicit id masks a wrong binding; taking the binding lets stale
    operator state override a host that knows better. Withholding is the only
    outcome that reaches a human who can fix it.
    """
    service.register(SCOPE, identity(), task_id="migrate", actor="op", reason="r")
    resolved = service.resolve(SCOPE, identity=identity(), explicit_task_id="docs")
    assert resolved.task_id is None
    assert resolved.resolution is BindingResolution.CONFLICT


def test_absent_identity_withholds_rather_than_matching_on_what_survives(service) -> None:
    """Hosts declare identity fields optional, so this is an ordinary turn."""
    service.register(SCOPE, identity(), task_id="migrate", actor="op", reason="r")
    resolved = service.resolve(SCOPE, identity=None)
    assert resolved.resolution is BindingResolution.NONE
    assert resolved.task_id is None


def test_the_resolver_never_exposes_candidates(service) -> None:
    """Structural, not behavioural: there is no field a candidate could live in.

    If no layer can return a set, a later change cannot quietly start choosing
    from one without deleting this contract first.
    """
    service.register(SCOPE, identity("session-1"), task_id="migrate", actor="op", reason="r")
    service.register(SCOPE, identity("session-2"), task_id="docs", actor="op", reason="r")
    resolved = service.resolve(SCOPE, identity=identity("session-3"))
    assert set(ResolvedTask.__slots__) == {
        "resolution", "task_id", "reason_code", "binding_id"
    }
    assert resolved.task_id is None


def test_a_delivering_resolution_must_name_a_task() -> None:
    with pytest.raises(ValueError, match="must name exactly one task"):
        ResolvedTask(BindingResolution.BOUND)
    with pytest.raises(ValueError, match="must name no task"):
        ResolvedTask(BindingResolution.CONFLICT, task_id="migrate")
