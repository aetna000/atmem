"""Conservative, source-bound formation through AtMem's governed memory path."""

from __future__ import annotations

from hashlib import sha256
import re

from atmem.code.contracts import CodeMemoryCandidate, CodeObservation, CodeScope
from atmem.core.canonical import canonical_json
from atmem.extract.rules import extract_facts
from atmem.memory import Memory


def memory_subject_id(scope: CodeScope) -> str:
    """Keep project and private lanes distinct in the existing canonical store."""
    lane = {
        "subject_id": scope.subject_id,
        "project_id": scope.project_id,
        "profile_id": scope.profile_id,
        "agent_id": scope.agent_id if scope.profile_id != "shared" else "shared",
    }
    return "code-" + sha256(canonical_json(lane).encode("utf-8")).hexdigest()


class CodeFormation:
    def __init__(self, memory: Memory) -> None:
        self.memory = memory

    def candidate(self, observation: CodeObservation) -> CodeMemoryCandidate | None:
        # Tool output and task summaries are useful evidence, but neither is
        # a user-authorized project fact by itself. Later attestation may add
        # them through a separate governed path.
        if observation.kind != "user_turn":
            return None
        extracted = extract_facts(observation.content, source_type="user_message")
        if not extracted:
            return None
        fact = extracted[0]
        if not fact.content.strip() or len(fact.content.encode("utf-8")) > 2_000:
            return None
        memory_class = (
            "preference" if re.search(r"\b(?:my|I (?:prefer|like|avoid))\b", fact.content, re.I)
            else "project_fact"
        )
        return CodeMemoryCandidate(
            observation.event_id, fact.content, memory_class,
            observation.content_sha256, observation.scope,
        )

    def form(self, observation: CodeObservation) -> dict:
        candidate = self.candidate(observation)
        if candidate is None:
            return {"event_id": observation.event_id, "formed": False,
                    "reason": "no_supported_durable_fact"}
        derived_subject = memory_subject_id(observation.scope)
        self.memory.store.register_code_scope_subject(
            owner_subject_id=observation.scope.subject_id,
            derived_subject_id=derived_subject,
            project_id=observation.scope.project_id,
            profile_id=observation.scope.profile_id,
            agent_id=(observation.scope.agent_id if observation.scope.profile_id != "shared" else "shared"),
        )
        result = self.memory.remember(
            derived_subject, observation.content,
            session_id=observation.session_id, turn_id=observation.turn_id,
            source_type="user_message", actor=f"code:{observation.host}",
            raw={
                "code_observation_id": observation.event_id,
                "code_source_ref": observation.source_ref,
                "code_source_sha256": observation.content_sha256,
                "code_project_id": observation.scope.project_id,
                "code_profile_id": observation.scope.profile_id,
                "code_agent_id": observation.scope.agent_id,
                "code_git_revision": observation.git_revision,
                "code_memory_class": candidate.memory_class,
            },
        )
        return {"event_id": observation.event_id,
                "formed": bool(result.get("records") or result.get("duplicate_ids")),
                "record_ids": [record["id"] for record in result.get("records", [])],
                "duplicate_ids": result.get("duplicate_ids", []),
                "refused": result.get("refused", [])}
