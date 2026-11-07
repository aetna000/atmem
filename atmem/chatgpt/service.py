"""Account-bound semantic memory operations using the actual AtMem engine."""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
from typing import Any
import uuid

from atmem import Memory
from atmem.core.canonical import canonical_json
from atmem.core.storage import HouseholdPolicy
from atmem.extract.validation import screen_content

from .config import Settings
from .repository import Repository


class Denied(ValueError):
    """A public, secretless error code suitable for an MCP result."""


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def record_view(row: dict) -> dict:
    return {key: row.get(key) for key in ("id", "content", "status", "source_type", "trust_tier", "created_at", "updated_at", "episode_id", "superseded_by_id") } | {"version": digest(row), "untrusted_data": True}


class Service:
    def __init__(self, settings: Settings, repository: Repository):
        self.settings = settings
        self.repository = repository

    @contextmanager
    def household(self, account: str):
        if not account or len(account) > 128 or not self.settings.permits_account(account):
            raise Denied("authentication_required")
        previous = self.repository.load(account)
        # Temp storage contains encrypted SQLite pages, never a plaintext DB.
        with tempfile.TemporaryDirectory(prefix="work-", dir=self.settings.home) as directory:
            path = Path(directory) / "memory.db"
            if previous.payload is not None:
                payload = json.loads(previous.payload)
                if payload.get("format") != "atmem-cloud-household-v1":
                    raise Denied("unsupported_household_version")
                path.write_bytes(base64.b64decode(payload["database"], validate=True))
                Path(str(path) + ".encryption.json").write_text(json.dumps(payload["policy"]))
            else:
                from atmem.core.keys import initialize_encrypted_household, DEFAULT_KEY_PATH
                if not DEFAULT_KEY_PATH.resolve().is_relative_to(self.settings.home):
                    raise Denied("cloud_key_home_mismatch_restart_process")
                initialize_encrypted_household(path)
            policy = HouseholdPolicy.load(path)
            if policy.state != "encrypted":
                raise Denied("plaintext_household_refused")
            memory = Memory(path, policy=policy, auto_vectors=False)
            try:
                connection = memory.store._conn
                connection.execute("CREATE TABLE IF NOT EXISTS chatgpt_scopes (scope TEXT PRIMARY KEY, label TEXT NOT NULL, created_at REAL NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS chatgpt_actions (id TEXT PRIMARY KEY, scope TEXT NOT NULL, intent_hash TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE, state TEXT NOT NULL, expires_at REAL NOT NULL, payload TEXT, result TEXT)")
                connection.execute("INSERT OR IGNORE INTO chatgpt_scopes VALUES ('personal','Personal',?)", (time.time(),))
                # Expired pending content is purged whenever a household is used.
                connection.execute("UPDATE chatgpt_actions SET state='expired',payload=NULL WHERE state IN ('pending','approved') AND expires_at<=?", (time.time(),))
                context = {"memory": memory, "connection": connection, "generation": previous.generation}
                yield context
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except BaseException:
                memory.close()
                raise
            else:
                memory.close()
                payload = canonical_json({"format": "atmem-cloud-household-v1", "database": base64.b64encode(path.read_bytes()).decode(), "policy": json.loads(Path(str(path)+".encryption.json").read_text())}).encode()
                context["cloud_receipt"] = self.repository.commit(account, previous, payload)

    def _subject(self, connection, account: str, scope: str) -> str:
        if not re.fullmatch(r"personal|project:[a-z0-9][a-z0-9-]{0,47}", scope):
            raise Denied("invalid_scope")
        if not connection.execute("SELECT 1 FROM chatgpt_scopes WHERE scope=?", (scope,)).fetchone():
            raise Denied("scope_not_available")
        return "chatgpt:" + self.settings.opaque_id("subject", account) + ":" + scope

    def _validate_intent(self, memory, subject, intent, expected_hash):
        bound={key:intent.get(key, "") for key in ("operation","scope","content","record_id","version","label")}
        if digest(bound)!=expected_hash:
            raise Denied("intent_integrity_failure")
        if intent["operation"] in {"correct","delete"}:
            row=memory.store.get_record(subject,intent["record_id"])
            if row is None or row["status"]!="active" or digest(row)!=intent["version"]:
                raise Denied("stale_record_requires_new_approval")
            if intent.get("previous_content")!=str(row["content"])[:2000]:
                raise Denied("intent_integrity_failure")

    def _event(self, memory, subject, event, **kwargs):
        event_id = memory.store.append_audit_event(subject_id=subject, event_type="chatgpt."+event,
            actor="authenticated-plugin-user", payload=kwargs)
        row = memory.store.get_audit_event(subject, event_id)
        return {"audit_event_id": event_id, "audit_event_hash": row["event_hash"]}

    def scopes(self, account: str) -> dict:
        with self.household(account) as ctx:
            rows = ctx["connection"].execute("SELECT scope,label FROM chatgpt_scopes ORDER BY scope LIMIT 51").fetchall()
            result = {"scopes": [{"id": row[0], "label": row[1]} for row in rows], "automatic_capture": False}
        return result

    def search(self, account: str, scope: str, query: str, limit: int = 5) -> dict:
        if not 1 <= len(query.strip()) <= 500 or not 1 <= limit <= 10:
            raise Denied("invalid_query_or_limit")
        with self.household(account) as ctx:
            subject = self._subject(ctx["connection"], account, scope)
            records = ctx["memory"].recall(subject, query, limit=limit)
            result = {"scope": scope, "records": [record_view(row) for row in records], "untrusted_data": True}
        return result

    def read(self, account: str, scope: str, record_id: str) -> dict:
        with self.household(account) as ctx:
            memory = ctx["memory"]; subject = self._subject(ctx["connection"], account, scope)
            row = memory.store.get_record(subject, record_id)
            if row is None or row["status"] != "active" or record_id in memory.store.excluded_record_ids(subject):
                raise Denied("memory_not_available")
            episode = memory.store.get_episode(subject, row["episode_id"])
            result = {"scope": scope, "record": record_view(row), "provenance": {
                "episode_id": row["episode_id"], "source_type": row.get("source_type"),
                "source_message": (episode or {}).get("message", "")[:2500],
                "assurance": "explicit_user_browser_approved", "untrusted_data": True},
                "receipt": self._event(memory, subject, "memory_read", record_id=record_id)}
        return result

    def propose(self, account: str, kind: str, scope: str, request_key: str, *,
                content: str = "", record_id: str = "", version: str = "", label: str = "") -> dict:
        if kind not in {"save", "correct", "delete", "create_scope"}:
            raise Denied("unknown_operation")
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{8,100}", request_key):
            raise Denied("invalid_idempotency_key")
        if kind in {"save", "correct"}:
            if not 1 <= len(content.strip()) <= 1800:
                raise Denied("content_length_out_of_range")
            screening = screen_content(content, trusted=False)
            if screening.reason_codes:
                raise Denied("content_refused:" + ",".join(screening.reason_codes))
        if kind == "create_scope" and (not re.fullmatch(r"project:[a-z0-9][a-z0-9-]{0,47}", scope) or not 1 <= len(label.strip()) <= 80):
            raise Denied("invalid_project_scope")
        intent = {"operation": kind, "scope": scope, "content": content, "record_id": record_id, "version": version, "label": label}
        intent_hash = digest(intent)
        with self.household(account) as ctx:
            connection = ctx["connection"]; memory = ctx["memory"]
            subject = self._subject(connection, account, "personal" if kind == "create_scope" else scope)
            previous = connection.execute("SELECT id,intent_hash,state,expires_at FROM chatgpt_actions WHERE request_key=?", (request_key,)).fetchone()
            if previous:
                if previous[1] != intent_hash:
                    raise Denied("idempotency_key_conflict")
                if previous[2] == "expired":
                    raise Denied("intent_expired_use_new_key")
                result = self._proposal_view(previous[0], scope, previous[2], previous[3], intent)
            else:
                if connection.execute("SELECT count(*) FROM chatgpt_actions WHERE state IN ('pending','approved')").fetchone()[0] >= 20:
                    raise Denied("pending_action_quota_exceeded")
                if kind in {"correct", "delete"}:
                    row = memory.store.get_record(subject, record_id)
                    if row is None or row["status"] != "active":
                        raise Denied("memory_not_available")
                    if digest(row) != version:
                        raise Denied("stale_record_read_again")
                    intent["previous_content"] = str(row["content"])[:2000]
                if kind == "create_scope" and connection.execute("SELECT 1 FROM chatgpt_scopes WHERE scope=?", (scope,)).fetchone():
                    raise Denied("scope_already_exists")
                if kind == "save" and len(memory.list(subject)) >= self.settings.max_records:
                    raise Denied("memory_quota_exceeded")
                action_id = "act_" + uuid.uuid4().hex
                expires = time.time()+600
                connection.execute("INSERT INTO chatgpt_actions VALUES (?,?,?,?,?,?,?,NULL)", (action_id, scope, intent_hash, request_key, "pending", expires, canonical_json(intent)))
                self._event(memory, subject, "action_proposed", action_id=action_id, operation=kind, intent_sha256=intent_hash)
                result = self._proposal_view(action_id, scope, "pending", expires, intent)
        return result

    def _proposal_view(self, action_id, scope, state, expires, intent):
        return {"action_id": action_id, "scope": scope, "state": state, "expires_at": expires,
                "preview": intent, "approval_url": self.settings.issuer + "/approve/" + action_id,
                "next_step": "Open approval_url and sign in. Only the authenticated user can approve. Then call commit_memory_action.",
                "saved": state == "completed"}

    def preview_action(self, account: str, action_id: str) -> dict:
        with self.household(account) as ctx:
            row = ctx["connection"].execute("SELECT scope,state,expires_at,payload,intent_hash FROM chatgpt_actions WHERE id=?", (action_id,)).fetchone()
            if not row:
                raise Denied("action_not_available")
            intent=json.loads(row[3]) if row[3] else None
            if intent:
                subject=self._subject(ctx["connection"],account,"personal" if intent["operation"]=="create_scope" else row[0])
                self._validate_intent(ctx["memory"],subject,intent,row[4])
            result = {"action_id": action_id, "scope": row[0], "state": row[1], "expires_at": row[2], "intent": intent}
        return result

    def approve(self, account: str, action_id: str, *, approve: bool) -> dict:
        # Only a browser endpoint that has independently authenticated the human
        # calls this method. No MCP tool exposes it or accepts approval booleans.
        with self.household(account) as ctx:
            c = ctx["connection"]; memory = ctx["memory"]
            row = c.execute("SELECT scope,state,payload,intent_hash FROM chatgpt_actions WHERE id=?", (action_id,)).fetchone()
            if not row or row[1] not in {"pending", "approved"}:
                raise Denied("action_not_pending")
            intent = json.loads(row[2])
            subject = self._subject(c, account, "personal" if intent["operation"] == "create_scope" else row[0])
            self._validate_intent(memory,subject,intent,row[3])
            state = "approved" if approve else "cancelled"
            c.execute("UPDATE chatgpt_actions SET state=?,payload=? WHERE id=?", (state, row[2] if approve else None, action_id))
            receipt = self._event(memory, subject, "action_" + state, action_id=action_id)
            result = {"state": state, "action_id": action_id, "receipt": receipt}
        return result

    def commit(self, account: str, scope: str, action_id: str, operation: str) -> dict:
        with self.household(account) as ctx:
            c = ctx["connection"]; memory = ctx["memory"]
            row = c.execute("SELECT scope,state,payload,result,intent_hash FROM chatgpt_actions WHERE id=?", (action_id,)).fetchone()
            if row is None or row[0] != scope:
                raise Denied("action_not_available")
            if row[1] == "expired":
                raise Denied("intent_expired_use_new_proposal")
            actual = json.loads(row[3] if row[1] == "completed" else row[2] or "{}")
            if actual.get("operation") != operation:
                raise Denied("operation_does_not_match_approved_intent")
            if row[1] == "completed":
                result = json.loads(row[3]); result["idempotent_replay"] = True
            else:
                if row[1] != "approved" or not row[2]:
                    raise Denied("independent_user_approval_required")
                intent = json.loads(row[2]); kind = intent["operation"]
                subject = self._subject(c, account, "personal" if kind == "create_scope" else scope)
                self._validate_intent(memory,subject,intent,row[4])
                with memory.store.transaction():
                    if kind in {"correct", "delete"}:
                        current = memory.store.get_record(subject, intent["record_id"])
                        if current is None or current["status"] != "active" or digest(current) != intent["version"]:
                            raise Denied("stale_record_requires_new_approval")
                    if kind == "save":
                        if len(memory.list(subject)) >= self.settings.max_records:
                            raise Denied("memory_quota_exceeded")
                        outcome = memory.remember(subject, message=intent["content"], interpreted_fact=intent["content"],
                            interpreted_fact_key="chatgpt:"+action_id, source_type="user_message", actor="authenticated-plugin-user",
                            raw={"interpreter":"user", "interpretation_assurance":"explicit_user_browser_approved", "source_binding":action_id})
                        if outcome.get("refused"):
                            raise Denied("content_refused")
                        ids = [r["id"] for r in outcome["records"]] or outcome.get("duplicate_ids", [])
                        if not ids:
                            raise Denied("no_memory_admitted")
                        result = {"operation": kind, "record_ids": ids}
                    elif kind == "correct":
                        outcome = memory.correct_record(subject, intent["record_id"], intent["content"], actor="authenticated-plugin-user")
                        result = {"operation": kind, "record_ids": [outcome["record"]["id"]], "replaced_record_id": outcome["replaced_record_id"]}
                    elif kind == "delete":
                        outcome = memory.forget_record(subject, intent["record_id"], actor="authenticated-plugin-user")
                        result = {"operation": kind, **outcome, "limits": "Current canonical/registered derived state only. ChatGPT copies, provider backups and Firestore PITR are not verified erased."}
                    else:
                        if c.execute("SELECT count(*) FROM chatgpt_scopes").fetchone()[0] >= 50:
                            raise Denied("scope_quota_exceeded")
                        if c.execute("SELECT 1 FROM chatgpt_scopes WHERE scope=?", (scope,)).fetchone():
                            raise Denied("scope_already_exists")
                        c.execute("INSERT INTO chatgpt_scopes VALUES (?,?,?)", (scope, intent["label"], time.time()))
                        result = {"operation": kind, "created_scope": scope}
                    result.update({"scope": scope, "action_id": action_id, "idempotent_replay": False,
                                   "audit_receipt": self._event(memory, subject, "action_committed", action_id=action_id, operation=kind)})
                    c.execute("UPDATE chatgpt_actions SET state='completed',payload=NULL,result=? WHERE id=?", (canonical_json(result), action_id))
        return result | {"durable": True, "cloud_receipt": ctx["cloud_receipt"]}

    def receipt(self, account: str, scope: str, action_id: str) -> dict:
        with self.household(account) as ctx:
            row = ctx["connection"].execute("SELECT scope,state,result FROM chatgpt_actions WHERE id=?", (action_id,)).fetchone()
            if not row or row[0] != scope:
                raise Denied("action_not_available")
            result = {"action_id": action_id, "state": row[1], "result": json.loads(row[2]) if row[2] else None}
        return result

    def activity(self, account: str, scope: str, limit: int = 10) -> dict:
        if not 1 <= limit <= 30:
            raise Denied("invalid_limit")
        with self.household(account) as ctx:
            memory = ctx["memory"]; subject = self._subject(ctx["connection"], account, scope)
            page = memory.store.query_audit_events(subject, limit=limit)
            # Never disclose arbitrary payloads; structural evidence only.
            events = page.get("events", page.get("items", []))
            result = {"scope": scope, "events": [{key: e.get(key) for key in ("event_id", "sequence", "event_type", "created_at", "record_id", "event_hash")} for e in events],
                      "audit_chain_valid": memory.store.verify_audit_chain(subject)}
        return result
