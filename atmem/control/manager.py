from __future__ import annotations

from dataclasses import replace
from fnmatch import fnmatchcase
import getpass
import json
from pathlib import Path
import re
import shlex
import sqlite3
import sys
from typing import Any, Mapping
import uuid

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.core.storage import HouseholdPolicy
from atmem.extract.rules import extract_facts
from atmem.retrieve.rank import rank_records
from atmem.store.sqlite import utc_now
from atmem.control.models import (
    ControlMode,
    ControlState,
    derive_provider_state,
)
from atmem.control.state import load_effective_state, load_state, state_lock, write_state
from atmem.control.store import ControlStore


DEFAULT_CONTROL_ROOT = Path.home() / ".atmem" / "migrations"
DEFAULT_STATE_PATH = Path.home() / ".atmem" / "control-plane.json"
DEFAULT_SUBJECT = "local-user"
GENERIC_CONFIG_NAME = "generic-adapter.json"

_ALLOWED_TRANSITIONS: dict[ControlMode, frozenset[ControlMode]] = {
    ControlMode.OFF: frozenset({ControlMode.SHADOW, ControlMode.ACTIVE}),
    ControlMode.SHADOW: frozenset({ControlMode.ACTIVE, ControlMode.OFF}),
    ControlMode.ACTIVE: frozenset({ControlMode.SHADOW, ControlMode.OFF}),
}


def _memory_overview_query(query: str) -> bool:
    text = query.casefold()
    return any(
        phrase in text
        for phrase in (
            "what do you remember",
            "what do you know about me",
            "list my memories",
            "show my memories",
            "everything you remember",
        )
    )


def _protocol_fact_key(value: Any) -> str | None:
    """Translate legacy human-readable slots into protocol-safe namespaces."""
    if value is None or not str(value).strip():
        return None
    parts: list[str] = []
    for raw in str(value).casefold().split("::")[:8]:
        part = re.sub(r"[^a-z0-9._-]+", "-", raw.strip()).strip("-._")[:64]
        if not part:
            return None
        parts.append(part)
    return "::".join(parts) if parts else None


def _storage_row(
    storage_id: str,
    label: str,
    role: str,
    path: Path,
    *,
    storage_type: str,
    optional: bool = False,
) -> dict[str, Any]:
    resolved = path.expanduser().resolve(strict=False)
    exists = resolved.is_file()
    try:
        size_bytes = resolved.stat().st_size if exists else 0
    except OSError:
        size_bytes = 0
    return {
        "id": storage_id,
        "label": label,
        "role": role,
        "type": storage_type,
        "path": str(resolved),
        "exists": exists,
        "optional": optional,
        "size_bytes": size_bytes,
    }


def _host_session_identity(
    host_type: str | None, session_key: str | None, session_epoch: str | None
) -> Any:
    """Build a complete host session identity, or None.

    All three parts or nothing. Hosts declare these fields as optional, so a
    partial identity arrives routinely; resolving on whatever survived would be
    guessing at which conversation this is, and guessing is what the binding
    exists to prevent (FR-052).
    """
    from atmem.contracts.task_state import HostSessionIdentity

    if not (host_type and session_key and session_epoch):
        return None
    try:
        return HostSessionIdentity(host_type, session_key, session_epoch)
    except ValueError:
        return None


def _withheld_task_context(
    scope: Any, task_id: str, context_id: str, prepared_at: str,
    reason_codes: tuple[str, ...], *, store: Any = None,
    host_run_id: str | None = None,
) -> dict[str, Any]:
    """A refusal that carries no task-state bytes and creates no exposure.

    A withholding for a task that *did* resolve is recorded as a preparation
    with no exposure (FR-015), so "the agent is being told nothing, and here is
    why" stays answerable from the counters.

    A withholding where no task resolved at all is not recorded: deliveries are
    keyed to a task by foreign key, and there is no task to key it to. Inventing
    a placeholder row would put a task id in the evidence that never existed.
    Those turns are visible instead as the absence of any delivery, which is the
    honest representation of "nothing was resolvable".

    `delivery_id` stays absent either way, so no caller can confirm exposure for
    bytes that were never sent.
    """
    from atmem.task_state.context import withhold

    package = withhold(
        scope=scope, task_id=task_id or "unknown", revision=1,
        context_id=context_id, reason_codes=reason_codes,
        prepared_at=prepared_at,
    )
    if store is not None and task_id:
        try:
            store.insert_task_delivery(
                task_id=task_id or "unknown",
                revision=package.revision,
                subject_id=scope.subject_id,
                agent_id=scope.agent_id,
                workspace_id=scope.workspace_id,
                disposition=package.disposition.value,
                prepared_at_utc=prepared_at,
                reason_codes=list(package.reason_codes),
                context_sha256=None,
                cache_key=package.cache_key(),
                preparation_id=host_run_id,
            )
        except Exception:  # pragma: no cover - never fail a refusal on bookkeeping
            # A refusal must still be a refusal even if recording it fails.
            # Losing the counter is bad; turning a withholding into an error, or
            # worse into a delivery, would be far worse.
            pass
    return {**package.to_dict(), "delivery_id": None}


class ControlPlaneManager:
    """Host-neutral memory control plane.

    The host integration reads one small, digest-bound state file. Candidate
    memories and migration evidence live in a separate SQLite database and cannot
    enter the ordinary AtMem recall path until a later, explicit import.
    """

    def __init__(self, state_path: str | Path = DEFAULT_STATE_PATH) -> None:
        self.state_path = Path(state_path).expanduser().resolve(strict=False)

    @classmethod
    def start(
        cls,
        *,
        host: str,
        state_path: str | Path = DEFAULT_STATE_PATH,
        control_root: str | Path = DEFAULT_CONTROL_ROOT,
        subject_id: str = DEFAULT_SUBJECT,
        memory_db: str | Path | None = None,
    ) -> "ControlPlaneManager":
        manager, _resumed = cls._start(
            host=host,
            state_path=state_path,
            control_root=control_root,
            subject_id=subject_id,
            memory_db=memory_db,
            resume_shadow=False,
        )
        return manager

    @classmethod
    def start_or_resume_shadow(
        cls,
        *,
        host: str,
        state_path: str | Path = DEFAULT_STATE_PATH,
        control_root: str | Path = DEFAULT_CONTROL_ROOT,
        subject_id: str = DEFAULT_SUBJECT,
        memory_db: str | Path | None = None,
    ) -> tuple["ControlPlaneManager", bool]:
        """Start a migration or reuse the same host's existing shadow safely."""

        return cls._start(
            host=host,
            state_path=state_path,
            control_root=control_root,
            subject_id=subject_id,
            memory_db=memory_db,
            resume_shadow=True,
        )

    @classmethod
    def _start(
        cls,
        *,
        host: str,
        state_path: str | Path,
        control_root: str | Path,
        subject_id: str,
        memory_db: str | Path | None,
        resume_shadow: bool,
    ) -> tuple["ControlPlaneManager", bool]:
        if host not in {"generic", "openclaw"}:
            raise ValueError(f"unsupported host adapter: {host}")
        manager = cls(state_path)
        with state_lock(manager.state_path):
            if manager.state_path.exists():
                current = load_state(manager.state_path)
                if current.mode is not ControlMode.OFF:
                    if (
                        resume_shadow
                        and current.mode is ControlMode.SHADOW
                        and current.host == host
                    ):
                        return manager, True
                    raise ValueError(
                        f"migration {current.migration_id} is already {current.mode.value}; "
                        "turn it off before starting another"
                    )
            migration_id = f"control_{uuid.uuid4().hex}"
            control_dir = (
                Path(control_root).expanduser().resolve(strict=False) / migration_id
            )
            control_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
            now = utc_now()
            state = ControlState(
                migration_id=migration_id,
                host=host,
                subject_id=subject_id or DEFAULT_SUBJECT,
                control_dir=str(control_dir),
                mode=ControlMode.SHADOW,
                revision=1,
                created_at=now,
                updated_at=now,
            )
            store = ControlStore(
                control_dir / "evidence.db",
                policy=HouseholdPolicy.load(control_dir / "openclaw-mirror.db"),
            )
            try:
                store.create_migration(migration_id, host, state.subject_id)
                store.append_transition(
                    migration_id,
                    revision=state.revision,
                    old_mode=ControlMode.OFF.value,
                    new_mode=ControlMode.SHADOW.value,
                    actor=_local_actor(),
                )
            finally:
                store.close()
            write_state(manager.state_path, state)
            if host == "generic":
                from atmem.control.topology import default_topology, write_topology

                write_topology(control_dir, default_topology(state.subject_id))
                configured_db = Path(memory_db or control_dir / "generic-memory.db").expanduser().resolve(strict=False)
                generic_config_path = control_dir / GENERIC_CONFIG_NAME
                generic_config_path.write_text(
                    json.dumps(
                        {
                            "format": "atmem-generic-adapter-config-v1",
                            "memory_db": str(configured_db),
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                generic_config_path.chmod(0o600)
        return manager, False

    def effective_state(self) -> tuple[ControlState, str | None]:
        return load_effective_state(self.state_path)

    def state(self) -> ControlState:
        return load_state(self.state_path)

    def _resolve_subject(
        self,
        state: ControlState,
        *,
        subject_id: str | None,
        agent_id: str | None,
    ) -> str:
        """Resolve one persistent agent scope and reject ambiguous cross-scope access."""

        if state.host != "openclaw":
            topology = self.agent_topology(state=state)
            agent_subjects = topology.get("agent_subjects") or {}
            known_subjects = {
                str(row.get("subject_id"))
                for row in topology.get("workspaces") or []
                if isinstance(row, dict) and row.get("subject_id")
            }
            resolved = agent_subjects.get(agent_id) if agent_id else None
            if agent_id and not resolved:
                raise ValueError(f"unmapped persistent agent: {agent_id}")
            if subject_id and resolved and subject_id != resolved:
                raise ValueError("agent and subject identify different workspaces")
            chosen = str(resolved or subject_id or state.subject_id)
            if known_subjects and chosen not in known_subjects:
                raise ValueError("subject is not part of the current agent topology")
            return chosen
        manifest_path = Path(state.control_dir) / "openclaw-mirror.json"
        if not manifest_path.is_file():
            return subject_id or state.subject_id
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("OpenClaw agent topology is unavailable") from exc
        topology = manifest.get("topology") or {}
        agent_subjects = topology.get("agent_subjects") or {}
        known_subjects = {
            str(row.get("subject_id"))
            for row in topology.get("workspaces") or []
            if isinstance(row, dict) and row.get("subject_id")
        }
        resolved = None
        if agent_id:
            resolved = agent_subjects.get(agent_id)
            if not resolved:
                raise ValueError(f"unmapped OpenClaw persistent agent: {agent_id}")
        if subject_id and resolved and subject_id != resolved:
            raise ValueError("agent and subject identify different OpenClaw workspaces")
        chosen = str(resolved or subject_id or state.subject_id)
        if known_subjects and chosen not in known_subjects:
            raise ValueError("subject is not part of the current OpenClaw topology")
        return chosen

    # Compatibility for integrations released before the host-neutral resolver.
    _resolve_openclaw_subject = _resolve_subject

    def agent_topology(self, *, state: ControlState | None = None) -> dict[str, Any]:
        state = state or self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import mirror_status
            from atmem.control.openclaw_topology import discover_agent_topology

            live = discover_agent_topology(base_subject_id=state.subject_id)
            mirrored = (mirror_status(state) or {}).get("topology") or {}
            matches = bool(mirrored) and all(
                mirrored.get(key) == live.get(key)
                for key in ("agent_subjects", "agent_workspaces")
            )
            verified = bool((mirror_status(state) or {}).get("audit_verified")) and matches
            return {
                **live,
                "verified": verified,
                "topology_matches_mirror": matches,
                "status": "working" if verified else "needs_refresh",
                "reason": (
                    "Every persistent agent is bound to its verified workspace memory scope."
                    if verified
                    else "Sync agents and memory so the detected topology is bound to the memory mirror."
                ),
            }
        from atmem.control.topology import load_topology

        topology = load_topology(state.control_dir, subject_id=state.subject_id)
        return {
            **topology,
            "verified": True,
            "status": "working",
            "reason": "Every registered agent is bound to an explicit memory workspace scope.",
        }

    def configure_agent_topology(self, agents: list[dict[str, Any]]) -> dict[str, Any]:
        state = self.state()
        if state.host == "openclaw":
            raise ValueError("OpenClaw agent topology is discovered from OpenClaw configuration")
        from atmem.control.topology import build_topology, write_topology

        topology = build_topology(agents, base_subject_id=state.subject_id)
        write_topology(state.control_dir, topology)
        return self.agent_topology(state=state)

    def _generic_memory_db(self, state: ControlState) -> Path:
        config_path = Path(state.control_dir) / GENERIC_CONFIG_NAME
        if config_path.is_file():
            try:
                value = json.loads(config_path.read_text(encoding="utf-8"))
                if value.get("format") == "atmem-generic-adapter-config-v1" and value.get("memory_db"):
                    return Path(str(value["memory_db"])).expanduser().resolve(strict=False)
            except (OSError, json.JSONDecodeError):
                pass
        return Path(state.control_dir) / "generic-memory.db"

    def _generic_subjects(self, state: ControlState) -> list[str]:
        return list(
            dict.fromkeys(
                str(row.get("subject_id"))
                for row in self.agent_topology(state=state).get("workspaces") or []
                if row.get("subject_id")
            )
        ) or [state.subject_id]

    def status(self) -> dict[str, Any]:
        state, warning = self.effective_state()
        result = state.public_status(warning=warning)
        if warning or state.migration_id == "unavailable":
            result["evidence"] = None
            result["readiness"] = {
                "ready_for_active": False,
                "reasons": ["state is missing or invalid; integration is fail-closed"],
            }
            result["provider_state"] = derive_provider_state(
                mode=state.mode,
                host=state.host,
                takeover=None,
                readiness=result["readiness"],
                warning=warning,
                migration_id=state.migration_id,
            ).value
            return result
        store = self._store(state)
        try:
            evidence = store.summary(state.migration_id)
            latest_restore_drill = store.latest_evidence(
                state.migration_id, kind="restore_drill"
            )
            latest_verification = store.latest_evidence(
                state.migration_id, kind="verification"
            )
        finally:
            store.close()
        mirror: dict[str, Any] | None = None
        takeover: dict[str, Any] | None = None
        if state.host == "openclaw":
            from atmem.control.openclaw_native import (
                mirror_status,
                takeover_status,
            )
            from atmem.control.openclaw_topology import discover_agent_topology

            mirror = mirror_status(state)
            takeover = takeover_status(state)
            try:
                live_topology = discover_agent_topology(
                    base_subject_id=state.subject_id
                )
                mirrored_topology = (mirror or {}).get("topology") or {}
                topology_matches = bool(mirrored_topology) and all(
                    mirrored_topology.get(key) == live_topology.get(key)
                    for key in ("agent_subjects", "agent_workspaces")
                )
                result["agent_topology"] = {
                    **live_topology,
                    "verified": bool((mirror or {}).get("audit_verified"))
                    and topology_matches,
                    "topology_matches_mirror": topology_matches,
                    "status": (
                        "working"
                        if bool((mirror or {}).get("audit_verified"))
                        and topology_matches
                        else "needs_refresh"
                    ),
                    "reason": (
                        "Every persistent agent is bound to its verified workspace memory scope."
                        if bool((mirror or {}).get("audit_verified"))
                        and topology_matches
                        else "Sync agents and memory so the detected topology is bound to the memory mirror."
                    ),
                }
            except (OSError, ValueError) as exc:
                result["agent_topology"] = {
                    "verified": False,
                    "status": "unavailable",
                    "reason": str(exc),
                    "agents": [],
                    "workspaces": [],
                }
        else:
            result["agent_topology"] = self.agent_topology(state=state)
            mirror = self.memory_status()
        result["evidence"] = evidence
        result["restore_drill"] = (
            latest_restore_drill["body"] if latest_restore_drill else None
        )
        result["verification"] = (
            latest_verification["body"] if latest_verification else None
        )
        result["mirror"] = mirror
        result["takeover"] = takeover
        result["storages"] = self._storage_inventory(state, mirror=mirror)
        result["readiness"] = self._readiness(state, evidence, mirror=mirror)
        result["provider_state"] = derive_provider_state(
            mode=state.mode,
            host=state.host,
            takeover=takeover,
            readiness=result["readiness"],
            warning=warning,
            migration_id=state.migration_id,
        ).value
        return result

    def semantic_health(self, subject_id: str | None = None) -> dict[str, Any]:
        """Project the same semantic-health contract used by the CLI."""

        from atmem.memory import Memory
        from atmem.semantic import (
            SemanticIndex,
            default_index_path,
            evaluate_semantic_health,
            inspect_semantic_health,
        )

        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import mirror_status

            mirror = mirror_status(state)
            memory_path = Path(
                str(
                    mirror.get("mirror_db")
                    or Path(state.control_dir) / "openclaw-mirror.db"
                )
            )
        else:
            memory_path = self._generic_memory_db(state)
        selected_subject = subject_id or state.subject_id
        memory = Memory(memory_path, retain_query_text=False, auto_vectors=False)
        registered = memory.store.semantic_index_paths(selected_subject)
        candidates = [
            Path(str(row["index_path"])).expanduser()
            for row in registered
            if row.get("index_path")
        ]
        candidates.append(default_index_path(memory_path))
        index_path = next((path for path in candidates if path.exists()), None)
        if index_path is None:
            memory.close()
            return evaluate_semantic_health(
                selected_subject, active_epoch=None
            ).to_dict()
        index = SemanticIndex(index_path, policy=memory.policy)
        try:
            return inspect_semantic_health(
                index, memory, selected_subject
            ).to_dict()
        finally:
            index.close()
            memory.close()

    def _storage_inventory(
        self,
        state: ControlState,
        *,
        mirror: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Describe local stores without making any of them authoritative by accident."""

        control_dir = Path(state.control_dir)
        if state.host == "openclaw":
            canonical_path = Path(
                str((mirror or {}).get("mirror_db") or control_dir / "openclaw-mirror.db")
            )
        else:
            canonical_path = self._generic_memory_db(state)
        canonical_path = canonical_path.expanduser().resolve(strict=False)

        vector_paths: set[Path] = set()
        vector_subjects: list[str] = []
        if canonical_path.is_file():
            from atmem.memory import Memory

            memory = Memory(canonical_path, retain_query_text=False)
            try:
                subjects = memory.store.subject_ids() or [state.subject_id]
                vector_subjects = [
                    subject_id
                    for subject_id in subjects
                    if memory.store.list_records(
                        subject_id,
                        statuses=("active", "quarantined", "superseded"),
                    )
                ]
                for subject_id in subjects:
                    for registered in memory.store.semantic_index_paths(subject_id):
                        if registered.get("index_path"):
                            vector_paths.add(
                                Path(str(registered["index_path"]))
                                .expanduser()
                                .resolve(strict=False)
                            )
            finally:
                memory.close()
        if not vector_paths:
            vector_paths.add(Path(f"{canonical_path}.vectors.db").resolve(strict=False))
        if not vector_subjects:
            vector_subjects = [state.subject_id]

        rows = [
            _storage_row(
                "canonical",
                "Canonical memory",
                "Memories, provenance and lifecycle state",
                canonical_path,
                storage_type="SQLite",
            ),
            {
                **_storage_row(
                    "graph",
                    "Entity graph",
                    "Entities, aliases and relationships",
                    canonical_path,
                    storage_type="Shared SQLite tables",
                ),
                "shared_with": "canonical",
            },
        ]
        for position, vector_path in enumerate(sorted(vector_paths, key=str)):
            vector_row = _storage_row(
                    "vectors" if position == 0 else f"vectors-{position + 1}",
                    "Semantic vectors" if position == 0 else f"Semantic vectors {position + 1}",
                    "Optional, rebuildable semantic retrieval index",
                    vector_path,
                    storage_type="SQLite vector sidecar",
                    optional=False,
                )
            vector_row["ready"] = False
            if vector_row["exists"]:
                from atmem.semantic import SemanticIndex

                try:
                    index = SemanticIndex(
                        vector_path, policy=HouseholdPolicy.load(canonical_path)
                    )
                    try:
                        index_status = index.status()
                    finally:
                        index.close()
                    vector_row["ready"] = any(
                        row.get("status") == "active"
                        and int(row.get("entry_count") or 0) > 0
                        for row in index_status["epochs"]
                    )
                except (OSError, ValueError):
                    vector_row["ready"] = False
            if not vector_row["ready"]:
                memory_arg = shlex.quote(str(canonical_path))
                python_arg = shlex.quote(sys.executable)
                commands = [
                    f'{python_arg} -m pip install "sentence-transformers>=5.0.0,<6.0.0"'
                ]
                for subject_id in vector_subjects:
                    subject_arg = shlex.quote(subject_id)
                    commands.extend(
                        [
                            (
                                f"{python_arg} -m atmem.cli index build {memory_arg} "
                                f"--subject {subject_arg} "
                                "--embedder sentence-transformers --model all-MiniLM-L6-v2"
                            ),
                            (
                                f"{python_arg} -m atmem.cli index verify {memory_arg} "
                                f"--subject {subject_arg}"
                            ),
                        ]
                    )
                vector_row["setup_commands"] = commands
                vector_row["setup_note"] = (
                    "AtMem creates a dependency-free local vector index automatically. "
                    "These optional commands upgrade semantic quality with a local model."
                )
            rows.append(vector_row)
        rows.append(
            _storage_row(
                "evidence",
                "Audit evidence",
                "Control decisions, transitions and verification evidence",
                control_dir / "evidence.db",
                storage_type="SQLite",
            )
        )
        return rows

    def storage_preview(self, storage_id: str, *, limit: int = 25) -> dict[str, Any]:
        """Return a bounded, domain-level view of one local store."""

        limit = max(1, min(int(limit), 50))
        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import mirror_status

            mirror = mirror_status(state)
        else:
            mirror = {"memory_db": str(self._generic_memory_db(state))}
        storages = self._storage_inventory(state, mirror=mirror)
        selected = next((row for row in storages if row["id"] == storage_id), None)
        if selected is None:
            raise ValueError("unknown storage")
        base = {
            "format": "atmem-storage-preview-v1",
            "storage": selected,
            "rows": [],
            "truncated": False,
        }
        if not selected["exists"]:
            return {**base, "summary": "This optional store has not been built yet."}

        canonical = next(row for row in storages if row["id"] == "canonical")
        canonical_path = Path(str(canonical["path"]))
        if storage_id == "canonical":
            from atmem.memory import Memory

            memory = Memory(canonical_path, retain_query_text=False)
            try:
                subjects = memory.store.subject_ids() or [state.subject_id]
                records = [
                    {**row, "subject_id": subject_id}
                    for subject_id in subjects
                    for row in memory.list(subject_id, include_inactive=True)
                ]
            finally:
                memory.close()
            records.sort(key=lambda row: (str(row.get("created_at") or ""), str(row["id"])), reverse=True)
            return {
                **base,
                "summary": f"{len(records)} canonical memory record(s)",
                "rows": [
                    {
                        "kind": "memory",
                        "id": row["id"],
                        "title": row.get("content") or "Empty memory",
                        "detail": f"{row.get('status', 'unknown')} · {row.get('subject_id', 'unknown subject')}",
                        "record_id": row["id"],
                    }
                    for row in records[:limit]
                ],
                "truncated": len(records) > limit,
            }
        if storage_id == "graph":
            from atmem.graph import GraphIndex
            from atmem.memory import Memory

            memory = Memory(canonical_path, retain_query_text=False)
            try:
                graph = GraphIndex(memory.store)
                subjects = memory.store.subject_ids() or [state.subject_id]
                relationships: list[dict[str, Any]] = []
                for subject_id in subjects:
                    report = graph.inspect(subject_id)
                    entities = {str(row["id"]): row for row in report["entities"]}
                    for edge in report["edges"]:
                        source = entities.get(str(edge.get("src_entity"))) or {}
                        destination = entities.get(str(edge.get("dst_entity"))) or {}
                        relationships.append(
                            {
                                "kind": "relationship",
                                "id": edge["id"],
                                "title": (
                                    f"{source.get('canonical', 'Unknown')} → "
                                    f"{destination.get('canonical') or edge.get('dst_value') or 'Unknown'}"
                                ),
                                "detail": (
                                    f"{edge.get('relation_label') or edge.get('relation')} · "
                                    f"{edge.get('status', 'unknown')} · {subject_id}"
                                ),
                                "record_id": edge.get("record_id"),
                            }
                        )
            finally:
                memory.close()
            relationships.sort(key=lambda row: str(row["id"]))
            return {
                **base,
                "summary": f"{len(relationships)} entity relationship(s)",
                "rows": relationships[:limit],
                "truncated": len(relationships) > limit,
            }
        if storage_id.startswith("vectors"):
            from atmem.semantic import SemanticIndex

            index = SemanticIndex(
                selected["path"], policy=HouseholdPolicy.load(canonical_path)
            )
            try:
                status = index.status()
                entries = index._conn.execute(
                    """
                    SELECT object_id, subject_id, status_at_index, dimensions, created_at
                    FROM vector_entries ORDER BY created_at DESC, object_id LIMIT ?
                    """,
                    (limit + 1,),
                ).fetchall()
            finally:
                index.close()
            return {
                **base,
                "summary": (
                    f"{sum(int(row.get('entry_count') or 0) for row in status['epochs'])} "
                    "indexed vector record(s); numerical vectors are intentionally hidden"
                ),
                "rows": [
                    {
                        "kind": "vector",
                        "id": str(row["object_id"]),
                        "title": f"Vector for memory {row['object_id']}",
                        "detail": (
                            f"{row['dimensions']} dimensions · {row['status_at_index']} · "
                            f"{row['subject_id']}"
                        ),
                        "record_id": str(row["object_id"]),
                    }
                    for row in entries[:limit]
                ],
                "truncated": len(entries) > limit,
                "epochs": status["epochs"],
            }
        if storage_id == "evidence":
            store = self._store(state)
            try:
                rows = store._conn.execute(
                    """
                    SELECT id, kind, sequence, created_at, body_json, entry_sha256
                    FROM evidence WHERE migration_id = ?
                    ORDER BY created_at DESC, kind, sequence DESC LIMIT ?
                    """,
                    (state.migration_id, limit + 1),
                ).fetchall()
            finally:
                store.close()
            items = []
            for row in rows[:limit]:
                body = json.loads(str(row["body_json"]))
                items.append(
                    {
                        "kind": "evidence",
                        "id": row["id"],
                        "title": body.get("event_type") or str(row["kind"]).replace("_", " "),
                        "detail": f"{row['created_at']} · sequence {row['sequence']}",
                        "digest": row["entry_sha256"],
                    }
                )
            return {
                **base,
                "summary": f"Showing {len(items)} recent control evidence event(s)",
                "rows": items,
                "truncated": len(rows) > limit,
            }
        raise ValueError("storage preview is unavailable")

    def capture(
        self,
        message: str,
        *,
        session_id: str | None = None,
        authenticated_user: bool,
        subject_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Capture a trusted source, ask AtBot for proposals, then let AtMem admit.

        The control-plane candidate copy is retained during the 2.2 migration so
        older review clients keep working. It is evidence, not authority; only
        ``Memory.submit_proposal`` can create canonical memory.
        """
        state, warning = self.effective_state()
        if warning or not state.mode.captures:
            return {"captured": 0, "candidate_ids": [], "reason": "migration is off"}
        if not authenticated_user:
            return {
                "captured": 0,
                "candidate_ids": [],
                "reason": "only authenticated user messages are eligible",
            }
        subject_id = self._resolve_subject(
            state, subject_id=subject_id, agent_id=agent_id
        )
        from atmem.control.atbot_companion import AtBotCompanionClient

        intelligence = AtBotCompanionClient().propose(message)
        proposal_rows = list(intelligence.get("proposals") or [])
        deterministic_rows = [
            {
                "fact": fact.content,
                "fact_key": fact.fact_key,
                "confidence": fact.confidence,
                "sensitivity": "personal",
                "entities": [],
                "suggested_action": "add",
                "related_record_ids": [],
            }
            for fact in extract_facts(message, source_type="user_message")
        ]
        # A local model can validly return no proposal, but explicit statements
        # recognized by the deterministic policy must not disappear merely
        # because model extraction was unavailable, malformed, or uncertain.
        source_terms = {
            term
            for term in re.findall(r"[a-z0-9]+", message.casefold())
            if len(term) >= 4
            and term not in {"remember", "that", "this", "user", "preferred", "favourite", "favorite"}
        }
        grounded_proposals = [
            row
            for row in proposal_rows
            if source_terms
            & {
                term
                for term in re.findall(r"[a-z0-9]+", str(row.get("fact") or "").casefold())
                if len(term) >= 4
            }
        ]
        if grounded_proposals:
            proposal_rows = grounded_proposals
            interpreter_value = dict(intelligence.get("interpreter") or {})
        elif deterministic_rows:
            # Explicit rule-verifiable statements are admitted from the source,
            # not replaced by a model interpretation. AtBot is still consulted
            # for messages the deterministic policy cannot interpret.
            proposal_rows = deterministic_rows
            interpreter_value: dict[str, Any] = {
                "provider": "atmem-rules",
                "model": "deterministic-capture-v1",
                "prompt_version": "atmem-rules-v1",
                "assurance": "rule_extracted",
                "egress_class": "none",
            }
        elif not intelligence.get("companion", {}).get("available"):
            proposal_rows = [
                {
                    "fact": fact.content,
                    "fact_key": fact.fact_key,
                    "confidence": fact.confidence,
                    "sensitivity": "personal",
                    "entities": [],
                    "suggested_action": "add",
                    "related_record_ids": [],
                }
                for fact in extract_facts(message, source_type="user_message")
            ]
            interpreter_value = {
                "provider": "atmem-rules",
                "model": "deterministic-capture-v1",
                "prompt_version": "atmem-rules-v1",
                "assurance": "rule_extracted",
                "egress_class": "none",
            }
        else:
            interpreter_value = dict(intelligence.get("interpreter") or {})

        admissions: list[dict[str, Any]] = []
        canonical_record_ids: list[str] = []
        canonical_candidate_ids: list[str] = []
        source_result: dict[str, Any] | None = None
        canonical_error: str | None = None
        if proposal_rows:
            try:
                from atmem.contracts import (
                    AuthorityScope,
                    InterpreterIdentity,
                    MemoryProposal,
                    SourceBinding,
                    SourceCaptureRequest,
                )
                from atmem.memory import Memory

                scope, memory_path = self._memory_authority_scope(
                    state, subject_id=subject_id, agent_id=agent_id
                )
                capture_digest = sha256_hex(
                    canonical_json(
                        {
                            "scope": scope.to_dict(),
                            "session_id": session_id,
                            "message_sha256": sha256_hex(message),
                        }
                    )
                )
                source_request = SourceCaptureRequest(
                    source_id=f"source_{capture_digest[:32]}",
                    idempotency_key=f"capture:{capture_digest}",
                    scope=scope,
                    message=message,
                    source_type="user_message",
                    session_id=session_id,
                    binding_method="host_authenticated_turn",
                    binding_assurance="host_authenticated",
                    retain_body=True,
                )
                memory = Memory(memory_path, retain_query_text=False, graph_recall=True)
                try:
                    captured_source = memory.capture_source(source_request)
                    source_result = captured_source.to_dict()
                    interpreter = InterpreterIdentity(
                        provider=str(interpreter_value.get("provider") or "atbot"),
                        model=str(interpreter_value.get("model") or "unknown"),
                        prompt_version=str(
                            interpreter_value.get("prompt_version") or "atbot-extract-v1"
                        ),
                        assurance=str(
                            interpreter_value.get("assurance") or "model_interpreted"
                        ),
                        egress_class=str(interpreter_value.get("egress_class") or "local"),
                    )
                    for index, row in enumerate(proposal_rows[:8]):
                        semantic_digest = sha256_hex(
                            canonical_json(
                                {
                                    "source_id": captured_source.source_id,
                                    "index": index,
                                    "proposal": row,
                                }
                            )
                        )
                        proposal = MemoryProposal(
                            proposal_id=f"proposal_{semantic_digest[:32]}",
                            idempotency_key=f"proposal:{semantic_digest}",
                            scope=scope,
                            fact=str(row.get("fact") or ""),
                            fact_key=(
                                _protocol_fact_key(row.get("fact_key"))
                            ),
                            confidence=float(row.get("confidence", 0.0)),
                            source_ids=(captured_source.source_id,),
                            interpreter=interpreter,
                            source_binding=SourceBinding(
                                method="host_authenticated_turn",
                                source_sha256=captured_source.source_sha256,
                                assurance="host_authenticated",
                            ),
                            entities=tuple(row.get("entities") or ()),
                            suggested_action=(
                                str(row.get("suggested_action") or "uncertain")
                                if state.mode is ControlMode.ACTIVE
                                else "uncertain"
                            ),
                            # Extraction receives no eligible record content, so
                            # AtBot has no authority to introduce relationships.
                            related_record_ids=(),
                            sensitivity=str(row.get("sensitivity") or "personal"),
                            session_id=session_id,
                        )
                        admitted = memory.submit_proposal(proposal)
                        admissions.append(admitted.to_dict())
                        canonical_record_ids.extend(admitted.record_ids)
                        canonical_candidate_ids.extend(admitted.candidate_ids)
                finally:
                    memory.close()
            except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
                canonical_error = str(exc)

        # Compatibility projection for existing shadow-review clients. It never
        # contains the raw source and cannot bypass canonical AtMem policy.
        store = self._store(state)
        created: list[str] = []
        duplicates: list[str] = []
        try:
            for row_value in proposal_rows:
                row, duplicate = store.insert_candidate(
                    state.migration_id,
                    content=str(row_value.get("fact") or ""),
                    fact_key=(
                        str(row_value["fact_key"])
                        if row_value.get("fact_key")
                        else None
                    ),
                    confidence=float(row_value.get("confidence", 0.0)),
                    source_type="user_message",
                    trust_tier="trusted_user",
                    source_message_sha256=sha256_hex(message),
                    source_session_id=session_id,
                    subject_id=subject_id,
                )
                (duplicates if duplicate else created).append(str(row["id"]))
                if not duplicate:
                    store.append_evidence(
                        state.migration_id,
                        kind="memory_control",
                        body={
                            "format": "atmem-memory-control-event-v1",
                            "event_type": "memory.candidate_captured",
                            "actor": "host-adapter",
                            "record_id": str(row["id"]),
                            "subject_id": subject_id,
                            "session_id": session_id,
                            "created_at": row["created_at"],
                            "payload": {
                                "content_sha256": row["content_sha256"],
                                "source_message_sha256": row["source_message_sha256"],
                                "status": row["status"],
                            },
                        },
                    )
        finally:
            store.close()
        return {
            "captured": max(len(created), len(admissions)),
            "candidate_ids": created,
            "duplicate_ids": duplicates,
            "record_ids": list(dict.fromkeys(canonical_record_ids)),
            "canonical_candidate_ids": list(dict.fromkeys(canonical_candidate_ids)),
            "admissions": admissions,
            "source": source_result,
            "atbot": intelligence.get("companion"),
            "canonical_error": canonical_error,
            "raw_message_stored": False,
            "subject_id": subject_id,
            "agent_id": agent_id,
        }

    def candidates(self, *, include_reviewed: bool = False) -> list[dict[str, Any]]:
        state = self.state()
        store = self._store(state)
        try:
            statuses = None if include_reviewed else ("candidate",)
            return store.list_candidates(state.migration_id, statuses=statuses)
        finally:
            store.close()

    def review(self, candidate_ids: list[str], *, approve: bool) -> list[dict[str, Any]]:
        state = self.state()
        store = self._store(state)
        try:
            rows = store.review_candidates(
                state.migration_id, candidate_ids, approve=approve
            )
            if approve:
                from atmem.memory import Memory

                for row in rows:
                    subject = str(row.get("subject_id") or state.subject_id)
                    _, memory_path = self._memory_authority_scope(
                        state, subject_id=subject, agent_id=None
                    )
                    memory = Memory(memory_path, retain_query_text=False, graph_recall=True)
                    try:
                        existing = memory.store.find_duplicate_record(
                            subject,
                            str(row.get("content") or ""),
                            statuses=("active", "quarantined"),
                        )
                        if existing is not None and existing.get("status") == "quarantined":
                            memory.promote(subject, str(existing["id"]))
                        elif existing is None:
                            memory.remember(
                                subject,
                                str(row.get("content") or ""),
                                interpreted_fact=str(row.get("content") or ""),
                                interpreted_fact_key=str(row.get("fact_key") or "") or None,
                                session_id=row.get("source_session_id"),
                                actor="local-reviewer",
                                raw={"control_candidate_id": str(row["id"])},
                            )
                    finally:
                        memory.close()
            for row in rows:
                store.append_evidence(
                    state.migration_id,
                    kind="memory_control",
                    body={
                        "format": "atmem-memory-control-event-v1",
                        "event_type": "memory.approved" if approve else "memory.rejected",
                        "actor": "local-reviewer",
                        "record_id": str(row["id"]),
                        "subject_id": row.get("subject_id"),
                        "created_at": row.get("reviewed_at") or utc_now(),
                        "payload": {
                            "content_sha256": row.get("content_sha256"),
                            "status": row.get("status"),
                        },
                    },
                )
            return rows
        finally:
            store.close()

    def memory_status(self) -> dict[str, Any]:
        """Return one host-neutral summary consumed by CLI, MCP, and dashboard."""

        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import mirror_status

            return mirror_status(state)
        store = self._store(state)
        try:
            rows = store.list_candidates(state.migration_id)
            evidence = store.summary(state.migration_id)
        finally:
            store.close()
        counts = {
            status: sum(row.get("status") == status for row in rows)
            for status in ("candidate", "approved", "rejected")
        }
        from atmem.memory import Memory

        memory = Memory(self._generic_memory_db(state), retain_query_text=False)
        try:
            canonical_rows = [
                row
                for subject in self._generic_subjects(state)
                for row in memory.list(subject, include_inactive=True)
            ]
            canonical_count = sum(row.get("status") == "active" for row in canonical_rows)
            canonical_pending = sum(row.get("status") == "quarantined" for row in canonical_rows)
            canonical_active_digests = {
                str(
                    row.get("content_sha256")
                    or sha256_hex(str(row.get("content") or ""))
                )
                for row in canonical_rows
                if row.get("status") == "active"
            }
            canonical_audit_valid = all(
                bool(memory.verify(subject).get("valid"))
                for subject in self._generic_subjects(state)
            )
        finally:
            memory.close()
        return {
            "format": "atmem-host-neutral-memory-status-v1",
            "host": state.host,
            "mode": state.mode.value,
            "synced": True,
            "audit_verified": bool(evidence["transition_chain"]["valid"])
            and canonical_audit_valid,
            "audit_error": None,
            "source_count": 0,
            "source_bytes": 0,
            "record_count": canonical_count
            + sum(
                row.get("status") == "approved"
                and str(row.get("content_sha256") or "")
                not in canonical_active_digests
                for row in rows
            ),
            "canonical_record_count": canonical_count,
            "candidate_count": counts["candidate"] + canonical_pending,
            "canonical_quarantined_count": canonical_pending,
            "rejected_count": counts["rejected"],
            "sources": [],
            "workspace": "registered agent workspaces",
            "memory_db": str(self._generic_memory_db(state)),
            "scope_note": (
                "Generic shadow memory is populated by authenticated host capture events. "
                "It does not read another runtime's private files automatically."
            ),
        }

    def memory_search(
        self,
        query: str,
        *,
        limit: int = 50,
        subject_id: str | None = None,
        agent_id: str | None = None,
        include_pending: bool = True,
    ) -> dict[str, Any]:
        state = self.state()
        subject = self._resolve_subject(
            state, subject_id=subject_id, agent_id=agent_id
        )
        if state.host == "openclaw":
            from atmem.control.openclaw_native import search_mirror

            return search_mirror(state, query, limit=limit, subject_id=subject)
        store = self._store(state)
        try:
            statuses = ("candidate", "approved") if include_pending else ("approved",)
            rows = store.list_candidates(
                state.migration_id, statuses=statuses, subject_id=subject
            )
        finally:
            store.close()
        terms = [term.casefold() for term in re.findall(r"[\w@.-]+", query)]
        matches: list[dict[str, Any]] = []
        for row in rows:
            content = str(row.get("content") or "")
            haystack = content.casefold()
            if terms and not all(term in haystack for term in terms):
                continue
            matches.append(
                {
                    "id": str(row["id"]),
                    "record_id": str(row["id"]),
                    "content": content,
                    "match_excerpt": content,
                    "status": row.get("status"),
                    "scope": "shadow candidate" if row.get("status") == "candidate" else "memory",
                    "subject_id": row.get("subject_id"),
                    "created_at": row.get("created_at"),
                    "content_sha256": row.get("content_sha256"),
                }
            )
        from atmem.memory import Memory

        memory = Memory(self._generic_memory_db(state), retain_query_text=False)
        try:
            allowed_statuses = (
                {"active", "quarantined"} if include_pending else {"active"}
            )
            for row in memory.list(subject, include_inactive=include_pending):
                if str(row.get("status") or "") not in allowed_statuses:
                    continue
                content = str(row.get("content") or "")
                haystack = content.casefold()
                if terms and not all(term in haystack for term in terms):
                    continue
                matches.append(
                    {
                        "id": str(row["id"]),
                        "record_id": str(row["id"]),
                        "content": content,
                        "match_excerpt": content,
                        "status": row.get("status"),
                        "scope": "canonical memory",
                        "subject_id": subject,
                        "created_at": row.get("created_at"),
                        "content_sha256": row.get("content_sha256"),
                    }
                )
        finally:
            memory.close()
        deduplicated: dict[tuple[str, str], dict[str, Any]] = {}
        for row in matches:
            key = (
                str(row.get("subject_id") or subject),
                str(
                    row.get("content_sha256")
                    or sha256_hex(str(row.get("content") or ""))
                ),
            )
            if key not in deduplicated or row.get("scope") == "canonical memory":
                deduplicated[key] = row
        return {
            "format": "atmem-host-neutral-memory-search-v1",
            "query": query,
            "subject_id": subject,
            "records": list(deduplicated.values())[: max(0, min(limit, 500))],
        }

    def memory_query(
        self,
        query: str,
        *,
        subject_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Answer a dashboard memory question through authorized candidates only."""
        clean = " ".join(query.split())
        if not clean:
            raise ValueError("query is required")
        state = self.state()
        subject = self._resolve_subject(
            state, subject_id=subject_id, agent_id=agent_id
        )
        expanded_queries = [clean]
        if _memory_overview_query(clean):
            scope, memory_path = self._memory_authority_scope(
                state, subject_id=subject, agent_id=agent_id
            )
            from atmem.memory import Memory

            memory = Memory(memory_path, retain_query_text=False)
            try:
                records = memory.list(subject)
                if state.host == "openclaw":
                    episodes = {
                        str(row.get("id") or ""): row
                        for row in memory.store.list_episodes(subject)
                    }

                    def is_human_memory(row: dict[str, Any]) -> bool:
                        episode = episodes.get(str(row.get("episode_id") or "")) or {}
                        raw = episode.get("raw") if isinstance(episode.get("raw"), dict) else {}
                        relative_path = str((raw or {}).get("relative_path") or "")
                        if not relative_path:
                            return True
                        normalized = relative_path.replace("\\", "/").casefold()
                        name = Path(normalized).name.upper()
                        return name in {"USER.MD", "MEMORY.MD"} or "/memory/" in f"/{normalized}"

                    records = [row for row in records if is_human_memory(row)]
                candidates = [
                    {
                        "id": row["id"],
                        "record_id": row["id"],
                        "content": row["content"],
                        "score": 1.0,
                        "status": row["status"],
                        "subject_id": subject,
                    }
                    for row in reversed(records)
                ][:20]
            finally:
                memory.close()
        else:
            from atmem.control.atbot_companion import AtBotCompanionClient

            expansion = AtBotCompanionClient().expand_query(clean)
            expanded_queries = list(expansion.get("expanded_queries") or [clean])
            candidates = self._hybrid_memory_candidates(
                expanded_queries,
                subject_id=subject,
                agent_id=agent_id,
            )
        candidate_set, scope, memory_path = self._durable_candidate_set(
            clean,
            candidates,
            subject_id=subject,
            agent_id=agent_id,
            limit=max(1, min(100, len(candidates) or 1)),
            reranker_model="memory-query",
        )
        candidates = []
        for candidate in candidate_set.candidates:
            row = candidate.to_dict()
            row["matched_queries"] = list(
                (row.get("signals") or {}).get("matched_queries") or ()
            )
            row["expansion_rank"] = int(
                (row.get("signals") or {}).get("expansion_rank") or 0
            )
            candidates.append(row)
        from atmem.control.atbot_companion import AtBotCompanionClient

        result = AtBotCompanionClient().query(clean, list(candidates))
        allowed = {
            str(row.get("record_id") or row.get("id")): row for row in candidates
        }
        ranked = [
            record_id
            for record_id in result.get("ranked_record_ids") or []
            if record_id in allowed
        ]
        from atmem.contracts import ContextRequest
        from atmem.memory import Memory

        memory = Memory(memory_path, retain_query_text=False, graph_recall=True)
        try:
            package = memory.prepare_context_v1(
                ContextRequest(
                    context_id=f"dashboard_context_{uuid.uuid4().hex}",
                    candidate_set_id=candidate_set.candidate_set_id,
                    scope=scope,
                    record_ids=tuple(ranked),
                    budget_chars=4_000,
                )
            )
        finally:
            memory.close()
        accepted = set(package.record_ids)
        ranked = [record_id for record_id in ranked if record_id in accepted]
        return {
            **result,
            "format": "atmem-dashboard-memory-query-v1",
            "query": clean,
            "subject_id": subject,
            "candidate_count": len(candidates),
            "used_memories": [allowed[record_id] for record_id in ranked],
            "candidate_set_id": candidate_set.candidate_set_id,
            "preparation_id": package.preparation_id,
            "context_sha256": package.context_sha256,
            "retrieval": {
                "queries": expanded_queries,
                "signals": ["lexical", "fact_key", "semantic", "graph", "trust", "recency"],
                "candidate_set_id": candidate_set.candidate_set_id,
                "candidate_generation": candidate_set.generation,
                "candidate_digest": candidate_set.candidate_digest,
                "preparation_id": package.preparation_id,
            },
        }

    def _memory_authority_scope(
        self,
        state: ControlState,
        *,
        subject_id: str,
        agent_id: str | None,
    ) -> tuple[Any, Path]:
        """Resolve the exact authority tuple and canonical database together."""
        from atmem.contracts import AuthorityScope

        if state.host == "openclaw":
            manifest_path = Path(state.control_dir) / "openclaw-mirror.json"
            if manifest_path.is_file():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    topology = dict(manifest.get("topology") or {})
                except (OSError, json.JSONDecodeError) as exc:
                    raise ValueError("OpenClaw agent topology is unavailable") from exc
            else:
                # AtMem-authenticated captures can exist before a host-native
                # mirror is installed. Keep those records in an AtMem-owned
                # canonical store; they never become OpenClaw native authority.
                selected = str(agent_id or "main")
                topology = {
                    "default_agent_id": selected,
                    "workspaces": [
                        {
                            "workspace_id": f"atmem:{subject_id}",
                            "subject_id": subject_id,
                            "agent_ids": [selected],
                        }
                    ],
                }
        else:
            topology = self.agent_topology(state=state)
        workspace = next(
            (
                row
                for row in topology.get("workspaces") or []
                if str(row.get("subject_id") or "") == subject_id
            ),
            None,
        )
        if not workspace:
            raise ValueError("memory subject has no authorized workspace")
        workspace_agents = [str(value) for value in workspace.get("agent_ids") or []]
        selected_agent = str(
            agent_id
            or next(
                (
                    value
                    for value in workspace_agents
                    if value == topology.get("default_agent_id")
                ),
                workspace_agents[0] if workspace_agents else "main",
            )
        )
        if workspace_agents and selected_agent not in workspace_agents:
            raise ValueError("agent is not authorized for this memory workspace")
        scope = AuthorityScope(
            subject_id=subject_id,
            agent_id=selected_agent,
            workspace_id=str(workspace["workspace_id"]),
        )
        if state.host == "openclaw":
            if manifest_path.is_file():
                from atmem.control.openclaw_native import mirror_status

                status = mirror_status(state)
                if not status.get("synced"):
                    raise ValueError(status.get("error") or "memory mirror is not synchronized")
                memory_path = Path(str(status["mirror_db"]))
            else:
                # Use the future mirror path from the first AtMem-owned capture.
                # Native synchronization preserves non-native active records, so
                # authority does not silently move to a second database later.
                memory_path = Path(state.control_dir) / "openclaw-mirror.db"
        else:
            memory_path = self._generic_memory_db(state)
        return scope, memory_path

    def _durable_candidate_set(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        *,
        subject_id: str,
        agent_id: str | None,
        limit: int,
        reranker_model: str,
        min_score: float = 0.0,
    ) -> tuple[Any, Any, Path]:
        from atmem.contracts import RecallRequest
        from atmem.control.atbot_service import AtBotServiceManager
        from atmem.memory import Memory

        state = self.state()
        scope, memory_path = self._memory_authority_scope(
            state, subject_id=subject_id, agent_id=agent_id
        )
        request = RecallRequest(
            request_id=f"fused_{uuid.uuid4().hex}",
            scope=scope,
            query=query,
            limit=max(1, min(100, limit)),
            candidate_limit=200,
            signals=("lexical", "semantic", "graph", "trust", "recency"),
            reranker_provider="atbot",
            reranker_model=reranker_model,
            egress_class=AtBotServiceManager().configured_egress_class(),
            min_score=min_score,
        )
        memory = Memory(memory_path, retain_query_text=False, graph_recall=True)
        try:
            candidate_set = memory.create_candidate_set_v1(request, candidates)
        finally:
            memory.close()
        return candidate_set, scope, memory_path

    def _hybrid_memory_candidates(
        self,
        queries: list[str],
        *,
        subject_id: str,
        agent_id: str | None,
        min_score: float = 0.3,
        limit: int = 50,
        reranker_model: str = "memory-query",
    ) -> list[dict[str, Any]]:
        """Fuse governed candidates for query-only AtBot expansions."""
        from atmem.contracts import RecallRequest
        from atmem.memory import Memory

        state = self.state()
        scope, memory_path = self._memory_authority_scope(
            state, subject_id=subject_id, agent_id=agent_id
        )
        memory = Memory(memory_path, retain_query_text=False, graph_recall=True)
        merged: dict[str, dict[str, Any]] = {}
        try:
            for index, query in enumerate(queries[:6]):
                request = RecallRequest(
                    request_id=f"dashboard_{uuid.uuid4().hex}",
                    scope=scope,
                    query=query,
                    limit=30,
                    candidate_limit=200,
                    signals=("lexical", "semantic", "graph", "trust", "recency"),
                    reranker_provider="atbot",
                    reranker_model=reranker_model,
                    egress_class="local",
                    min_score=min_score,
                )
                candidate_set = memory.eligible_candidates(request)
                for candidate in candidate_set.candidates:
                    row = candidate.to_dict()
                    record_id = str(row["record_id"])
                    normalized = {
                        **row,
                        "id": record_id,
                        "matched_queries": [query],
                        "expansion_rank": index,
                    }
                    current = merged.get(record_id)
                    if current is None:
                        merged[record_id] = normalized
                    else:
                        current["matched_queries"] = list(
                            dict.fromkeys([*current["matched_queries"], query])
                        )
                        if float(normalized.get("score") or 0.0) > float(
                            current.get("score") or 0.0
                        ):
                            normalized["matched_queries"] = current["matched_queries"]
                            merged[record_id] = normalized
        finally:
            memory.close()
        return sorted(
            merged.values(),
            key=lambda row: (
                int(row.get("expansion_rank") or 0),
                -float(row.get("score") or 0.0),
                str(row["record_id"]),
            ),
        )[: max(0, min(limit, 100))]

    # --- Governed Task State (Spec 007) ------------------------------------

    def _task_service(self, state: Any = None) -> tuple[Any, Any]:
        """Open the task service over the same store the memory plane uses."""
        from atmem.memory import Memory
        from atmem.task_state.service import TaskStateService

        state = state or self.state()
        memory = Memory(
            self._proposal_memory_db(state), retain_query_text=False,
            auto_vectors=False,
        )
        return TaskStateService(memory.store), memory

    def task_state_mode(
        self, *, subject_id: str | None = None, agent_id: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """Whether governed task state runs for one exact scope."""
        from atmem.contracts import AuthorityScope
        from atmem.task_state.enablement import ScopeEnablement

        state = self.state()
        scope = self._task_scope(
            state, subject_id=subject_id, agent_id=agent_id,
            workspace_id=workspace_id,
        )
        service, memory = self._task_service(state)
        try:
            mode = ScopeEnablement(memory.store).mode(scope)
            return {**mode.to_dict(), "scope": scope.to_dict()}
        finally:
            memory.close()

    def list_tasks(
        self, *, subject_id: str | None = None, agent_id: str | None = None,
        workspace_id: str | None = None, lifecycles: tuple[str, ...] | None = None,
        cursor: str | None = None, limit: int = 50,
    ) -> dict[str, Any]:
        state = self.state()
        scope = self._task_scope(
            state, subject_id=subject_id, agent_id=agent_id,
            workspace_id=workspace_id,
        )
        service, memory = self._task_service(state)
        try:
            return service.list(
                scope, lifecycles=lifecycles, cursor=cursor, limit=limit
            )
        finally:
            memory.close()

    def task_detail(
        self, task_id: str, *, subject_id: str | None = None,
        agent_id: str | None = None, workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """One task, or a non-disclosing refusal for anything not ours."""
        from atmem.task_state.service import TaskStateError

        state = self.state()
        scope = self._task_scope(
            state, subject_id=subject_id, agent_id=agent_id,
            workspace_id=workspace_id,
        )
        service, memory = self._task_service(state)
        try:
            return service.get(scope, task_id).to_dict()
        except TaskStateError as exc:
            return {
                "format": "atmem-task-unavailable-v1",
                "task_id": task_id,
                "reason_code": exc.reason_code,
                "message": str(exc),
            }
        finally:
            memory.close()

    def task_timeline(
        self, task_id: str, *, subject_id: str | None = None,
        agent_id: str | None = None, workspace_id: str | None = None,
    ) -> dict[str, Any]:
        from atmem.task_state.service import TaskStateError

        state = self.state()
        scope = self._task_scope(
            state, subject_id=subject_id, agent_id=agent_id,
            workspace_id=workspace_id,
        )
        service, memory = self._task_service(state)
        try:
            return service.timeline(scope, task_id)
        except TaskStateError as exc:
            return {
                "format": "atmem-task-unavailable-v1",
                "task_id": task_id,
                "reason_code": exc.reason_code,
                "message": str(exc),
            }
        finally:
            memory.close()

    def task_health(
        self, *, subject_id: str | None = None, agent_id: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        from atmem.task_state.observability import TaskObservability

        state = self.state()
        scope = self._task_scope(
            state, subject_id=subject_id, agent_id=agent_id,
            workspace_id=workspace_id,
        )
        service, memory = self._task_service(state)
        try:
            return TaskObservability(memory.store, clock=service.clock).snapshot(scope)
        finally:
            memory.close()

    def task_provenance(
        self, task_id: str, *, target_kind: str, target_id: str,
        subject_id: str | None = None, agent_id: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        from atmem.task_state.provenance import ProvenanceResolver

        state = self.state()
        scope = self._task_scope(
            state, subject_id=subject_id, agent_id=agent_id,
            workspace_id=workspace_id,
        )
        service, memory = self._task_service(state)
        try:
            return ProvenanceResolver(memory.store).resolve(
                scope, task_id, target_kind=target_kind, target_id=target_id
            )
        finally:
            memory.close()

    def prepare_task_context(
        self,
        *,
        task_id: str | None,
        subject_id: str | None = None,
        agent_id: str | None = None,
        workspace_id: str | None = None,
        host_run_id: str | None = None,
        session_id: str | None = None,
        host_type: str | None = None,
        session_key: str | None = None,
        session_epoch: str | None = None,
        budget_chars: int = 4_000,
    ) -> dict[str, Any]:
        """Build the task-state block for one exact task, or withhold it.

        Task identity resolves in one fixed total order (FR-043): an explicit
        host-supplied id, then an operator-registered binding for this exact
        conversation, then withholding. AtMem never infers or selects among
        open tasks; resolving a binding is a lookup of a recorded
        authorization, not a choice.

        Every refusal path returns zero task-state bytes and records the
        preparation without exposure. An unknown, ineligible, or out-of-scope
        id withholds with a reason that does not disclose which of those it
        was.
        """
        from atmem.contracts.task_state import ContextDisposition, TaskLifecycle
        from atmem.core.time import to_iso
        from atmem.task_state import context as task_context
        from atmem.task_state.binding import SessionBindingService
        from atmem.task_state.enablement import ScopeEnablement
        from atmem.task_state.service import TaskStateError

        state = self.state()
        scope = self._task_scope(
            state, subject_id=subject_id, agent_id=agent_id,
            workspace_id=workspace_id,
        )
        service, memory = self._task_service(state)
        try:
            prepared_at = to_iso(service.clock.now())
            context_id = f"taskctx_{sha256_hex(f'{scope.to_dict()}{task_id}{host_run_id}')[:32]}"

            mode = ScopeEnablement(memory.store).mode(scope)
            if not mode.influences_agent:
                return _withheld_task_context(
                    scope, task_id or "", context_id, prepared_at,
                    ("task_state_disabled",)
                    if not mode.enabled
                    else ("task_state_shadow_mode",),
                    store=memory.store, host_run_id=host_run_id,
                )
            identity = _host_session_identity(host_type, session_key, session_epoch)
            resolved = SessionBindingService(memory.store, service.clock).resolve(
                scope, identity=identity, explicit_task_id=task_id
            )
            if not resolved.resolution.delivers:
                # Includes disagreement between an explicit id and a live
                # binding, which withholds rather than preferring either: one
                # would mask a misconfigured binding, the other would let stale
                # operator state override a host that knows better.
                return _withheld_task_context(
                    scope, task_id or "", context_id, prepared_at,
                    (resolved.reason_code or "task_context_selection_required",),
                    store=memory.store, host_run_id=host_run_id,
                )
            task_id = resolved.task_id or ""

            try:
                view = service.get(scope, task_id)
            except TaskStateError:
                return _withheld_task_context(
                    scope, task_id, context_id, prepared_at,
                    ("task_context_not_eligible",),
                    store=memory.store, host_run_id=host_run_id,
                )

            reason = task_context.eligibility_reason(
                view.state.lifecycle, in_scope=True
            )
            if reason is not None:
                package = task_context.withhold(
                    scope=scope, task_id=task_id, revision=view.state.revision,
                    context_id=context_id, reason_codes=(reason,),
                    prepared_at=prepared_at,
                    profile_version=view.profile.version,
                )
            else:
                package = task_context.prepare(
                    view.state, view.profile, scope=scope, context_id=context_id,
                    prepared_at=prepared_at, budget_chars=budget_chars,
                )

            delivery_id = memory.store.insert_task_delivery(
                task_id=task_id,
                revision=package.revision,
                subject_id=scope.subject_id,
                agent_id=scope.agent_id,
                workspace_id=scope.workspace_id,
                disposition=package.disposition.value,
                prepared_at_utc=prepared_at,
                reason_codes=list(package.reason_codes),
                context_sha256=package.context_sha256 or None,
                cache_key=package.cache_key(),
                preparation_id=host_run_id,
            )
            return {**package.to_dict(), "delivery_id": delivery_id}
        finally:
            memory.close()

    def confirm_task_exposure(self, delivery_id: str) -> bool:
        """Record that prepared task bytes reached the model. Truthfully (FR-053).

        Preparation authorizes exactly one model call, and this records what
        happened on that call. If the task expired, was cancelled, or was
        unbound between preparation and this confirmation, the exposure is
        still recorded: the bytes did reach the model, and evidence that says
        otherwise is evidence that is wrong. The subsequent terminal outcome is
        its own later event, linked to this delivery.

        The safety property worth having is not "no exposure record" -- it is
        "the task stops influencing later calls", and that comes from
        re-resolving identity on every subsequent call and withholding. Nothing
        is gained by denying a call that already happened, and the audit trail
        is strictly worse for it.

        Returns False only when the delivery is unknown or was already
        confirmed, which is the exactly-once guarantee, not a policy judgement.
        """
        service, memory = self._task_service()
        try:
            return bool(memory.store.mark_task_delivery_exposed(delivery_id))
        finally:
            memory.close()

    def submit_task_proposal(self, proposal: Any) -> dict[str, Any]:
        """Hand one typed delta to AtMem. The proposer never writes."""
        from atmem.task_state.enablement import ScopeEnablement
        from atmem.task_state.service import TaskStateError

        service, memory = self._task_service()
        try:
            mode = ScopeEnablement(memory.store).mode(proposal.scope)
            if not mode.enabled:
                return {
                    "format": "atmem-task-unavailable-v1",
                    "reason_code": "task_state_disabled",
                    "message": "Governed task state is disabled for this scope.",
                }
            try:
                return service.submit(proposal).to_dict()
            except TaskStateError as exc:
                return {
                    "format": "atmem-task-unavailable-v1",
                    "reason_code": exc.reason_code,
                    "message": str(exc),
                }
        finally:
            memory.close()

    # --- host-boundary write path (Amendment A) -----------------------------

    def _host_boundary(self, state: Any = None) -> tuple[Any, Any, Any]:
        from atmem.task_state.host_boundary import HostBoundary

        service, memory = self._task_service(state)
        return HostBoundary(service, memory.store), service, memory

    def observe_task_step(
        self,
        payload: Mapping[str, Any],
        *,
        subject_id: str | None = None,
        agent_id: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """Admit one observed workflow step from a host adapter (FR-049).

        The adapter reports what it saw and never a delta: interpretation
        happens in the authorized companion path, and AtMem revalidates the
        result against the current head before commit.
        """
        from atmem.contracts.task_state import HostTaskObservationRequest

        return self._host_call(
            HostTaskObservationRequest, payload, "observe",
            subject_id=subject_id, agent_id=agent_id, workspace_id=workspace_id,
        )

    def propose_task_delta(
        self,
        payload: Mapping[str, Any],
        *,
        subject_id: str | None = None,
        agent_id: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """Admit one typed delta already in delta form (FR-044)."""
        from atmem.contracts.task_state import HostTaskProposalRequest

        return self._host_call(
            HostTaskProposalRequest, payload, "propose",
            subject_id=subject_id, agent_id=agent_id, workspace_id=workspace_id,
        )

    def request_task_lifecycle(
        self,
        payload: Mapping[str, Any],
        *,
        subject_id: str | None = None,
        agent_id: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """Take a host lifecycle *request*. Gates decide it; it bypasses none."""
        from atmem.contracts.task_state import HostTaskLifecycleRequest

        return self._host_call(
            HostTaskLifecycleRequest, payload, "request_lifecycle",
            subject_id=subject_id, agent_id=agent_id, workspace_id=workspace_id,
        )

    def _host_call(
        self,
        contract: Any,
        payload: Mapping[str, Any],
        operation: str,
        *,
        subject_id: str | None,
        agent_id: str | None,
        workspace_id: str | None,
    ) -> dict[str, Any]:
        """Parse, then run the shared gate sequence.

        A malformed request -- incomplete session identity, a smuggled
        authority field, an unknown key -- is refused here, before a scope is
        even resolved. Nothing about the task surface is disclosed by it.
        """
        state = self.state()
        scope = self._task_scope(
            state, subject_id=subject_id, agent_id=agent_id, workspace_id=workspace_id,
        )
        try:
            request = contract.from_dict(dict(payload))
        except (ValueError, KeyError, TypeError) as exc:
            return {
                "format": "atmem-task-unavailable-v1",
                "reason_code": "session_identity_required"
                if "session identity" in str(exc)
                else "capability_denied",
                "message": str(exc),
            }
        boundary, _service, memory = self._host_boundary(state)
        try:
            return getattr(boundary, operation)(scope, request)
        finally:
            memory.close()

    def change_task_lifecycle(
        self,
        task_id: str,
        action: str,
        *,
        actor: str,
        reason: str = "",
        expected_revision: Any = None,
        subject_id: str | None = None,
        agent_id: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """Pause, resume, complete, or cancel one task from the dashboard.

        A stale expected revision is a conflict the operator must see and
        resubmit; it is never retried on their behalf.
        """
        from atmem.contracts.task_state import ActorRole
        from atmem.task_state.service import TaskCompletionDenied, TaskStateError

        if action not in {"pause", "resume", "complete", "cancel"}:
            raise ValueError(f"unsupported task lifecycle action: {action!r}")
        state = self.state()
        scope = self._task_scope(
            state, subject_id=subject_id, agent_id=agent_id,
            workspace_id=workspace_id,
        )
        service, memory = self._task_service(state)
        try:
            if expected_revision is not None:
                current = service.get(scope, task_id).state.revision
                if int(expected_revision) != current:
                    return {
                        "format": "atmem-task-conflict-v1",
                        "task_id": task_id,
                        "reason_code": "stale_base_revision",
                        "expected_revision": int(expected_revision),
                        "current_revision": current,
                        "message": (
                            f"This task is at revision {current}, not "
                            f"{expected_revision}. Review the change and submit "
                            "a fresh request."
                        ),
                    }
            try:
                view = getattr(service, action)(
                    scope, task_id, actor=actor,
                    actor_role=ActorRole.OPERATOR, reason=reason or action,
                )
                return {"format": "atmem-task-lifecycle-result-v1", **view.to_dict()}
            except TaskCompletionDenied as exc:
                return {
                    "format": "atmem-task-unavailable-v1",
                    "task_id": task_id,
                    "reason_code": exc.reason_code,
                    "message": str(exc),
                    "guard": exc.guard.to_dict(),
                }
            except TaskStateError as exc:
                return {
                    "format": "atmem-task-unavailable-v1",
                    "task_id": task_id,
                    "reason_code": exc.reason_code,
                    "message": str(exc),
                }
        finally:
            memory.close()

    def _task_scope(
        self, state: Any, *, subject_id: str | None, agent_id: str | None,
        workspace_id: str | None,
    ) -> Any:
        from atmem.contracts import AuthorityScope

        return AuthorityScope(
            subject_id=subject_id or state.subject_id,
            agent_id=agent_id or "default-agent",
            workspace_id=workspace_id or "default-workspace",
        )

    def extraction_proposals(
        self, subject_id: str | None = None, *, limit: int = 100
    ) -> dict[str, Any]:
        """Project the same review queue the CLI shows, for the dashboard.

        Both surfaces read one service, so a proposal's state, evidence, and
        allowed actions cannot drift between them.
        """
        from atmem.extract.review import ReviewService
        from atmem.memory import Memory

        state = self.state()
        memory = Memory(
            self._proposal_memory_db(state), retain_query_text=False, auto_vectors=False
        )
        try:
            return ReviewService(memory).queue(subject_id, limit=limit)
        finally:
            memory.close()

    def decide_extraction_proposal(
        self,
        proposal_id: str,
        decision: str,
        *,
        actor: str,
        reason: str = "",
        edited_fact: str | None = None,
    ) -> dict[str, Any]:
        """Record one dashboard review decision through the shared service."""
        from atmem.extract.review import ReviewService
        from atmem.memory import Memory

        state = self.state()
        memory = Memory(
            self._proposal_memory_db(state), retain_query_text=False, auto_vectors=False
        )
        try:
            return ReviewService(memory).decide(
                proposal_id,
                decision,
                actor=actor,
                reason=reason,
                edited_fact=edited_fact,
            )
        finally:
            memory.close()

    def _proposal_memory_db(self, state: Any) -> Path:
        if state.host == "openclaw":
            from atmem.control.openclaw_native import mirror_status

            mirror = mirror_status(state)
            return Path(
                str(
                    mirror.get("mirror_db")
                    or Path(state.control_dir) / "openclaw-mirror.db"
                )
            )
        return self._generic_memory_db(state)

    def memory_reviews(self) -> dict[str, Any]:
        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import list_mirror_reviews

            return list_mirror_reviews(state)
        rows = self.candidates(include_reviewed=False)
        from atmem.memory import Memory

        memory = Memory(self._generic_memory_db(state), retain_query_text=False)
        try:
            canonical = [
                {**row, "subject_id": subject}
                for subject in self._generic_subjects(state)
                for row in memory.list(subject, include_inactive=True)
                if row.get("status") == "quarantined"
            ]
            canonical_valid = all(
                bool(memory.verify(subject).get("valid"))
                for subject in self._generic_subjects(state)
            )
        finally:
            memory.close()
        return {
            "format": "atmem-host-neutral-review-queue-v1",
            "audit_chain_valid": bool(self.memory_status()["audit_verified"])
            and canonical_valid,
            "records": [
                {
                    "record_id": row["id"],
                    "content": row["content"],
                    "scope": "authenticated user memory",
                    "status": row["status"],
                    "subject_id": row.get("subject_id"),
                    "created_at": row["created_at"],
                    "content_sha256": row.get("content_sha256")
                    or sha256_hex(str(row.get("content") or "")),
                }
                for row in rows
            ]
            + [
                {
                    "record_id": row["id"],
                    "content": row["content"],
                    "scope": "canonical quarantined memory",
                    "status": row["status"],
                    "subject_id": row.get("subject_id"),
                    "created_at": row["created_at"],
                    "content_sha256": row.get("content_sha256")
                    or sha256_hex(str(row.get("content") or "")),
                }
                for row in canonical
            ],
        }

    def memory_record(self, record_id: str) -> dict[str, Any]:
        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import inspect_mirror_record

            return inspect_mirror_record(state, record_id)
        store = self._store(state)
        try:
            rows = store.list_candidates(state.migration_id)
            chain = store.verify_transitions(state.migration_id)
            control_exposures = store.list_record_exposures(
                state.migration_id, record_id
            )
            blackbox_entries = store.list_evidence(
                state.migration_id, kind="agent_blackbox"
            )
        finally:
            store.close()
        deliveries: list[dict[str, Any]] = []
        control_timeline: list[dict[str, Any]] = []
        for exposure in control_exposures:
            preview_id = str(exposure.get("preview_id") or "")
            linked_events = [
                entry
                for entry in blackbox_entries
                if str((entry.get("body") or {}).get("context_receipt_id") or "")
                == preview_id
            ]
            response_entry = next(
                (
                    entry
                    for entry in linked_events
                    if (entry.get("body") or {}).get("event_type") == "model.output"
                ),
                None,
            )
            response_body = (response_entry or {}).get("body") or {}
            response_payload = response_body.get("payload") or {}
            deliveries.append(
                {
                    "retrieval_id": None,
                    "session_id": exposure.get("session_id"),
                    "recalled_at": exposure.get("preview_created_at"),
                    "returned": True,
                    "rank": None,
                    "score": None,
                    "context_event_id": exposure.get("exposure_id"),
                    "context_injected_at": (
                        exposure.get("shown_at") if exposure.get("shown") else None
                    ),
                    "response_event_id": response_body.get("event_id"),
                    "response_sha256": response_payload.get("response_sha256"),
                    "context_receipt_id": preview_id,
                    "run_id": exposure.get("host_run_id"),
                }
            )
            control_timeline.append(
                {
                    "title": "Selected for runtime context",
                    "detail": (
                        "The adapter confirmed that this memory reached the model request."
                        if exposure.get("shown")
                        else "AtMem prepared this memory, but exact model exposure was not confirmed."
                    ),
                    "at": exposure.get("shown_at")
                    or exposure.get("preview_created_at"),
                    "actor": "runtime-adapter",
                    "event_id": exposure.get("exposure_id") or preview_id,
                    "session_id": exposure.get("session_id"),
                }
            )
        row = next((item for item in rows if str(item["id"]) == record_id), None)
        if row is None:
            from atmem.memory import Memory

            memory = Memory(self._generic_memory_db(state), retain_query_text=False)
            try:
                canonical = None
                canonical_subject = None
                for subject in self._generic_subjects(state):
                    candidate = memory.store.get_record(subject, record_id)
                    if candidate is not None:
                        canonical = candidate
                        canonical_subject = subject
                        break
                if canonical is None:
                    raise ValueError(f"unknown memory record: {record_id}")
                audit = memory.audit(str(canonical_subject))
                source_episode = next(
                    (
                        episode
                        for episode in memory.store.list_episodes(
                            str(canonical_subject)
                        )
                        if str(episode.get("id") or "")
                        == str(canonical.get("episode_id") or "")
                    ),
                    None,
                )
            finally:
                memory.close()
            audit_events = list(audit.get("audit_log") or [])
            related_events = [
                event
                for event in audit_events
                if str(event.get("record_id") or "") == record_id
                or record_id in canonical_json(event.get("payload") or {})
            ]
            source_event = next(
                (
                    event
                    for event in audit_events
                    if event.get("event_type") == "episode.ingested"
                    and str((event.get("payload") or {}).get("episode_id") or "")
                    == str(canonical.get("episode_id") or "")
                ),
                None,
            )
            canonical_timeline = [
                {
                    "title": str(event.get("event_type") or "Memory event").replace(
                        ".", " "
                    ),
                    "detail": ", ".join(
                        str(key).replace("_", " ")
                        for key in list((event.get("payload") or {}).keys())[:4]
                    )
                    or "Canonical memory evidence recorded.",
                    "at": event.get("created_at"),
                    "actor": event.get("actor"),
                    "event_id": event.get("event_id"),
                    "session_id": event.get("session_id"),
                }
                for event in related_events
            ]
            for retrieval in audit.get("retrieval_events") or []:
                ranked = next(
                    (
                        candidate
                        for candidate in retrieval.get("candidates") or []
                        if str(candidate.get("record_id") or "") == record_id
                    ),
                    None,
                )
                if ranked is None:
                    continue
                retrieval_id = str(retrieval.get("id") or "")
                injection = next(
                    (
                        event
                        for event in audit_events
                        if event.get("event_type") == "memory.context_injected"
                        and str(
                            (event.get("payload") or {}).get("retrieval_id") or ""
                        )
                        == retrieval_id
                        and record_id
                        in ((event.get("payload") or {}).get("record_ids") or [])
                    ),
                    None,
                )
                response = next(
                    (
                        event
                        for event in audit_events
                        if event.get("event_type") == "agent.response_after_memory"
                        and record_id
                        in (
                            (event.get("payload") or {}).get(
                                "injected_record_ids"
                            )
                            or []
                        )
                        and (
                            injection is None
                            or str(
                                (event.get("payload") or {}).get(
                                    "context_event_id"
                                )
                                or ""
                            )
                            == str((injection or {}).get("event_id") or "")
                        )
                    ),
                    None,
                )
                deliveries.append(
                    {
                        "retrieval_id": retrieval_id,
                        "session_id": retrieval.get("session_id"),
                        "recalled_at": retrieval.get("created_at"),
                        "returned": bool(ranked.get("returned")),
                        "rank": ranked.get("rank"),
                        "score": ranked.get("score"),
                        "context_event_id": (injection or {}).get("event_id"),
                        "context_injected_at": (injection or {}).get(
                            "created_at"
                        ),
                        "response_event_id": (response or {}).get("event_id"),
                        "response_sha256": ((response or {}).get("payload") or {}).get(
                            "response_sha256"
                        ),
                    }
                )
            raw = canonical.get("raw") or {}
            return {
                "format": "atmem-host-neutral-memory-record-v1",
                "record": {
                    **canonical,
                    "content_sha256": canonical.get("content_sha256")
                    or sha256_hex(str(canonical.get("content") or "")),
                },
                "status": canonical.get("status"),
                "audit_chain_valid": bool(audit.get("audit_chain_valid")),
                "provenance": {
                    "source_message_sha256": raw.get("source_message_sha256")
                    or ((source_event or {}).get("payload") or {}).get(
                        "message_sha256"
                    ),
                    "source_binding": "canonical-atmem-memory",
                    "episode_id": canonical.get("episode_id"),
                    "plane": "canonical",
                    "source_type": canonical.get("source_type"),
                    "original_context": (source_episode or {}).get("message"),
                    "original_context_retained": bool(
                        source_episode
                        and (source_episode.get("message") or "") != "[purged]"
                    ),
                    "source_actor": (source_event or {}).get("actor"),
                    "source_session_id": canonical.get("source_session_id")
                    or (source_episode or {}).get("session_id"),
                },
                "lifecycle": {
                    "created_at": canonical.get("created_at"),
                    "superseded_at": canonical.get("updated_at")
                    if canonical.get("status") == "superseded"
                    else None,
                    "deleted_at": canonical.get("deleted_at"),
                },
                "deliveries": deliveries,
                "timeline": sorted(
                    [*canonical_timeline, *control_timeline],
                    key=lambda event: str(event.get("at") or ""),
                ),
                "deletion_receipt": None,
            }
        status = str(row.get("status") or "candidate")
        return {
            "format": "atmem-host-neutral-memory-record-v1",
            "record": {
                "id": record_id,
                "content": row.get("content"),
                "content_sha256": row.get("content_sha256"),
                "subject_id": row.get("subject_id"),
            },
            "status": status,
            "audit_chain_valid": bool(chain["valid"]),
            "provenance": {
                "source_message_sha256": row.get("source_message_sha256"),
                "source_binding": "authenticated-host-capture",
                "episode_id": None,
                "plane": "generic-shadow",
            },
            "lifecycle": {
                "created_at": row.get("created_at"),
                "reviewed_at": row.get("reviewed_at"),
                "superseded_at": None,
                "deleted_at": None,
            },
            "deliveries": deliveries,
            "timeline": [
                {
                    "title": "Captured in shadow mode",
                    "detail": (
                        "Approved for active recall." if status == "approved"
                        else "Waiting for review." if status == "candidate"
                        else "Rejected by an operator."
                    ),
                    "at": row.get("created_at"),
                    "actor": "host-adapter",
                    "event_id": None,
                }
            ]
            + control_timeline,
            "deletion_receipt": None,
        }

    def memory_provenance(self, record_id: str) -> dict[str, Any]:
        """Return the human contract for a memory, with raw proof kept separate."""
        report = self.memory_record(record_id)
        record = report.get("record") or {}
        provenance = report.get("provenance") or {}
        lifecycle = report.get("lifecycle") or {}
        deliveries = list(report.get("deliveries") or [])
        status = str(report.get("status") or record.get("status") or "unknown")
        subject_id = str(
            record.get("subject_id")
            or report.get("subject_id")
            or self.state().subject_id
        )
        short_id = str(record_id).removeprefix("rec_")[-8:].upper()

        native_path = str(provenance.get("native_path") or "")
        source_type = str(
            provenance.get("source_type")
            or record.get("source_type")
            or "unknown"
        )
        model = provenance.get("interpreting_model")
        if native_path:
            source_kind, source_label = "file", native_path
        elif source_type in {"user_message", "trusted_user"}:
            source_kind, source_label = "conversation", "Conversation"
        elif source_type in {"tool", "tool_output"}:
            source_kind, source_label = "tool", "Tool output"
        elif source_type in {"website", "web"}:
            source_kind, source_label = "website", "Website"
        elif source_type in {"document", "media"}:
            source_kind, source_label = "file", "Imported content"
        else:
            source_kind, source_label = "system", source_type.replace("_", " ").title()

        if model:
            creation_method = "model_inference"
            creation_label = f"Inferred by {model}"
        elif native_path:
            creation_method = "imported"
            creation_label = "Imported from a source file"
        elif record.get("scope") == "user_note":
            creation_method = "copied"
            creation_label = "Saved from the user's words"
        else:
            creation_method = "rule_extraction"
            creation_label = "Extracted by deterministic rules"

        confidence = record.get("confidence")
        if confidence is None:
            confidence_label = "Not recorded"
        elif float(confidence) >= 0.9:
            confidence_label = "Certain"
        elif float(confidence) >= 0.7:
            confidence_label = "Likely"
        else:
            confidence_label = "Uncertain"
        if status == "quarantined":
            confidence_label = "Awaiting approval"

        returned = [row for row in deliveries if row.get("returned")]
        injected = [row for row in deliveries if row.get("context_injected_at")]
        response_bound = [row for row in deliveries if row.get("response_event_id")]
        last_used_at = max(
            (
                str(row.get("context_injected_at") or row.get("recalled_at") or "")
                for row in deliveries
            ),
            default="",
        ) or None
        if injected:
            usage_summary = (
                f"Delivered to agent context in {len(injected)} recorded "
                f"{'run' if len(injected) == 1 else 'runs'}."
            )
            evidence_strength = "context_delivery_recorded"
        elif returned:
            usage_summary = "Returned by memory search; context delivery was not recorded."
            evidence_strength = "search_return_recorded"
        elif deliveries:
            usage_summary = "Considered by memory search but not returned."
            evidence_strength = "search_consideration_recorded"
        else:
            usage_summary = "No recorded use."
            evidence_strength = "none"

        topology = self.agent_topology()
        workspace = next(
            (
                row
                for row in topology.get("workspaces") or []
                if str(row.get("subject_id") or "") == subject_id
            ),
            {},
        )
        agent_ids = list(
            workspace.get("agent_ids")
            or workspace.get("agents")
            or []
        )
        workspace_label = (
            workspace.get("workspace")
            or workspace.get("path")
            or workspace.get("name")
            or "Default workspace"
        )

        storages = []
        for storage in self.status().get("storages") or []:
            storage_id = str(storage.get("id") or "")
            if storage_id == "canonical":
                present, detail = True, "Authoritative record and provenance"
            elif storage_id == "graph":
                present = bool(storage.get("count") or storage.get("entry_count"))
                detail = "Entity link available" if present else "No entity link for this memory is proven"
            elif storage_id.startswith("vectors"):
                present = bool(storage.get("ready"))
                detail = "Semantic index is active" if present else "Semantic index is not active"
            elif storage_id == "evidence":
                present, detail = bool(report.get("timeline")), "Lifecycle and usage evidence"
            else:
                present, detail = bool(storage.get("exists")), str(storage.get("role") or "Stored locally")
            storages.append(
                {
                    "id": storage_id,
                    "label": storage.get("label") or storage_id.replace("-", " ").title(),
                    "present": present,
                    "detail": detail,
                    "path": storage.get("path"),
                }
            )

        timeline = list(report.get("timeline") or [])
        changes = [
            {
                "at": item.get("at"),
                "actor": item.get("actor") or "system",
                "summary": item.get("title") or item.get("type") or "Memory changed",
                "reason": item.get("detail") or "A lifecycle event was recorded.",
            }
            for item in timeline
            if any(
                word in str(item.get("type") or item.get("title") or "").casefold()
                for word in ("create", "admit", "approve", "reject", "supersed", "forget", "correct")
            )
        ]
        original_context = provenance.get("original_context")
        if original_context and len(str(original_context)) > 1200:
            original_context = str(original_context)[:1199].rstrip() + "…"

        excluded = False
        graph_record_present = False
        vector_record_present = False
        try:
            memory, action_subject = self._open_canonical_record(record_id)
            try:
                excluded = record_id in memory.store.excluded_record_ids(
                    action_subject
                )
                graph_record_present = memory.store._conn.execute(
                    """
                    SELECT 1 FROM edges
                    WHERE subject_id = ? AND record_id = ? AND status != 'tombstoned'
                    UNION ALL
                    SELECT 1 FROM entities
                    WHERE subject_id = ? AND source_record = ? AND status != 'tombstoned'
                    UNION ALL
                    SELECT 1 FROM entity_aliases
                    WHERE subject_id = ? AND source_record = ? AND status != 'tombstoned'
                    LIMIT 1
                    """,
                    (
                        action_subject,
                        record_id,
                        action_subject,
                        record_id,
                        action_subject,
                        record_id,
                    ),
                ).fetchone() is not None
                for registry in memory.store.semantic_index_paths(action_subject):
                    index_path = Path(str(registry.get("index_path") or ""))
                    if not index_path.is_file():
                        continue
                    try:
                        connection = sqlite3.connect(
                            f"file:{index_path.resolve()}?mode=ro", uri=True
                        )
                        try:
                            found = connection.execute(
                                """
                                SELECT 1 FROM vector_entries AS entry
                                JOIN vector_epochs AS epoch
                                  ON epoch.epoch_id = entry.epoch_id
                                WHERE entry.subject_id = ? AND entry.object_id = ?
                                  AND epoch.status = 'active'
                                LIMIT 1
                                """,
                                (action_subject, record_id),
                            ).fetchone()
                        finally:
                            connection.close()
                    except sqlite3.Error:
                        continue
                    if found is not None:
                        vector_record_present = True
                        break
            finally:
                memory.close()
        except ValueError:
            pass
        for storage in storages:
            if storage["id"] == "graph":
                storage["present"] = graph_record_present
                storage["detail"] = (
                    "This memory has entity or relationship links"
                    if graph_record_present
                    else "This memory has no entity or relationship links"
                )
            elif storage["id"].startswith("vectors"):
                storage["present"] = vector_record_present
                storage["detail"] = (
                    "This exact memory is in the active semantic index"
                    if vector_record_present
                    else "This exact memory is not in the active semantic index"
                )
        return {
            "format": "atmem-memory-provenance-v1",
            "memory": {
                "display_id": short_id,
                "record_id": record_id,
                "text": record.get("content") or "This memory has been deleted.",
                "status": status,
            },
            "origin": {
                "kind": source_kind,
                "label": source_label,
                "provided_by": provenance.get("source_actor")
                or ("OpenClaw" if native_path else "User"),
                "learned_at": lifecycle.get("created_at") or record.get("created_at"),
                "updated_at": record.get("updated_at") or lifecycle.get("superseded_at"),
                "original_context": original_context,
                "original_context_retained": bool(
                    provenance.get("original_context_retained")
                ),
            },
            "creation": {
                "method": creation_method,
                "label": creation_label,
                "model": model,
                "confidence": confidence,
                "confidence_label": confidence_label,
                "assurance": provenance.get("interpretation_assurance"),
            },
            "changes": changes,
            "usage": {
                "summary": usage_summary,
                "considered_count": len(deliveries),
                "returned_count": len(returned),
                "delivered_count": len(injected),
                "response_bound_count": len(response_bound),
                "last_used_at": last_used_at,
                "best_rank": min(
                    (int(row["rank"]) for row in returned if row.get("rank") is not None),
                    default=None,
                ),
                "evidence_strength": evidence_strength,
            },
            "scope": {
                "subject_id": subject_id,
                "user": "Current AtMem user",
                "workspace": workspace_label,
                "agent_ids": agent_ids,
            },
            "storage": storages,
            "controls": {
                "can_correct": status == "active",
                "can_exclude": status == "active",
                "can_approve": status == "quarantined",
                "can_reject": status == "quarantined",
                "can_forget": status not in {"deleted", "tombstoned", "audit-only"},
                "excluded": excluded,
            },
            "deletion": {
                "deleted": bool(report.get("deletion_receipt")),
                "summary": (
                    "Canonical, graph, vector and linked source cleanup was verified."
                    if report.get("deletion_receipt")
                    else "This memory has not been deleted."
                ),
                "receipt_available": bool(report.get("deletion_receipt")),
            },
            "technical": report,
        }

    def _open_canonical_record(self, record_id: str) -> tuple[Any, str]:
        from atmem.memory import Memory

        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import mirror_status

            mirror = mirror_status(state)
            if not mirror.get("synced"):
                raise ValueError(mirror.get("error") or "memory mirror is not synchronized")
            memory = Memory(mirror["mirror_db"], retain_query_text=False)
            subjects = memory.store.subject_ids() or [state.subject_id]
        else:
            memory = Memory(self._generic_memory_db(state), retain_query_text=False)
            subjects = self._generic_subjects(state)
        for subject in subjects:
            if memory.store.get_record(subject, record_id) is not None:
                return memory, str(subject)
        memory.close()
        raise ValueError(f"unknown memory record: {record_id}")

    def correct_memory(
        self, record_id: str, corrected_text: str, reason: str = ""
    ) -> dict[str, Any]:
        memory, subject = self._open_canonical_record(record_id)
        try:
            return memory.correct_record(
                subject,
                record_id,
                corrected_text,
                reason=reason,
                actor="dashboard-reviewer",
            )
        finally:
            memory.close()

    def exclude_memory(
        self, record_id: str, excluded: bool, reason: str = ""
    ) -> dict[str, Any]:
        memory, subject = self._open_canonical_record(record_id)
        try:
            return memory.set_retrieval_excluded(
                subject,
                record_id,
                excluded,
                reason=reason,
                actor="dashboard-reviewer",
            )
        finally:
            memory.close()

    def forget_memory(self, record_id: str) -> dict[str, Any]:
        memory, subject = self._open_canonical_record(record_id)
        try:
            return memory.forget_record(
                subject, record_id, actor="dashboard-reviewer"
            )
        finally:
            memory.close()

    def memory_audit(
        self,
        *,
        query: str = "",
        event_type: str = "",
        actor: str = "",
        session_id: str = "",
        record_id: str = "",
        since: str = "",
        until: str = "",
        direction: str = "desc",
        cursor: int | None = None,
        limit: int = 100,
        include_facets: bool = False,
    ) -> dict[str, Any]:
        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import query_mirror_audit

            return query_mirror_audit(
                state,
                query=query,
                event_type=event_type,
                actor=actor,
                session_id=session_id,
                record_id=record_id,
                since=since,
                until=until,
                direction=direction,
                cursor=cursor,
                limit=limit,
                include_facets=include_facets,
            )
        store = self._store(state)
        try:
            entries = store.list_evidence(state.migration_id, kind="memory_control")
            chain = store.verify_evidence_chain(state.migration_id, kind="memory_control")
        finally:
            store.close()
        all_rows: list[dict[str, Any]] = []

        def matches(row: dict[str, Any]) -> bool:
            searchable = canonical_json(row).casefold()
            return not (
                (query and query.casefold() not in searchable)
                or (
                    event_type
                    and not fnmatchcase(str(row.get("event_type") or ""), event_type)
                )
                or (actor and str(row.get("actor") or "") != actor)
                or (session_id and str(row.get("session_id") or "") != session_id)
                or (
                    record_id
                    and str(row.get("record_id") or "") != record_id
                    and record_id not in canonical_json(row.get("payload") or {})
                )
                or (since and str(row.get("created_at") or "") < since)
                or (until and str(row.get("created_at") or "") > until)
            )

        for entry in entries:
            body = entry.get("body") or {}
            row = {
                "sequence": entry.get("sequence"),
                "source_chain": "control",
                "source_sequence": entry.get("sequence"),
                "created_at": body.get("created_at") or entry.get("created_at"),
                "event_type": body.get("event_type"),
                "actor": body.get("actor"),
                "record_id": body.get("record_id"),
                "session_id": body.get("session_id"),
                "turn_id": body.get("turn_id"),
                "event_id": entry.get("id"),
                "prev_hash": entry.get("prev_sha256"),
                "event_hash": entry.get("entry_sha256"),
                "payload": body.get("payload") or {},
            }
            all_rows.append(row)
        from atmem.memory import Memory

        memory = Memory(self._generic_memory_db(state), retain_query_text=False)
        try:
            canonical_chains: list[bool] = []
            for subject in self._generic_subjects(state):
                audit = memory.audit(subject)
                canonical_chains.append(bool(audit.get("audit_chain_valid")))
                for event in audit.get("audit_log") or []:
                    row = {
                        **event,
                        "source_chain": f"canonical:{subject}",
                        "source_sequence": event.get("sequence"),
                    }
                    all_rows.append(row)
        finally:
            memory.close()
        rows = [row for row in all_rows if matches(row)]
        reverse = direction != "asc"
        rows.sort(
            key=lambda row: (
                str(row.get("created_at") or ""),
                str(row.get("source_chain") or ""),
                int(row.get("source_sequence") or row.get("sequence") or 0),
            ),
            reverse=reverse,
        )
        start = max(0, int(cursor or 0))
        page_limit = max(1, min(int(limit), 500))
        page = rows[start : start + page_limit]
        next_cursor = start + len(page) if start + len(page) < len(rows) else None
        facets: dict[str, list[dict[str, Any]]] | None = None
        histogram: list[dict[str, Any]] | None = None
        if include_facets:
            def counted(field: str) -> list[dict[str, Any]]:
                counts: dict[str, int] = {}
                for row in all_rows:
                    value = str(row.get(field) or "")
                    if value:
                        counts[value] = counts.get(value, 0) + 1
                return [
                    {"value": value, "count": count}
                    for value, count in sorted(
                        counts.items(), key=lambda item: (-item[1], item[0])
                    )
                ]

            buckets: dict[str, int] = {}
            for row in rows:
                created_at = str(row.get("created_at") or "")
                bucket = created_at[:13] if len(created_at) >= 13 else ""
                if bucket:
                    buckets[bucket] = buckets.get(bucket, 0) + 1
            facets = {
                "event_types": counted("event_type"),
                "actors": counted("actor"),
            }
            histogram = [
                {"bucket": bucket, "count": count}
                for bucket, count in sorted(buckets.items())
            ]
        return {
            "format": "atmem-host-neutral-memory-audit-v1",
            "audit_chain_valid": bool(chain["valid"]) and all(canonical_chains),
            "matched_total": len(rows),
            "events": page,
            "has_more": next_cursor is not None,
            "next_cursor": next_cursor,
            "result_digest": sha256_hex(canonical_json(page)),
            "direction": "desc" if reverse else "asc",
            "limit": page_limit,
            "facets": facets,
            "histogram": histogram,
        }

    def verify(self, *, probe: bool = False) -> dict[str, Any]:
        """Run the adapter-aware verification used by every operator surface."""

        from atmem.control.verify import run_verification

        return run_verification(self.state(), probe=probe)

    def export_memory_audit(
        self, *, output_format: str, filters: dict[str, Any]
    ) -> tuple[str, str]:
        """Export one complete filtered audit view through the active adapter."""

        if output_format not in {"json", "ndjson", "csv", "text"}:
            raise ValueError("format must be json, ndjson, csv, or text")
        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import export_mirror_audit

            return export_mirror_audit(
                state, output_format=output_format, filters=filters
            )
        events: list[dict[str, Any]] = []
        cursor: int | None = None
        while len(events) < 100_000:
            page = self.memory_audit(
                **filters,
                cursor=cursor,
                limit=500,
                include_facets=False,
            )
            events.extend(page.get("events") or [])
            cursor = page.get("next_cursor")
            if not page.get("has_more") or cursor is None:
                break
        report = {
            "format": "atmem-audit-export-v1",
            "created_at": utc_now(),
            "host": state.host,
            "filters": filters,
            "result_count": len(events),
            "truncated": len(events) >= 100_000,
            "audit_chain_valid": bool(page.get("audit_chain_valid")),
            "events": events,
        }
        report["result_digest"] = sha256_hex(canonical_json(events))
        report["report_sha256"] = sha256_hex(canonical_json(report))
        if output_format == "json":
            return (
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                "application/json; charset=utf-8",
            )
        if output_format == "ndjson":
            metadata = {key: value for key, value in report.items() if key != "events"}
            lines = [json.dumps({"metadata": metadata}, sort_keys=True)]
            lines.extend(
                json.dumps({"event": event}, sort_keys=True) for event in events
            )
            return "\n".join(lines) + "\n", "application/x-ndjson; charset=utf-8"
        if output_format == "csv":
            import csv
            import io

            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "sequence",
                    "source_chain",
                    "created_at",
                    "event_type",
                    "actor",
                    "session_id",
                    "turn_id",
                    "record_id",
                    "event_id",
                    "event_hash",
                    "payload_json",
                ]
            )
            for event in events:
                writer.writerow(
                    [
                        event.get("sequence"),
                        event.get("source_chain"),
                        event.get("created_at"),
                        event.get("event_type"),
                        event.get("actor"),
                        event.get("session_id"),
                        event.get("turn_id"),
                        event.get("record_id"),
                        event.get("event_id"),
                        event.get("event_hash"),
                        canonical_json(event.get("payload") or {}),
                    ]
                )
            return stream.getvalue(), "text/csv; charset=utf-8"
        lines = [
            "AtMem audit investigation",
            f"Generated: {report['created_at']}",
            f"Host: {state.host}",
            f"Integrity: {'PASSED' if report['audit_chain_valid'] else 'FAILED'}",
            f"Events: {len(events)}",
            "",
        ]
        lines.extend(
            " | ".join(
                str(value or "-")
                for value in (
                    event.get("created_at"),
                    event.get("event_type"),
                    event.get("actor"),
                    event.get("record_id"),
                    event.get("event_id"),
                )
            )
            for event in events
        )
        return "\n".join(lines) + "\n", "text/plain; charset=utf-8"

    def review_memory(self, record_id: str, decision: str) -> dict[str, Any]:
        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import review_mirror_record

            return review_mirror_record(
                state, record_id, decision, actor="local-reviewer"
            )
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        candidate_rows = self.candidates(include_reviewed=True)
        candidate = next(
            (row for row in candidate_rows if str(row["id"]) == record_id), None
        )
        if candidate is not None:
            if candidate.get("status") != "candidate":
                raise ValueError(
                    f"memory candidate {record_id} was already {candidate.get('status')}"
                )
            canonical_records: list[dict[str, Any]] = []
            canonical_duplicate_ids: list[str] = []
            from atmem.memory import Memory

            memory = Memory(self._generic_memory_db(state), retain_query_text=False)
            try:
                existing = memory.store.find_duplicate_record(
                    str(candidate.get("subject_id") or state.subject_id),
                    str(candidate.get("content") or ""),
                    statuses=("active", "quarantined"),
                )
                if existing is not None and existing.get("status") == "quarantined":
                    if decision == "approve":
                        canonical_records = [
                            memory.promote(
                                str(candidate.get("subject_id") or state.subject_id),
                                str(existing["id"]),
                            )
                        ]
                    else:
                        memory.reject(
                            str(candidate.get("subject_id") or state.subject_id),
                            str(existing["id"]),
                        )
                elif decision == "approve":
                    admission = memory.remember(
                        str(candidate.get("subject_id") or state.subject_id),
                        str(candidate.get("content") or ""),
                        interpreted_fact=str(candidate.get("content") or ""),
                        interpreted_fact_key=str(candidate.get("fact_key") or "") or None,
                        session_id=candidate.get("source_session_id"),
                        actor="local-reviewer",
                        raw={
                            "control_candidate_id": record_id,
                            "source_message_sha256": candidate.get(
                                "source_message_sha256"
                            ),
                        },
                    )
                    canonical_records = list(admission.get("records") or [])
                    canonical_duplicate_ids = list(
                        admission.get("duplicate_ids") or []
                    )
                    if not canonical_records and canonical_duplicate_ids:
                        duplicate = memory.store.get_record(
                            str(candidate.get("subject_id") or state.subject_id),
                            canonical_duplicate_ids[0],
                        )
                        if duplicate is not None:
                            canonical_records = [duplicate]
            finally:
                memory.close()
            rows = self.review([record_id], approve=decision == "approve")
            if decision == "approve":
                store = self._store(state)
                try:
                    store.append_evidence(
                        state.migration_id,
                        kind="memory_control",
                        body={
                            "format": "atmem-memory-control-event-v1",
                            "event_type": "memory.canonicalized",
                            "actor": "local-reviewer",
                            "record_id": record_id,
                            "subject_id": candidate.get("subject_id"),
                            "created_at": utc_now(),
                            "payload": {
                                "canonical_record_ids": [
                                    str(row["id"]) for row in canonical_records
                                ],
                                "canonical_duplicate_ids": canonical_duplicate_ids,
                                "content_sha256": candidate.get("content_sha256"),
                            },
                        },
                    )
                finally:
                    store.close()
            return {
                "reviewed": True,
                "record_id": record_id,
                "decision": decision,
                "record": rows[0] if rows else None,
                "canonical_records": canonical_records,
                "canonical_duplicate_ids": canonical_duplicate_ids,
            }
        from atmem.memory import Memory

        memory = Memory(self._generic_memory_db(state), retain_query_text=False)
        try:
            found = None
            found_subject = None
            for subject in self._generic_subjects(state):
                row = memory.store.get_record(subject, record_id)
                if row is not None:
                    found = row
                    found_subject = subject
                    break
            if found is None or found_subject is None:
                raise ValueError(f"unknown memory record: {record_id}")
            if decision == "approve":
                reviewed = memory.promote(found_subject, record_id)
            else:
                reviewed = memory.reject(found_subject, record_id)
        finally:
            memory.close()
        return {
            "reviewed": True,
            "record_id": record_id,
            "decision": decision,
            "record": reviewed,
        }

    def sync_memory(self) -> dict[str, Any]:
        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import sync_mirror

            return sync_mirror(state)
        return {
            **self.memory_status(),
            "changed": False,
            "message": "Generic shadow capture is event-driven; there are no host files to synchronize.",
        }

    def prepare(
        self,
        query: str,
        *,
        session_id: str | None = None,
        host_run_id: str | None = None,
        turn_id: str | None = None,
        user_id: str | None = None,
        workspace_id: str | None = None,
        limit: int = 3,
        max_chars: int = 1200,
        min_score: float = 0.3,
        subject_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        state, warning = self.effective_state()
        if warning or not state.mode.captures:
            return self._no_context(state, warning or "migration is off")
        subject_id = self._resolve_subject(
            state, subject_id=subject_id, agent_id=agent_id
        )
        store = self._store(state)
        try:
            from atmem.delegated import DelegatedBinding, DelegatedContextService

            delegated_service = DelegatedContextService()
            delegated_decision: dict[str, Any] | None = None
            if delegated_service.config.has_enabled_for_agent(agent_id):
                missing = [
                    name
                    for name, value in (
                        ("host_run_id", host_run_id),
                        ("turn_id", turn_id),
                        ("session_id", session_id),
                        ("agent_id", agent_id),
                        ("user_id", user_id),
                        ("workspace_id", workspace_id),
                    )
                    if not value
                ]
                if missing:
                    return {
                        **self._no_context(
                            state,
                            "delegated context failed closed: missing " + ", ".join(missing),
                        ),
                        "authority": "delegated",
                        "decision": "provider_failure",
                        "native_fallback": False,
                    }
                if not state.mode.influences_agent:
                    return {
                        **self._no_context(state, "delegated context requires active mode"),
                        "authority": "delegated",
                        "decision": "withhold",
                        "native_fallback": False,
                    }
                topology = self.agent_topology(state=state)
                scoped_agent = next(
                    (
                        row for row in topology.get("agents") or []
                        if str(row.get("agent_id") or "") == agent_id
                    ),
                    None,
                )
                if scoped_agent is None or str(scoped_agent.get("workspace_id") or "") != workspace_id:
                    return {
                        **self._no_context(
                            state,
                            "delegated context failed closed: agent and workspace are not bound by AtMem topology",
                        ),
                        "authority": "delegated",
                        "decision": "provider_failure",
                        "native_fallback": False,
                    }
                binding = DelegatedBinding.from_dict(
                    {
                        "run_id": host_run_id,
                        "turn_id": turn_id,
                        "session_id": session_id,
                        "agent_id": agent_id,
                        "user_id": user_id,
                        "workspace_id": workspace_id,
                    }
                )
                delegated_decision = delegated_service.prepare(
                    query=query,
                    binding=binding,
                    migration_id=state.migration_id,
                    store=store,
                )
                if delegated_decision and not delegated_decision.get("native_fallback"):
                    delegated_reason = delegated_decision.get("withhold_reason")
                    if isinstance(delegated_reason, dict):
                        delegated_reason = delegated_reason.get("code")
                    return {
                        **self._no_context(
                            state,
                            delegated_reason
                            or delegated_decision.get("failure_reason")
                            or "delegated provider withheld context",
                        ),
                        **delegated_decision,
                        "mode": state.mode.value,
                        "context_receipt_id": (
                            (delegated_decision.get("receipt") or {}).get("id")
                        ),
                        "manifest_sha256": delegated_decision.get("result_sha256"),
                        "preview_context": delegated_decision.get("context", ""),
                        "candidate_ids": [],
                    }

            from atmem.control.atbot_companion import AtBotCompanionClient
            from atmem.contracts import ContextRequest
            from atmem.memory import Memory

            companion = AtBotCompanionClient()
            expansion = companion.expand_query(query)
            expanded_queries = list(expansion.get("expanded_queries") or [query])

            canonical_candidates = self._hybrid_memory_candidates(
                expanded_queries,
                subject_id=subject_id,
                agent_id=agent_id,
                min_score=min_score,
                limit=max(50, limit * 10),
                reranker_model="control-prepare",
            )
            candidate_set, scope, memory_path = self._durable_candidate_set(
                query,
                canonical_candidates,
                subject_id=subject_id,
                agent_id=agent_id,
                limit=max(1, min(100, len(canonical_candidates) or 1)),
                reranker_model="control-prepare",
                min_score=min_score,
            )
            eligible_rows = [row.to_dict() for row in candidate_set.candidates]
            eligible = {str(row["record_id"]): row for row in eligible_rows}
            ranking = companion.query(query, eligible_rows)
            ranked_ids = list(
                dict.fromkeys(
                    str(record_id)
                    for record_id in ranking.get("ranked_record_ids") or []
                    if str(record_id) in eligible
                )
            )[: max(0, limit)]

            # This is the final authority boundary. It rejects stale generations,
            # expired sets, unknown IDs, deleted records, and scope changes before
            # serializing the exact context bytes that an adapter may deliver.
            memory = Memory(memory_path, retain_query_text=False, graph_recall=True)
            try:
                package = memory.prepare_context_v1(
                    ContextRequest(
                        context_id=f"control_context_{uuid.uuid4().hex}",
                        candidate_set_id=candidate_set.candidate_set_id,
                        scope=scope,
                        record_ids=tuple(ranked_ids),
                        budget_chars=max_chars,
                    )
                )
            finally:
                memory.close()
            candidate_ids = list(package.record_ids)
            candidate_hashes = [
                sha256_hex(str(eligible[record_id]["content"]))
                for record_id in candidate_ids
            ]
            context = package.context if candidate_ids else ""
            turn = store.insert_turn(
                state.migration_id,
                query_sha256=sha256_hex(query),
                session_id=session_id,
                host_run_id=host_run_id,
                subject_id=subject_id,
                agent_id=agent_id,
            )
            manifest = {
                "format": "atmem-control-context-v1",
                "migration_id": state.migration_id,
                "state_revision": state.revision,
                "mode": state.mode.value,
                "query_sha256": sha256_hex(query),
                "candidate_ids": candidate_ids,
                "candidate_content_sha256": candidate_hashes,
                "context_sha256": package.context_sha256,
                "candidate_set_id": candidate_set.candidate_set_id,
                "preparation_id": package.preparation_id,
                "serializer_version": package.serializer_version,
            }
            preview = store.insert_preview(
                state.migration_id,
                str(turn["id"]),
                candidate_ids=candidate_ids,
                context_text=context,
                manifest_sha256=sha256_hex(canonical_json(manifest)),
            )
            inject = bool(context) and state.mode.influences_agent
            reason: str | None = None
            exposure = None
            if inject:
                exposure = store.insert_exposure(
                    state.migration_id,
                    turn_id=str(turn["id"]),
                    preview_id=str(preview["id"]),
                    session_id=session_id,
                    mode=state.mode.value,
                )
            return {
                "authority": (
                    "atmem_fallback" if delegated_decision else "atmem"
                ),
                "decision": "native_context",
                "native_fallback": bool(delegated_decision),
                "delegated": delegated_decision,
                "mode": state.mode.value,
                "turn_id": turn["id"],
                "preview_id": preview["id"],
                "context_receipt_id": preview["id"],
                "manifest_sha256": preview["manifest_sha256"],
                "candidate_ids": candidate_ids,
                "candidate_set_id": candidate_set.candidate_set_id,
                "preparation_id": package.preparation_id,
                "context_sha256": package.context_sha256,
                "context": context if inject else "",
                "preview_context": context,
                "inject": inject,
                "exposure_id": exposure["id"] if exposure else None,
                "reason": reason,
                "retrieval": {
                    "queries": expanded_queries,
                    "signals": [
                        "lexical",
                        "fact_key",
                        "semantic",
                        "graph",
                        "trust",
                        "recency",
                    ],
                    "eligible_candidate_count": len(eligible_rows),
                    "ranked_candidate_ids": ranked_ids,
                    "candidate_set_id": candidate_set.candidate_set_id,
                    "candidate_generation": candidate_set.generation,
                    "candidate_digest": candidate_set.candidate_digest,
                    "preparation_id": package.preparation_id,
                    "companion": ranking.get("companion"),
                },
            }
        finally:
            store.close()

    def confirm_exposure(self, exposure_id: str) -> bool:
        state = self.state()
        store = self._store(state)
        try:
            return store.mark_exposure_shown(state.migration_id, exposure_id)
        finally:
            store.close()

    def record_blackbox_event(
        self,
        *,
        event_type: str,
        run_id: str,
        session_id: str | None = None,
        tool_call_id: str | None = None,
        turn_id: str | None = None,
        retrieval_id: str | None = None,
        context_event_id: str | None = None,
        context_receipt_id: str | None = None,
        outcome_id: str | None = None,
        agent_id: str | None = None,
        workspace_id: str | None = None,
        subject_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append one content-minimizing host observation to the flight chain."""

        from atmem.control.blackbox import EVIDENCE_KIND, normalize_event

        state, warning = self.effective_state()
        if warning or state.migration_id == "unavailable":
            raise ValueError("blackbox recording requires a valid control state")
        resolved_subject = self._resolve_subject(
            state, subject_id=subject_id, agent_id=agent_id
        )
        topology: dict[str, Any] = {}
        if agent_id or workspace_id:
            if state.host == "openclaw":
                manifest_path = Path(state.control_dir) / "openclaw-mirror.json"
                if manifest_path.is_file():
                    try:
                        topology = dict(
                            json.loads(manifest_path.read_text(encoding="utf-8")).get("topology") or {}
                        )
                    except (OSError, json.JSONDecodeError):
                        topology = {}
            else:
                topology = self.agent_topology(state=state)
        agent_row = next(
            (row for row in topology.get("agents") or [] if row.get("agent_id") == agent_id),
            None,
        )
        resolved_workspace = str((agent_row or {}).get("workspace_id") or workspace_id or "") or None
        if workspace_id and resolved_workspace != workspace_id:
            raise ValueError("agent and workspace identify different scopes")
        workspace_row = next(
            (
                row
                for row in topology.get("workspaces") or []
                if row.get("workspace_id") == resolved_workspace
            ),
            None,
        )
        if resolved_workspace and topology.get("workspaces") and workspace_row is None:
            raise ValueError("workspace is not part of the current agent topology")
        workspace_subject = str((workspace_row or {}).get("subject_id") or "") or None
        if subject_id and workspace_subject and subject_id != workspace_subject:
            raise ValueError("workspace and subject identify different scopes")
        if workspace_subject:
            resolved_subject = workspace_subject
        body = normalize_event(
            migration_id=state.migration_id,
            host=state.host,
            event_type=event_type,
            run_id=run_id,
            session_id=session_id,
            tool_call_id=tool_call_id,
            turn_id=turn_id,
            retrieval_id=retrieval_id,
            context_event_id=context_event_id,
            context_receipt_id=context_receipt_id,
            outcome_id=outcome_id,
            agent_id=agent_id,
            workspace_id=resolved_workspace,
            subject_id=resolved_subject,
            payload=payload,
        )
        store = self._store(state)
        try:
            entry = store.append_evidence(
                state.migration_id,
                kind=EVIDENCE_KIND,
                body=body,
            )
        finally:
            store.close()
        return {
            "recorded": True,
            "event_id": entry["id"],
            "sequence": entry["sequence"],
            "entry_sha256": entry["entry_sha256"],
        }

    def blackbox_events(self, *, run_id: str | None = None) -> list[dict[str, Any]]:
        from atmem.control.blackbox import EVIDENCE_KIND

        state = self.state()
        store = self._store(state)
        try:
            entries = store.list_evidence(state.migration_id, kind=EVIDENCE_KIND)
        finally:
            store.close()
        if run_id is None:
            return entries
        return [
            entry
            for entry in entries
            if str((entry.get("body") or {}).get("run_id") or "") == run_id
        ]

    def blackbox_runs(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        from atmem.control.blackbox import (
            EVIDENCE_KIND,
            flight_runs,
            recent_model_baseline,
            verify_flight,
        )

        state = self.state()
        store = self._store(state)
        try:
            entries = store.list_evidence(state.migration_id, kind=EVIDENCE_KIND)
            chain = store.verify_evidence_chain(
                state.migration_id, kind=EVIDENCE_KIND
            )
            acknowledgements = store.list_attention_acknowledgements(
                state.migration_id
            )
        finally:
            store.close()
        runs = flight_runs(entries)
        page_offset = max(0, int(offset))
        page_limit = max(0, min(int(limit), 500))
        visible_runs = runs[page_offset : page_offset + page_limit]
        entries_by_run: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            entry_run_id = str((entry.get("body") or {}).get("run_id") or "")
            if entry_run_id:
                entries_by_run.setdefault(entry_run_id, []).append(entry)
        baseline_model = recent_model_baseline(entries)
        for row in visible_runs:
            report = verify_flight(
                run_id=str(row["run_id"]),
                entries=entries_by_run[str(row["run_id"])],
                chain=chain,
                model_baseline=baseline_model,
            )
            points = report.get("attention_points") or []
            row["verdict"] = report.get("verdict")
            row["coverage_status"] = (report.get("coverage_matrix") or {}).get(
                "overall_status"
            )
            row["attention_points"] = points
            row["current_contract_observed"] = bool(
                (report.get("compatibility") or {}).get(
                    "current_contract_observed"
                )
            )
        if any(row["current_contract_observed"] for row in visible_runs):
            for row in visible_runs:
                row["attention_points"] = [
                    point
                    for point in row["attention_points"]
                    if point.get("code") != "legacy_evidence_contract"
                ]
        acknowledgement_keys = {
            (
                str(item["run_id"]),
                str(item["attention_code"]),
                str(item["attention_sha256"]),
            ): item
            for item in acknowledgements
        }
        for row in visible_runs:
            active_points: list[dict[str, Any]] = []
            acknowledged_points: list[dict[str, Any]] = []
            for point in row["attention_points"]:
                key = (
                    str(row["run_id"]),
                    str(point.get("code") or ""),
                    sha256_hex(canonical_json(point)),
                )
                acknowledgement = acknowledgement_keys.get(key)
                if acknowledgement is None:
                    active_points.append(point)
                else:
                    acknowledged_points.append(
                        {
                            **point,
                            "acknowledgement": {
                                "id": acknowledgement["id"],
                                "actor": acknowledgement["actor"],
                                "created_at": acknowledgement["created_at"],
                            },
                        }
                    )
            row["attention_points"] = active_points
            row["acknowledged_attention_points"] = acknowledged_points
        codes_by_severity = {"critical": set(), "high": set(), "medium": set()}
        codes_by_check = {"completion": set(), "tools": set(), "context_model": set()}
        attention_codes: set[str] = set()
        affected_runs: set[str] = set()
        occurrences = 0
        for row in visible_runs:
            points = row["attention_points"]
            for point in points:
                severity = str(point.get("severity") or "")
                check = str(point.get("check") or "")
                code = str(point.get("code") or "")
                occurrences += 1
                attention_codes.add(code)
                affected_runs.add(str(row["run_id"]))
                if severity in codes_by_severity:
                    codes_by_severity[severity].add(code)
                if check in codes_by_check:
                    codes_by_check[check].add(code)
        return {
            "format": "atmem-agent-blackbox-index-v2",
            "enabled": True,
            "host": state.host,
            "migration_id": state.migration_id,
            "raw_content_stored": False,
            "chain": chain,
            "total_runs": len(runs),
            "total_events": len(entries),
            "attention": {
                **{
                    name: len(codes)
                    for name, codes in {**codes_by_severity, **codes_by_check}.items()
                },
                "total": len(attention_codes),
                "occurrences": occurrences,
                "affected_runs": len(affected_runs),
                "healthy_runs": sum(
                    not row["attention_points"] for row in visible_runs
                ),
                "evaluated_runs": len(visible_runs),
            },
            "runs": visible_runs,
            "offset": page_offset,
            "has_more": page_offset + len(visible_runs) < len(runs),
        }

    def verify_blackbox_flight(self, run_id: str) -> dict[str, Any]:
        from atmem.control.blackbox import EVIDENCE_KIND, verify_flight

        state = self.state()
        store = self._store(state)
        try:
            entries = store.list_evidence(state.migration_id, kind=EVIDENCE_KIND)
            chain = store.verify_evidence_chain(
                state.migration_id, kind=EVIDENCE_KIND
            )
            acknowledgements = store.list_attention_acknowledgements(
                state.migration_id, run_id=run_id
            )
        finally:
            store.close()
        report = verify_flight(run_id=run_id, entries=entries, chain=chain)
        acknowledgement_keys = {
            (str(item["attention_code"]), str(item["attention_sha256"])): item
            for item in acknowledgements
        }
        active_points: list[dict[str, Any]] = []
        acknowledged_points: list[dict[str, Any]] = []
        for point in report.get("attention_points") or []:
            key = (
                str(point.get("code") or ""),
                sha256_hex(canonical_json(point)),
            )
            acknowledgement = acknowledgement_keys.get(key)
            if acknowledgement is None:
                active_points.append(point)
            else:
                acknowledged_points.append(
                    {
                        **point,
                        "acknowledgement": {
                            "id": acknowledgement["id"],
                            "actor": acknowledgement["actor"],
                            "created_at": acknowledgement["created_at"],
                        },
                    }
                )
        report["operator_review"] = {
            "active_attention_points": active_points,
            "acknowledged_attention_points": acknowledged_points,
        }
        return report

    def acknowledge_blackbox_attention(
        self,
        run_id: str,
        attention_code: str,
        *,
        actor: str = "dashboard-reviewer",
    ) -> dict[str, Any]:
        """Acknowledge the exact current finding without altering flight evidence."""

        report = self.verify_blackbox_flight(run_id)
        point = next(
            (
                item
                for item in (report.get("operator_review") or {}).get(
                    "active_attention_points", []
                )
                if str(item.get("code") or "") == attention_code
            ),
            None,
        )
        if point is None:
            raise ValueError("that attention item is not active for this flight")
        state = self.state()
        store = self._store(state)
        try:
            acknowledgement = store.acknowledge_attention(
                state.migration_id,
                run_id=run_id,
                attention_point=point,
                actor=actor,
            )
        finally:
            store.close()
        return {
            "acknowledged": True,
            "run_id": run_id,
            "attention_code": attention_code,
            "acknowledgement": {
                "id": acknowledgement["id"],
                "actor": acknowledgement["actor"],
                "created_at": acknowledgement["created_at"],
                "attention_sha256": acknowledgement["attention_sha256"],
            },
        }

    def blackbox_flight_story(
        self,
        run_id: str,
        *,
        trajectory_root: str | Path | None = None,
    ) -> dict[str, Any]:
        """Build a local, human-readable flight story without changing evidence."""

        report = self.verify_blackbox_flight(run_id)
        state = self.state()
        candidate_ids: list[str] = []
        duration_ms: int | None = None
        tool_names: list[str] = []
        usage: dict[str, Any] = {}
        for event in report.get("timeline") or []:
            payload = event.get("payload") or {}
            if event.get("event_type") == "context.disposition":
                candidate_ids.extend(str(value) for value in payload.get("candidate_ids") or [])
            if event.get("event_type") == "turn.ended" and payload.get("duration_ms") is not None:
                duration_ms = int(payload["duration_ms"])
            if event.get("event_type") == "tool.requested" and (
                payload.get("tool_canonical_name") or payload.get("tool_name")
            ):
                tool_names.append(
                    str(payload.get("tool_canonical_name") or payload["tool_name"])
                )
            if event.get("event_type") == "model.output":
                usage = dict(payload.get("usage") or {})
        candidate_ids = list(dict.fromkeys(candidate_ids))

        memories: list[dict[str, str]] = []
        if candidate_ids and state.host == "openclaw":
            from atmem.control.openclaw_native import mirror_status
            from atmem.memory import Memory

            status = mirror_status(state)
            mirror_db = status.get("mirror_db")
            if mirror_db:
                memory = Memory(mirror_db, retain_query_text=True)
                try:
                    records = memory.store.get_records(state.subject_id, candidate_ids)
                    memories = [
                        {
                            "record_id": record_id,
                            "content": str(records[record_id].get("content") or ""),
                        }
                        for record_id in candidate_ids
                        if record_id in records
                    ]
                finally:
                    memory.close()
        elif candidate_ids:
            store = self._store(state)
            try:
                rows = store.list_candidates(
                    state.migration_id,
                    subject_id=str(report.get("subject_id") or state.subject_id),
                )
            finally:
                store.close()
            by_id = {str(row["id"]): row for row in rows}
            memories = [
                {
                    "record_id": record_id,
                    "content": str(by_id[record_id].get("content") or ""),
                }
                for record_id in candidate_ids
                if record_id in by_id
            ]
            missing = [record_id for record_id in candidate_ids if record_id not in by_id]
            if missing:
                from atmem.memory import Memory

                memory = Memory(self._generic_memory_db(state), retain_query_text=False)
                try:
                    records = memory.store.get_records(
                        str(report.get("subject_id") or state.subject_id), missing
                    )
                    memories.extend(
                        {
                            "record_id": record_id,
                            "content": str(records[record_id].get("content") or ""),
                        }
                        for record_id in missing
                        if record_id in records
                    )
                finally:
                    memory.close()

        request_text: str | None = None
        response_text: str | None = None
        websites: list[str] = []
        recorded_cost: float | None = None
        local_failure: str | None = None
        local_provider: str | None = None
        local_model: str | None = None

        def collect_local_details(value: Any) -> None:
            nonlocal recorded_cost
            if isinstance(value, str):
                websites.extend(re.findall(r"https?://[^\s\]\[\"'<>]+", value))
                return
            if isinstance(value, list):
                for nested in value:
                    collect_local_details(nested)
                return
            if not isinstance(value, dict):
                return
            name = value.get("name") or value.get("toolName")
            kind = str(value.get("type") or "").casefold()
            if name and "tool" in kind:
                tool_names.append(str(name))
            cost = value.get("cost")
            if isinstance(cost, dict) and isinstance(cost.get("total"), (int, float)):
                if float(cost["total"]) > 0:
                    recorded_cost = float(cost["total"])
            for nested in value.values():
                collect_local_details(nested)
        session_id = str(report.get("session_id") or "")
        root = (
            Path(trajectory_root).expanduser().resolve(strict=False)
            if trajectory_root is not None
            else Path.home() / ".openclaw" / "agents"
        )
        if state.host == "openclaw" and session_id and root.is_dir():
            for path in sorted(root.glob(f"*/sessions/{session_id}.trajectory.jsonl")):
                try:
                    resolved = path.resolve(strict=True)
                    resolved.relative_to(root.resolve(strict=True))
                    if not resolved.is_file() or resolved.stat().st_size > 32 * 1024 * 1024:
                        continue
                    lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
                except (OSError, ValueError):
                    continue
                run_started_at: str | None = None
                run_ended_at: str | None = None
                for line in lines:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if str(event.get("runId") or "") != run_id:
                        continue
                    event_type = event.get("type")
                    data = event.get("data") or {}
                    if event_type == "session.started":
                        run_started_at = str(event.get("ts") or "") or None
                        local_provider = str(event.get("provider") or "") or None
                        local_model = str(event.get("modelId") or "") or None
                    if event_type == "session.ended":
                        run_ended_at = str(event.get("ts") or "") or None
                        local_failure = str(
                            data.get("promptError") or data.get("error") or ""
                        ) or None
                    if event_type != "model.completed":
                        continue
                    collect_local_details(data.get("messagesSnapshot") or [])
                    for message in data.get("messagesSnapshot") or []:
                        if message.get("role") == "user" and isinstance(message.get("content"), str):
                            request_text = message["content"][:20000]
                    assistant_texts = data.get("assistantTexts") or []
                    if assistant_texts:
                        response_text = "\n".join(str(value) for value in assistant_texts)[:20000]
                if duration_ms is None and run_started_at and run_ended_at:
                    try:
                        from datetime import datetime

                        started = datetime.fromisoformat(run_started_at.replace("Z", "+00:00"))
                        ended = datetime.fromisoformat(run_ended_at.replace("Z", "+00:00"))
                        duration_ms = max(0, int((ended - started).total_seconds() * 1000))
                    except ValueError:
                        pass
                if request_text is not None or response_text is not None:
                    break

            # Failed harness runs may not emit model.completed, but OpenClaw's
            # local session transcript still says what was requested and why
            # execution stopped.  This is display-only context, never appended
            # to the immutable Black Box evidence.
            if request_text is None or response_text is None or local_failure is None:
                for path in sorted(root.glob(f"*/sessions/{session_id}.jsonl")):
                    try:
                        resolved = path.resolve(strict=True)
                        resolved.relative_to(root.resolve(strict=True))
                        if not resolved.is_file() or resolved.stat().st_size > 32 * 1024 * 1024:
                            continue
                        transcript_lines = resolved.read_text(
                            encoding="utf-8", errors="replace"
                        ).splitlines()
                    except (OSError, ValueError):
                        continue
                    in_run = False
                    for line in transcript_lines:
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        message = row.get("message") or {}
                        role = message.get("role")
                        idempotency_key = str(message.get("idempotencyKey") or "")
                        if role == "user":
                            if in_run:
                                break
                            if idempotency_key != f"{run_id}:user":
                                continue
                            in_run = True
                            content = message.get("content")
                            if isinstance(content, str):
                                request_text = content[:20000]
                            continue
                        if not in_run:
                            continue
                        collect_local_details(message)
                        if role == "assistant" and response_text is None:
                            content = message.get("content")
                            if isinstance(content, str) and content.strip():
                                response_text = content[:20000]
                        if role == "toolResult" and message.get("isError"):
                            content = message.get("content")
                            rendered = json.dumps(content, ensure_ascii=False)
                            if "declined" in rendered.casefold():
                                local_failure = "OpenClaw declined the requested commands; no change was made."
                            elif local_failure is None:
                                local_failure = "OpenClaw reported a tool error."
                    if in_run:
                        break

        websites = list(dict.fromkeys(websites))
        tool_names = list(dict.fromkeys(tool_names))
        memory_text = "\n".join(row["content"] for row in memories)
        risks: list[str] = []
        if memories:
            risks.append(
                f"{len(memories)} memory record(s) were included in the request sent "
                f"to {((report.get('model') or {}).get('provider') or 'the model provider')}."
            )
        if re.search(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", memory_text):
            risks.append("The injected memory included an email address (personal data).")
        if websites:
            risks.append("The flight referenced external website addresses.")
        if tool_names:
            risks.append("Tools were invoked and may have interacted with systems outside the model.")
        lifecycle = report.get("lifecycle") or {}
        tool_errors = (report.get("tools") or {}).get("errors") or []
        blocked_by = lifecycle.get("reason") or local_failure
        if not blocked_by and tool_errors:
            blocked_by = "One or more tools returned an error."
        outcome_ids = (report.get("correlation") or {}).get("outcome_ids") or []

        return {
            "format": "atmem-local-flight-story-v1",
            "run_id": run_id,
            "request_text": request_text,
            "response_text": response_text,
            "memories": memories,
            "memory_count": len(candidate_ids),
            "tools": tool_names,
            "websites": websites,
            "provider": (report.get("model") or {}).get("provider") or local_provider,
            "model": (report.get("model") or {}).get("model") or local_model,
            "duration_ms": duration_ms,
            "usage": {
                "input_tokens": usage.get("input"),
                "output_tokens": usage.get("output"),
                "total_tokens": usage.get("total"),
                "recorded_cost_usd": recorded_cost,
            },
            "risks": risks,
            "compromise_assessment": (
                "No compromise was detected in the observed flight. This is not a "
                "security scan and does not prove that compromise was impossible."
            ),
            "blocked_by": blocked_by,
            "outcome_evidence": (
                f"{len(outcome_ids)} independently linked outcome receipt(s) were recorded."
                if outcome_ids
                else "No external real-world outcome was claimed or independently proven."
            ),
            "success": bool((report.get("lifecycle") or {}).get("success")),
            "source_note": (
                "Request and reply are read from the local OpenClaw transcript; "
                "memory text is read from the local AtMem mirror. Raw text is not "
                "added to the Black Box evidence or its exports."
                if state.host == "openclaw"
                else "Generic adapters retain digests and bounded metadata by default. "
                "Request and reply text is unavailable unless the host supplies a separate protected evidence reader."
            ),
        }

    def transition(
        self,
        mode: ControlMode | str,
        *,
        actor: str | None = None,
    ) -> ControlState:
        target = mode if isinstance(mode, ControlMode) else ControlMode(mode)
        with state_lock(self.state_path):
            state = load_state(self.state_path)
            if target is state.mode:
                return state
            if target not in _ALLOWED_TRANSITIONS[state.mode]:
                raise ValueError(
                    f"cannot move directly from {state.mode.value} to {target.value}"
                )
            evidence_store = self._store(state)
            try:
                mirror = None
                if state.host == "openclaw":
                    from atmem.control.openclaw_native import mirror_status

                    mirror = mirror_status(state)
                else:
                    mirror = self.memory_status()
                readiness = self._readiness(
                    state,
                    evidence_store.summary(state.migration_id),
                    mirror=mirror,
                )
                if target is ControlMode.ACTIVE and not readiness["ready_for_active"]:
                    raise ValueError("; ".join(readiness["reasons"]))
                now = utc_now()
                updated = replace(
                    state,
                    mode=target,
                    revision=state.revision + 1,
                    updated_at=now,
                    state_sha256="",
                )
                evidence_store.append_transition(
                    state.migration_id,
                    revision=updated.revision,
                    old_mode=state.mode.value,
                    new_mode=target.value,
                    actor=actor or _local_actor(),
                )
                return write_state(self.state_path, updated)
            finally:
                evidence_store.close()

    def activate(self, *, actor: str | None = None, progress: Any = None) -> dict[str, Any]:
        """Activate AtMem through the current adapter and return one shared receipt."""

        readiness = self.status().get("readiness") or {}
        if not readiness.get("ready_for_active"):
            raise ValueError("; ".join(readiness.get("reasons") or ["control plane is not ready"]))
        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import activate_takeover, restore_takeover

            takeover = activate_takeover(state, self.state_path, progress=progress)
            try:
                state = self.transition(ControlMode.ACTIVE, actor=actor)
            except Exception:
                restore_takeover(state)
                raise
        else:
            state = self.transition(ControlMode.ACTIVE, actor=actor)
            takeover = {
                "activated": True,
                "host": state.host,
                "native_memory_replaced": False,
                "boundary": "The host must inject only context returned with inject=true.",
            }
        return {
            **state.public_status(),
            "takeover": takeover,
            "mirror": self.memory_status(),
        }

    def deactivate(self, *, actor: str | None = None, progress: Any = None) -> dict[str, Any]:
        """Stop context influence while preserving shadow capture and evidence."""

        state = self.state()
        if state.host == "openclaw":
            from atmem.control.openclaw_native import restore_takeover

            restored = restore_takeover(state, progress=progress)
            if state.mode is not ControlMode.OFF:
                state = self.transition(ControlMode.OFF, actor=actor or "restore")
            return {
                **state.public_status(),
                "restored": bool(restored.get("valid")),
                "takeover": restored,
                "restore_boundary": (
                    "The saved OpenClaw configuration was restored. Evidence and past outputs are preserved."
                ),
            }
        if state.mode is ControlMode.ACTIVE:
            state = self.transition(ControlMode.SHADOW, actor=actor or "return-to-shadow")
        return {
            **state.public_status(),
            "restored": True,
            "takeover": {
                "activated": False,
                "host": state.host,
                "native_memory_replaced": False,
            },
            "restore_boundary": (
                "AtMem returned to shadow mode. Capture and evidence continue, but prepare never authorizes injection."
            ),
        }

    def _readiness(
        self,
        state: ControlState,
        evidence: dict[str, Any],
        *,
        mirror: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        counts = evidence["candidates"]
        approved = int(counts.get("approved", 0))
        chain_valid = bool(evidence["transition_chain"]["valid"])
        mirror_ready = bool(
            mirror
            and mirror.get("synced")
            and mirror.get("audit_verified")
        )
        reasons: list[str] = []
        if not chain_valid:
            reasons.append("migration transition evidence did not verify")
        if approved < 1 and not mirror_ready:
            reasons.append("mirror native memory or approve at least one candidate")
        ready_for_active = chain_valid and (approved > 0 or mirror_ready)
        return {
            "ready_for_active": ready_for_active,
            "mirror_ready": mirror_ready,
            "reasons": reasons,
        }

    def _store(self, state: ControlState) -> ControlStore:
        control_dir = Path(state.control_dir)
        return ControlStore(
            control_dir / "evidence.db",
            policy=HouseholdPolicy.load(control_dir / "openclaw-mirror.db"),
        )

    @staticmethod
    def _no_context(state: ControlState, reason: str) -> dict[str, Any]:
        return {
            "mode": ControlMode.OFF.value
            if state.migration_id == "unavailable"
            else state.mode.value,
            "preview_id": None,
            "manifest_sha256": None,
            "candidate_ids": [],
            "context": "",
            "preview_context": "",
            "inject": False,
            "exposure_id": None,
            "reason": reason,
        }


def _local_actor() -> str:
    try:
        return f"local-user:{getpass.getuser()}"
    except Exception:  # pragma: no cover - defensive platform fallback
        return "local-user"
