"""The sole supported plaintext boundary for encrypted evidence."""

from __future__ import annotations

from hashlib import sha256
import base64
import json
from pathlib import Path
from typing import Any
from collections.abc import Iterator
import os

from atmem.core.canonical import canonical_json
from atmem.evidence.accounts import EvidenceAccountStore
from atmem.evidence.crypto import encrypted_export, load_existing_key, load_or_create_key, open_json, seal_json, write_key
from atmem.evidence.models import (
    CaptureMode,
    EvidenceOperation,
    EvidencePrincipal,
    EvidenceRole,
    EvidenceScope,
)
from atmem.evidence.store import EncryptedEvidenceStore


class EvidenceService:
    def __init__(self, root: str | Path, *, vault_id: str) -> None:
        self.root = Path(root).expanduser().resolve(strict=False)
        self.vault_id = str(vault_id)
        self.key_path = self.root.parent / ".evidence-keys" / f"{self.vault_id}.key"
        self.vault_path = self.root / "protected-evidence.db"
        self.identity_key_path = self.root.parent / ".evidence-identity-keys" / f"{self.vault_id}.key"
        self._identity_key = load_or_create_key(self.identity_key_path)
        self.locked_key_path = self.key_path.with_suffix(".locked")
        self._key: bytes | None
        try:
            self._key = (
                load_existing_key(self.key_path)
                if self.vault_path.exists()
                else load_or_create_key(self.key_path)
            )
        except FileNotFoundError:
            self._key = None
        self.accounts_path = self.root.parent / ".evidence-accounts" / f"{self.vault_id}.json"
        self.rotation_path = self.key_path.with_suffix(".rotation")
        if self._key is not None and self.rotation_path.exists():
            self._resume_rotation()
        self.accounts = EvidenceAccountStore(self.accounts_path, self._identity_key)
        if self.accounts_path.exists():
            try:
                self.accounts._load()
            except Exception:
                if self._key is None:
                    raise RuntimeError("evidence identity records require migration while the vault key is available")
                legacy_accounts = EvidenceAccountStore(self.accounts_path, self._key)
                value = legacy_accounts._load()
                self.accounts._write(value)

    def _key_opens_vault(self, key: bytes) -> bool:
        try:
            with EncryptedEvidenceStore(self.vault_path, key) as store:
                next(iter(store.documents()), None)
            return True
        except Exception:
            return False

    def _resume_rotation(self) -> None:
        assert self._key is not None
        wrapper = json.loads(self.rotation_path.read_text(encoding="utf-8"))
        try:
            value = open_json(
                self._key,
                f"rotation:{self.vault_id}",
                base64.b64decode(wrapper["nonce"], validate=True),
                base64.b64decode(wrapper["ciphertext"], validate=True),
            )
        except Exception:
            if self._key_opens_vault(self._key):
                self.rotation_path.unlink()
                return
            self._key = None
            return
        candidate = base64.b64decode(value["new_key"], validate=True)
        if self._key_opens_vault(candidate):
            from atmem.control.store import reencrypt_control_container

            control_path = self.root / "evidence.db"
            if control_path.exists():
                reencrypt_control_container(control_path, self._key, candidate)
            write_key(self.key_path, candidate, replace=True)
            self._key = candidate
        self.rotation_path.unlink()

    def _write_rotation_journal(self, new_key: bytes) -> None:
        assert self._key is not None
        nonce, ciphertext = seal_json(
            self._key,
            f"rotation:{self.vault_id}",
            {"format": "atmem-evidence-key-rotation-v1", "new_key": base64.b64encode(new_key).decode()},
        )
        descriptor = os.open(self.rotation_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                {"format": "atmem-encrypted-key-rotation-journal-v1", "nonce": base64.b64encode(nonce).decode(), "ciphertext": base64.b64encode(ciphertext).decode()},
                handle,
                separators=(",", ":"),
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _store(self) -> EncryptedEvidenceStore:
        if self._key is None:
            raise PermissionError(
                "encrypted evidence is locked because its external key is unavailable"
            )
        return EncryptedEvidenceStore(self.vault_path, self._key)

    def storage_key(self) -> bytes:
        if self._key is None:
            raise PermissionError("encrypted evidence is locked")
        return self._key

    def protection_status(self) -> dict[str, Any]:
        from atmem.control.store import ENCRYPTED_CONTROL_MAGIC

        plaintext_sources: list[str] = []
        for candidate in self.root.glob("*.db"):
            if candidate == self.vault_path:
                continue
            try:
                if not candidate.read_bytes()[: len(ENCRYPTED_CONTROL_MAGIC)] == ENCRYPTED_CONTROL_MAGIC:
                    plaintext_sources.append(candidate.name)
            except OSError:
                plaintext_sources.append(candidate.name)
        if self._key is None:
            return {
                "format": "atmem-evidence-protection-status-v1",
                "encrypted": True,
                "locked": True,
                "key_source": "application-locked" if self.locked_key_path.exists() else "external-key-unavailable",
                "capture_mode": "unavailable",
                "data_enabled": False,
                "recorder_enabled": False,
                "plaintext_export_role": EvidenceRole.EVIDENCE_COLLECTOR.value,
                "stored_objects": None,
                "at_rest_state": "encrypted_locked",
                "plaintext_source_exists": bool(plaintext_sources),
                "plaintext_sources": plaintext_sources,
                "recovery_action": "Authenticate as Evidence Collector and unlock AtMem." if self.locked_key_path.exists() else "Restore the configured evidence key, then restart AtMem.",
            }
        with self._store() as store:
            mode = store.capture_mode()
            return {
                "format": "atmem-evidence-protection-status-v1",
                "encrypted": True,
                "locked": False,
                "key_source": "external-mode-0600-development-key",
                "capture_mode": mode.value,
                "data_enabled": mode is CaptureMode.FULL,
                "recorder_enabled": mode is not CaptureMode.OFF,
                "plaintext_export_role": EvidenceRole.EVIDENCE_COLLECTOR.value,
                "stored_objects": store.count(),
                "at_rest_state": "plaintext_source_exists" if plaintext_sources else "encrypted",
                "plaintext_source_exists": bool(plaintext_sources),
                "plaintext_sources": plaintext_sources,
            }

    def set_capture_mode(self, principal: EvidencePrincipal, mode: CaptureMode) -> dict[str, Any]:
        target = EvidenceScope(principal.scope.tenant_id, principal.scope.subject_id)
        principal.authorize(EvidenceOperation.RETENTION, target)
        with self._store() as store:
            store.set_capture_mode(mode, actor=principal.principal_id)
            store.access_event(self._audit(principal, "capture_mode", target, True, mode=mode.value))
        return self.protection_status()

    def capture(self, envelope: dict[str, Any]) -> dict[str, Any]:
        scope = self._scope_from_envelope(envelope)
        with self._store() as store:
            result = store.capture(envelope)
            mode = store.capture_mode()
        return {
            "format": "atmem-protected-capture-receipt-v1",
            "captured": result is not None,
            "capture_mode": mode.value,
            "reconstructable": mode is CaptureMode.FULL,
            "object_id": result.get("object_id") if result else None,
            "scope": scope.to_dict(),
        }

    def events(self, principal: EvidencePrincipal, run_id: str) -> list[dict[str, Any]]:
        target = EvidenceScope(
            principal.scope.tenant_id,
            principal.scope.subject_id,
            principal.scope.workspace_id,
            run_id,
        )
        try:
            principal.authorize(EvidenceOperation.VIEW, target)
        except PermissionError:
            self._record_access(principal, "view", target, False)
            raise
        with self._store() as store:
            values = []
            for item in store.documents():
                if item.get("record_type") != "evidence":
                    continue
                envelope = dict(item.get("envelope") or {})
                item_scope = self._scope_from_envelope(envelope)
                if (
                    principal.scope.permits(item_scope)
                    and str(envelope.get("run_id") or "") == run_id
                ):
                    values.append(item)
            store.access_event(self._audit(principal, "view", target, True, count=len(values)))
        return values

    def reconstruct(self, principal: EvidencePrincipal, run_id: str) -> dict[str, Any]:
        target = EvidenceScope(
            principal.scope.tenant_id,
            principal.scope.subject_id,
            principal.scope.workspace_id,
            run_id,
        )
        try:
            principal.authorize(EvidenceOperation.RECONSTRUCT, target)
        except PermissionError:
            self._record_access(principal, "reconstruct", target, False)
            raise
        events = self.events(principal, run_id)
        reconstructable = bool(events) and all(item.get("reconstructable") is True for item in events)
        self._record_access(
            principal,
            "reconstruct",
            target,
            True,
            event_count=len(events),
            reconstructable=reconstructable,
        )
        return {
            "format": "atmem-evidence-reconstruction-v1",
            "run_id": run_id,
            "reconstructable": reconstructable,
            "events": events,
        }

    def search(self, principal: EvidencePrincipal, query: str) -> list[dict[str, Any]]:
        clean = str(query or "").strip()
        if not clean:
            raise ValueError("evidence search query is required")
        target = EvidenceScope(
            principal.scope.tenant_id,
            principal.scope.subject_id,
            principal.scope.workspace_id,
            principal.scope.run_id,
        )
        try:
            principal.authorize(EvidenceOperation.SEARCH, target)
        except PermissionError:
            self._record_access(principal, "search", target, False)
            raise
        needle = clean.casefold()
        matches: list[dict[str, Any]] = []
        with self._store() as store:
            for item in store.documents():
                if item.get("record_type") != "evidence":
                    continue
                envelope = dict(item.get("envelope") or {})
                scope = self._scope_from_envelope(envelope)
                if principal.scope.permits(scope) and needle in canonical_json(envelope).casefold():
                    matches.append(item)
            store.access_event(self._audit(principal, "search", target, True, count=len(matches)))
        return matches

    def replay_manifest(self, principal: EvidencePrincipal, run_id: str) -> dict[str, Any]:
        target = EvidenceScope(
            principal.scope.tenant_id, principal.scope.subject_id,
            principal.scope.workspace_id, run_id,
        )
        try:
            principal.authorize(EvidenceOperation.REPLAY_MANIFEST, target)
        except PermissionError:
            self._record_access(principal, "replay_manifest", target, False)
            raise
        events = self.events(principal, run_id)
        canonical = canonical_json(events)
        manifest = {
            "format": "atmem-inert-replay-manifest-v1",
            "run_id": run_id,
            "event_count": len(events),
            "events_sha256": sha256(canonical.encode()).hexdigest(),
            "executable": False,
            "warning": "This manifest reconstructs captured inputs; it does not authorize execution.",
        }
        self._record_access(principal, "replay_manifest", target, True)
        return manifest

    def grant(
        self, principal: EvidencePrincipal, *, principal_id: str,
        role: EvidenceRole, scope: EvidenceScope,
    ) -> dict[str, str]:
        principal.authorize(EvidenceOperation.GRANT, scope)
        if not principal.scope.permits(scope):
            raise PermissionError("cannot grant evidence access outside the collector scope")
        credential = self.accounts.grant(principal_id, role, scope)
        self._record_access(principal, "grant", scope, True, grantee=principal_id, role=role.value)
        return credential

    def revoke(self, principal: EvidencePrincipal, *, principal_id: str) -> bool:
        target = principal.scope
        principal.authorize(EvidenceOperation.GRANT, target)
        changed = self.accounts.revoke(principal_id)
        self._record_access(principal, "revoke", target, True, grantee=principal_id, changed=changed)
        return changed

    def delete_run(self, principal: EvidencePrincipal, run_id: str, *, confirmation: str) -> dict[str, Any]:
        target = EvidenceScope(
            principal.scope.tenant_id, principal.scope.subject_id,
            principal.scope.workspace_id, run_id,
        )
        try:
            principal.authorize(EvidenceOperation.DELETE, target)
            if confirmation != f"DELETE {run_id}":
                raise PermissionError("evidence deletion requires exact confirmation")
            with self._store() as store:
                result = store.delete_run(run_id)
                store.access_event(self._audit(principal, "delete", target, True, **result))
            return {"run_id": run_id, "deleted": result}
        except PermissionError:
            self._record_access(principal, "delete", target, False)
            raise

    def rotate_key(self, principal: EvidencePrincipal, *, confirmation: str) -> dict[str, Any]:
        target = principal.scope
        try:
            principal.authorize(EvidenceOperation.ROTATE, target)
            if confirmation != "ROTATE EVIDENCE KEY":
                raise PermissionError("key rotation requires exact confirmation")
            if self._key is None:
                raise PermissionError("evidence vault is locked")
            old_key = self._key
            new_key = os.urandom(32)
            self._write_rotation_journal(new_key)
            with self._store() as store:
                result = store.rotate_key(new_key)
            try:
                from atmem.control.store import reencrypt_control_container

                control_path = self.root / "evidence.db"
                if control_path.exists():
                    reencrypt_control_container(control_path, old_key, new_key)
                write_key(self.key_path, new_key, replace=True)
            except Exception:
                with EncryptedEvidenceStore(self.vault_path, new_key) as store:
                    store.rotate_key(old_key)
                if control_path.exists():
                    reencrypt_control_container(control_path, new_key, old_key)
                raise
            self._key = new_key
            self.rotation_path.unlink(missing_ok=True)
            self._record_access(principal, "rotate", target, True, **result)
            return {"rotated": True, **result}
        except PermissionError:
            self._record_access(principal, "rotate", target, False)
            raise

    def lock(self, principal: EvidencePrincipal, *, confirmation: str) -> dict[str, Any]:
        target = principal.scope
        principal.authorize(EvidenceOperation.LOCK, target)
        if confirmation != "LOCK EVIDENCE":
            raise PermissionError("locking evidence requires exact confirmation")
        if self._key is None:
            return self.protection_status()
        self._record_access(principal, "lock", target, True)
        nonce, ciphertext = seal_json(
            self._identity_key,
            f"locked-key:{self.vault_id}",
            {"format": "atmem-locked-evidence-key-v1", "key": base64.b64encode(self._key).decode()},
        )
        descriptor = os.open(self.locked_key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                {"format": "atmem-locked-evidence-key-wrapper-v1", "nonce": base64.b64encode(nonce).decode(), "ciphertext": base64.b64encode(ciphertext).decode()},
                handle,
                separators=(",", ":"),
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.key_path.unlink()
        self._key = None
        return self.protection_status()

    def unlock(self, principal: EvidencePrincipal, *, confirmation: str) -> dict[str, Any]:
        target = principal.scope
        principal.authorize(EvidenceOperation.UNLOCK, target)
        if confirmation != "UNLOCK EVIDENCE":
            raise PermissionError("unlocking evidence requires exact confirmation")
        if self._key is not None:
            return self.protection_status()
        if not self.locked_key_path.is_file():
            raise PermissionError("no application-locked evidence key is available")
        wrapper = json.loads(self.locked_key_path.read_text(encoding="utf-8"))
        value = open_json(
            self._identity_key,
            f"locked-key:{self.vault_id}",
            base64.b64decode(wrapper["nonce"], validate=True),
            base64.b64decode(wrapper["ciphertext"], validate=True),
        )
        candidate = base64.b64decode(value["key"], validate=True)
        if not self._key_opens_vault(candidate):
            raise PermissionError("locked evidence key does not open this vault")
        write_key(self.key_path, candidate)
        self._key = candidate
        self.locked_key_path.unlink()
        self._record_access(principal, "unlock", target, True)
        return self.protection_status()

    def plaintext_export(
        self,
        principal: EvidencePrincipal,
        run_id: str,
        *,
        confirmation: str,
    ) -> bytes:
        return b"".join(
            self.iter_plaintext_export(
                principal, run_id, confirmation=confirmation
            )
        )

    def iter_plaintext_export(
        self,
        principal: EvidencePrincipal,
        run_id: str,
        *,
        confirmation: str,
    ) -> Iterator[bytes]:
        target = EvidenceScope(
            principal.scope.tenant_id,
            principal.scope.subject_id,
            principal.scope.workspace_id,
            run_id,
        )
        try:
            principal.authorize(EvidenceOperation.PLAINTEXT_EXPORT, target)
            if confirmation != f"EXPORT {run_id}":
                raise PermissionError("plaintext export requires exact confirmation")
            def stream() -> Iterator[bytes]:
                digest = sha256()
                complete = False
                try:
                    opening = b"[\n"
                    digest.update(opening)
                    yield opening
                    first = True
                    with self._store() as store:
                        for item in store.documents():
                            if item.get("record_type") != "evidence":
                                continue
                            envelope = dict(item.get("envelope") or {})
                            if (
                                str(envelope.get("run_id") or "") != run_id
                                or not principal.scope.permits(self._scope_from_envelope(envelope))
                            ):
                                continue
                            chunk = (("" if first else ",\n") + json.dumps(item, sort_keys=True)).encode()
                            first = False
                            digest.update(chunk)
                            yield chunk
                    closing = b"\n]\n"
                    digest.update(closing)
                    yield closing
                    complete = True
                finally:
                    self._record_access(
                        principal,
                        "plaintext_export",
                        target,
                        complete,
                        sha256=digest.hexdigest() if complete else None,
                        interrupted=not complete,
                    )
            return stream()
        except PermissionError:
            self._record_access(principal, "plaintext_export", target, False)
            raise

    def recipient_export(
        self,
        principal: EvidencePrincipal,
        run_id: str,
        *,
        recipient_public_key: bytes,
        signing_secret_key: bytes,
        signing_public_key: bytes,
    ) -> dict[str, Any]:
        target = EvidenceScope(
            principal.scope.tenant_id,
            principal.scope.subject_id,
            principal.scope.workspace_id,
            run_id,
        )
        try:
            principal.authorize(EvidenceOperation.ENCRYPTED_EXPORT, target)
            content = canonical_json(self.events(principal, run_id)).encode()
            bundle = encrypted_export(
                content,
                recipient_public_key=recipient_public_key,
                signing_secret_key=signing_secret_key,
                signing_public_key=signing_public_key,
            )
            self._record_access(principal, "encrypted_export", target, True)
            return bundle
        except PermissionError:
            self._record_access(principal, "encrypted_export", target, False)
            raise

    def create_demo_accounts(self, *, subject_id: str) -> list[dict[str, str]]:
        return self.accounts.create_demo_accounts(
            EvidenceScope("local", subject_id)
        )

    def authenticate(self, token: str) -> EvidencePrincipal | None:
        return self.accounts.authenticate(token)

    def _record_access(
        self,
        principal: EvidencePrincipal,
        operation: str,
        target: EvidenceScope,
        allowed: bool,
        **detail: Any,
    ) -> None:
        with self._store() as store:
            store.access_event(self._audit(principal, operation, target, allowed, **detail))

    @staticmethod
    def _audit(
        principal: EvidencePrincipal,
        operation: str,
        target: EvidenceScope,
        allowed: bool,
        **detail: Any,
    ) -> dict[str, Any]:
        return {
            "principal_id": principal.principal_id,
            "role": principal.role.value,
            "operation": operation,
            "target_scope": target.to_dict(),
            "allowed": allowed,
            "detail": detail,
        }

    @staticmethod
    def _scope_from_envelope(envelope: dict[str, Any]) -> EvidenceScope:
        return EvidenceScope(
            tenant_id=str(envelope.get("tenant_id") or "local"),
            subject_id=str(envelope.get("subject_id") or "local-user"),
            workspace_id=str(envelope.get("workspace_id")) if envelope.get("workspace_id") else None,
            run_id=str(envelope.get("run_id")) if envelope.get("run_id") else None,
        )
