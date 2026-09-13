"""Scope-authorized execution and coverage reads."""

from __future__ import annotations

from typing import Any

from atmem.execution.projection import execution_projection
from atmem.service.application import APIError, APIPrincipal


class ExecutionService:
    def __init__(self, manager: Any) -> None:
        self.manager = manager

    def get(self, principal: APIPrincipal, execution_id: str) -> dict[str, Any]:
        principal.require("audit:read")
        entries = self.manager.execution_events(
            subject_id=principal.subject_id, execution_id=execution_id, limit=100
        )
        try:
            return execution_projection(
                entries, subject_id=principal.subject_id, execution_id=execution_id
            )
        except LookupError as exc:
            # Deliberately identical for missing and inaccessible IDs.
            raise APIError("not_found", "execution not found", status=404) from exc

    def list(self, principal: APIPrincipal, *, limit: int = 50) -> dict[str, Any]:
        principal.require("audit:read")
        rows = self.manager.blackbox_runs(limit=max(1, min(limit, 100))).get("runs") or []
        visible = [row for row in rows if row.get("subject_id") == principal.subject_id]
        return {
            "format": "atmem-execution-list-v1",
            "executions": visible,
            "count": len(visible),
            "scope": "authorized_subject",
        }
