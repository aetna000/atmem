"""Answering "where did this come from?" in words, not hashes.

An operator looking at a task should be able to point at any value — a status,
a phase, the goal itself — and get a readable account: who said so, how they
knew, how strongly it is evidenced, which revision introduced it, what it
replaced, and whether it ever reached a model.

Digests are included for verification, but they come last. A person should
never have to interpret a hash to understand their own memory.
"""

from __future__ import annotations

from typing import Any

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import ActorRole, Assurance


# How each assurance class reads to a person, and what it does not claim.
ASSURANCE_LANGUAGE: dict[str, str] = {
    "asserted": "stated without supporting evidence",
    "model_interpreted": "inferred by a model from an observation",
    "rule_extracted": "derived by a deterministic AtMem rule",
    "host_reported": "reported successful by the host's own tool result",
    "operator_confirmed": "confirmed by an authenticated operator",
    "independently_verified": "verified by a registered independent verifier",
}

ROLE_LANGUAGE: dict[str, str] = {
    "atmem_authority": "AtMem itself",
    "policy_evaluator": "AtMem's scoped policy evaluator",
    "atbot_intelligence": "the AtBot intelligence companion",
    "host_agent": "the host agent",
    "operator": "an authenticated operator",
    "administrator": "an administrator",
    "verifier": "a registered verifier",
    "auditor": "an auditor",
    "delegated_provider": "a delegated context provider",
}

METHOD_LANGUAGE: dict[str, str] = {
    "task_start": "recorded when the task was started",
    "typed_delta": "changed by an accepted typed delta",
    "lifecycle_open": "the task was opened",
    "lifecycle_paused": "the task was paused",
    "lifecycle_completed": "the task was completed",
    "lifecycle_cancelled": "the task was cancelled",
    "lifecycle_expired": "the task expired under its bound policy rule",
}


def describe_assurance(value: str) -> str:
    return ASSURANCE_LANGUAGE.get(value, value.replace("_", " "))


def describe_role(value: str) -> str:
    return ROLE_LANGUAGE.get(value, value.replace("_", " "))


def describe_method(value: str) -> str:
    return METHOD_LANGUAGE.get(value, value.replace("_", " "))


class ProvenanceResolver:
    """Scope-authorized lineage for one task value or status."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def resolve(
        self,
        scope: AuthorityScope,
        task_id: str,
        *,
        target_kind: str,
        target_id: str,
    ) -> dict[str, Any]:
        """The full history of one value, oldest first.

        Returns an empty, non-disclosing result for a task outside this scope:
        a caller must not learn that someone else's task exists.
        """
        task = self.store.get_task(
            subject_id=scope.subject_id, agent_id=scope.agent_id,
            workspace_id=scope.workspace_id, task_id=task_id,
        )
        if task is None:
            return {
                "format": "atmem-task-provenance-v1",
                "task_id": task_id,
                "target_kind": target_kind,
                "target_id": target_id,
                "found": False,
                "history": [],
                "deliveries": [],
            }

        rows = self.store.list_task_provenance(
            task_id, target_kind=target_kind, target_id=target_id
        )
        return {
            "format": "atmem-task-provenance-v1",
            "task_id": task_id,
            "target_kind": target_kind,
            "target_id": target_id,
            "found": bool(rows),
            "current_revision": int(task["head_revision"]),
            "history": [self._describe(row) for row in rows],
            "deliveries": self._deliveries(task_id, rows),
        }

    def task_lineage(
        self, scope: AuthorityScope, task_id: str
    ) -> dict[str, Any]:
        """Every provenance record for a task, grouped by what it describes."""
        task = self.store.get_task(
            subject_id=scope.subject_id, agent_id=scope.agent_id,
            workspace_id=scope.workspace_id, task_id=task_id,
        )
        if task is None:
            return {
                "format": "atmem-task-lineage-v1",
                "task_id": task_id,
                "found": False,
                "targets": [],
            }
        rows = self.store.list_task_provenance(task_id)
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault((row["target_kind"], row["target_id"]), []).append(row)
        return {
            "format": "atmem-task-lineage-v1",
            "task_id": task_id,
            "found": True,
            "targets": [
                {
                    "target_kind": kind,
                    "target_id": identifier,
                    "history": [self._describe(row) for row in entries],
                }
                for (kind, identifier), entries in sorted(grouped.items())
            ],
        }

    def _describe(self, row: dict[str, Any]) -> dict[str, Any]:
        """One provenance record, explained before it is hashed."""
        actor_role = str(row["actor_role"])
        assurance = str(row["assurance"])
        summary = (
            f"{describe_method(str(row['method'])).capitalize()} by "
            f"{describe_role(actor_role)} ({row['actor']}) at "
            f"{row['observed_at_utc']}; {describe_assurance(assurance)}."
        )
        if row.get("superseded_revision"):
            summary += (
                f" This replaced the value from revision "
                f"{row['superseded_revision']}."
            )
        return {
            "summary": summary,
            "revision": int(row["revision"]),
            "actor": str(row["actor"]),
            "actor_role": actor_role,
            "actor_description": describe_role(actor_role),
            "method": str(row["method"]),
            "method_description": describe_method(str(row["method"])),
            "assurance": assurance,
            "assurance_description": describe_assurance(assurance),
            # An honest ceiling: a host tool result is not independent proof.
            "independently_verified": assurance
            == Assurance.INDEPENDENTLY_VERIFIED.value,
            "interpreter": row.get("interpreter"),
            "observed_at_utc": str(row["observed_at_utc"]),
            "superseded_revision": row.get("superseded_revision"),
            "evidence": list(row.get("evidence") or ()),
        }

    def _deliveries(
        self, task_id: str, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Whether the revisions carrying this value ever reached a model."""
        revisions = {int(row["revision"]) for row in rows}
        return [
            {
                "revision": row["revision"],
                "disposition": row["disposition"],
                "reason_codes": row["reason_codes"],
                "exposed": row["exposed"],
                "prepared_at_utc": row["prepared_at_utc"],
                "context_sha256": row["context_sha256"],
            }
            for row in self.store.list_task_deliveries(task_id)
            if int(row["revision"]) in revisions
        ]
