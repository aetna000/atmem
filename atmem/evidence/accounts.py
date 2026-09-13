"""Explicit development identities for exercising evidence privileges."""

from __future__ import annotations

import base64
from hashlib import scrypt
import json
import os
from pathlib import Path
import secrets
from typing import Any

from atmem.evidence.crypto import open_json, seal_json
from atmem.evidence.models import EvidencePrincipal, EvidenceRole, EvidenceScope


ACCOUNT_OBJECT_ID = "obj_accounts"


def _digest(secret: str, salt: bytes) -> bytes:
    return scrypt(secret.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


class EvidenceAccountStore:
    def __init__(self, path: str | Path, key: bytes) -> None:
        self.path = Path(path).expanduser().resolve(strict=False)
        self.key = key

    def create_demo_accounts(self, scope: EvidenceScope) -> list[dict[str, str]]:
        if self.path.exists():
            raise ValueError("evidence test accounts already exist")
        accounts: list[dict[str, Any]] = []
        credentials: list[dict[str, str]] = []
        for principal_id, role in (
            ("atmem-viewer", EvidenceRole.VIEWER),
            ("atmem-investigator", EvidenceRole.INVESTIGATOR),
            ("atmem-evidence-collector", EvidenceRole.EVIDENCE_COLLECTOR),
        ):
            # A stable non-option prefix keeps tokens safe as direct CLI values.
            token = "atmem_" + secrets.token_urlsafe(32)
            salt = os.urandom(16)
            accounts.append(
                {
                    "principal_id": principal_id,
                    "role": role.value,
                    "scope": scope.to_dict(),
                    "salt": base64.b64encode(salt).decode(),
                    "token_digest": base64.b64encode(_digest(token, salt)).decode(),
                }
            )
            credentials.append(
                {"principal_id": principal_id, "role": role.value, "token": token}
            )
        nonce, ciphertext = seal_json(
            self.key,
            ACCOUNT_OBJECT_ID,
            {"format": "atmem-evidence-test-accounts-v1", "accounts": accounts},
        )
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "format": "atmem-encrypted-account-file-v1",
                    "nonce": base64.b64encode(nonce).decode(),
                    "ciphertext": base64.b64encode(ciphertext).decode(),
                },
                handle,
                separators=(",", ":"),
            )
            handle.write("\n")
        return credentials

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"format": "atmem-evidence-test-accounts-v1", "accounts": []}
        wrapper = json.loads(self.path.read_text(encoding="utf-8"))
        return open_json(
            self.key,
            ACCOUNT_OBJECT_ID,
            base64.b64decode(wrapper["nonce"], validate=True),
            base64.b64decode(wrapper["ciphertext"], validate=True),
        )

    def _write(self, value: dict[str, Any]) -> None:
        nonce, ciphertext = seal_json(self.key, ACCOUNT_OBJECT_ID, value)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "format": "atmem-encrypted-account-file-v1",
                        "nonce": base64.b64encode(nonce).decode(),
                        "ciphertext": base64.b64encode(ciphertext).decode(),
                    },
                    handle,
                    separators=(",", ":"),
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def grant(self, principal_id: str, role: EvidenceRole, scope: EvidenceScope) -> dict[str, str]:
        value = self._load()
        if any(row.get("principal_id") == principal_id and not row.get("revoked") for row in value["accounts"]):
            raise ValueError("an active evidence grant already exists for this principal")
        token = "atmem_" + secrets.token_urlsafe(32)
        salt = os.urandom(16)
        value["accounts"].append(
            {
                "principal_id": principal_id,
                "role": role.value,
                "scope": scope.to_dict(),
                "salt": base64.b64encode(salt).decode(),
                "token_digest": base64.b64encode(_digest(token, salt)).decode(),
                "revoked": False,
            }
        )
        self._write(value)
        return {"principal_id": principal_id, "role": role.value, "token": token}

    def revoke(self, principal_id: str) -> bool:
        value = self._load()
        changed = False
        for row in value["accounts"]:
            if row.get("principal_id") == principal_id and not row.get("revoked"):
                row["revoked"] = True
                changed = True
        if changed:
            self._write(value)
        return changed

    def rotate_key(self, new_key: bytes) -> None:
        value = self._load()
        old_key = self.key
        self.key = new_key
        try:
            self._write(value)
        except Exception:
            self.key = old_key
            raise

    def authenticate(self, token: str) -> EvidencePrincipal | None:
        if not self.path.is_file() or not token:
            return None
        value = self._load()
        for row in value.get("accounts") or []:
            if row.get("revoked"):
                continue
            salt = base64.b64decode(row["salt"], validate=True)
            expected = base64.b64decode(row["token_digest"], validate=True)
            if secrets.compare_digest(_digest(token, salt), expected):
                scope = row["scope"]
                return EvidencePrincipal(
                    principal_id=str(row["principal_id"]),
                    role=EvidenceRole(str(row["role"])),
                    scope=EvidenceScope(
                        tenant_id=str(scope["tenant_id"]),
                        subject_id=str(scope["subject_id"]),
                        workspace_id=scope.get("workspace_id"),
                        run_id=scope.get("run_id"),
                    ),
                )
        return None
