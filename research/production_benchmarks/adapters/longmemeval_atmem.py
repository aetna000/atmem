"""Inert LongMemEval-V2 adapter using only AtMem's public product API.

This file is copied into a pinned official checkout.  It does not inspect
questions, answers, abilities, or benchmark splits while inserting memory.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import atexit
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


def _ordered_action_batches(
    trajectory_id: str, actions: list[object], *, maximum_bytes: int = 7_000
) -> tuple[str, ...]:
    """Serialize every source action into bounded, ordered JSON batches."""
    batches: list[str] = []
    current: list[object] = []
    offset = 0
    for action in actions:
        candidate = [*current, action]
        encoded = _canonical({
            "id": trajectory_id,
            "action_offset": offset,
            "actions": candidate,
        })
        if current and len(encoded.encode("utf-8")) > maximum_bytes:
            batches.append(_canonical({
                "id": trajectory_id,
                "action_offset": offset,
                "actions": current,
            }))
            offset += len(current)
            current = [action]
        else:
            current = candidate
    if current:
        batches.append(_canonical({
            "id": trajectory_id,
            "action_offset": offset,
            "actions": current,
        }))
    return tuple(batches)


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
        self._sensitive_observation_handling = (
            "admit_encrypted" if require_encrypted else "review"
        )
        self._media_cache = Path(tempfile.mkdtemp(prefix="atmem-lme-media-"))
        self._last_query_metadata: dict[str, object] | None = None
        atexit.register(shutil.rmtree, self._media_cache, True)

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
        metadata_payload = {
            key: trajectory[key]
            for key in (
                "id", "domain", "environment", "goal", "outcome", "start_url",
                "actions",
            )
            if key in trajectory
        }
        actions = metadata_payload.pop("actions", None)
        if actions is None:
            # Preserve the source trajectory's ordered action sequence in its
            # own bounded metadata unit.  This is derived exclusively from the
            # inserted episode—not questions, answers, or benchmark labels—and
            # gives procedure retrieval the same immutable navigation surface
            # that raw-state slice baselines expose.
            actions = [
                state["action"]
                for state in states
                if isinstance(state, dict)
                and state.get("action") not in (None, "")
            ]
        metadata = _canonical(metadata_payload)
        parts.append(EpisodePart(
            part_id="trajectory-metadata", ordinal=0, kind="state",
            source_type="tool_output", content=metadata,
            content_sha256=_digest_text(metadata),
        ))
        if not isinstance(actions, list):
            raise ValueError("trajectory.actions must be a list when present")
        for batch_index, action_batch in enumerate(
            _ordered_action_batches(trajectory_id, actions)
        ):
            parts.append(EpisodePart(
                part_id=f"trajectory-actions-{batch_index}",
                ordinal=len(parts),
                kind="state",
                source_type="tool_output",
                content=action_batch,
                content_sha256=_digest_text(action_batch),
            ))
        for state_index, state in enumerate(states):
            if not isinstance(state, dict):
                raise ValueError(f"trajectory state {state_index} must be an object")
            body = _canonical({
                key: state[key]
                for key in (
                    "state_index", "step", "url", "action", "thought", "thoughts",
                    "text", "accessibility_tree",
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
                source_root = self.trajectory_pool_root.resolve()
                image = (source_root / str(screenshot)).resolve()
                if source_root != image and source_root not in image.parents:
                    raise ValueError("trajectory screenshot escapes its source root")
                if not image.is_file():
                    raise FileNotFoundError(f"trajectory screenshot is missing: {image}")
                parts.append(EpisodePart(
                    part_id=f"state-{state_index}-screenshot", ordinal=len(parts),
                    kind="media_reference", source_type="tool_output",
                    reference_id=str(image), reference_sha256=_digest_file(image),
                ))
        request = EpisodeIngestRequest(
            episode_id=f"trajectory-{trajectory_id}",
            idempotency_key=f"longmemeval-trajectory-{trajectory_id}",
            scope=self.scope,
            parts=tuple(parts),
            binding_method="host_asserted",
            binding_assurance="host_asserted",
            session_id=f"trajectory:{trajectory_id}",
            retain_body=True,
            # LongMemEval is a synthetic, pinned corpus and this run is an
            # explicit evaluation opt-in.  Preserve synthetic UI observations
            # in the encrypted household instead of creating an unattended
            # human-review queue for words such as "salary" or "diagnosis".
            # Normal product ingestion retains the conservative review default.
            sensitive_observation_handling=self._sensitive_observation_handling,
        )
        source_bytes = sum(
            len((part.content or "").encode("utf-8")) for part in parts
        ) + sum(
            Path(str(part.reference_id)).stat().st_size
            for part in parts if part.reference_id
        )
        budget = RetrievalBudget(
            source_bytes=max(262_144, source_bytes),
            proposals=max(256, len(parts) * 8),
            wall_time_ms=60_000,
        )
        formed = self._memory.form_episode(request, budget=budget)
        previous_pending: tuple[tuple[str, str], ...] | None = None
        for _ in range(1023):
            pending = tuple(
                (
                    str(position.get("part_id") or ""),
                    str(position.get("proposal_id") or ""),
                )
                for position in formed["receipt"].get("next_positions") or ()
            )
            if not pending:
                break
            # Large enterprise accessibility trees can legitimately require
            # more than 32 bounded proposal batches.  Continue while the
            # durable cursor advances, but fail immediately on a true stall.
            if pending == previous_pending:
                raise RuntimeError(
                    f"AtMem formation stalled for trajectory {trajectory_id}; "
                    f"pending={len(pending)}"
                )
            previous_pending = pending
            formed = self._memory.form_episode(request, budget=budget)
        receipt = formed["receipt"]
        if (
            not receipt.get("processing_complete")
            or not receipt.get("representation_complete")
            or not receipt.get("retrieval_ready")
        ):
            raise RuntimeError(
                f"AtMem did not completely represent trajectory {trajectory_id}; "
                "refusing an unusable LongMemEval checkpoint; "
                f"reasons={receipt.get('reason_codes')}; "
                f"pending={len(receipt.get('next_positions') or ())}"
            )

    def query(self, query: str, query_image: str | None = None) -> list[dict[str, str]]:
        total_input_bytes = int(
            self.memory_params.get("total_input_bytes", 8_388_608)
        )
        total_input_bytes -= int(
            self.memory_params.get("reader_overhead_bytes", 131_072)
        )
        if total_input_bytes <= 0:
            raise RuntimeError("reader overhead exhausts the frozen input budget")
        question_media_bytes = 0
        if query_image is not None:
            question_path = Path(query_image)
            if not question_path.is_file():
                raise RuntimeError("question image is missing")
            question_media_bytes = 64 + 4 * ((question_path.stat().st_size + 2) // 3)
        memory_input_bytes = total_input_bytes - question_media_bytes
        if memory_input_bytes <= len(query.encode("utf-8")):
            raise RuntimeError("question exhausts the frozen total-input budget")
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
                # Keep the reader-facing evidence package bounded.  The source
                # archive remains lossless in AtMem; retrieval should expose a
                # small, complementary package rather than make the reader
                # rediscover evidence inside a near-context-window dump.
                context_bytes=int(self.memory_params.get("context_bytes", 32_768)),
                total_input_bytes=memory_input_bytes,
            ),
        ))
        self._last_query_metadata = {
            "format": "atmem-longmemeval-query-metadata-v1",
            "context_id": package.context_id,
            "preparation_id": package.preparation_id,
            "profile_id": package.profile_id,
            "need": package.need.to_dict(),
            "sufficiency": package.sufficiency.to_dict(),
            "record_ids": list(package.record_ids),
            "source_ids": list(package.source_ids),
            "provenance": list(package.provenance),
            "excluded_evidence_ids": list(package.excluded_evidence_ids),
            "reason_codes": list(package.reason_codes),
            "context_sha256": package.context_sha256,
        }
        result: list[dict[str, str]] = []
        delivered_bytes = (
            len(query.encode("utf-8"))
            + question_media_bytes
            + len(package.context.encode("utf-8"))
        )
        if package.context:
            result.append({"type": "text", "value": package.context})
        for reference in package.media_references:
            image = Path(str(reference["reference_id"]))
            if (
                str(reference["reference_id"]).startswith("atmem-protected:")
                or not image.is_file()
                or _digest_file(image) != reference.get("reference_sha256")
            ):
                media_id = str(reference.get("media_id") or "")
                if not media_id:
                    raise RuntimeError("required media is missing and has no protected copy")
                suffix = str(reference.get("original_suffix") or "")
                if not suffix.startswith(".") or len(suffix) > 16:
                    suffix = ".bin"
                image = self._memory.materialize_protected_media(
                    self.scope, media_id, self._media_cache / f"{media_id}{suffix}"
                )
            delivered_bytes += 64 + 4 * ((image.stat().st_size + 2) // 3)
            if delivered_bytes > total_input_bytes:
                raise RuntimeError("reader input exceeds the frozen total-input budget")
            result.append({"type": "image", "value": str(image)})
        return result

    def post_query_hook(
        self,
        *,
        query: str,
        query_image: str | None,
        memory_context: list[dict[str, str]],
    ) -> dict[str, object] | None:
        """Expose content-free product receipts to the evaluator harness."""
        metadata = self._last_query_metadata
        self._last_query_metadata = None
        if metadata is None:
            raise RuntimeError("AtMem query metadata is missing")
        return metadata

    @classmethod
    def reconcile_loaded_memory_config(
        cls,
        saved_config: dict[str, object],
        requested_config: dict[str, object] | None,
    ) -> dict[str, object]:
        """Allow only the run-local database destination to change on restore."""
        if requested_config is None:
            return {
                "memory_type": str(saved_config["memory_type"]),
                "memory_params": dict(saved_config["memory_params"]),
            }
        if saved_config.get("memory_type") != cls.memory_type:
            raise RuntimeError("saved AtMem memory type does not match the adapter")
        if requested_config.get("memory_type") != cls.memory_type:
            raise RuntimeError("requested AtMem memory type does not match the adapter")
        saved_params = dict(saved_config["memory_params"])
        requested_params = dict(requested_config["memory_params"])
        saved_database = str(saved_params.pop("database_path", "")).strip()
        requested_database = str(requested_params.pop("database_path", "")).strip()
        if not saved_database or not requested_database:
            raise RuntimeError("loaded AtMem memory requires a database path")
        # The official runner reconstructs only the run-local identity fields;
        # retrieval limits are persisted by the checkpoint.  Preserve every
        # saved parameter, while still rejecting any explicit runtime override
        # that differs from the checkpoint.  This keeps restoration immutable
        # without requiring the runner to duplicate adapter-specific defaults.
        conflicting = {
            name
            for name, value in requested_params.items()
            if name not in saved_params or saved_params[name] != value
        }
        if conflicting:
            raise RuntimeError(
                "loaded AtMem memory parameters differ beyond the run-local database path: "
                + ", ".join(sorted(conflicting))
            )
        return {
            "memory_type": cls.memory_type,
            "memory_params": {
                **saved_params,
                "database_path": requested_database,
            },
        }

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
