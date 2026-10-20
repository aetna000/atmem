"""Exact, state-bound project clearing through canonical deletion methods."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets

from atmem.code.application import CodeApplication, digest


class CodeDeletion:
    def __init__(self, application: CodeApplication) -> None:
        self.app = application

    def _selection(self, project: str, profile: str | None, agent: str | None) -> dict:
        # Do not silently clear only the first page of a large selection.
        all_records = []
        for lane in self.app.lanes(project, profile=profile):
            for row in self.app.memory.list(lane["derived_subject_id"], include_inactive=True):
                raw = self.app.store.code_document(self.app.subject_id, project, "origin", row["id"]) or row.get("raw") or {}
                if agent is None or (raw.get("code_agent_id") or lane["agent_id"]) == agent:
                    if row["status"] != "tombstoned":
                        all_records.append({"id": row["id"], "subject_id": lane["derived_subject_id"], "sha256": digest(row)})
        observations = [dict(row) for row in self.app.store._conn.execute(
            "SELECT * FROM code_observations WHERE subject_id=? AND project_id=? ORDER BY event_id",
            (self.app.subject_id, project),
        ).fetchall() if (profile is None or row["profile_id"] == profile) and (agent is None or row["agent_id"] == agent)]
        knowledge = []
        for kind in ("knowledge-generation", "knowledge-job", "code-experience", "execution-receipt", "experience-environment"):
            for item in self.app.store.code_document_items(self.app.subject_id, project, kind):
                scope = item["value"].get("scope", {})
                if (profile is None or scope.get("profile_id") == profile) and (agent is None or scope.get("agent_id") == agent):
                    knowledge.append({"kind": kind, "id": item["document_id"], "sha256": digest(item["value"])})
        return {"records": sorted(all_records, key=lambda row: row["id"]),
                "observations": [{"id": row["event_id"], "sha256": digest(row)} for row in observations],
                "knowledge": knowledge,
                "profile": profile, "agent": agent}

    def preview(self, project: str, *, profile: str | None = None, agent: str | None = None) -> dict:
        self.app.authorize(project)
        with self.app.store.transaction():
            selection = self._selection(project, profile, agent)
            token = secrets.token_urlsafe(32)
            value = {"selection": selection, "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}
            self.app.store.put_code_document(self.app.subject_id, project, "clear-preview", digest(token), value)
        return {"preview_token": token, "record_count": len(selection["records"]),
                "knowledge_document_count": len(selection["knowledge"]),
                "observation_count": len(selection["observations"]), "selection_sha256": digest(selection),
                "project_id": project, "profile": profile, "agent": agent,
                "external_providers": "provider data is not deleted by local clear"}

    def clear(self, project: str, token: str) -> dict:
        self.app.authorize(project)
        with self.app.store.transaction():
            preview = self.app.store.code_document(self.app.subject_id, project, "clear-preview", digest(token))
            if preview is None or datetime.fromisoformat(preview["expires_at"]) < datetime.now(timezone.utc):
                raise ValueError("clear preview is missing or expired")
            selected = preview["selection"]
            if self._selection(project, selected["profile"], selected["agent"]) != selected:
                raise ValueError("memory changed since preview; preview again")
            receipts = [self.app.forget(project, row["id"])["receipt"] for row in selected["records"]]
            for document in selected["knowledge"]:
                self.app.store.delete_code_documents(self.app.subject_id, project, document["kind"], document["id"])
            for row in selected["observations"]:
                self.app.store._conn.execute("DELETE FROM code_observations WHERE event_id=? AND subject_id=? AND project_id=?",
                                             (row["id"], self.app.subject_id, project))
            record_ids = {row["id"] for row in selected["records"]}
            event_ids = {row["id"] for row in selected["observations"]}
            def matches(scope):
                return (selected["profile"] is None or scope.get("profile_id") == selected["profile"]) and (
                    selected["agent"] is None or scope.get("agent_id") == selected["agent"])
            # Delete only affected derived copies. Adjacent private lanes keep
            # their own context history and caches.
            for kind in ("exposure", "turn-result", "provider-receipt", "review", "hook-event", 'curation-exposure'):
                for item in self.app.store.code_document_items(self.app.subject_id, project, kind):
                    document = item["value"]
                    exposure = document.get("exposure", document)
                    scope = exposure.get("request", {}).get("scope", document.get("scope", {}))
                    package = document.get("context", exposure.get("package", {}))
                    affected = bool(record_ids.intersection(package.get("memory_ids", [])))
                    affected = affected or item["document_id"] in event_ids
                    affected = affected or bool(scope and matches(scope))
                    affected = affected or selected["profile"] is None and selected["agent"] is None
                    if affected:
                        self.app.store.delete_code_documents(self.app.subject_id, project, kind, item["document_id"])
            if selected["profile"] is None and selected["agent"] is None:
                self.app.store.delete_code_documents(self.app.subject_id, project, "graph")
            self.app.store.delete_code_documents(self.app.subject_id, project, "clear-preview", digest(token))
            remaining = self._selection(project, selected["profile"], selected["agent"])
            verified = not remaining["records"] and not remaining["observations"] and not remaining["knowledge"]
            self.app.store.append_audit_event(subject_id=self.app.subject_id, event_type="code.cleared", actor="user",
                                              payload={"project_id": project, "selection_sha256": digest(selected), "verified": verified})
        routes = self.app.store.code_documents(self.app.subject_id, project, "route")
        return {"deleted_count": len(receipts), "local_verified": verified, "receipts": receipts,
                "external_status": "not_requested" if routes else "not_applicable",
                "complete": verified and not routes}
