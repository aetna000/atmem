"""Ordered, preview-only lifecycle policy evaluation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .models import LifecyclePolicy, LifecycleState


def preview_policies(records: Iterable[dict[str, Any]], policies: Iterable[LifecyclePolicy], *, evaluated_at: datetime | None = None) -> list[dict[str, Any]]:
    now = (evaluated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ordered = sorted(policies, key=lambda item: (item.priority, item.policy_id))
    proposals: list[dict[str, Any]] = []
    for record in records:
        created = datetime.fromisoformat(str(record["created_at"]).replace("Z", "+00:00"))
        for policy in ordered:
            age = now - created
            target = None
            reason = None
            if policy.expire_after_days is not None and age >= timedelta(days=policy.expire_after_days):
                target, reason = LifecycleState.FORGOTTEN, "policy_expired"
            elif policy.archive_after_days is not None and age >= timedelta(days=policy.archive_after_days):
                target, reason = LifecycleState.ARCHIVED, "policy_archive_due"
            elif policy.review_after_days is not None and age >= timedelta(days=policy.review_after_days):
                reason = "policy_review_due"
            if reason:
                proposals.append({"record_id": record["id"], "policy_id": policy.policy_id, "proposed_state": target.value if target else None, "reason_code": reason, "automatic": policy.automatic, "evaluated_at": now.isoformat()})
                break
    return proposals
