"""One authorized application boundary for Code CLI, hooks and dashboard."""

from __future__ import annotations

from hashlib import sha256
from copy import deepcopy
from functools import wraps
from datetime import datetime
from typing import Any

from atmem.code.contracts import CodeScope, _id
from atmem.code.formation import memory_subject_id
from atmem.core.canonical import canonical_json
from atmem.extract.validation import screen_content
from atmem.memory import Memory


DEFAULT_SETTINGS = {
    "auto_capture": True, "auto_recall": True, "review_workflow": False,
    "max_context_bytes": 4096, "graph_enabled": False,
    "context_tags": [],
    "context_mode": "content", "index_limit": 3, "index_bytes": 1024,
}
CURATION_SETTINGS = {'context_mode', 'index_limit', 'index_bytes'}


def _transaction(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.store.transaction():
            return method(self, *args, **kwargs)
    return wrapped


class CodeApplication:
    def __init__(self, memory: Memory, *, subject_id: str) -> None:
        _id("subject_id", subject_id)
        if memory.store.path != ":memory:" and memory.store.policy.state != "encrypted":
            raise RuntimeError("Code memory requires encrypted AtMem storage")
        self.memory = memory
        self.store = memory.store
        self.subject_id = subject_id

    def authorize(self, project_id: str) -> None:
        _id("project_id", project_id)
        if not self.store.code_project_exists(self.subject_id, project_id):
            raise PermissionError("project is not owned by this subject")

    def projects(self) -> dict:
        projects = self.store.code_projects(self.subject_id)
        return {"projects": projects, "details": [{"project_id": project, **(self.store.code_document(
            self.subject_id, project, "project-info", "info") or {"name": project})} for project in projects]}

    @_transaction
    def settings(self, project_id: str, changes: dict[str, Any] | None = None) -> dict:
        self.authorize(project_id)
        stored = self.store.code_document(self.subject_id, project_id, 'settings', 'effective') or {}
        current = {**deepcopy(DEFAULT_SETTINGS), **stored}
        if changes is not None:
            if not isinstance(changes, dict) or set(changes) - set(DEFAULT_SETTINGS):
                raise ValueError("unknown Code setting")
            for key, value in changes.items():
                if key == "context_tags":
                    if not isinstance(value, list) or len(value) > 32 or any(not isinstance(item, str) for item in value) or len(set(value)) != len(value):
                        raise ValueError("context_tags must be a bounded unique list")
                    for tag in value:
                        _id("context tag", tag)
                elif key == "max_context_bytes":
                    if type(value) is not int or not 256 <= value <= 32768:
                        raise ValueError("max_context_bytes must be between 256 and 32768")
                elif key == 'context_mode':
                    if value not in ('index', 'content'):
                        raise ValueError('context_mode must be index or content')
                elif key in {'index_limit', 'index_bytes'}:
                    minimum, maximum = (1, 8) if key == 'index_limit' else (256, 4096)
                    if type(value) is not int or not minimum <= value <= maximum:
                        raise ValueError('invalid Code index bound')
                elif type(value) is not bool:
                    raise ValueError(f"{key} must be boolean")
            current.update(changes)
            # Editing a legacy boolean setting must not silently migrate its
            # persisted/export format to the curation configuration contract.
            persisted = (current if CURATION_SETTINGS.intersection(stored) or CURATION_SETTINGS.intersection(changes)
                         else {key: value for key, value in current.items() if key not in CURATION_SETTINGS})
            self.store.put_code_document(self.subject_id, project_id, "settings", "effective", persisted)
            self.store.append_audit_event(subject_id=self.subject_id, event_type="code.settings_changed", actor="user",
                                          payload={"project_id": project_id, "changes": changes})
        return current

    def lanes(self, project_id: str, *, profile: str | None = None) -> list[dict]:
        self.authorize(project_id)
        if profile is not None:
            _id("profile", profile)
        return [row for row in self.store.code_scopes(self.subject_id, project_id)
                if profile is None or row["profile_id"] == profile]

    def records(self, project_id: str, *, query: str = "", profile: str | None = None,
                agent: str | None = None, status: str | None = "active",
                memory_class: str | None = None, source: str | None = None,
                after: str | None = None, before: str | None = None, limit: int = 100) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if agent is not None:
            _id("agent", agent)
        from atmem.code.contracts import _timestamp
        after_time = datetime.fromisoformat(_timestamp(after).replace("Z", "+00:00")) if after else None
        before_time = datetime.fromisoformat(_timestamp(before).replace("Z", "+00:00")) if before else None
        result = []
        for lane in self.lanes(project_id, profile=profile):
            rows = (self.memory.recall(lane["derived_subject_id"], query, limit=limit, use_graph=False)
                    if query else self.memory.list(lane["derived_subject_id"], include_inactive=True))
            for record in rows:
                raw = record.get("raw") or {}
                origin = self.store.code_document(self.subject_id, project_id, "origin", record["id"]) or raw
                record_agent = origin.get("code_agent_id") or lane["agent_id"]
                if agent is not None and record_agent != agent:
                    continue
                if status is not None and record["status"] != status:
                    continue
                if memory_class is not None and origin.get("code_memory_class") != memory_class:
                    continue
                if source is not None and source not in str(origin.get("code_source_ref") or ""):
                    continue
                created = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
                if after_time and created < after_time or before_time and created > before_time:
                    continue
                from atmem.memory import _screenable_metadata
                if any(not screen_content(value, trusted=True).admissible for value in _screenable_metadata(record)):
                    continue
                result.append({**record, "project_id": project_id, "profile_id": lane["profile_id"],
                               "agent_id": record_agent, "code_source": origin})
        return result[:limit]

    def exact(self, project_id: str, record_id: str) -> tuple[dict, dict]:
        _id("record_id", record_id)
        for lane in self.lanes(project_id):
            record = self.store.get_record(lane["derived_subject_id"], record_id)
            if record is not None:
                return lane, record
        raise PermissionError("record is not in the authorized project")

    def inspect(self, project_id: str, record_id: str) -> dict:
        lane, record = self.exact(project_id, record_id)
        if not screen_content(record["content"], trusted=True).admissible:
            raise PermissionError("record content is withheld by secret screening")
        self.store.append_audit_event(subject_id=self.subject_id, event_type="code.record_inspected", actor="user",
                                      payload={"project_id": project_id, "record_id": record_id})
        episode = self.store.get_episode(lane["derived_subject_id"], record["episode_id"]) if record.get("episode_id") else None
        from atmem.memory import _screenable_metadata
        if episode and any(not screen_content(value, trusted=True).admissible for value in _screenable_metadata(episode)):
            raise PermissionError("source contains protected secret material")
        result = {"record": record, "source": episode, "scope": lane}
        origin = self.store.code_document(self.subject_id, project_id, "origin", record_id) or {}
        if origin.get("experience_proposal_id"):
            value = self.store.code_document(self.subject_id, project_id, "code-experience", origin["experience_proposal_id"])
            if value:
                result["experience"] = {"proposal": value["proposal"], "formation": value["formation"],
                                        "snapshot": value["snapshot"], "receipt_ids": value["receipt_ids"],
                                        "outcome_assurance": "authenticated_producer_report_not_independent_verification"}
        return result

    def correct(self, project_id: str, record_id: str, text: str) -> dict:
        lane, old = self.exact(project_id, record_id)
        with self.store.transaction():
            result = self.memory.correct_record(lane["derived_subject_id"], record_id, text, actor="user")
            origin = self.store.code_document(self.subject_id, project_id, "origin", record_id) or old.get("raw") or {}
            self.store.put_code_document(self.subject_id, project_id, "origin", result["record"]["id"], origin)
        return result

    def forget(self, project_id: str, record_id: str) -> dict:
        lane, _ = self.exact(project_id, record_id)
        with self.store.transaction():
            origin = self.store.code_document(self.subject_id, project_id, "origin", record_id) or {}
            result = self.memory.forget_record(lane["derived_subject_id"], record_id, actor="user")
            if origin.get("experience_proposal_id"):
                proposal_id = origin["experience_proposal_id"]
                self.store.put_code_document(self.subject_id, project_id, "experience-tombstone", proposal_id,
                                             {"scope": CodeScope(self.subject_id, project_id, lane["profile_id"], lane["agent_id"]).to_dict(),
                                              "proposal_id": proposal_id, "reason": "owner_forget"})
                value = self.store.code_document(self.subject_id, project_id, "code-experience", proposal_id)
                if value:
                    for receipt_id in value.get("receipt_ids", []):
                        # Receipts may support another experience; preserve only
                        # those still referenced in that same authorized project.
                        others = self.store.code_documents(self.subject_id, project_id, "code-experience")
                        if not any(d.get("proposal", {}).get("proposal_id") != proposal_id and receipt_id in d.get("receipt_ids", []) for d in others):
                            self.store.delete_code_documents(self.subject_id, project_id, "execution-receipt", receipt_id)
                    self.store.delete_code_documents(self.subject_id, project_id, "code-experience", proposal_id)
            self.store.delete_code_documents(self.subject_id, project_id, "origin", record_id)
            # New curation projections are retained evidence, not an independent
            # memory authority. Forget removes their copies of this record too.
            for item in self.store.code_document_items(self.subject_id, project_id, 'curation-exposure'):
                value = item['value']
                rows = value.get('response', {}).get('items', []) + value.get('delivered_response', {}).get('items', [])
                if any(row.get('id') == 'exp:' + record_id for row in rows):
                    self.store.delete_code_documents(self.subject_id, project_id, 'curation-exposure', item['document_id'])
        return result

    def dispatch(self, action: str, body: dict[str, Any]) -> dict:
        """Identical command handling for authenticated CLI and dashboard callers."""
        project = str(body.get("project_id") or "")
        if action == "projects":
            return self.projects()
        if action == "project-add":
            from atmem.code.install import CodeInstall
            return CodeInstall(self.store).setup(str(body.get("root") or ""), subject_id=self.subject_id,
                                                 profile_id=str(body.get("profile") or "shared"),
                                                 agent_id=str(body.get("agent") or body.get("host") or "codex"), host=str(body.get("host") or "codex"),
                                                 apply=bool(body.get("apply", False)))
        if action == "bundle-keys":
            from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
            import base64
            recipient_public, recipient_secret = generate_recipient_keypair()
            signing_public, signing_secret = generate_signing_keypair()
            return {name: base64.b64encode(value).decode() for name, value in zip(
                ("recipient.public", "recipient.secret", "signing.public", "signing.secret"),
                (recipient_public, recipient_secret, signing_public, signing_secret))}
        if action in {"bundle-preview", "bundle-import"}:
            from atmem.code.portable import CodePortable
            import base64
            portable = CodePortable(self)
            value = portable.open(body["bundle"], recipient_secret_key=base64.b64decode(body["recipient_secret_key"], validate=True),
                                  trusted_signing_public_key=base64.b64decode(body["trusted_signing_key"], validate=True))
            return (portable.preview(value, root=body["root"]) if action == "bundle-preview" else
                    portable.restore(value, root=body["root"], preview_token=body["preview_token"]))
        self.authorize(project)
        if action == 'experience-evidence':
            from atmem.code.experience_view import execution_evidence
            return execution_evidence(self, project, body.get('record_id'), body.get('receipt_id'))
        if action in {'discover', 'fetch', 'changes', 'curation-capabilities'}:
            from atmem.code.curation import Curation
            scope = CodeScope(self.subject_id, project, body.get('profile') or 'shared', body.get('agent') or 'codex')
            service = Curation(self, scope, str(body.get('root') or ''))
            return service.prepare('capabilities' if action == 'curation-capabilities' else action, body.get('arguments', {}))
        if action == "project-attach":
            from atmem.code.identity import CodeIdentity
            scope = CodeIdentity(self.store).resolve(str(body.get("root") or ""), subject_id=self.subject_id,
                profile_id=str(body.get("profile") or "shared"), agent_id=str(body.get("agent") or "codex"),
                rebind_project_id=project, confirm_remote_change=bool(body.get("confirm_remote_change", False)))
            return {"attached": True, "scope": scope.to_dict()}
        if action == "bundle-export":
            from atmem.code.portable import CodePortable
            import base64
            return {"bundle": CodePortable(self).export(project,
                recipient_public_key=base64.b64decode(body["recipient_public_key"], validate=True),
                signing_public_key=base64.b64decode(body["signing_public_key"], validate=True),
                signing_secret_key=base64.b64decode(body["signing_secret_key"], validate=True))}
        if action == "hosts":
            rows = self.store._conn.execute(
                "SELECT host,enabled FROM code_installations WHERE subject_id=? AND project_id=? ORDER BY host",
                (self.subject_id, project),
            ).fetchall()
            return {"hosts": [{"host": row["host"], "enabled": bool(row["enabled"])} for row in rows]}
        if action.startswith("host-"):
            from atmem.code.install import CodeInstall
            from atmem.code.identity import repository_key
            root = str(body.get("root") or "")
            binding = self.store.code_project_binding(self.subject_id, repository_key(root))
            if binding is None or binding["project_id"] != project:
                raise PermissionError("host root does not match selected project")
            operation = action.removeprefix("host-")
            if operation not in {"enable", "disable", "uninstall", "status"}:
                raise ValueError("unsupported host operation")
            return getattr(CodeInstall(self.store), operation)(project=root, subject_id=self.subject_id, host=str(body.get("host") or ""))
        if action == "search":
            keys = {"query", "profile", "agent", "status", "memory_class", "source", "after", "before", "limit"}
            return {"records": self.records(project, **{key: body[key] for key in keys if key in body})}
        if action == "inspect":
            return self.inspect(project, str(body.get("record_id") or ""))
        if action == "correct":
            return self.correct(project, str(body.get("record_id") or ""), str(body.get("text") or ""))
        if action == "forget":
            return self.forget(project, str(body.get("record_id") or ""))
        if action == "config":
            return {"settings": self.settings(project, body.get("changes"))}
        if action == "reviews":
            return {"reviews": self.store.code_documents(self.subject_id, project, "review")}
        if action == "review":
            from atmem.code.contracts import CodeObservation
            from atmem.code.formation import CodeFormation
            event_id = str(body.get("event_id") or "")
            value = self.store.code_document(self.subject_id, project, "review", event_id)
            if value is None or body.get("decision") not in {"approve", "reject"}:
                raise ValueError("review or decision is invalid")
            observation = CodeObservation.from_dict(value)
            with self.store.transaction():
                result = (CodeFormation(self.memory).form(observation) if body["decision"] == "approve" else {"formed": False})
                self.store.set_code_observation_state(event_id, "formed" if result["formed"] else "refused")
                self.store.delete_code_documents(self.subject_id, project, "review", event_id)
                self.store.append_audit_event(subject_id=self.subject_id, event_type="code.review_decided", actor="user",
                                              payload={"project_id": project, "event_id": event_id, "decision": body["decision"]})
            return result
        if action == "context":
            from atmem.code.contracts import CodeContextRequest
            from atmem.code.providers import CodeRouter
            request = CodeContextRequest.from_dict(body["request"])
            if request.scope.project_id != project:
                raise PermissionError("context project binding mismatch")
            result = CodeRouter(self).prepare(request, tags=tuple(body.get("tags", [])))
            return {**result, "package": result["package"].to_dict()}
        if action in {"clear-preview", "clear"}:
            from atmem.code.deletion import CodeDeletion
            service = CodeDeletion(self)
            return (service.preview(project, profile=body.get("profile"), agent=body.get("agent"))
                    if action == "clear-preview" else service.clear(project, str(body.get("preview_token") or "")))
        if action in {"routes", "route-set", "route-delete"}:
            from atmem.code.providers import CodeRouter
            return CodeRouter(self).configure(action, project, body)
        if action in {"graph-index", "graph-search", "graph-status"}:
            from atmem.code.graph import CodeGraph
            graph = CodeGraph(self, project)
            if action == "graph-index":
                return graph.index(str(body.get("root") or ""))
            return graph.query(str(body.get("root") or ""), str(body.get("query") or ""), limit=int(body.get("limit", 20)))
        if action in {"knowledge-config", "mcp-config", "experiences"}:
            scope = CodeScope(self.subject_id, project, str(body.get("profile") or "shared"), str(body.get("agent") or "codex"))
            root = str(body.get("root") or "")
            if action == "experiences":
                from atmem.code.experience_view import experiences
                return experiences(self, scope, root, query=body.get("query", ""),
                                   limit=body.get("limit", 20), offset=body.get("offset", 0))
            from atmem.code.knowledge_setup import configure, mcp_configuration
            return (configure(self, scope, root, image_id=body.get("image_id")) if action == "knowledge-config"
                    else mcp_configuration(self, scope, root, tool_profile=body.get('tool_profile', 'expanded')))
        if action in {"knowledge-index", "knowledge-query", "knowledge-status", "knowledge-source"}:
            from atmem.knowledge.projections import CodeKnowledge
            from atmem.knowledge.code.queries import query_current
            scope = CodeScope(self.subject_id, project, str(body.get("profile") or "shared"), str(body.get("agent") or "codex"))
            knowledge = CodeKnowledge(self, scope)
            root = str(body.get("root") or "")
            if action == "knowledge-index":
                from atmem.knowledge.worker import ExtractionWorker
                approved = self.store.code_document(self.subject_id, project, "knowledge-runtime", "approved") or {}
                image_id = body.get("image_id") or approved.get("image_id")
                if not image_id:
                    raise ValueError("configure a local extractor with knowledge-config --image-id first")
                return knowledge.index(root, ExtractionWorker(image_id))
            if action == "knowledge-query":
                result = query_current(knowledge, root, operation=body.get("operation", "query_facts"),
                                       query=body.get("query", ""), config=body.get("options"))
            elif action == "knowledge-source":
                from atmem.knowledge.contracts import source_path
                import base64
                generation = knowledge.current(root)
                if generation is None:
                    return {"status": "not_current"}
                name = source_path(body.get("path"))
                if name not in generation["source_bytes"]:
                    raise PermissionError("source is not in the current authorized generation")
                start, count = body.get("start_line", 1), body.get("line_count", 30)
                if type(start) is not int or start < 1 or type(count) is not int or not 1 <= count <= 100:
                    raise ValueError("invalid source excerpt range")
                from atmem.knowledge.source_text import source_text
                lines = source_text(name, base64.b64decode(generation["source_bytes"][name], validate=True)).splitlines()
                excerpt = "\n".join(lines[start - 1:start - 1 + count])
                if len(excerpt.encode()) > 8192:
                    raise ValueError("source excerpt exceeds byte budget")
                result = {"status": "current", "path": name, "start_line": start, "content": excerpt,
                          "snapshot_id": generation["snapshot_id"], "source_sha256": dict(generation["snapshot"]["files"])[name]}
                latest = knowledge.current(root)
                if latest is None or latest["snapshot_id"] != generation["snapshot_id"]:
                    return {"status": "withheld", "reason": "source_changed_during_inspection"}
            else:
                generation = knowledge.current(root)
                result = ({"status": "current", "snapshot_id": generation["snapshot_id"], "generation": generation["generation"],
                           "object_count": len(generation["objects"]), "relation_count": len(generation["relations"]),
                           "coverage": generation["coverage"], "receipt": generation["receipt"], "excluded_counts": generation["excluded_counts"]}
                          if generation else {"status": "not_current"})
            self.store.append_audit_event(subject_id=self.subject_id, event_type="code.knowledge_inspected", actor="user",
                                          payload={"project_id": project, "operation": action, "status": result["status"]})
            return result
        raise ValueError("unknown Code action")


def digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()
