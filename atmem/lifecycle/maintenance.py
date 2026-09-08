"""Verified forgetting across every declared derived consumer."""

from __future__ import annotations

from typing import Any

from .models import LifecycleState, LifecycleTransition
from .service import LifecycleService


def forget_with_verification(service: LifecycleService, subject_id: str, record_id: str, *, generation: int, actor: str, reason: str, backup_policy: dict[str, Any] | None = None) -> dict[str, Any]:
    receipt = service.transition(LifecycleTransition(record_id, subject_id, LifecycleState.FORGOTTEN, generation, actor, reason))
    backup = dict(backup_policy or {"status": "not_registered", "physical_removal_proven": False})
    return {"format": "atmem-forget-verification-v1", "transition": receipt.to_dict(), "derived_verified": receipt.invalidations["verified"], "backup": backup, "fully_verified": receipt.invalidations["verified"] and backup.get("status") in {"not_applicable", "crypto_erased", "retention_expired"}}
