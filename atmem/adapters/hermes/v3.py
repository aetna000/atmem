"""Scoped Hermes bridge to the existing V3 episode/context product APIs.

No alternative extractor, planner, ranker or packer lives here. History-import
authority is supplied only by a persisted administrator-selected binding.
"""
from __future__ import annotations

from contextlib import contextmanager
import base64
import hashlib
import json
import os
from typing import Any
import uuid

from atmem.contracts import EpisodeIngestRequest, EpisodePart, RetrievalBudget
from atmem.context_engine import ContextRequestV3
from atmem.core.canonical import canonical_json, sha256_hex
from atmem.extract.validation import screen_content
from atmem.memory import Memory


PROFILE = "authorized-at-recall-context-v3"
CONTEXT_BYTES = 32_000
CANDIDATE_LIMIT = 200


def _queries(scope):
    clause = "subject_id=? AND agent_id=? AND workspace_id=?"
    params = (scope.subject_id, scope.agent_id, scope.workspace_id)
    sources = "SELECT source_id FROM context_source_episodes WHERE " + clause
    generations = "SELECT generation_id FROM context_view_generations WHERE " + clause
    queries = {table: f"SELECT * FROM {table} WHERE " + clause for table in (
        "context_source_episodes", "context_view_generations", "context_backfill_state")}
    for table in ("context_source_parts", "context_source_ranges"):
        queries[table] = f"SELECT * FROM {table} WHERE source_id IN ({sources})"
    for table in ("context_evidence_units", "context_unit_ranges", "context_evidence_links",
                  "context_coverage", "context_loss_receipts", "context_vectors", "context_unit_views"):
        queries[table] = f"SELECT * FROM {table} WHERE generation_id IN ({generations})"
    return queries, params


class V3HistoryBinding:
    def __init__(self, manager: Any, identity: Any, profile_id: str):
        self.manager, self.identity, self.profile_id = manager, identity, profile_id

    @contextmanager
    def memory(self, *, importing: bool = False):
        scope, path = self.manager._memory_authority_scope(
            self.manager.state(), subject_id=self.identity.subject_id,
            agent_id=self.identity.agent_id,
        )
        if scope.workspace_id != self.identity.workspace_id:
            raise PermissionError("V3 scope no longer matches the binding")
        authority = ({"principal_id": self.principal, "subject_id": scope.subject_id,
            "agent_id": scope.agent_id, "workspace_id": scope.workspace_id,
            "scopes": ("history_import:review", "procedure:review"),
            "assurance": "explicit_hermes_administrator_configuration"},) if importing else ()
        memory = Memory(path, retain_query_text=False, auto_vectors=False,
                        review_authorities=authority)
        try:
            yield memory, scope
        finally:
            memory.close()

    @property
    def principal(self) -> str:
        return "hermes-history-import:" + self.profile_id

    def observe(self, text: str, *, session_id: str, observation_id: str) -> dict[str, Any]:
        screening = screen_content(text, trusted=True)
        if not screening.admissible:
            return {"captured": False, "reason": "policy_refused",
                    "reason_codes": list(screening.reason_codes), "memory_mutated": False}
        key = sha256_hex(canonical_json([self.profile_id, session_id, observation_id]))
        with self.memory(importing=True) as (memory, scope):
            request = EpisodeIngestRequest(
                episode_id="hermes-v3-" + key, idempotency_key="hermes-v3-" + key,
                scope=scope, parts=(EpisodePart(part_id="dated-message-0000", ordinal=0,
                    kind="text", source_type="user_message", content=text,
                    content_sha256="sha256:" + sha256_hex(text)),),
                binding_method="host_asserted", binding_assurance="host_asserted",
                session_id="hermes-v3-" + key, retain_body=True,
                source_observation_granularity="sentence",
            )
            receipt = memory.form_context_episode(request, history_import_principal=self.principal)
            return {"captured": True, "profile": PROFILE, "formation": receipt,
                    "source_events_observed": receipt["source_events_observed"]}

    def recall(self, query: str, *, turn_id: str) -> dict[str, Any]:
        with self.memory() as (memory, scope):
            # Do not activate or mutate an in-progress ingestion generation
            # merely because Hermes prefetches before a history interaction.
            try:
                generation = memory.context_generation(scope)
            except RuntimeError:
                return {"context": "", "reason": "history_not_frozen", "profile": PROFILE}
            request_id = "hermes-v3-" + uuid.uuid4().hex
            package = memory.prepare_context_v3(ContextRequestV3(
                context_id=request_id, request_id=request_id, scope=scope,
                query=query, profile_id="context-fast", mode="active",
                generation=int(generation["canonical_generation"]), turn_id=turn_id,
                budget=RetrievalBudget(total_candidates=CANDIDATE_LIMIT, context_bytes=CONTEXT_BYTES),
            ))
            return {"context": package.context,
                "reason": "authorized" if package.status == "sufficient" else package.status,
                "candidate_ids": package.selected_unit_ids,
                "exposure_id": package.audit_event_id,
                "context_receipt_id": package.preparation_id, "profile": PROFILE}

    def freeze(self) -> None:
        with self.memory() as (memory, scope):
            memory.freeze_context_engine(scope)

    def checkpoint(self) -> dict[str, Any]:
        """Fingerprint scoped V3 evidence, including actual retained source bytes.

        Read/audit telemetry is excluded. This is not a database backup or a
        promise to detect every physical corruption of SQLite's FTS internals.
        """
        with self.memory() as (memory, scope):
            connection = memory.store._conn
            queries, params = _queries(scope)
            identities = {}
            # One read transaction gives a consistent identity across tables.
            with memory.store.transaction(immediate=False):
                for table, query in queries.items():
                    columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
                    ordering = ",".join(str(index + 1) for index in range(len(columns)))
                    digest, count = hashlib.sha256(), 0
                    for row in connection.execute(query + " ORDER BY " + ordering, params):
                        values = [({"bytes_sha256": sha256_hex(bytes(value)), "size": len(value)}
                                   if isinstance(value, (bytes, bytearray, memoryview)) else value)
                                  for value in row]
                        encoded = canonical_json(values).encode()
                        digest.update(len(encoded).to_bytes(8, "big"))
                        digest.update(encoded)
                        count += 1
                    identities[table] = {"rows": count, "sha256": digest.hexdigest()}
            return {"format": "atmem-hermes-context-v3-checkpoint-v1", "scope": scope.to_dict(),
                    "profile": PROFILE, "tables": identities,
                    "sha256": sha256_hex(canonical_json(identities))}

    def export(self, destination, *, actor: str) -> dict[str, Any]:
        """Authorized plaintext evidence export, not an encrypted DB/key backup.

        Called only after the service's admin and scope checks. Binary source
        parts are losslessly base64 encoded; no key or binding credential rows
        are included. Rebuildable FTS internals are deliberately not exported.
        """
        digest, count = hashlib.sha256(), 0
        with self.memory() as (memory, scope):
            queries, params = _queries(scope)
            fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'wb') as output, memory.store.transaction(immediate=False):
                header = {'format': 'atmem-context-v3-export-v1', 'scope': scope.to_dict(),
                          'plaintext_authorized_export': True, 'fts_rebuild_required': True}
                encoded = (json.dumps(header) + '\n').encode()
                output.write(encoded)
                digest.update(encoded)
                for table, query in queries.items():
                    columns = memory.store._conn.execute(f'PRAGMA table_info({table})').fetchall()
                    ordering = ','.join(str(i + 1) for i in range(len(columns)))
                    for row in memory.store._conn.execute(query + ' ORDER BY ' + ordering, params):
                        values = {key: ({'base64': base64.b64encode(bytes(value)).decode()}
                                       if isinstance(value, (bytes, bytearray, memoryview)) else value)
                                  for key, value in dict(row).items()}
                        encoded = (json.dumps({'table': table, 'row': values}) + '\n').encode()
                        output.write(encoded)
                        digest.update(encoded)
                        count += 1
                output.flush()
                os.fsync(output.fileno())
            memory.store.append_audit_event(subject_id=scope.subject_id,
                event_type='context.v3.exported', actor=actor,
                payload={'rows': count, 'sha256': digest.hexdigest(), 'content_retained': False})
        return {'format': 'atmem-context-v3-export-receipt-v1', 'rows': count,
                'sha256': digest.hexdigest(), 'plaintext_authorized_export': True}
