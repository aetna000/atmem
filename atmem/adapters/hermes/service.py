"""Scoped Hermes operations over the existing encrypted control store."""
from __future__ import annotations

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
from threading import Lock
import time
from typing import Any
import uuid

from atmem.adapters.base import AtMemAdapterIdentity
from atmem.evidence.crypto import open_json, seal_json
from atmem.locking import ProcessFileLock
from atmem.service import APIError, APIPrincipal

from .binding import HermesMemoryBinding, _identifier

_HERMES_EVENT_TYPES = frozenset({
    "turn.input", "context.disposition", "model.input", "model.output", "turn.ended",
})
_EVIDENCE_WRITER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="atmem-hermes-evidence")
_DRAINING: set[str] = set()
_REDRAIN: set[str] = set()
_DRAINING_LOCK = Lock()


def _event_time() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _write_events(binding: Any, events: list[dict[str, Any]]) -> bool:
    """Preserve event order; a failed suffix remains recoverable in the spool."""
    for event in events:
        try:
            result = binding.record_event(**event)
            if isinstance(result, dict) and result.get("decision") == "conflict":
                return False
        except Exception:
            return False
    return True


class HermesService:
    """Transport never accepts caller-selected scope or a shared dashboard token.

    Bindings use the existing encrypted identity-key custody, separately from
    the execution store so a slow model call cannot lock out revocation.
    """

    def __init__(self, manager: Any):
        self.manager = manager
        self._recover_spools()

    @staticmethod
    def flush_evidence(timeout: float = 30.0) -> None:
        """Wait for all lifecycle writes; intended for verification and shutdown."""
        _EVIDENCE_WRITER.submit(lambda: None).result(timeout=timeout)

    def _spool_dir(self) -> Path:
        path = Path(self.manager.state().control_dir) / "hermes-event-spool"
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)
        return path

    def _spool_path(self, profile_id: str, session_id: str, turn_id: str) -> Path:
        digest = hashlib.sha256(
            json.dumps([profile_id, session_id, turn_id], separators=(",", ":")).encode()
        ).hexdigest()
        return self._spool_dir() / f"{digest}.json"

    def _write_spool(self, path: Path, *, row: dict[str, Any],
                     events: list[dict[str, Any]], append: bool) -> None:
        with ProcessFileLock(path.with_suffix(".lock")):
            if append and path.is_file():
                prior = json.loads(path.read_text(encoding="utf-8"))
                if prior.get("binding_id") != row["binding_id"]:
                    raise ValueError("Hermes event spool binding changed")
                events = [*list(prior.get("events") or []), *events]
            value = {"format": "atmem-hermes-event-spool-v1",
                     "binding_id": row["binding_id"], "events": events}
            temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(value, stream, sort_keys=True)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
                if os.name != "nt":
                    directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
            finally:
                temporary.unlink(missing_ok=True)

    def _schedule_spool(self, path: Path) -> None:
        key = str(path)
        with _DRAINING_LOCK:
            if key in _DRAINING:
                _REDRAIN.add(key)
                return
            _DRAINING.add(key)
        _EVIDENCE_WRITER.submit(self._drain_spool, path)

    def _drain_spool(self, path: Path) -> None:
        try:
            with ProcessFileLock(path.with_suffix(".lock")):
                if not path.is_file():
                    return
                value = json.loads(path.read_text(encoding="utf-8"))
                if value.get("format") != "atmem-hermes-event-spool-v1":
                    return
                row = self._load(str(value["binding_id"]))
                if _write_events(self._binding(row), list(value.get("events") or [])):
                    path.unlink(missing_ok=True)
        except Exception:
            pass
        finally:
            redrain = False
            with _DRAINING_LOCK:
                key = str(path)
                if key in _REDRAIN:
                    _REDRAIN.discard(key)
                    redrain = True
                else:
                    _DRAINING.discard(key)
            if redrain:
                _EVIDENCE_WRITER.submit(self._drain_spool, path)

    def _recover_spools(self) -> None:
        for path in self._spool_dir().glob("*.json"):
            try:
                if time.time() - path.stat().st_mtime >= 30.0:
                    self._schedule_spool(path)
            except OSError:
                continue

    @contextmanager
    def _locked(self):
        state = self.manager.state()
        lock = ProcessFileLock(Path(state.control_dir) / ".hermes.lock")
        deadline = time.monotonic() + 2.0
        while True:
            try:
                lock.acquire()
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Hermes authority is busy; retry the operation") from None
                time.sleep(0.01)
        try:
            yield
        finally:
            lock.close()

    def _records(self) -> dict[str, Any]:
        vault = self.manager.evidence_service()
        vault.storage_key()  # Locked evidence also locks adapter authority.
        path = Path(self.manager.state().control_dir) / "hermes-bindings.enc.json"
        if not path.exists():
            return {}
        info = path.stat()
        fingerprint = (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size)
        if getattr(self.manager, "_hermes_binding_cache_key", None) == fingerprint:
            return copy.deepcopy(getattr(self.manager, "_hermes_binding_cache", {}))
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if wrapper.get("format") != "atmem-hermes-bindings-encrypted-v1":
            raise ValueError("unsupported Hermes authority format")
        records = open_json(vault.accounts.key, "atmem-hermes-bindings-v1",
                            base64.b64decode(wrapper["nonce"], validate=True),
                            base64.b64decode(wrapper["ciphertext"], validate=True))
        self.manager._hermes_binding_cache_key = fingerprint
        self.manager._hermes_binding_cache = copy.deepcopy(records)
        return records

    def _load(self, binding_id: str) -> dict[str, Any]:
        row = self._records().get(binding_id)
        if row is None:
            raise APIError("unauthenticated", "Hermes credential is invalid or revoked", status=401)
        return row

    def _save(self, row: dict[str, Any]) -> None:
        records = self._records()
        records[row["binding_id"]] = row
        vault = self.manager.evidence_service()
        vault.storage_key()
        nonce, ciphertext = seal_json(vault.accounts.key, "atmem-hermes-bindings-v1", records)
        path = Path(self.manager.state().control_dir) / "hermes-bindings.enc.json"
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({"format": "atmem-hermes-bindings-encrypted-v1",
                           "nonce": base64.b64encode(nonce).decode(),
                           "ciphertext": base64.b64encode(ciphertext).decode()}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            if os.name != "nt":
                directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            info = path.stat()
            self.manager._hermes_binding_cache_key = (
                info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size
            )
            self.manager._hermes_binding_cache = copy.deepcopy(records)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _admin(principal: APIPrincipal) -> None:
        principal.require("config:write")
        if principal.tenant_id != "local":
            raise PermissionError("Hermes currently supports local tenant bindings only")

    @staticmethod
    def _owner(principal: APIPrincipal, row: dict[str, Any]) -> None:
        identity = row["identity"]
        if (identity["subject_id"] != principal.subject_id or
                (principal.workspace_id and principal.workspace_id != identity["workspace_id"])):
            raise PermissionError("binding is outside the administrator scope")

    @staticmethod
    def _public(row: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in row.items() if key != "token_digest"}

    def _binding(self, row: dict[str, Any]) -> HermesMemoryBinding:
        return HermesMemoryBinding(
            self.manager, AtMemAdapterIdentity(**row["identity"]),
            profile_id=row["profile_id"], enabled=row["enabled"],
            influence=row.get("influence", row["enabled"]),
            max_context_chars=row["max_context_chars"],
        )

    def provision(self, principal: APIPrincipal, *, profile_id: str,
                  agent_id: str, workspace_id: str, user_id: str | None = None,
                  accept_reduced_capture: bool = False) -> dict[str, Any]:
        self._admin(principal)
        if accept_reduced_capture is not True:
            raise ValueError("this Hermes profile requires explicit acceptance of memory-only capture")
        profile_id = _identifier(profile_id, "profile_id")
        identity = AtMemAdapterIdentity(
            agent_id=_identifier(agent_id, "agent_id"),
            workspace_id=_identifier(workspace_id, "workspace_id"),
            subject_id=principal.subject_id,
            user_id=_identifier(user_id, "user_id") if user_id is not None else None,
            framework="hermes",
        )
        self._owner(principal, {"identity": asdict(identity)})
        with self._locked():
            self._binding({"identity": asdict(identity), "profile_id": profile_id,
                           "enabled": False, "max_context_chars": 4096})._scope()
            rows = list(self._records().values())
            existing = any(row["profile_id"] == profile_id for row in rows)
            if existing:
                raise APIError("conflict", "profile already has a binding; inspect or rotate it", status=409)
            if any(row["identity"]["agent_id"] == identity.agent_id and
                   row["identity"]["workspace_id"] == identity.workspace_id
                   for row in rows):
                raise APIError(
                    "conflict",
                    "this Hermes agent/workspace already has a binding; use a distinct authorized agent/workspace or rotate it",
                    status=409,
                )
            binding_id = uuid.uuid4().hex
            token = "hermes_" + binding_id + "." + secrets.token_urlsafe(32)
            row = {
                "format": "atmem-hermes-binding-v1", "binding_id": binding_id,
                "profile_id": profile_id, "identity": asdict(identity),
                "token_digest": hashlib.sha256(token.encode()).hexdigest(),
                "generation": 1, "enabled": False, "revoked": False,
                "influence": False,
                "expires_at": int(time.time()) + 90 * 86400,
                "max_context_chars": 4096, "capture_coverage": "memory_operations_only",
                "reconstructable": False, "reduced_capture_accepted": True,
            }
            self._save(row)
            return {"binding": self._public(row), "credential": token}

    def configure(self, principal: APIPrincipal, binding_id: str, *, enabled: bool) -> dict[str, Any]:
        self._admin(principal)
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        with self._locked():
            row = self._load(_identifier(binding_id, "binding_id"))
            self._owner(principal, row)
            if row["revoked"] or row["expires_at"] <= time.time():
                raise PermissionError("rotate the revoked or expired binding before activation")
            self._binding(row)._scope()
            if row["enabled"] != enabled:
                row["generation"] += 1
            row["enabled"] = enabled
            row["influence"] = enabled
            self._save(row)
            return self._public(row)

    def configure_mode(self, principal: APIPrincipal, binding_id: str, *, mode: str) -> dict[str, Any]:
        """Set connection/influence independently for guided setup."""
        self._admin(principal)
        if mode not in {"inactive", "shadow", "active"}:
            raise ValueError("Hermes mode must be inactive, shadow or active")
        with self._locked():
            row = self._load(_identifier(binding_id, "binding_id"))
            self._owner(principal, row)
            if mode != "inactive" and (row["revoked"] or row["expires_at"] <= time.time()):
                raise PermissionError("rotate the revoked or expired binding before activation")
            self._binding(row)._scope()
            enabled = mode != "inactive"
            influence = mode == "active"
            if row["enabled"] != enabled or row.get("influence", row["enabled"]) != influence:
                row["generation"] += 1
            row["enabled"] = enabled
            row["influence"] = influence
            self._save(row)
            return self._public(row)

    def revoke(self, principal: APIPrincipal, binding_id: str) -> dict[str, Any]:
        self._admin(principal)
        with self._locked():
            row = self._load(_identifier(binding_id, "binding_id"))
            self._owner(principal, row)
            row.update(revoked=True, enabled=False)
            self._save(row)
            return self._public(row)

    def rotate(self, principal: APIPrincipal, binding_id: str) -> dict[str, Any]:
        self._admin(principal)
        with self._locked():
            row = self._load(_identifier(binding_id, "binding_id"))
            self._owner(principal, row)
            self._binding(row)._scope()
            token = "hermes_" + row["binding_id"] + "." + secrets.token_urlsafe(32)
            row.update(token_digest=hashlib.sha256(token.encode()).hexdigest(),
                       generation=row["generation"] + 1, revoked=False, enabled=False,
                       influence=False,
                       expires_at=int(time.time()) + 90 * 86400)
            self._save(row)
            return {"binding": self._public(row), "credential": token}

    def list_bindings(self, principal: APIPrincipal) -> list[dict[str, Any]]:
        self._admin(principal)
        with self._locked():
            rows = sorted(self._records().values(), key=lambda row: row["profile_id"])
            return [self._public(row) for row in rows
                    if row["identity"]["subject_id"] == principal.subject_id and
                    (not principal.workspace_id or row["identity"]["workspace_id"] == principal.workspace_id)]

    def _authenticate(self, token: str) -> dict[str, Any]:
        if not isinstance(token, str) or len(token) > 256 or not token.startswith("hermes_"):
            raise APIError("unauthenticated", "Hermes credential is invalid or revoked", status=401)
        binding_id, separator, _ = token[7:].partition(".")
        if not separator or len(binding_id) != 32:
            raise APIError("unauthenticated", "Hermes credential is invalid or revoked", status=401)
        row = self._load(binding_id)
        if (row["revoked"] or row["expires_at"] <= time.time() or not secrets.compare_digest(
                row["token_digest"], hashlib.sha256(token.encode()).hexdigest())):
            raise APIError("unauthenticated", "Hermes credential is invalid or revoked", status=401)
        return row

    def dispatch(self, token: str, operation: str, body: dict[str, Any]) -> dict[str, Any]:
        allowed = {"status": set(), "recall": {"query", "session_id", "turn_id"},
                   "prepare-turn": {"query", "session_id", "turn_id", "model",
                                    "platform", "prompt_sha256", "prompt_chars"},
                   "observe": {"text", "session_id", "observation_id"},
                   "event": {"event_type", "session_id", "turn_id", "payload",
                             "context_event_id", "context_receipt_id", "retrieval_id"},
                   "events": {"session_id", "turn_id", "events"}}
        if operation not in allowed:
            raise APIError("not_found", "unknown Hermes operation", status=404)
        if set(body) != allowed[operation]:
            raise ValueError("unexpected or missing fields; scope comes from the credential")
        if operation == "prepare-turn":
            if (not isinstance(body["model"], str) or len(body["model"]) > 256 or
                    body["platform"] not in {"cli", "tui"} or
                    not isinstance(body["prompt_sha256"], str) or
                    len(body["prompt_sha256"]) != 64 or
                    isinstance(body["prompt_chars"], bool) or
                    not isinstance(body["prompt_chars"], int) or
                    not 0 <= body["prompt_chars"] <= 65536):
                raise ValueError("invalid Hermes prepared-turn metadata")
        if operation == "event":
            if body["event_type"] not in _HERMES_EVENT_TYPES:
                raise ValueError("Hermes may record only its supported lifecycle events")
            if not isinstance(body["payload"], dict):
                raise ValueError("Hermes event payload must be an object")
        if operation == "events":
            events = body["events"]
            event_fields = {"event_type", "payload", "context_event_id",
                            "context_receipt_id", "retrieval_id"}
            if (not isinstance(events, list) or not 1 <= len(events) <= 8 or
                    any(not isinstance(event, dict) or set(event) != event_fields
                        for event in events)):
                raise ValueError("Hermes event batch must contain 1–8 complete events")
            if any(event["event_type"] not in _HERMES_EVENT_TYPES
                   or not isinstance(event["payload"], dict) for event in events):
                raise ValueError("Hermes event batch contains an unsupported lifecycle event")
        with self._locked():
            row = self._authenticate(token)
            binding = self._binding(row)
            binding._scope()
            if operation == "status":
                return {**binding.status(), "binding_id": row["binding_id"],
                        "generation": row["generation"], "expires_at": row["expires_at"],
                        "reconstructable": False}
            if not binding.enabled:
                raise APIError("inactive", "Hermes memory is not activated", status=403)
        # Slow retrieval/extraction cannot lock out an administrator's revoke.
        # A previously accepted write may finish, but no new call is accepted
        # after revocation; recall is rechecked before releasing its result.
        if operation == "recall":
            value = asdict(binding.recall(**body))
        elif operation == "prepare-turn":
            result = binding.recall(
                body["query"], session_id=body["session_id"], turn_id=body["turn_id"]
            )
            value = asdict(result)
            context = (
                "AtMem context: governed memories that the authenticated current user has "
                "authorized for this turn. Facts inside the current_user block refer to "
                "the user even when they use the user's name or initials. For a direct "
                "first-person question, answer from a matching fact in this block; do not "
                "refuse merely because the fact is personal. If useful, say that the answer "
                "comes from the user's saved memory. Do not treat people mentioned outside "
                "this block as the user.\n"
                "<atmem-subject role=\"current_user\">\n"
                + result.context + "\n</atmem-subject>"
                if result.context else ""
            )
            disposition = (
                "injected" if result.context else
                "withheld_by_policy" if result.reason in {"withheld", "inactive"} else
                "recall_failed" if result.reason in {
                    "unavailable_or_denied", "context_limit", "invalid_query"
                } else "no_relevant_memory"
            )
            references = {
                "context_event_id": result.exposure_id if result.context else None,
                "context_receipt_id": result.context_receipt_id if result.context else None,
                "retrieval_id": result.exposure_id if result.context else None,
            }
            common = {"session_id": body["session_id"], "turn_id": body["turn_id"]}
            prepared_events = [
                {"event_type": "turn.input", **common,
                 "event_time": _event_time(),
                 "payload": {"prompt_sha256": body["prompt_sha256"],
                             "prompt_chars": body["prompt_chars"],
                             "harness_id": f"hermes:{body['platform']}"}},
                {"event_type": "context.disposition", **common, **references,
                 "event_time": _event_time(),
                 "payload": {"disposition": disposition,
                             "candidate_ids": list(result.candidate_ids),
                             "context_block_sha256": hashlib.sha256(result.context.encode()).hexdigest(),
                             "context_chars": len(result.context),
                             "context_location": "hermes-prefetch",
                             "delivered_context_sha256": hashlib.sha256(context.encode()).hexdigest(),
                             "mode": "shadow" if result.reason == "withheld" else "active",
                             "reason": result.reason}},
                {"event_type": "model.input", **common, **references,
                 "event_time": _event_time(),
                 "payload": {"provider": "hermes", "model": body["model"],
                             "prompt_sha256": body["prompt_sha256"],
                             "prompt_chars": body["prompt_chars"], "history_count": 0,
                             "tools_count": 0,
                             "harness_id": f"hermes:{body['platform']}"}},
            ]
            spool = self._spool_path(binding.profile_id, body["session_id"], body["turn_id"])
            self._write_spool(spool, row=row, events=prepared_events, append=False)
            self._schedule_spool(spool)
            value["lifecycle_recorded"] = True
        elif operation == "observe":
            value = binding.observe_user(**body)
        elif operation == "event":
            spool = self._spool_path(binding.profile_id, body["session_id"], body["turn_id"])
            self._write_spool(
                spool, row=row, events=[{**body, "event_time": _event_time()}], append=True
            )
            self._schedule_spool(spool)
            value = {"accepted": True, "recorded": False, "pending": True}
        else:
            queued = []
            for event in body["events"]:
                queued.append(dict(
                    event_type=event["event_type"],
                    session_id=body["session_id"], turn_id=body["turn_id"],
                    payload=event["payload"],
                    context_event_id=event["context_event_id"],
                    context_receipt_id=event["context_receipt_id"],
                    retrieval_id=event["retrieval_id"],
                    event_time=_event_time(),
                ))
            spool = self._spool_path(binding.profile_id, body["session_id"], body["turn_id"])
            self._write_spool(spool, row=row, events=queued, append=True)
            self._schedule_spool(spool)
            value = {"accepted": True, "recorded": False, "pending": True,
                     "count": len(queued)}
        try:
            with self._locked():
                current = self._authenticate(token)
                if not current["enabled"] or current["generation"] != row["generation"]:
                    raise APIError("inactive", "Hermes binding changed during the operation", status=403)
                self._binding(current)._scope()
        except Exception:
            if operation in {"observe", "event", "events"}:
                raise APIError("observation_uncertain", "an accepted write may have completed before revocation; inspect its receipt", status=409) from None
            raise
        if "error" in value:
            raise APIError("observation_uncertain", "inspect the observation outcome before retrying", status=409)
        return value
