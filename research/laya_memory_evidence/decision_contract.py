"""Host-neutral contract for evidence-bound memory understanding proposals."""

from __future__ import annotations

from typing import Any


DISPOSITION_TO_AUTHORITY_PATHS = {
    "STORE": frozenset({"ADD"}),
    "UPDATE": frozenset({"UPDATE", "SUPERSEDE"}),
    "DUPLICATE": frozenset({"NOOP"}),
    "DO_NOT_STORE": frozenset({"REJECT"}),
    "FORGET": frozenset({"GOVERNED_FORGET"}),
    "REVIEW": frozenset({"NOOP", "WITHHOLD_FOR_REVIEW"}),
}

DISPOSITION_RELATIONS = {
    "STORE": frozenset({"new"}),
    "UPDATE": frozenset({"refines", "contradicts", "supersedes"}),
    "DUPLICATE": frozenset({"repeats"}),
    "DO_NOT_STORE": frozenset({"not_applicable"}),
    "FORGET": frozenset({"removes"}),
    "REVIEW": frozenset({"uncertain", "not_applicable", "new", "refines", "contradicts"}),
}


def validate_understanding_proposal(proposal: dict[str, Any]) -> None:
    disposition = proposal.get("disposition")
    if disposition not in DISPOSITION_TO_AUTHORITY_PATHS:
        raise ValueError("unknown memory-understanding disposition")
    meaning = proposal.get("meaning")
    if disposition == "DO_NOT_STORE":
        if meaning is not None:
            raise ValueError("DO_NOT_STORE cannot create a meaning state")
        return
    if disposition == "REVIEW" and meaning is None:
        return
    if not isinstance(meaning, dict):
        raise ValueError("understanding-bearing disposition requires meaning")
    relation = meaning.get("relation_to_prior")
    if relation not in DISPOSITION_RELATIONS[disposition]:
        raise ValueError("relation_to_prior is incompatible with disposition")
    if disposition == "UPDATE" and not proposal.get("supersedes_turn_ids"):
        raise ValueError("UPDATE requires a concrete same-scope prior target")
    if disposition == "DUPLICATE" and not proposal.get("duplicate_of_turn_ids"):
        raise ValueError("DUPLICATE requires a concrete same-scope prior target")


def authority_path_allowed(disposition: str, path: str) -> bool:
    return path in DISPOSITION_TO_AUTHORITY_PATHS.get(disposition, frozenset())
