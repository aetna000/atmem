"""The authority that actually commits governed task state.

Policy decides; this service is the only thing that writes. It owns the
transaction boundary, the optimistic head advance, the immutable revision and
provenance records, the step ledger, and the lifecycle operations.

Two invariants shape almost every method here:

- A proposer never writes. It hands over a typed delta and receives a decision.
- Expiry is a policy operation, not a cancellation. Only the scoped evaluator
  may retire a task for age, and it must cite the rule and the trusted time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import sqlite3
from typing import Any

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    EvidenceRef,
    GuardSignal,
    GuardType,
    ItemStatus,
    OperationKind,
    StepOutcome,
    TaskConstraint,
    TaskItem,
    TaskLifecycle,
    TaskOperation,
    TaskProfile,
    TaskStartRequest,
    TaskState,
    TaskStateProposal,
    TransitionDecision,
)
from atmem.core.canonical import canonical_json, sha256_hex
from atmem.core.time import (
    DEFAULT_CLOCK,
    TrustedUtcClock,
    elapsed_ms,
    from_iso,
    to_iso,
)
from atmem.task_state.governance import capability_for, require
from atmem.task_state.models import summarize
from atmem.task_state.policy import PolicyDecision, evaluate, evaluate_completion
from atmem.task_state.profiles import ProfileRegistry


class TaskStateError(ValueError):
    """A task-state request that AtMem refuses, with a stable reason code."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class TaskView:
    """A task and its current state, as an operator or agent reads it."""

    task: dict[str, Any]
    state: TaskState
    profile: TaskProfile
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "atmem-task-view-v1",
            "task_id": self.task["task_id"],
            "lifecycle": self.task["lifecycle"],
            "revision": self.state.revision,
            "profile_version": self.task["profile_version"],
            "summary": self.summary,
            "state": self.state.to_dict(),
            "created_at_utc": self.task["created_at_utc"],
            "updated_at_utc": self.task["updated_at_utc"],
            "last_progress_at_utc": self.task["last_progress_at_utc"],
            "terminal_reason": self.task.get("terminal_reason"),
            "continues_task_id": self.task.get("continues_task_id"),
        }


class TaskStateService:
    """AtMem's authority over governed task state."""

    def __init__(
        self,
        store: Any,
        *,
        clock: TrustedUtcClock | None = None,
        registry: ProfileRegistry | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or DEFAULT_CLOCK
        self.registry = registry or ProfileRegistry(store)

    # --- reads --------------------------------------------------------------

    def get(
        self,
        scope: AuthorityScope,
        task_id: str,
        *,
        evaluate_expiry: bool = True,
    ) -> TaskView:
        """Read one task within its exact scope, expiring it first if due.

        Expiry is evaluated lazily on read so a task that aged out while
        nothing was running is already terminal by the time anyone sees it.
        """
        row = self._require_task(scope, task_id)
        if evaluate_expiry and not TaskLifecycle(row["lifecycle"]).terminal:
            expired = self._expire_if_due(scope, row)
            if expired is not None:
                row = expired
        return self._view(row)

    def list(
        self,
        scope: AuthorityScope | None = None,
        *,
        lifecycles: tuple[str, ...] | None = None,
        cursor: str | None = None,
        limit: int = 50,
        evaluate_expiry: bool = True,
    ) -> dict[str, Any]:
        rows = self.store.list_tasks(
            subject_id=scope.subject_id if scope else None,
            agent_id=scope.agent_id if scope else None,
            workspace_id=scope.workspace_id if scope else None,
            lifecycles=lifecycles,
            cursor=cursor,
            limit=limit,
        )
        if evaluate_expiry:
            refreshed: list[dict[str, Any]] = []
            for row in rows:
                if not TaskLifecycle(row["lifecycle"]).terminal:
                    row = self._expire_if_due(self._scope_of(row), row) or row
                refreshed.append(row)
            rows = refreshed
        next_cursor = (
            f"{rows[-1]['created_at_utc']}|{rows[-1]['task_id']}"
            if len(rows) == limit
            else None
        )
        return {
            "format": "atmem-task-list-v1",
            "count": len(rows),
            "next_cursor": next_cursor,
            "tasks": [
                {
                    "task_id": row["task_id"],
                    "goal": row["goal"],
                    "lifecycle": row["lifecycle"],
                    "revision": row["head_revision"],
                    "profile_version": row["profile_version"],
                    "created_at_utc": row["created_at_utc"],
                    "last_progress_at_utc": row["last_progress_at_utc"],
                }
                for row in rows
            ],
        }

    def timeline(self, scope: AuthorityScope, task_id: str) -> dict[str, Any]:
        """Everything that happened to this task, in order."""
        self._require_task(scope, task_id)
        return {
            "format": "atmem-task-timeline-v1",
            "task_id": task_id,
            "revisions": self.store.list_task_revisions(task_id),
            "steps": self.store.list_task_steps(task_id),
            "proposals": self.store.list_task_proposals(task_id),
            "deliveries": self.store.list_task_deliveries(task_id),
        }

    # --- start --------------------------------------------------------------

    def start(
        self,
        request: TaskStartRequest,
        *,
        items: tuple[TaskItem, ...] = (),
    ) -> TaskView:
        """Create revision 1 of a governed task.

        The profile's expiry rule is copied onto the task here and never read
        from the profile again: changing a profile must not retroactively
        expire work that started under different rules.
        """
        require(request.actor_role, "change_lifecycle")
        existing = self.store.find_task_by_idempotency_key(
            subject_id=request.scope.subject_id,
            agent_id=request.scope.agent_id,
            workspace_id=request.scope.workspace_id,
            idempotency_key=request.idempotency_key,
        )
        if existing is not None:
            return self._view(existing)

        profile = self.registry.get(request.profile_version)
        if profile is None:
            raise TaskStateError(
                "task_not_eligible",
                f"unknown task profile version: {request.profile_version!r}",
            )
        now = self.clock.now()
        now_iso = to_iso(now)
        state = TaskState(
            task_id=request.task_id,
            scope=request.scope,
            revision=1,
            lifecycle=TaskLifecycle.OPEN,
            phase=profile.initial_phase,
            goal=request.goal,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            items=tuple(items),
            constraints=tuple(
                TaskConstraint(constraint_id=f"constraint-{index + 1}", text=text)
                for index, text in enumerate(request.constraints)
            ),
            sources_to_inspect=tuple(request.sources_to_inspect),
            created_at=now_iso,
            updated_at=now_iso,
            last_progress_at=now_iso,
        )
        with self.store.transaction():
            task = self.store.insert_task(
                task_id=request.task_id,
                subject_id=request.scope.subject_id,
                agent_id=request.scope.agent_id,
                workspace_id=request.scope.workspace_id,
                profile_id=profile.profile_id,
                profile_version=profile.version,
                goal=request.goal,
                lifecycle=TaskLifecycle.OPEN.value,
                head_revision=1,
                created_at_utc=now_iso,
                last_progress_at_utc=now_iso,
                expiry_rule=profile.expiry.to_dict(),
                clock_source=getattr(self.clock, "source", "system-utc-v1"),
                idempotency_key=request.idempotency_key,
                continues_task_id=request.continues_task_id,
            )
            self._write_revision(
                state,
                actor=request.actor,
                actor_role=request.actor_role,
                reason_codes=["lifecycle_change_accepted"],
                evidence=[ref.to_dict() for ref in request.evidence],
                created_at_utc=now_iso,
                is_progress=False,
            )
            self.store.insert_task_provenance(
                task_id=request.task_id,
                revision=1,
                target_kind="task",
                target_id=request.task_id,
                actor=request.actor,
                actor_role=request.actor_role.value,
                method="task_start",
                assurance=Assurance.OPERATOR_CONFIRMED.value,
                observed_at_utc=now_iso,
                evidence=[ref.to_dict() for ref in request.evidence],
            )
            for item in items:
                self.store.insert_task_provenance(
                    task_id=request.task_id, revision=1, target_kind="item",
                    target_id=item.item_id, actor=request.actor,
                    actor_role=request.actor_role.value, method="task_start",
                    assurance=item.assurance.value, observed_at_utc=now_iso,
                )
            self.store.insert_task_step(
                task_id=request.task_id, step_kind="task_start",
                outcome=StepOutcome.ACCEPTED.value, base_revision=1,
                resulting_revision=1, actor=request.actor,
                recorded_at_utc=now_iso, reason_codes=["lifecycle_change_accepted"],
            )
        return self._view(task)

    # --- transitions --------------------------------------------------------

    def submit(
        self,
        proposal: TaskStateProposal,
        *,
        allow_privileged: bool = False,
        step_kind: str = "host_observation",
    ) -> TransitionDecision:
        """Validate one proposal and, if it is accepted, commit it.

        Every path through this method produces exactly one decision and one
        recorded step, including the paths that change nothing.
        """
        started = self.clock.now()
        row = self.store.get_task(
            subject_id=proposal.scope.subject_id,
            agent_id=proposal.scope.agent_id,
            workspace_id=proposal.scope.workspace_id,
            task_id=proposal.task_id,
        )
        if row is None:
            # Non-disclosing: an unauthorized task and a missing task look the
            # same from outside, so a caller cannot probe for existence.
            raise TaskStateError(
                "task_not_eligible", "no eligible task for this scope and identity"
            )

        replayed = self.store.find_task_proposal(
            proposal.task_id, proposal.idempotency_key
        )
        if replayed is not None:
            if str(replayed["payload_sha256"]) != proposal.payload_digest():
                raise TaskStateError(
                    "task_not_eligible",
                    "proposal idempotency key was reused with a different delta",
                )
            stored = dict(replayed["decision"])
            stored["replayed"] = True
            return _decision_from_dict(stored)

        if not TaskLifecycle(row["lifecycle"]).terminal:
            row = self._expire_if_due(proposal.scope, row) or row

        view = self._view(row)
        decision = evaluate(
            state=view.state,
            profile=view.profile,
            proposal=proposal,
            now_iso=to_iso(self.clock.now()),
            allow_privileged=allow_privileged,
        )
        return self._commit(
            proposal=proposal,
            task=row,
            view=view,
            decision=decision,
            started=started,
            step_kind=step_kind,
        )

    def submit_atbot_observation(
        self,
        scope: AuthorityScope,
        task_id: str,
        observation: str,
        *,
        evidence: tuple[EvidenceRef, ...] = (),
        client: Any | None = None,
    ) -> TransitionDecision:
        """Ask AtBot for a bounded delta, then independently validate and commit it.

        Only the exact scope-authorized snapshot is sent. The companion returns
        no authority decision; every operation is rebuilt as a closed AtMem
        contract and evaluated against the current head again by ``submit``.
        """
        view = self.get(scope, task_id)
        snapshot = view.state.to_dict()
        snapshot["phases"] = list(view.profile.phases)
        if client is None:
            from atmem.control.atbot_companion import AtBotCompanionClient

            client = AtBotCompanionClient()
        result = client.propose_task_state(
            snapshot=snapshot,
            observation=observation,
            task_id=task_id,
            base_revision=view.state.revision,
        )
        delta = result.get("delta") if isinstance(result, dict) else None
        operations: list[TaskOperation] = []
        if isinstance(delta, dict):
            if (
                delta.get("format") != "atbot-task-state-delta-v1"
                or str(delta.get("task_id") or "") != task_id
                or int(delta.get("base_revision") or 0) != view.state.revision
            ):
                raise TaskStateError(
                    "task_not_eligible",
                    "AtBot changed the authorized task identity or base revision",
                )
            for row in delta.get("operations") or ():
                if not isinstance(row, dict):
                    raise TaskStateError("task_not_eligible", "AtBot returned a malformed operation")
                try:
                    operations.append(
                        TaskOperation(
                            kind=OperationKind(str(row["kind"])),
                            item_id=row.get("item_id"),
                            constraint_id=row.get("constraint_id"),
                            source_id=row.get("source_id"),
                            phase=row.get("phase"),
                            status=ItemStatus(str(row["status"])) if row.get("status") else None,
                            content=dict(row["content"]) if isinstance(row.get("content"), dict) else None,
                            reason=row.get("reason"),
                            assurance=Assurance.MODEL_INTERPRETED,
                        )
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise TaskStateError(
                        "task_not_eligible", "AtBot returned an invalid operation"
                    ) from exc
        if not operations:
            # A companion that finds no supported progress still resolves to
            # the normal recorded `no_change` path; it never invents work.
            operations.append(
                TaskOperation(
                    kind=OperationKind.SET_PHASE,
                    phase=view.state.phase,
                    assurance=Assurance.MODEL_INTERPRETED,
                )
            )
        digest = sha256_hex(
            canonical_json(
                {
                    "task_id": task_id,
                    "base_revision": view.state.revision,
                    "observation_sha256": sha256_hex(str(observation)),
                    "operations": [operation.to_dict() for operation in operations],
                }
            )
        )
        proposal = TaskStateProposal(
            proposal_id=f"proposal_{digest[:32]}",
            task_id=task_id,
            scope=scope,
            base_revision=view.state.revision,
            idempotency_key=f"atbot:{digest}",
            actor="atbot",
            actor_role=ActorRole.ATBOT_INTELLIGENCE,
            assurance=Assurance.MODEL_INTERPRETED,
            operations=tuple(operations),
            evidence=evidence,
        )
        return self.submit(proposal, step_kind="atbot_observation")

    def _commit(
        self,
        *,
        proposal: TaskStateProposal,
        task: dict[str, Any],
        view: TaskView,
        decision: PolicyDecision,
        started: Any,
        step_kind: str,
    ) -> TransitionDecision:
        now = self.clock.now()
        now_iso = to_iso(now)
        outcome = decision.outcome
        resulting_revision: int | None = None

        with self.store.transaction():
            if decision.accepted:
                assert decision.next_state is not None
                try:
                    self._write_revision(
                        decision.next_state,
                        actor=proposal.actor,
                        actor_role=proposal.actor_role,
                        reason_codes=list(decision.reason_codes),
                        evidence=[ref.to_dict() for ref in proposal.evidence],
                        created_at_utc=now_iso,
                        is_progress=decision.is_progress,
                    )
                    advanced = self.store.advance_task_head(
                        task_id=proposal.task_id,
                        expected_head=view.state.revision,
                        new_head=decision.next_state.revision,
                        updated_at_utc=now_iso,
                        last_progress_at_utc=now_iso if decision.is_progress else None,
                    )
                except sqlite3.IntegrityError:
                    # Another writer already claimed this base revision.
                    advanced = False
                if not advanced:
                    outcome = StepOutcome.CONFLICT
                    decision = PolicyDecision(
                        outcome=StepOutcome.CONFLICT,
                        reason_codes=("concurrent_successor_committed",),
                    )
                else:
                    resulting_revision = decision.next_state.revision
                    self._write_transition_provenance(
                        proposal=proposal,
                        revision=resulting_revision,
                        previous=view.state,
                        current=decision.next_state,
                        now_iso=now_iso,
                    )
            elif outcome is StepOutcome.NO_CHANGE:
                resulting_revision = view.state.revision

            typed = TransitionDecision(
                decision_id=f"decision_{sha256_hex(proposal.proposal_id + now_iso)[:32]}",
                proposal_id=proposal.proposal_id,
                task_id=proposal.task_id,
                scope=proposal.scope,
                outcome=outcome,
                reason_codes=decision.reason_codes,
                base_revision=proposal.base_revision,
                resulting_revision=resulting_revision,
                decided_at=now_iso,
                assurance=decision.effective_assurance,
                evidence=proposal.evidence,
                guards=decision.guards,
            )
            try:
                self._record_proposal(proposal, typed, outcome, resulting_revision, now_iso)
            except sqlite3.IntegrityError as exc:
                # A proposal id is an identity, not a label. Reusing one for a
                # different delta is a caller error, not a silent overwrite.
                raise TaskStateError(
                    "task_not_eligible",
                    f"proposal id {proposal.proposal_id!r} is already recorded "
                    "for a different request",
                ) from exc
            self.store.insert_task_step(
                task_id=proposal.task_id,
                step_kind=step_kind,
                outcome=outcome.value,
                proposal_id=proposal.proposal_id,
                base_revision=proposal.base_revision,
                resulting_revision=resulting_revision,
                reason_codes=list(decision.reason_codes),
                action_fingerprint=proposal.action_fingerprint,
                actor=proposal.actor,
                duration_ms=elapsed_ms(started, now),
                recorded_at_utc=now_iso,
            )
        return typed

    def _record_proposal(
        self,
        proposal: TaskStateProposal,
        typed: TransitionDecision,
        outcome: StepOutcome,
        resulting_revision: int | None,
        now_iso: str,
    ) -> None:
        self.store.insert_task_proposal(
            proposal_id=proposal.proposal_id,
            task_id=proposal.task_id,
            subject_id=proposal.scope.subject_id,
            agent_id=proposal.scope.agent_id,
            workspace_id=proposal.scope.workspace_id,
            idempotency_key=proposal.idempotency_key,
            payload_sha256=proposal.payload_digest(),
            base_revision=proposal.base_revision,
            actor=proposal.actor,
            actor_role=proposal.actor_role.value,
            proposal=proposal.to_dict(),
            decision=typed.to_dict(),
            outcome=outcome.value,
            resulting_revision=resulting_revision,
            created_at_utc=now_iso,
        )

    # --- lifecycle ----------------------------------------------------------

    def pause(
        self, scope: AuthorityScope, task_id: str, *, actor: str,
        actor_role: ActorRole, reason: str,
    ) -> TaskView:
        return self._lifecycle(
            scope, task_id, TaskLifecycle.PAUSED, actor=actor,
            actor_role=actor_role, reason=reason,
        )

    def resume(
        self, scope: AuthorityScope, task_id: str, *, actor: str,
        actor_role: ActorRole, reason: str = "resumed",
    ) -> TaskView:
        return self._lifecycle(
            scope, task_id, TaskLifecycle.OPEN, actor=actor,
            actor_role=actor_role, reason=reason,
        )

    def complete(
        self, scope: AuthorityScope, task_id: str, *, actor: str,
        actor_role: ActorRole, reason: str = "completed",
    ) -> TaskView:
        """Complete a task, but only if the profile's gates are satisfied."""
        row = self._require_task(scope, task_id)
        view = self._view(row)
        allowed, reasons, guard = evaluate_completion(view.state, view.profile)
        if not allowed:
            assert guard is not None
            raise TaskCompletionDenied(reasons[0], guard)
        return self._lifecycle(
            scope, task_id, TaskLifecycle.COMPLETED, actor=actor,
            actor_role=actor_role, reason=reason,
        )

    def cancel(
        self, scope: AuthorityScope, task_id: str, *, actor: str,
        actor_role: ActorRole, reason: str,
    ) -> TaskView:
        if not reason.strip():
            raise TaskStateError("reason_required", "cancellation requires a reason")
        return self._lifecycle(
            scope, task_id, TaskLifecycle.CANCELLED, actor=actor,
            actor_role=actor_role, reason=reason,
        )

    def _lifecycle(
        self,
        scope: AuthorityScope,
        task_id: str,
        target: TaskLifecycle,
        *,
        actor: str,
        actor_role: ActorRole,
        reason: str,
        expiry_rule: str | None = None,
    ) -> TaskView:
        """Change lifecycle and record it as a revision, with pause accounting."""
        if target is TaskLifecycle.EXPIRED:
            require(actor_role, "expire_task")
        else:
            require(actor_role, "change_lifecycle")
        row = self._require_task(scope, task_id)
        if target is not TaskLifecycle.EXPIRED and not (
            TaskLifecycle(row["lifecycle"]).terminal
        ):
            # A task that aged out while nothing was running is already
            # terminal; the operator's request arrives too late and must be
            # refused rather than reviving it. (Skipped when this call *is*
            # the expiry, which would otherwise recurse.)
            row = self._expire_if_due(scope, row) or row
        current = TaskLifecycle(row["lifecycle"])
        if current.terminal:
            raise TaskStateError(
                "task_is_terminal",
                f"task {task_id} is {current.value} and cannot be changed",
            )
        if current is target:
            return self._view(row)

        now = self.clock.now()
        now_iso = to_iso(now)
        view = self._view(row)
        next_state = replace(
            view.state,
            revision=view.state.revision + 1,
            parent_revision=view.state.revision,
            lifecycle=target,
            updated_at=now_iso,
        )

        # Pause accounting: opening a pause records when it began; closing one
        # adds its duration so the no-progress clock excludes paused time.
        paused_at: str | None = None
        clear_paused = False
        add_paused_ms = 0
        if target is TaskLifecycle.PAUSED:
            paused_at = now_iso
        elif row.get("paused_at_utc"):
            clear_paused = True
            add_paused_ms = elapsed_ms(from_iso(str(row["paused_at_utc"])), now)

        with self.store.transaction():
            self._write_revision(
                next_state,
                actor=actor,
                actor_role=actor_role,
                reason_codes=["lifecycle_change_accepted"],
                evidence=(
                    [{"kind": "policy_rule", "reference_id": expiry_rule}]
                    if expiry_rule
                    else []
                ),
                created_at_utc=now_iso,
                is_progress=False,
            )
            advanced = self.store.advance_task_head(
                task_id=task_id,
                expected_head=view.state.revision,
                new_head=next_state.revision,
                updated_at_utc=now_iso,
                lifecycle=target.value,
                terminal_reason=reason if target.terminal else None,
                paused_at_utc=paused_at,
                clear_paused_at=clear_paused,
                add_paused_ms=add_paused_ms,
            )
            if not advanced:
                raise TaskStateError(
                    "stale_base_revision",
                    "the task changed while this lifecycle request was in flight",
                )
            self.store.insert_task_provenance(
                task_id=task_id,
                revision=next_state.revision,
                target_kind="lifecycle",
                target_id=target.value,
                actor=actor,
                actor_role=actor_role.value,
                method=f"lifecycle_{target.value}",
                assurance=(
                    Assurance.RULE_EXTRACTED.value
                    if target is TaskLifecycle.EXPIRED
                    else Assurance.OPERATOR_CONFIRMED.value
                ),
                observed_at_utc=now_iso,
                evidence=(
                    [{"kind": "policy_rule", "reference_id": expiry_rule}]
                    if expiry_rule
                    else []
                ),
            )
            self.store.insert_task_step(
                task_id=task_id,
                step_kind=f"lifecycle_{target.value}",
                outcome=StepOutcome.ACCEPTED.value,
                base_revision=view.state.revision,
                resulting_revision=next_state.revision,
                reason_codes=["lifecycle_change_accepted"],
                actor=actor,
                recorded_at_utc=now_iso,
            )
        return self._view(self._require_task(scope, task_id))

    # --- correction ---------------------------------------------------------

    def correct(
        self,
        scope: AuthorityScope,
        task_id: str,
        proposal: TaskStateProposal,
        *,
        reason: str,
    ) -> TransitionDecision:
        """An authorized operator correction: appends history, never overwrites."""
        require(proposal.actor_role, "correct_state")
        if not reason.strip():
            raise TaskStateError("reason_required", "a correction requires a reason")
        return self.submit(
            replace(proposal, reason=reason),
            allow_privileged=True,
            step_kind="operator_correction",
        )

    # --- expiry -------------------------------------------------------------

    def evaluate_expiry(
        self, scope: AuthorityScope, task_id: str
    ) -> dict[str, Any] | None:
        """Expire one task if its bound rule is due. Returns the task if changed."""
        row = self.store.get_task(
            subject_id=scope.subject_id, agent_id=scope.agent_id,
            workspace_id=scope.workspace_id, task_id=task_id,
        )
        if row is None:
            return None
        return self._expire_if_due(scope, row)

    def scan_for_expiry(self, *, limit: int = 200) -> dict[str, Any]:
        """Idempotent maintenance scan. Terminal tasks are never re-evaluated."""
        expired: list[str] = []
        for row in self.store.tasks_due_for_expiry_scan(limit=limit):
            if self._expire_if_due(self._scope_of(row), row) is not None:
                expired.append(str(row["task_id"]))
        return {
            "format": "atmem-task-expiry-scan-v1",
            "scanned_at_utc": to_iso(self.clock.now()),
            "expired_task_ids": expired,
            "expired": len(expired),
        }

    def expiry_status(self, row: dict[str, Any]) -> dict[str, Any]:
        """How close this task is to each of its bound thresholds."""
        rule = dict(row.get("expiry_rule") or {})
        now = self.clock.now()
        created = from_iso(str(row["created_at_utc"]))
        progressed = from_iso(str(row["last_progress_at_utc"]))
        absolute_ms = elapsed_ms(created, now)

        # No-progress age counts only active time: completed paused intervals
        # are subtracted, and a currently open pause is subtracted live.
        paused_ms = int(row.get("no_progress_paused_ms") or 0)
        if row.get("paused_at_utc"):
            paused_ms += elapsed_ms(from_iso(str(row["paused_at_utc"])), now)
        no_progress_ms = max(0, elapsed_ms(progressed, now) - paused_ms)

        max_absolute = rule.get("max_absolute_age_ms")
        max_no_progress = rule.get("max_no_progress_age_ms")
        due_reason: str | None = None
        if max_absolute is not None and absolute_ms >= int(max_absolute):
            due_reason = "expired_absolute_age"
        elif max_no_progress is not None and no_progress_ms >= int(max_no_progress):
            due_reason = "expired_no_progress"
        return {
            "format": "atmem-task-expiry-status-v1",
            "rule": rule,
            "clock_source": row.get("clock_source"),
            "evaluated_at_utc": to_iso(now),
            "absolute_age_ms": absolute_ms,
            "no_progress_age_ms": no_progress_ms,
            "paused_ms": paused_ms,
            "max_absolute_age_ms": max_absolute,
            "max_no_progress_age_ms": max_no_progress,
            "due": due_reason is not None,
            "due_reason": due_reason,
        }

    def _expire_if_due(
        self, scope: AuthorityScope, row: dict[str, Any]
    ) -> dict[str, Any] | None:
        status = self.expiry_status(row)
        if not status["due"]:
            return None
        try:
            self._lifecycle(
                scope,
                str(row["task_id"]),
                TaskLifecycle.EXPIRED,
                actor="atmem-policy-evaluator",
                actor_role=ActorRole.POLICY_EVALUATOR,
                reason=str(status["due_reason"]),
                expiry_rule=str(status["due_reason"]),
            )
        except TaskStateError as exc:
            # A concurrent evaluator won the race, or the task became terminal
            # between the read and the write. Either way there is exactly one
            # expired head, which is the guarantee that matters.
            if exc.reason_code not in {"task_is_terminal", "stale_base_revision"}:
                raise
        return self.store.get_task(
            subject_id=scope.subject_id, agent_id=scope.agent_id,
            workspace_id=scope.workspace_id, task_id=str(row["task_id"]),
        )

    # --- deletion -----------------------------------------------------------

    def forget(
        self, scope: AuthorityScope, task_id: str, *, actor: str,
        actor_role: ActorRole,
    ) -> dict[str, Any]:
        """Remove a task and everything derived from it, with a receipt."""
        require(actor_role, "delete_state")
        row = self.store.get_task(
            subject_id=scope.subject_id, agent_id=scope.agent_id,
            workspace_id=scope.workspace_id, task_id=task_id,
        )
        if row is None:
            raise TaskStateError(
                "task_not_eligible", "no eligible task for this scope and identity"
            )
        revisions = len(self.store.list_task_revisions(task_id))
        result = self.store.delete_task(
            subject_id=scope.subject_id, agent_id=scope.agent_id,
            workspace_id=scope.workspace_id, task_id=task_id,
        )
        return {
            "format": "atmem-task-deletion-receipt-v1",
            "task_id": task_id,
            "deleted": result["deleted"],
            "removed": result["removed"],
            "revisions_removed": revisions,
            "goal_sha256": f"sha256:{sha256_hex(str(row['goal']))}",
            "actor": actor,
            "deleted_at_utc": to_iso(self.clock.now()),
        }

    # --- internals ----------------------------------------------------------

    def _require_task(self, scope: AuthorityScope, task_id: str) -> dict[str, Any]:
        row = self.store.get_task(
            subject_id=scope.subject_id, agent_id=scope.agent_id,
            workspace_id=scope.workspace_id, task_id=task_id,
        )
        if row is None:
            raise TaskStateError(
                "task_not_eligible", "no eligible task for this scope and identity"
            )
        return row

    def _view(self, row: dict[str, Any]) -> TaskView:
        revision = self.store.get_task_revision(
            str(row["task_id"]), int(row["head_revision"])
        )
        assert revision is not None, "a task always has its head revision stored"
        state = _state_from_dict(revision["state"])
        profile = self.registry.require(str(row["profile_version"]))
        return TaskView(
            task=row,
            state=state,
            profile=profile,
            summary=summarize(state, profile),
        )

    def _scope_of(self, row: dict[str, Any]) -> AuthorityScope:
        return AuthorityScope(
            subject_id=str(row["subject_id"]),
            agent_id=str(row["agent_id"]),
            workspace_id=str(row["workspace_id"]),
        )

    def _write_revision(
        self,
        state: TaskState,
        *,
        actor: str,
        actor_role: ActorRole,
        reason_codes: list[str],
        evidence: list[dict[str, Any]],
        created_at_utc: str,
        is_progress: bool,
    ) -> None:
        self.store.insert_task_revision(
            task_id=state.task_id,
            revision=state.revision,
            parent_revision=state.parent_revision,
            state=state.to_dict(),
            state_sha256=state.state_digest(),
            semantic_sha256=state.semantic_digest(),
            actor=actor,
            actor_role=actor_role.value,
            reason_codes=reason_codes,
            evidence=evidence,
            created_at_utc=created_at_utc,
            is_progress=is_progress,
        )

    def _write_transition_provenance(
        self,
        *,
        proposal: TaskStateProposal,
        revision: int,
        previous: TaskState,
        current: TaskState,
        now_iso: str,
    ) -> None:
        """Record provenance for the transition and for each value it changed."""
        evidence = [ref.to_dict() for ref in proposal.evidence]
        self.store.insert_task_provenance(
            task_id=proposal.task_id, revision=revision, target_kind="transition",
            target_id=proposal.proposal_id, actor=proposal.actor,
            actor_role=proposal.actor_role.value, method="typed_delta",
            assurance=proposal.assurance.value, interpreter=proposal.interpreter,
            observed_at_utc=now_iso, evidence=evidence,
            superseded_revision=previous.revision,
        )
        if current.phase != previous.phase:
            self.store.insert_task_provenance(
                task_id=proposal.task_id, revision=revision, target_kind="field",
                target_id="phase", actor=proposal.actor,
                actor_role=proposal.actor_role.value, method="typed_delta",
                assurance=proposal.assurance.value, observed_at_utc=now_iso,
                evidence=evidence, superseded_revision=previous.revision,
            )
        for item in current.items:
            before = previous.item(item.item_id)
            if before is None or before.status is not item.status:
                # The honest assurance of a status change is the strongest
                # claim actually behind it: the item's own, or the one the
                # proposal made. Policy checks the same pair when it decides
                # whether a completion is evidenced.
                claimed = (
                    item.assurance
                    if item.assurance.rank >= proposal.assurance.rank
                    else proposal.assurance
                )
                self.store.insert_task_provenance(
                    task_id=proposal.task_id, revision=revision,
                    target_kind="status", target_id=item.item_id,
                    actor=proposal.actor, actor_role=proposal.actor_role.value,
                    method="typed_delta", assurance=claimed.value,
                    interpreter=proposal.interpreter, observed_at_utc=now_iso,
                    evidence=evidence,
                    superseded_revision=None if before is None else previous.revision,
                )
        for constraint in current.constraints:
            before_constraint = previous.constraint(constraint.constraint_id)
            if before_constraint is None or (
                before_constraint.satisfied != constraint.satisfied
            ):
                self.store.insert_task_provenance(
                    task_id=proposal.task_id, revision=revision,
                    target_kind="constraint", target_id=constraint.constraint_id,
                    actor=proposal.actor, actor_role=proposal.actor_role.value,
                    method="typed_delta", assurance=proposal.assurance.value,
                    observed_at_utc=now_iso, evidence=evidence,
                )


class TaskCompletionDenied(TaskStateError):
    """Completion was requested while the profile's gates were unsatisfied."""

    def __init__(self, reason_code: str, guard: GuardSignal) -> None:
        super().__init__(reason_code, guard.message)
        self.guard = guard


def _state_from_dict(payload: dict[str, Any]) -> TaskState:
    """Rebuild a snapshot from its stored canonical form."""
    scope = payload["scope"]
    return TaskState(
        task_id=str(payload["task_id"]),
        scope=AuthorityScope(
            subject_id=scope["subject_id"],
            agent_id=scope["agent_id"],
            workspace_id=scope["workspace_id"],
        ),
        revision=int(payload["revision"]),
        lifecycle=TaskLifecycle(payload["lifecycle"]),
        phase=str(payload["phase"]),
        goal=str(payload["goal"]),
        profile_id=str(payload["profile_id"]),
        profile_version=str(payload["profile_version"]),
        items=tuple(_item_from_dict(row) for row in payload.get("items") or ()),
        constraints=tuple(
            TaskConstraint(
                constraint_id=str(row["constraint_id"]),
                text=str(row["text"]),
                satisfied=bool(row.get("satisfied")),
                required_for_completion=bool(row.get("required_for_completion", True)),
            )
            for row in payload.get("constraints") or ()
        ),
        sources_to_inspect=tuple(payload.get("sources_to_inspect") or ()),
        completed_sources=tuple(payload.get("completed_sources") or ()),
        schema_locked=bool(payload.get("schema_locked")),
        created_at=str(payload.get("created_at") or ""),
        updated_at=str(payload.get("updated_at") or ""),
        last_progress_at=str(payload.get("last_progress_at") or ""),
        parent_revision=payload.get("parent_revision"),
        policy_generation=int(payload.get("policy_generation", 1)),
    )


def _item_from_dict(payload: dict[str, Any]) -> TaskItem:
    return TaskItem(
        item_id=str(payload["item_id"]),
        kind=str(payload["kind"]),
        title=str(payload["title"]),
        status=ItemStatus(payload.get("status", "pending")),
        content=dict(payload.get("content") or {}),
        depends_on=tuple(payload.get("depends_on") or ()),
        blocker_reason=payload.get("blocker_reason"),
        skip_reason=payload.get("skip_reason"),
        assurance=Assurance(payload.get("assurance", "asserted")),
        evidence=tuple(
            EvidenceRef(
                kind=str(row["kind"]),
                reference_id=str(row["reference_id"]),
                sha256=row.get("sha256"),
            )
            for row in payload.get("evidence") or ()
        ),
        required=bool(payload.get("required")),
    )


def _decision_from_dict(payload: dict[str, Any]) -> TransitionDecision:
    scope = payload["scope"]
    return TransitionDecision(
        decision_id=str(payload["decision_id"]),
        proposal_id=str(payload["proposal_id"]),
        task_id=str(payload["task_id"]),
        scope=AuthorityScope(
            subject_id=scope["subject_id"],
            agent_id=scope["agent_id"],
            workspace_id=scope["workspace_id"],
        ),
        outcome=StepOutcome(payload["outcome"]),
        reason_codes=tuple(payload.get("reason_codes") or ()),
        base_revision=int(payload["base_revision"]),
        resulting_revision=payload.get("resulting_revision"),
        decided_at=str(payload.get("decided_at") or ""),
        decided_by=str(payload.get("decided_by") or "atmem-authority"),
        assurance=Assurance(payload.get("assurance", "asserted")),
        guards=tuple(
            GuardSignal(
                guard_type=GuardType(row["guard_type"]),
                task_id=str(row["task_id"]),
                revision=int(row["revision"]),
                message=str(row["message"]),
                blocking_item_ids=tuple(row.get("blocking_item_ids") or ()),
                repeated_action_count=int(row.get("repeated_action_count", 0)),
                enforced=bool(row.get("enforced")),
            )
            for row in payload.get("guards") or ()
        ),
        replayed=bool(payload.get("replayed")),
    )
