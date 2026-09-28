"""Inert LongMemEval-V2 adapter using only AtMem's public product API.

This file is copied into a pinned official checkout.  It does not inspect
questions, answers, abilities, or benchmark splits while inserting memory.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import uuid

from atmem import Memory as AtMem
from atmem.contracts import (
    AuthorityScope,
    ContextRequestV2,
    EpisodeIngestRequest,
    EpisodePart,
    RecallRequest,
    RetrievalBudget,
)
from atmem.service.household import HouseholdApplication
from memory_modules.memory import Memory, register_memory


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


@register_memory
class AtMemMemory(Memory):
    memory_type = "atmem"

    def __init__(self, memory_params: dict[str, object]) -> None:
        super().__init__(memory_params)
        required = {"database_path", "subject_id", "agent_id", "workspace_id"}
        missing = sorted(required - set(memory_params))
        if missing:
            raise ValueError(f"AtMem memory_params missing: {', '.join(missing)}")
        self.database_path = Path(str(memory_params["database_path"])).expanduser().resolve()
        self.scope = AuthorityScope(
            str(memory_params["subject_id"]),
            str(memory_params["agent_id"]),
            str(memory_params["workspace_id"]),
        )
        self.trajectory_pool_root = (
            Path(str(memory_params["trajectory_pool_root"])).expanduser().resolve()
            if memory_params.get("trajectory_pool_root") else None
        )
        require_encrypted = bool(memory_params.get("require_encrypted", True))
        if require_encrypted:
            status = HouseholdApplication.status(self.database_path)
            if status["state"] != "encrypted" or not status["encrypted_header"]:
                raise RuntimeError(
                    "AtMem LongMemEval adapter requires an initialized encrypted "
                    "household; run `atmem household init <database> --encrypted`"
                )
        self._memory = AtMem(
            self.database_path, retain_query_text=False, auto_vectors=False,
            allow_insecure_typed_development=not require_encrypted,
        )
        self._allow_insecure_typed_development = not require_encrypted

    def insert(self, trajectory: dict[str, object]) -> None:
        trajectory_id = str(trajectory.get("id") or "").strip()
        if not trajectory_id:
            raise ValueError("trajectory.id must be non-empty")
        states = trajectory.get("states")
        if not isinstance(states, list):
            raise ValueError("trajectory.states must be a list")
        parts: list[EpisodePart] = []
        # The official public trajectory schema is explicitly allowlisted.
        # Evaluation annotations or future harness-only fields cannot enter
        # AtMem merely because upstream added them to the same object.
        metadata = _canonical({
            key: trajectory[key]
            for key in ("id", "goal", "outcome", "start_url", "actions")
            if key in trajectory
        })
        parts.append(EpisodePart(
            part_id="trajectory-metadata", ordinal=0, kind="state",
            source_type="tool_output", content=metadata,
            content_sha256=_digest_text(metadata),
        ))
        for state_index, state in enumerate(states):
            if not isinstance(state, dict):
                raise ValueError(f"trajectory state {state_index} must be an object")
            body = _canonical({
                key: state[key]
                for key in (
                    "state_index", "step", "url", "action", "thoughts", "text"
                )
                if key in state
            })
            parts.append(EpisodePart(
                part_id=f"state-{state_index}", ordinal=len(parts), kind="state",
                source_type="tool_output", content=body,
                content_sha256=_digest_text(body),
            ))
            screenshot = state.get("screenshot")
            if screenshot:
                if self.trajectory_pool_root is None:
                    raise ValueError("trajectory_pool_root is required for screenshot references")
                image = self.trajectory_pool_root / trajectory_id / str(screenshot)
                if not image.is_file():
                    raise FileNotFoundError(f"trajectory screenshot is missing: {image}")
                parts.append(EpisodePart(
                    part_id=f"state-{state_index}-screenshot", ordinal=len(parts),
                    kind="media_reference", source_type="tool_output",
                    reference_id=str(image), reference_sha256=_digest_file(image),
                ))
        self._memory.form_episode(EpisodeIngestRequest(
            episode_id=f"trajectory-{trajectory_id}",
            idempotency_key=f"longmemeval-trajectory-{trajectory_id}",
            scope=self.scope,
            parts=tuple(parts),
            binding_method="host_asserted",
            binding_assurance="host_asserted",
            session_id=f"trajectory:{trajectory_id}",
            retain_body=True,
        ))

    def query(self, query: str, query_image: str | None = None) -> list[dict[str, str]]:
        del query_image  # The official reader receives the question image separately.
        request_id = f"lme-{uuid.uuid4().hex}"
        candidates = self._memory.eligible_candidates(RecallRequest(
            request_id=request_id,
            scope=self.scope,
            query=query,
            limit=int(self.memory_params.get("limit", 20)),
            candidate_limit=int(self.memory_params.get("candidate_limit", 200)),
            signals=("lexical", "graph"),
            retrieval_strategy="core-rrf-v1",
        ))
        package = self._memory.prepare_context_v2(ContextRequestV2(
            context_id=f"context-{request_id}",
            candidate_set_id=candidates.candidate_set_id,
            scope=self.scope,
            query=query,
            budget=RetrievalBudget(
                context_bytes=int(self.memory_params.get("context_bytes", 120_000))
            ),
        ))
        result: list[dict[str, str]] = []
        if package.context:
            result.append({"type": "text", "value": package.context})
        for reference in package.media_references:
            image = Path(str(reference["reference_id"]))
            if image.is_file() and _digest_file(image) == reference.get("reference_sha256"):
                result.append({"type": "image", "value": str(image)})
        return result

    def _save_backend(self, output_dir: Path) -> None:
        self._memory.close()
        try:
            shutil.copy2(self.database_path, output_dir / "atmem.db")
            policy = Path(f"{self.database_path}.encryption.json")
            if policy.exists():
                shutil.copy2(policy, output_dir / "atmem.db.encryption.json")
        finally:
            self._memory = AtMem(
                self.database_path, retain_query_text=False, auto_vectors=False,
                allow_insecure_typed_development=self._allow_insecure_typed_development,
            )

    def _load_backend(self, input_dir: Path) -> None:
        source = input_dir / "atmem.db"
        if not source.is_file():
            raise FileNotFoundError(f"saved AtMem database is missing: {source}")
        self._memory.close()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, self.database_path)
        policy = input_dir / "atmem.db.encryption.json"
        if policy.exists():
            shutil.copy2(policy, Path(f"{self.database_path}.encryption.json"))
        self._memory = AtMem(
            self.database_path, retain_query_text=False, auto_vectors=False,
            allow_insecure_typed_development=self._allow_insecure_typed_development,
        )
