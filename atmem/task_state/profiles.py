"""Task profiles: the rules a task is governed by, fixed when it starts.

A profile decides which phases exist, which transitions are legal, which items
must be settled before completion, and when a task ages out. It is versioned
and immutable: changing the rules under a running task would invalidate every
decision already made against it, so a new version is registered instead.

The built-in `general-v1` covers the ordinary shape of agent work. It is
deliberately general rather than modelled on any particular workflow product.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from atmem.contracts.task_state import (
    ExpiryPolicy,
    OperationKind,
    TaskProfile,
)


GENERAL_V1 = TaskProfile(
    profile_id="general",
    version="general-v1",
    phases=("plan", "collect", "validate", "execute", "verify", "complete"),
    phase_transitions=(
        ("plan", "collect"),
        ("plan", "execute"),
        ("collect", "validate"),
        ("collect", "collect"),
        ("validate", "collect"),
        ("validate", "execute"),
        ("execute", "verify"),
        ("execute", "execute"),
        ("verify", "execute"),
        ("verify", "complete"),
    ),
    required_item_kinds=(),
    # Reduced first when the context budget is tight, in this exact order.
    optional_context_fields=(
        "completed_sources",
        "sources_to_inspect",
        "item_content",
        "settled_items",
    ),
    permitted_operations=tuple(OperationKind),
    no_progress_action_threshold=3,
    expiry=ExpiryPolicy(),
    allow_schema_extension_phases=("plan", "collect"),
    description=(
        "General agent workflow: plan the work, collect what it needs, "
        "validate that, execute, verify the result, then complete."
    ),
)


BUILT_IN_PROFILES: dict[str, TaskProfile] = {GENERAL_V1.version: GENERAL_V1}


@dataclass(frozen=True, slots=True)
class ProfileRegistration:
    """The result of registering — or dry-running — a custom profile.

    Registration never enables a profile or touches an existing task. It
    records that a versioned rule set exists and what its digest is.
    """

    profile: TaskProfile
    digest: str
    dry_run: bool
    registered: bool
    reason_codes: tuple[str, ...]
    conflict: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "atmem-task-profile-registration-v1",
            "profile_id": self.profile.profile_id,
            "version": self.profile.version,
            "digest": self.digest,
            "dry_run": self.dry_run,
            "registered": self.registered,
            "reason_codes": list(self.reason_codes),
            "conflict": self.conflict,
        }


class ProfileRegistry:
    """Built-in profiles plus any the operator has explicitly registered."""

    def __init__(self, store: Any | None = None) -> None:
        self.store = store

    def get(self, version: str) -> TaskProfile | None:
        selected = BUILT_IN_PROFILES.get(str(version))
        if selected is not None:
            return selected
        if self.store is None:
            return None
        row = self.store.get_task_profile(str(version))
        return TaskProfile.from_dict(row["profile"]) if row else None

    def require(self, version: str) -> TaskProfile:
        profile = self.get(version)
        if profile is None:
            raise ValueError(f"unknown task profile version: {version!r}")
        return profile

    def list_profiles(self) -> list[TaskProfile]:
        rows = list(BUILT_IN_PROFILES.values())
        if self.store is not None:
            rows.extend(
                TaskProfile.from_dict(row["profile"])
                for row in self.store.list_task_profiles()
            )
        return sorted(rows, key=lambda item: item.version)

    def validate(self, payload: Mapping[str, Any]) -> tuple[TaskProfile | None, tuple[str, ...]]:
        """Parse a candidate profile without registering it."""
        try:
            profile = TaskProfile.from_dict(payload)
        except (ValueError, KeyError, TypeError) as exc:
            return None, (f"invalid_profile: {exc}",)
        reasons: list[str] = []
        if profile.version in BUILT_IN_PROFILES:
            reasons.append("version_conflicts_with_built_in_profile")
        if not profile.phase_transitions:
            reasons.append("profile_declares_no_transitions")
        unreachable = _unreachable_phases(profile)
        if unreachable:
            reasons.append(f"unreachable_phases: {sorted(unreachable)}")
        return profile, tuple(reasons)

    def register(
        self,
        payload: Mapping[str, Any],
        *,
        actor: str,
        dry_run: bool = False,
    ) -> ProfileRegistration:
        """Store one immutable versioned profile after validating it.

        Re-registering the identical bytes is idempotent. Re-registering a
        different rule set under the same version is refused: a version that
        can change is not a version.
        """
        profile, reasons = self.validate(payload)
        if profile is None:
            return ProfileRegistration(
                profile=GENERAL_V1,
                digest="",
                dry_run=dry_run,
                registered=False,
                reason_codes=reasons,
            )
        digest = profile.profile_digest()
        if reasons:
            return ProfileRegistration(profile, digest, dry_run, False, reasons)
        if self.store is None:
            return ProfileRegistration(
                profile, digest, dry_run, False, ("no_profile_store_available",)
            )
        existing = self.store.get_task_profile(profile.version)
        if existing is not None:
            if str(existing["digest"]) == digest:
                return ProfileRegistration(
                    profile, digest, dry_run, False, ("already_registered_identically",)
                )
            return ProfileRegistration(
                profile,
                digest,
                dry_run,
                False,
                ("version_already_registered_with_different_rules",),
                conflict=str(existing["digest"]),
            )
        if dry_run:
            return ProfileRegistration(
                profile, digest, True, False, ("dry_run_validated",)
            )
        self.store.insert_task_profile(
            version=profile.version,
            profile_id=profile.profile_id,
            digest=digest,
            profile=profile.to_dict(),
            actor=actor,
        )
        return ProfileRegistration(
            profile, digest, False, True, ("profile_registered",)
        )


def _unreachable_phases(profile: TaskProfile) -> set[str]:
    """Phases no sequence of legal transitions can reach from the first one."""
    reachable = {profile.initial_phase}
    edges = list(profile.phase_transitions)
    changed = True
    while changed:
        changed = False
        for source, target in edges:
            if source in reachable and target not in reachable:
                reachable.add(target)
                changed = True
    return set(profile.phases) - reachable
