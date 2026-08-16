from __future__ import annotations

from dataclasses import replace
import getpass
import json
from pathlib import Path
import re
from typing import Any
import uuid

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.core.storage import HouseholdPolicy
from atmem.extract.rules import extract_facts
from atmem.retrieve.rank import rank_records
from atmem.store.sqlite import utc_now
from atmem.control.models import ControlMode, ControlState
from atmem.control.state import load_effective_state, load_state, state_lock, write_state
from atmem.control.store import ControlStore


DEFAULT_CONTROL_ROOT = Path.home() / ".atmem" / "migrations"
DEFAULT_STATE_PATH = Path.home() / ".atmem" / "control-plane.json"
DEFAULT_SUBJECT = "local-user"

_ALLOWED_TRANSITIONS: dict[ControlMode, frozenset[ControlMode]] = {
    ControlMode.OFF: frozenset({ControlMode.SHADOW, ControlMode.ACTIVE}),
    ControlMode.SHADOW: frozenset({ControlMode.ACTIVE, ControlMode.OFF}),
    ControlMode.ACTIVE: frozenset({ControlMode.OFF}),
}


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
    ) -> "ControlPlaneManager":
        manager, _resumed = cls._start(
            host=host,
            state_path=state_path,
            control_root=control_root,
            subject_id=subject_id,
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
    ) -> tuple["ControlPlaneManager", bool]:
        """Start a migration or reuse the same host's existing shadow safely."""

        return cls._start(
            host=host,
            state_path=state_path,
            control_root=control_root,
            subject_id=subject_id,
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
        resume_shadow: bool,
    ) -> tuple["ControlPlaneManager", bool]:
        if host != "openclaw":
            raise ValueError("the verified host adapter in this release is openclaw")
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
        return manager, False

    def effective_state(self) -> tuple[ControlState, str | None]:
        return load_effective_state(self.state_path)

    def state(self) -> ControlState:
        return load_state(self.state_path)

    def status(self) -> dict[str, Any]:
        state, warning = self.effective_state()
        result = state.public_status(warning=warning)
        if warning or state.migration_id == "unavailable":
            result["evidence"] = None
            result["readiness"] = {
                "ready_for_active": False,
                "reasons": ["state is missing or invalid; integration is fail-closed"],
            }
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

            mirror = mirror_status(state)
            takeover = takeover_status(state)
        result["evidence"] = evidence
        result["restore_drill"] = (
            latest_restore_drill["body"] if latest_restore_drill else None
        )
        result["verification"] = (
            latest_verification["body"] if latest_verification else None
        )
        result["mirror"] = mirror
        result["takeover"] = takeover
        result["readiness"] = self._readiness(state, evidence, mirror=mirror)
        return result

    def capture(
        self,
        message: str,
        *,
        session_id: str | None = None,
        authenticated_user: bool,
    ) -> dict[str, Any]:
        state, warning = self.effective_state()
        if warning or not state.mode.captures:
            return {"captured": 0, "candidate_ids": [], "reason": "migration is off"}
        if not authenticated_user:
            return {
                "captured": 0,
                "candidate_ids": [],
                "reason": "only authenticated user messages are eligible",
            }
        facts = extract_facts(message, source_type="user_message")
        store = self._store(state)
        created: list[str] = []
        duplicates: list[str] = []
        try:
            for fact in facts:
                row, duplicate = store.insert_candidate(
                    state.migration_id,
                    content=fact.content,
                    fact_key=fact.fact_key,
                    confidence=fact.confidence,
                    source_type=fact.source_type,
                    trust_tier=fact.trust_tier,
                    source_message_sha256=sha256_hex(message),
                    source_session_id=session_id,
                )
                (duplicates if duplicate else created).append(str(row["id"]))
        finally:
            store.close()
        return {
            "captured": len(created),
            "candidate_ids": created,
            "duplicate_ids": duplicates,
            "raw_message_stored": False,
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
            return store.review_candidates(
                state.migration_id, candidate_ids, approve=approve
            )
        finally:
            store.close()

    def prepare(
        self,
        query: str,
        *,
        session_id: str | None = None,
        host_run_id: str | None = None,
        limit: int = 3,
        max_chars: int = 1200,
        min_score: float = 0.3,
    ) -> dict[str, Any]:
        state, warning = self.effective_state()
        if warning or not state.mode.captures:
            return self._no_context(state, warning or "migration is off")
        store = self._store(state)
        try:
            approved = store.list_candidates(
                state.migration_id, statuses=("approved",)
            )
            ranked = rank_records(query, approved)
            candidate_chosen = [
                item
                for item in ranked
                if item.text_score > 0 and item.score >= min_score
            ][: max(0, limit)]
            mirror_records: list[dict[str, Any]] = []
            if state.host == "openclaw":
                from atmem.control.openclaw_native import search_mirror

                try:
                    mirror_records = list(
                        search_mirror(state, query, limit=limit).get("records") or []
                    )
                except ValueError:
                    mirror_records = []
            lines: list[str] = []
            candidate_ids: list[str] = []
            candidate_hashes: list[str] = []
            used_chars = 0
            chosen_rows = [
                (
                    str(item.record["id"]),
                    str(item.record["content"]),
                    str(item.record["content_sha256"]),
                )
                for item in candidate_chosen
            ]
            chosen_rows.extend(
                (
                    str(record["id"]),
                    str(record.get("content") or ""),
                    sha256_hex(str(record.get("content") or "")),
                )
                for record in mirror_records
            )
            seen: set[str] = set()
            for record_id, value, content_sha256 in chosen_rows:
                content = value.strip()
                normalized = content.casefold()
                if not content or normalized in seen:
                    continue
                seen.add(normalized)
                line = f"- {content}"
                if used_chars + len(line) + 1 > max_chars:
                    break
                lines.append(line)
                candidate_ids.append(record_id)
                candidate_hashes.append(content_sha256)
                used_chars += len(line) + 1
            context = (
                "<atmem_control_plane>\n"
                + "\n".join(lines)
                + "\n</atmem_control_plane>"
                if lines
                else ""
            )
            turn = store.insert_turn(
                state.migration_id,
                query_sha256=sha256_hex(query),
                session_id=session_id,
                host_run_id=host_run_id,
            )
            manifest = {
                "format": "atmem-control-context-v1",
                "migration_id": state.migration_id,
                "state_revision": state.revision,
                "mode": state.mode.value,
                "query_sha256": sha256_hex(query),
                "candidate_ids": candidate_ids,
                "candidate_content_sha256": candidate_hashes,
                "context_sha256": sha256_hex(context),
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
                "mode": state.mode.value,
                "turn_id": turn["id"],
                "preview_id": preview["id"],
                "context_receipt_id": preview["id"],
                "manifest_sha256": preview["manifest_sha256"],
                "candidate_ids": candidate_ids,
                "context": context if inject else "",
                "preview_context": context,
                "inject": inject,
                "exposure_id": exposure["id"] if exposure else None,
                "reason": reason,
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
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append one content-minimizing host observation to the flight chain."""

        from atmem.control.blackbox import EVIDENCE_KIND, normalize_event

        state, warning = self.effective_state()
        if warning or state.migration_id == "unavailable":
            raise ValueError("blackbox recording requires a valid control state")
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

    def blackbox_runs(self, *, limit: int = 50) -> dict[str, Any]:
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
        visible_runs = runs[: max(0, min(int(limit), 500))]
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

        request_text: str | None = None
        response_text: str | None = None
        websites: list[str] = []
        recorded_cost: float | None = None

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
        if session_id and root.is_dir():
            for path in sorted(root.glob(f"*/sessions/{session_id}.trajectory.jsonl")):
                try:
                    resolved = path.resolve(strict=True)
                    resolved.relative_to(root.resolve(strict=True))
                    if not resolved.is_file() or resolved.stat().st_size > 32 * 1024 * 1024:
                        continue
                    lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
                except (OSError, ValueError):
                    continue
                for line in lines:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if str(event.get("runId") or "") != run_id:
                        continue
                    if event.get("type") != "model.completed":
                        continue
                    data = event.get("data") or {}
                    collect_local_details(data.get("messagesSnapshot") or [])
                    for message in data.get("messagesSnapshot") or []:
                        if message.get("role") == "user" and isinstance(message.get("content"), str):
                            request_text = message["content"][:20000]
                    assistant_texts = data.get("assistantTexts") or []
                    if assistant_texts:
                        response_text = "\n".join(str(value) for value in assistant_texts)[:20000]
                if request_text is not None or response_text is not None:
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
        blocked_by = lifecycle.get("reason")
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
            "provider": (report.get("model") or {}).get("provider"),
            "model": (report.get("model") or {}).get("model"),
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
