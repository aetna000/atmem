from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from hashlib import scrypt, sha256
import os
from pathlib import Path
import secrets
from typing import Any, Callable

from atmem.evidence.crypto import load_or_create_key
from atmem.evidence.models import EvidencePrincipal, EvidenceRole, EvidenceScope
from atmem.identity.models import LocalRole, normalize_username, validate_password
from atmem.identity.store import EncryptedIdentityDocument


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _password_hash(password: str, salt: bytes) -> bytes:
    return scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)


def _temporary_password() -> str:
    # 32 random bytes provide 256 bits before URL-safe encoding.
    return "AtMem-" + secrets.token_urlsafe(32)


class LocalIdentityService:
    IDLE = timedelta(minutes=30)
    ABSOLUTE = timedelta(hours=12)

    def __init__(
        self,
        root: str | Path,
        *,
        vault_id: str,
        subject_id: str,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        base = Path(root).expanduser().resolve(strict=False)
        identity_root = base.parent / ".local-identity"
        key = load_or_create_key(base.parent / ".evidence-identity-keys" / f"{vault_id}.key")
        self.subject_id = subject_id
        self.clock = clock
        self.accounts = EncryptedIdentityDocument(
            identity_root / f"{vault_id}-accounts.json",
            key,
            f"local-accounts:{vault_id}",
            {"format": "atmem-local-accounts-v1", "accounts": [], "audit": []},
        )
        self.sessions = EncryptedIdentityDocument(
            identity_root / f"{vault_id}-sessions.json",
            key,
            f"local-sessions:{vault_id}",
            {"format": "atmem-local-sessions-v1", "sessions": [], "throttle": {}},
        )

    @property
    def initialized(self) -> bool:
        return self.accounts.path.is_file() and bool(self.accounts.load().get("accounts"))

    def _audit(self, value: dict[str, Any], operation: str, actor: str, target: str, allowed: bool) -> None:
        value.setdefault("audit", []).append(
            {
                "event_id": secrets.token_hex(16),
                "operation": operation,
                "actor": actor,
                "target": target,
                "allowed": bool(allowed),
                "recorded_at": _iso(self.clock()),
            }
        )

    def _account_public(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "username": row["username"],
            "display_name": row.get("display_name") or row["username"],
            "role": row["role"],
            "scope": dict(row["scope"]),
            "enabled": bool(row.get("enabled", True)),
            "password_change_required": bool(row.get("password_change_required")),
            "revision": int(row.get("revision", 1)),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def _new_account(self, username: str, password: str, role: LocalRole, display_name: str = "") -> dict[str, Any]:
        canonical = normalize_username(username)
        validate_password(password, canonical)
        salt = os.urandom(16)
        now = _iso(self.clock())
        return {
            "username": canonical,
            "display_name": str(display_name or canonical).strip()[:128],
            "role": role.value,
            "scope": {"tenant_id": "local", "subject_id": self.subject_id, "workspace_id": None, "run_id": None},
            "enabled": True,
            "revision": 1,
            "password_change_required": True,
            "password": {
                "format": "scrypt-v1",
                "n": 2**14,
                "r": 8,
                "p": 1,
                "salt": base64.b64encode(salt).decode("ascii"),
                "digest": base64.b64encode(_password_hash(password, salt)).decode("ascii"),
            },
            "created_at": now,
            "updated_at": now,
        }

    def bootstrap(self) -> dict[str, Any]:
        if self.initialized:
            return {"created": False, "username": "administrator", "password": None}
        password = _temporary_password()
        value = self.accounts.load()
        value["accounts"] = [self._new_account("administrator", password, LocalRole.ADMINISTRATOR, "Local Administrator")]
        self._audit(value, "bootstrap", "local-os-owner", "administrator", True)
        self.accounts.write(value)
        self.sessions.write(self.sessions.load())
        return {"created": True, "username": "administrator", "password": password, "password_change_required": True}

    def _find(self, value: dict[str, Any], username: str) -> dict[str, Any] | None:
        try:
            canonical = normalize_username(username)
        except ValueError:
            return None
        return next((row for row in value.get("accounts", []) if row.get("username") == canonical), None)

    def _verify(self, row: dict[str, Any], password: str) -> bool:
        verifier = row.get("password") or {}
        if verifier.get("format") != "scrypt-v1":
            return False
        try:
            salt = base64.b64decode(verifier["salt"], validate=True)
            expected = base64.b64decode(verifier["digest"], validate=True)
            actual = _password_hash(password, salt)
        except (KeyError, TypeError, ValueError):
            return False
        return secrets.compare_digest(actual, expected)

    def _session_projection(self, row: dict[str, Any], token: str) -> dict[str, Any]:
        account = self._find(self.accounts.load(), row["username"])
        if account is None:
            raise PermissionError("account no longer exists")
        return {
            "authenticated": True,
            "session_token": token,
            "csrf_token": row["csrf_token"],
            "account": self._account_public(account),
            "expires_at": row["absolute_expires_at"],
        }

    def login(self, username: str, password: str, *, source: str = "loopback") -> dict[str, Any]:
        accounts = self.accounts.load()
        sessions = self.sessions.load()
        try:
            canonical = normalize_username(username)
        except ValueError:
            canonical = "invalid"
        bucket = f"{canonical}:{source}"
        throttle = sessions.setdefault("throttle", {}).get(bucket) or {"failures": 0, "blocked_until": None}
        now = self.clock()
        if throttle.get("blocked_until") and _parse(throttle["blocked_until"]) > now:
            raise PermissionError("sign-in temporarily unavailable; wait and try again")
        row = self._find(accounts, canonical)
        allowed = bool(row and row.get("enabled", True) and self._verify(row, password))
        if not allowed:
            failures = int(throttle.get("failures", 0)) + 1
            sessions["throttle"][bucket] = {
                "failures": failures,
                "blocked_until": _iso(now + timedelta(seconds=30)) if failures >= 5 else None,
            }
            if failures >= 5:
                self._audit(accounts, "login_failure_threshold", canonical, canonical, False)
                self.accounts.write(accounts)
            self.sessions.write(sessions)
            raise PermissionError("username or password is incorrect")
        sessions["throttle"].pop(bucket, None)
        token = secrets.token_urlsafe(32)
        session = {
            "token_sha256": sha256(token.encode()).hexdigest(),
            "username": row["username"],
            "account_revision": int(row.get("revision", 1)),
            "csrf_token": secrets.token_urlsafe(24),
            "created_at": _iso(now),
            "last_seen_at": _iso(now),
            "idle_expires_at": _iso(now + self.IDLE),
            "absolute_expires_at": _iso(now + self.ABSOLUTE),
        }
        sessions.setdefault("sessions", []).append(session)
        self._audit(accounts, "login", row["username"], row["username"], True)
        self.accounts.write(accounts)
        self.sessions.write(sessions)
        return self._session_projection(session, token)

    def authenticate_session(self, token: str, *, touch: bool = True) -> dict[str, Any] | None:
        if not token:
            return None
        value = self.sessions.load()
        digest = sha256(token.encode()).hexdigest()
        row = next((item for item in value.get("sessions", []) if secrets.compare_digest(item.get("token_sha256", ""), digest)), None)
        if row is None:
            return None
        account = self._find(self.accounts.load(), row["username"])
        now = self.clock()
        if (
            account is None
            or not account.get("enabled", True)
            or int(account.get("revision", 1)) != int(row.get("account_revision", 0))
            or _parse(row["idle_expires_at"]) <= now
            or _parse(row["absolute_expires_at"]) <= now
        ):
            value["sessions"] = [item for item in value["sessions"] if item is not row]
            self.sessions.write(value)
            return None
        if touch:
            row["last_seen_at"] = _iso(now)
            row["idle_expires_at"] = _iso(min(now + self.IDLE, _parse(row["absolute_expires_at"])))
            self.sessions.write(value)
        return self._session_projection(row, token)

    def logout(self, token: str) -> None:
        session = self.authenticate_session(token, touch=False)
        value = self.sessions.load()
        digest = sha256(token.encode()).hexdigest()
        value["sessions"] = [row for row in value.get("sessions", []) if not secrets.compare_digest(row.get("token_sha256", ""), digest)]
        self.sessions.write(value)
        if session:
            accounts = self.accounts.load()
            username = session["account"]["username"]
            self._audit(accounts, "logout", username, username, True)
            self.accounts.write(accounts)

    def _replace_password(self, row: dict[str, Any], password: str, *, required: bool) -> None:
        validate_password(password, row["username"])
        salt = os.urandom(16)
        row["password"] = {
            "format": "scrypt-v1", "n": 2**14, "r": 8, "p": 1,
            "salt": base64.b64encode(salt).decode("ascii"),
            "digest": base64.b64encode(_password_hash(password, salt)).decode("ascii"),
        }
        row["password_change_required"] = required
        row["revision"] = int(row.get("revision", 1)) + 1
        row["updated_at"] = _iso(self.clock())

    def change_password(self, token: str, current_password: str, new_password: str) -> dict[str, Any]:
        session = self.authenticate_session(token, touch=False)
        if session is None:
            raise PermissionError("sign-in required")
        accounts = self.accounts.load()
        row = self._find(accounts, session["account"]["username"])
        assert row is not None
        # This restricted session has just authenticated the temporary credential.
        # Asking for it a second time adds friction without another auth factor.
        if not row.get("password_change_required") and not self._verify(row, current_password):
            raise PermissionError("current password is incorrect")
        self._replace_password(row, new_password, required=False)
        self._audit(accounts, "password_change", row["username"], row["username"], True)
        self.accounts.write(accounts)
        sessions = self.sessions.load()
        sessions["sessions"] = []
        self.sessions.write(sessions)
        return self.login(row["username"], new_password)

    def require_administrator(self, token: str, *, allow_temporary: bool = False) -> dict[str, Any]:
        session = self.authenticate_session(token)
        if session is None:
            value = self.accounts.load()
            self._audit(value, "administration_denied", "unauthenticated", "local-users", False)
            self.accounts.write(value)
            raise PermissionError("sign-in required")
        account = session["account"]
        if account["password_change_required"] and not allow_temporary:
            value = self.accounts.load(); self._audit(value, "administration_denied", account["username"], "local-users", False); self.accounts.write(value)
            raise PermissionError("password change required")
        if account["role"] != LocalRole.ADMINISTRATOR.value:
            value = self.accounts.load(); self._audit(value, "administration_denied", account["username"], "local-users", False); self.accounts.write(value)
            raise PermissionError("Administrator access required")
        return session

    def revoke_all_sessions(self, token: str, *, reason: str) -> dict[str, Any]:
        """Rotate web sessions after a privileged home/identity transition."""

        actor = self.require_administrator(token)["account"]["username"]
        sessions = self.sessions.load()
        revoked = len(sessions.get("sessions") or [])
        sessions["sessions"] = []
        sessions["throttle"] = {}
        self.sessions.write(sessions)
        accounts = self.accounts.load()
        self._audit(accounts, "sessions_revoked", actor, reason, True)
        self.accounts.write(accounts)
        return {"revoked_sessions": revoked, "reason": reason}

    def list_users(self, token: str) -> list[dict[str, Any]]:
        self.require_administrator(token)
        return [self._account_public(row) for row in self.accounts.load().get("accounts", [])]

    def security_audit(self, token: str, *, limit: int = 100) -> list[dict[str, Any]]:
        self.require_administrator(token)
        return list(self.accounts.load().get("audit", []))[-max(1, min(int(limit), 500)):]

    def create_user(self, token: str, username: str, role: str, *, display_name: str = "") -> dict[str, Any]:
        actor = self.require_administrator(token)["account"]["username"]
        selected = LocalRole(role)
        password = _temporary_password()
        value = self.accounts.load()
        canonical = normalize_username(username)
        if self._find(value, canonical):
            raise ValueError("username already exists")
        row = self._new_account(canonical, password, selected, display_name)
        value["accounts"].append(row)
        self._audit(value, "user_create", actor, canonical, True)
        self.accounts.write(value)
        return {**self._account_public(row), "temporary_password": password}

    def update_user(self, token: str, username: str, *, enabled: bool | None = None, role: str | None = None) -> dict[str, Any]:
        actor = self.require_administrator(token)["account"]["username"]
        value = self.accounts.load()
        row = self._find(value, username)
        if row is None:
            raise ValueError("user not found")
        new_role = LocalRole(role).value if role is not None else row["role"]
        new_enabled = bool(enabled) if enabled is not None else bool(row.get("enabled", True))
        if row["role"] == LocalRole.ADMINISTRATOR.value and (new_role != row["role"] or not new_enabled):
            active_admins = [item for item in value["accounts"] if item.get("enabled", True) and item.get("role") == LocalRole.ADMINISTRATOR.value]
            if len(active_admins) <= 1:
                raise ValueError("the final enabled Administrator cannot be disabled or demoted")
        row["role"] = new_role
        row["enabled"] = new_enabled
        row["revision"] = int(row.get("revision", 1)) + 1
        row["updated_at"] = _iso(self.clock())
        self._audit(value, "user_update", actor, row["username"], True)
        self.accounts.write(value)
        return self._account_public(row)

    def reset_password(self, token: str, username: str) -> dict[str, Any]:
        actor = self.require_administrator(token)["account"]["username"]
        value = self.accounts.load()
        row = self._find(value, username)
        if row is None:
            raise ValueError("user not found")
        password = _temporary_password()
        self._replace_password(row, password, required=True)
        self._audit(value, "password_reset", actor, row["username"], True)
        self.accounts.write(value)
        return {**self._account_public(row), "temporary_password": password}

    def recover_administrator(self, confirmation: str) -> dict[str, Any]:
        if confirmation != "RECOVER LOCAL ADMINISTRATOR":
            raise ValueError("type RECOVER LOCAL ADMINISTRATOR to confirm")
        for path in (self.accounts.path, self.sessions.path, self.accounts.path.parent):
            if path.exists() and hasattr(os, "getuid"):
                stat = path.stat()
                if stat.st_uid != os.getuid() or stat.st_mode & 0o022:
                    raise PermissionError("local identity files must be owned by the current OS user and not group/other writable")
        value = self.accounts.load()
        row = next((item for item in value.get("accounts", []) if item.get("role") == LocalRole.ADMINISTRATOR.value), None)
        if row is None:
            raise ValueError("no local Administrator exists")
        password = _temporary_password()
        row["enabled"] = True
        self._replace_password(row, password, required=True)
        self._audit(value, "administrator_recovery", "local-os-owner", row["username"], True)
        self.accounts.write(value)
        sessions = self.sessions.load()
        sessions["sessions"] = []
        sessions["throttle"] = {}
        self.sessions.write(sessions)
        return {"username": row["username"], "temporary_password": password, "password_change_required": True}

    def evidence_principal(self, session: dict[str, Any]) -> EvidencePrincipal:
        account = session["account"]
        scope = account["scope"]
        return EvidencePrincipal(
            account["username"],
            EvidenceRole(account["role"]),
            EvidenceScope(scope["tenant_id"], scope["subject_id"], scope.get("workspace_id"), scope.get("run_id")),
        )
