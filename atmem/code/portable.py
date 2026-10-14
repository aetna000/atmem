"""Project-scoped, signed post-quantum encrypted memory bundles."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from atmem.code.application import CodeApplication, DEFAULT_SETTINGS, digest
from atmem.code.contracts import CodeScope
from atmem.code.formation import memory_subject_id
from atmem.code.identity import repository_key, _git
from atmem.core.canonical import canonical_json
from atmem.evidence.crypto import encrypted_export, decrypt_export
from atmem.extract.validation import screen_content


FORMAT = "atmem-code-project-bundle-v1"
TABLES = ("episodes", "records", "audit_log", "memory_proposals", "memory_reviews",
          "memory_lineage", "memory_lifecycle", "memory_lifecycle_transitions", "retrieval_exclusions")
_DOCUMENT_KINDS = {"settings", "origin", "exposure"}


class CodePortable:
    def __init__(self, application: CodeApplication) -> None:
        self.app = application

    def export(self, project: str, *, recipient_public_key: bytes, signing_public_key: bytes,
               signing_secret_key: bytes) -> dict:
        self.app.authorize(project)
        with self.app.store.transaction():
            lanes = self.app.store.code_scopes(self.app.subject_id, project)
            tables = {}
            for table in TABLES:
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
            documents = {kind: self.app.store.code_document_items(self.app.subject_id, project, kind) for kind in _DOCUMENT_KINDS}
            state = {"lanes": lanes, "tables": tables, "observations": observations, "documents": documents}
            manifest = {"format": FORMAT, "created_at": datetime.now(timezone.utc).isoformat(),
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
        bundle = encrypted_export(plaintext, recipient_public_key=recipient_public_key,
                                  signing_public_key=signing_public_key, signing_secret_key=signing_secret_key)
        from pqcrypto.sign.ml_dsa_65 import verify
        verify(signing_public_key, canonical_json({key: item for key, item in bundle.items() if key != "signature"}).encode(),
               base64.b64decode(bundle["signature"], validate=True))
        return bundle

    def open(self, bundle: dict, *, recipient_secret_key: bytes, trusted_signing_public_key: bytes) -> dict:
        if base64.b64decode(bundle.get("signing_public_key", ""), validate=True) != trusted_signing_public_key:
            raise PermissionError("bundle signer does not match the trusted key")
        plaintext = decrypt_export(bundle, recipient_secret_key)
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
        if manifest.get("format") != FORMAT or digest(state) != manifest.get("state_sha256"):
            raise ValueError("project bundle integrity mismatch")
        if manifest.get("owner_subject_id") != self.app.subject_id:
            raise PermissionError("bundle belongs to another subject")
        if set(state) != {"lanes", "tables", "observations", "documents"} or set(state["tables"]) != set(TABLES):
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
        if set(state["documents"]) != _DOCUMENT_KINDS:
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
                elif type(setting) is not bool:
                    raise ValueError("invalid portable setting")
        for item in state["documents"]["origin"]:
            if item["document_id"] not in references["record_id"]:
                raise PermissionError("portable origin does not name a project record")
        for item in state["documents"]["exposure"]:
            scope = item["value"]["request"]["scope"]
            if scope["subject_id"] != self.app.subject_id or scope["project_id"] != project:
                raise PermissionError("portable exposure scope mismatch")
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
            for table in TABLES:
                for row in state["tables"][table]:
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
