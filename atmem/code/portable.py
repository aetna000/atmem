"""Project-scoped, signed post-quantum encrypted memory bundles."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from atmem.code.application import CodeApplication, DEFAULT_SETTINGS, CURATION_SETTINGS, digest
from atmem.code.contracts import CodeScope
from atmem.code.formation import memory_subject_id
from atmem.code.identity import repository_key, _git
from atmem.core.canonical import canonical_json
from atmem.code.bundle_transport import seal_project_bytes, open_project_bytes
from atmem.extract.validation import screen_content


FORMAT = "atmem-code-project-bundle-v1"
FORMAT_V2 = "atmem-code-project-bundle-v2"
FORMAT_V3 = 'atmem-code-project-bundle-v3'
TABLES = ("episodes", "records", "audit_log", "memory_proposals", "memory_reviews",
          "memory_lineage", "memory_lifecycle", "memory_lifecycle_transitions", "retrieval_exclusions")
TABLES_V2 = TABLES + ("protocol_sources", "protocol_proposals", "typed_memory_units", "typed_unit_evidence",
                       "memory_proposal_sources", "formation_receipts", "source_adjacency",
                       "typed_identity_mappings", "typed_identity_review_queue", "typed_exclusion_identities")
_DOCUMENT_KINDS = {"settings", "origin", "exposure"}
_DOCUMENT_KINDS_V2 = _DOCUMENT_KINDS | {"knowledge-generation", "knowledge-job", "code-experience",
                                        "execution-receipt", "experience-tombstone", "experience-environment"}
_DOCUMENT_KINDS_V3 = _DOCUMENT_KINDS_V2 | {'curation-exposure'}


class CodePortable:
    def __init__(self, application: CodeApplication) -> None:
        self.app = application

    def export(self, project: str, *, recipient_public_key: bytes, signing_public_key: bytes,
               signing_secret_key: bytes) -> dict:
        self.app.authorize(project)
        curated = (bool(self.app.store.code_documents(self.app.subject_id, project, 'curation-exposure'))
                   or any(CURATION_SETTINGS.intersection(row) for row in self.app.store.code_documents(self.app.subject_id, project, 'settings')))
        extended = any(self.app.store.code_documents(self.app.subject_id, project, kind) for kind in (
                "knowledge-generation", "code-experience", "execution-receipt", "experience-tombstone"))
        extended = extended or curated
        table_names = TABLES_V2 if extended else TABLES
        document_kinds = _DOCUMENT_KINDS_V3 if curated else _DOCUMENT_KINDS_V2 if extended else _DOCUMENT_KINDS
        with self.app.store.transaction():
            lanes = self.app.store.code_scopes(self.app.subject_id, project)
            tables = {}
            for table in table_names:
                rows = []
                for lane in lanes:
                    order = "sequence" if table == "audit_log" else "rowid"
                    for row in self.app.store._conn.execute(
                        f'SELECT * FROM "{table}" WHERE subject_id=? ORDER BY {order}', (lane["derived_subject_id"],),
                    ).fetchall():
                        value = dict(row)
                        if table == "audit_log":
                            # Global sequence is local allocation; chain hashes
                            # bind the event fields and preserve relative order.
                            value.pop("sequence")
                        rows.append(value)
                tables[table] = rows
            observations = [dict(row) for row in self.app.store._conn.execute(
                "SELECT * FROM code_observations WHERE subject_id=? AND project_id=? ORDER BY event_id",
                (self.app.subject_id, project),
            ).fetchall()]
            documents = {kind: self.app.store.code_document_items(self.app.subject_id, project, kind) for kind in document_kinds}
            state = {"lanes": lanes, "tables": tables, "observations": observations, "documents": documents}
            manifest = {"format": FORMAT_V3 if curated else FORMAT_V2 if extended else FORMAT, "created_at": datetime.now(timezone.utc).isoformat(),
                        "owner_subject_id": self.app.subject_id, "project_id": project,
                        "schema_migrations": self.app.store.applied_migrations(), "state_sha256": digest(state),
                        "index_policy": "rebuild lexical, memory graph and local hashing vectors; reindex source graph in new clone",
                        "excluded": ["host configuration", "enrollment credentials", "provider routes"]}
            self._validate({"manifest": manifest, "state": state})
            plaintext = canonical_json({"manifest": manifest, "state": state}).encode("utf-8")
            self.app.store.append_audit_event(subject_id=self.app.subject_id, event_type="code.project_exported", actor="user",
                                              payload={"project_id": project, "state_sha256": manifest["state_sha256"]})
        if len(plaintext) > 128_000_000:
            raise ValueError("project bundle exceeds 128 MB limit")
        bundle = seal_project_bytes(plaintext, recipient_public_key=recipient_public_key,
                                  signing_public_key=signing_public_key, signing_secret_key=signing_secret_key)
        return bundle

    def open(self, bundle: dict, *, recipient_secret_key: bytes, trusted_signing_public_key: bytes) -> dict:
        if base64.b64decode(bundle.get("signing_public_key", ""), validate=True) != trusted_signing_public_key:
            raise PermissionError("bundle signer does not match the trusted key")
        plaintext = open_project_bytes(bundle, recipient_secret_key=recipient_secret_key,
                                       trusted_signing_public_key=trusted_signing_public_key)
        if len(plaintext) > 128_000_000:
            raise ValueError("project bundle exceeds limit")
        from atmem.delegated.validation import parse_json_strict
        value = parse_json_strict(plaintext)
        self._validate(value)
        return value

    def _validate(self, value: dict) -> None:
        if set(value) != {"manifest", "state"}:
            raise ValueError("bundle fields do not match the contract")
        manifest, state = value["manifest"], value["state"]
        if manifest.get("format") not in {FORMAT, FORMAT_V2, FORMAT_V3} or digest(state) != manifest.get("state_sha256"):
            raise ValueError("project bundle integrity mismatch")
        if manifest.get("owner_subject_id") != self.app.subject_id:
            raise PermissionError("bundle belongs to another subject")
        extended = manifest["format"] in {FORMAT_V2, FORMAT_V3}
        table_names = TABLES_V2 if extended else TABLES
        document_kinds = _DOCUMENT_KINDS_V3 if manifest['format'] == FORMAT_V3 else _DOCUMENT_KINDS_V2 if extended else _DOCUMENT_KINDS
        if set(state) != {"lanes", "tables", "observations", "documents"} or set(state["tables"]) != set(table_names):
            raise ValueError("unexpected bundle state tables")
        project = manifest["project_id"]
        if not set(manifest.get("schema_migrations", [])).issubset(self.app.store.applied_migrations()):
            raise ValueError("bundle requires a newer AtMem schema")
        allowed_subjects = set()
        for lane in state["lanes"]:
            scope = CodeScope(self.app.subject_id, project, lane["profile_id"], lane["agent_id"])
            if lane["owner_subject_id"] != self.app.subject_id or lane["project_id"] != project or lane["derived_subject_id"] != memory_subject_id(scope):
                raise PermissionError("bundle lane binding mismatch")
            allowed_subjects.add(lane["derived_subject_id"])
        if len(allowed_subjects) != len(state["lanes"]):
            raise ValueError("bundle contains duplicate lanes")
        for table, rows in state["tables"].items():
            columns = {row[1] for row in self.app.store._conn.execute(f'PRAGMA table_info("{table}")')}
            expected = columns - {"sequence"} if table == "audit_log" else columns
            for row in rows:
                if set(row) != expected or row.get("subject_id") not in allowed_subjects:
                    raise PermissionError("bundle table schema or subject mismatch")
                from atmem.memory import _screenable_metadata
                textual = {key: row[key] for key in ("content", "message", "raw") if key in row}
                if any(not screen_content(text, trusted=True).admissible for text in _screenable_metadata(textual)):
                    raise PermissionError("bundle contains searchable secret material")
        references = {"episode_id": {row["id"]: row["subject_id"] for row in state["tables"]["episodes"]},
                      "record_id": {row["id"]: row["subject_id"] for row in state["tables"]["records"]},
                      "proposal_id": {row["proposal_id"]: row["subject_id"] for row in state["tables"]["memory_proposals"]}}
        for table, rows in state["tables"].items():
            for row in rows:
                for column in ("episode_id", "record_id", "supersedes_id", "predecessor_record_id", "successor_record_id", "proposal_id"):
                    target = row.get(column)
                    if target is None:
                        continue
                    reference = ("record_id" if column in {"supersedes_id", "predecessor_record_id", "successor_record_id"} else column)
                    if table == "memory_proposals" and column == "proposal_id":
                        continue
                    if references[reference].get(target) != row["subject_id"]:
                        raise PermissionError("bundle contains a foreign source or record reference")
        for row in state["observations"]:
            if row["subject_id"] != self.app.subject_id or row["project_id"] != project:
                raise PermissionError("bundle observation scope mismatch")
        if set(state["documents"]) != document_kinds:
            raise ValueError("bundle contains unsupported configuration")
        for documents in state["documents"].values():
            for document in documents:
                if set(document) != {"document_id", "value"} or not isinstance(document["document_id"], str):
                    raise ValueError("invalid portable document")
        for item in state["documents"]["settings"]:
            settings = item["value"]
            if item["document_id"] != "effective" or set(settings) - set(DEFAULT_SETTINGS):
                raise ValueError("unsupported portable settings")
            for key, setting in settings.items():
                if key == "context_tags":
                    from atmem.code.contracts import _id
                    if not isinstance(setting, list) or len(setting) > 32:
                        raise ValueError("invalid portable context tags")
                    for tag in setting:
                        _id("context tag", tag)
                elif key == "max_context_bytes":
                    if type(setting) is not int or not 256 <= setting <= 32768:
                        raise ValueError("invalid portable context budget")
                elif key == 'context_mode':
                    if setting not in ('index', 'content'):
                        raise ValueError('invalid portable context mode')
                elif key in {'index_limit', 'index_bytes'}:
                    low, high = (1, 8) if key == 'index_limit' else (256, 4096)
                    if type(setting) is not int or not low <= setting <= high:
                        raise ValueError('invalid portable index bound')
                elif type(setting) is not bool:
                    raise ValueError("invalid portable setting")
        for item in state["documents"]["origin"]:
            if item["document_id"] not in references["record_id"]:
                raise PermissionError("portable origin does not name a project record")
        for item in state["documents"]["exposure"]:
            scope = item["value"]["request"]["scope"]
            if scope["subject_id"] != self.app.subject_id or scope["project_id"] != project:
                raise PermissionError("portable exposure scope mismatch")
        if extended:
            self._validate_extended(state, project, references)
        for item in state['documents'].get('curation-exposure', []):
            scope = CodeScope.from_dict(item['value']['scope'])
            if scope.subject_id != self.app.subject_id or scope.project_id != project:
                raise PermissionError('portable curation scope mismatch')
            for response in ('response', 'delivered_response'):
                for evidence in item['value'].get(response, {}).get('items', []):
                    identity = evidence.get('id', '')
                    if identity.startswith('exp:') and evidence.get('status') not in {'missing', 'withheld'}:
                        if references['record_id'].get(identity[4:]) != memory_subject_id(scope):
                            raise PermissionError('portable curation record mismatch')
        columns = {row[1] for row in self.app.store._conn.execute("PRAGMA table_info(code_observations)")}
        for row in state["observations"]:
            if set(row) != columns:
                raise ValueError("unexpected observation columns")
            from atmem.code.contracts import CodeObservation
            observation = CodeObservation.from_dict(json.loads(row["payload_json"]))
            if (observation.scope.subject_id != self.app.subject_id or observation.scope.project_id != project
                    or any(getattr(observation, key) != row[key] for key in ("event_id", "session_id", "turn_id"))
                    or observation.scope.profile_id != row["profile_id"] or observation.scope.agent_id != row["agent_id"]
                    or sha256(canonical_json(observation.to_dict()).encode()).hexdigest() != row["payload_sha256"]):
                raise PermissionError("portable observation binding or digest mismatch")
        from atmem.memory import _screenable_metadata
        if any(not screen_content(text, trusted=True).admissible for text in _screenable_metadata(state)):
            raise PermissionError("bundle contains unprotected secret material")

    def _validate_extended(self, state, project, references):
        from atmem.knowledge.contracts import SourceSnapshot, ExperienceProposal, ExecutionReceipt, StructuralObject, StructuralRelation
        sources = {row["source_id"]: row for row in state["tables"]["protocol_sources"]}
        lane_agents = {lane["derived_subject_id"]: lane["agent_id"] for lane in state["lanes"]}
        for row in sources.values():
            if references["episode_id"].get(row["episode_id"]) != row["subject_id"]:
                raise PermissionError("portable source episode is outside scope")
            request = json.loads(row["request_json"])
            episode = next(r for r in state["tables"]["episodes"] if r["id"] == row["episode_id"])
            if row["workspace_id"] != project or row["agent_id"] != lane_agents[row["subject_id"]]:
                raise PermissionError("portable source lane mismatch")
            if request == {"format": "atmem-source-capture-request-v1", "source_id": row["source_id"], "redacted": True}:
                result = json.loads(row["result_json"])
                if episode["message"] != "[purged]" or result.get("retained") is not False or result.get("redacted") is not True:
                    raise PermissionError("portable deleted source has retained body")
                continue
            authority = request.get("scope", {})
            if (authority.get("subject_id"), authority.get("agent_id"), authority.get("workspace_id")) != (
                    row["subject_id"], row["agent_id"], row["workspace_id"]):
                raise PermissionError("portable source authority mismatch")
            if episode["message"] != "[purged]" and "sha256:" + sha256(episode["message"].encode()).hexdigest() != row["source_sha256"]:
                raise PermissionError("portable source content digest mismatch")
        units = {(row["subject_id"], row["workspace_id"], row["unit_id"]): row for row in state["tables"]["typed_memory_units"]}
        for row in units.values():
            if references["record_id"].get(row["record_id"]) != row["subject_id"]:
                raise PermissionError("portable typed record scope mismatch")
        for table in ("typed_unit_evidence", "memory_proposal_sources"):
            for row in state["tables"][table]:
                source = sources.get(row["source_id"])
                if source is None or source["subject_id"] != row["subject_id"] or source["workspace_id"] != row["workspace_id"]:
                    raise PermissionError("portable typed source is outside scope")
                if table == "typed_unit_evidence" and (row["subject_id"], row["workspace_id"], row["unit_id"]) not in units:
                    raise PermissionError("portable typed evidence has no unit")
        for kind in _DOCUMENT_KINDS_V2 - _DOCUMENT_KINDS:
            for item in state["documents"][kind]:
                value = item["value"]
                scope = CodeScope.from_dict(value["scope"])
                if scope.subject_id != self.app.subject_id or scope.project_id != project:
                    raise PermissionError("portable knowledge document scope mismatch")
                if kind == "code-experience":
                    proposal, snapshot = ExperienceProposal.from_dict(value["proposal"]), SourceSnapshot.from_dict(value["snapshot"])
                    if proposal.scope != scope or snapshot.scope != scope or proposal.snapshot_id != snapshot.snapshot_id:
                        raise PermissionError("portable experience source binding mismatch")
                    if any(references["record_id"].get(record_id) != memory_subject_id(scope) for record_id in value["formation"]["record_ids"]):
                        raise PermissionError("portable experience record mismatch")
                elif kind == "execution-receipt":
                    receipt, snapshot = ExecutionReceipt.from_dict(value["receipt"]), SourceSnapshot.from_dict(value["snapshot"])
                    result = base64.b64decode(value["result"], validate=True)
                    if receipt.scope != scope or snapshot.scope != scope or receipt.snapshot_id != snapshot.snapshot_id or sha256(result).hexdigest() != receipt.result_sha256:
                        raise PermissionError("portable execution evidence mismatch")
                elif kind == "knowledge-generation":
                    snapshot = SourceSnapshot.from_dict(value["snapshot"])
                    if snapshot.scope != scope or snapshot.snapshot_id != value["snapshot_id"]:
                        raise PermissionError("portable knowledge snapshot mismatch")
                    if set(value["source_bytes"]) != set(dict(snapshot.files)):
                        raise PermissionError("portable knowledge source set mismatch")
                    for name, expected in snapshot.files:
                        content = base64.b64decode(value["source_bytes"][name], validate=True)
                        from atmem.knowledge.source_text import source_text
                        if sha256(content).hexdigest() != expected or not screen_content(source_text(name, content), trusted=True).admissible:
                            raise PermissionError("portable knowledge source content mismatch")
                    objects = [StructuralObject.from_dict(o) for o in value["objects"]]
                    if any(o.scope != scope or o.snapshot_id != snapshot.snapshot_id for o in objects):
                        raise PermissionError("portable structural object scope mismatch")
                    identities = {o.object_id for o in objects}
                    for row in value["relations"]:
                        relation = StructuralRelation.from_dict(row)
                        if relation.source_id not in identities or relation.target_id is not None and relation.target_id not in identities:
                            raise PermissionError("portable relation target outside projection")

    def preview(self, value: dict, *, root: str) -> dict:
        project = value["manifest"]["project_id"]
        key = repository_key(root)
        binding = self.app.store.code_project_binding(self.app.subject_id, key)
        collisions = []
        if self.app.store.code_project_exists(self.app.subject_id, project):
            collisions.append("project identity already exists")
        if binding is not None:
            collisions.append("destination repository already bound")
        for lane in value["state"]["lanes"]:
            if self.app.store.list_records(lane["derived_subject_id"], statuses=None):
                collisions.append("destination lane already has records")
        return {"project_id": project, "owner_subject_id": self.app.subject_id,
                "repository_key": key, "state_sha256": value["manifest"]["state_sha256"],
                "record_count": len(value["state"]["tables"]["records"]),
                "collisions": sorted(set(collisions)), "can_import": not collisions,
                "preview_token": digest([value["manifest"]["state_sha256"], key, self.app.subject_id])}

    def restore(self, value: dict, *, root: str, preview_token: str) -> dict:
        # Revalidate even when called directly with a previously opened object.
        self._validate(value)
        if value["manifest"]["owner_subject_id"] != self.app.subject_id or digest(value["state"]) != value["manifest"]["state_sha256"]:
            raise PermissionError("bundle state changed after verification")
        preview = self.preview(value, root=root)
        if not preview["can_import"] or preview_token != preview["preview_token"]:
            raise ValueError("import preview conflicts or no longer matches")
        state, project = value["state"], preview["project_id"]
        with self.app.store.transaction():
            # Foreign keys may refer to later rows within the same project.
            self.app.store._conn.execute("PRAGMA defer_foreign_keys=ON")
            for table, rows in state["tables"].items():
                for row in rows:
                    columns = list(row)
                    names = ",".join('"' + name + '"' for name in columns)
                    marks = ",".join("?" for _ in columns)
                    self.app.store._conn.execute(f'INSERT INTO "{table}" ({names}) VALUES ({marks})', [row[name] for name in columns])
            for lane in state["lanes"]:
                self.app.store.register_code_scope_subject(**lane)
                if not self.app.store.verify_audit_chain(lane["derived_subject_id"]):
                    raise ValueError("imported memory audit chain is invalid")
                for record in self.app.store.list_records(lane["derived_subject_id"], statuses=None):
                    self.app.memory.graph.index_record(record)
                    if record["status"] != "tombstoned":
                        self.app.store._upsert_fts(record["id"], record["subject_id"], record["content"])
                        self.app.store._upsert_search_terms(record_id=record["id"], subject_id=record["subject_id"],
                                                            workspace_id=str(record.get("workspace_id") or ""),
                                                            content=record["content"], fact_key=record.get("fact_key"))
            for row in state["observations"]:
                columns = list(row)
                names = ",".join('"' + name + '"' for name in columns)
                self.app.store._conn.execute(f'INSERT INTO code_observations ({names}) VALUES ({",".join("?" for _ in columns)})', list(row.values()))
            for kind, docs in state["documents"].items():
                for document in docs:
                    self.app.store.put_code_document(self.app.subject_id, project, kind, document["document_id"], document["value"])
            remote = _git(Path(root).resolve(), "remote", "get-url", "origin")
            self.app.store.bind_code_project(subject_id=self.app.subject_id, repository_key=preview["repository_key"],
                                             project_id=project, remote_sha256=sha256(remote.encode()).hexdigest() if remote else None)
            label = Path(root).resolve().name
            self.app.store.put_code_document(self.app.subject_id, project, "project-info", "info",
                                             {"name": label if screen_content(label, trusted=True).admissible else "Project"})
            self.app.store.append_audit_event(subject_id=self.app.subject_id, event_type="code.project_imported", actor="user",
                                              payload={"project_id": project, "state_sha256": value["manifest"]["state_sha256"]})
        vectors = []
        for lane in state["lanes"]:
            vectors.append(self.app.memory.sync_default_vectors(lane["derived_subject_id"]))
        graph = None
        if self.app.settings(project)["graph_enabled"]:
            from atmem.code.graph import CodeGraph
            try:
                graph = CodeGraph(self.app, project).index(root)
            except (ValueError, OSError, RuntimeError) as exc:
                # Canonical import has committed. Report a rebuild requirement,
                # not a failed import that tempts the user to duplicate it.
                graph = {"status": "rebuild_required", "reason": type(exc).__name__}
        return {"imported": True, "project_id": project, "record_count": preview["record_count"],
                "vectors": vectors, "source_graph": graph or "disabled", "hosts_enabled": False}
