"""Delegated HTTP authentication v1. No query, context or secret logging.

This boundary authenticates transport, not the truth of a provider response.
See docs/contracts/delegated-request-auth-v1.md for the interoperable byte format.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import tempfile
import time
from typing import Any, Iterator, Mapping

PROFILE = "atmem-hmac-sha256-v1"
MAX_LIFETIME = 30
MAX_SKEW = 5
MAX_OVERLAP = 300
FIELDS = ("Profile", "Provider", "Instance", "Key-Id", "Issued", "Expires", "Nonce")
PREFIX = "X-AtMem-"
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,256}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


class AuthenticationError(ValueError):
    """Safe, content-free transport failure."""


def private_read(path: str | Path, limit: int = 65536) -> bytes:
    try:
        path = Path(path).expanduser()
        if not path.is_absolute() or path.parent.is_symlink():
            raise ValueError()
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                    or info.st_uid != os.getuid() or info.st_nlink != 1):
                raise ValueError()
            raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise ValueError()
            return raw
    except (OSError, ValueError) as exc:
        raise AuthenticationError("request credential file must be a private owner-only regular file") from exc


def load_secret(path: str | Path) -> bytes:
    try:
        encoded = private_read(path, 128).strip()
        key = base64.b64decode(encoded, validate=True)
        if len(key) != 32 or base64.b64encode(key) != encoded:
            raise ValueError()
        return key
    except (ValueError, TypeError) as exc:
        raise AuthenticationError("request credential must contain a base64-encoded 32-byte secret") from exc


def _private_directory(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
        raise AuthenticationError("request authentication directory must be owner-only")


def _atomic_json(path: Path, value: Any) -> None:
    _private_directory(path.parent)
    if path.is_symlink():
        raise AuthenticationError("unsafe request authentication configuration")
    fd, name = tempfile.mkstemp(prefix=".auth-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def _keyring_lock(path: Path) -> Iterator[None]:
    _private_directory(path.parent)
    fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
            raise AuthenticationError("unsafe authentication lock")
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _new_key(root: Path) -> dict[str, Any]:
    key_id = "request-" + secrets.token_hex(12)
    path = root / (key_id + ".key")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(base64.b64encode(secrets.token_bytes(32)) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return {"key_id": key_id, "secret_file": str(path), "valid_until": None}


def load_keyring(path: Path) -> dict[str, Any]:
    try:
        from atmem.delegated.validation import parse_json_strict
        value = parse_json_strict(private_read(path))
        if set(value) != {"profile", "provider_id", "instance_id", "active_key_id", "keys"} or value["profile"] != PROFILE:
            raise ValueError()
        for field in ("provider_id", "instance_id", "active_key_id"):
            if not isinstance(value[field], str) or not _ID.fullmatch(value[field]):
                raise ValueError()
        keys = value["keys"]
        if not isinstance(keys, list) or not 1 <= len(keys) <= 2:
            raise ValueError()
        ids = set()
        for key in keys:
            if set(key) != {"key_id", "secret_file", "valid_until"} or not _ID.fullmatch(key["key_id"]):
                raise ValueError()
            if key["key_id"] in ids or not isinstance(key["secret_file"], str):
                raise ValueError()
            ids.add(key["key_id"])
            if key["valid_until"] is not None and (type(key["valid_until"]) is not int or key["valid_until"] <= 0):
                raise ValueError()
            if key["key_id"] == value["active_key_id"] and key["valid_until"] is not None:
                raise ValueError()
        if value["active_key_id"] not in ids:
            raise ValueError()
        return value
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError("request authentication setup required; use provider auth-init") from exc


def configure_keyring(path: Path, *, provider_id: str, instance_id: str,
                      rotate: bool = False, overlap_seconds: int = 30) -> dict[str, Any]:
    path = path.absolute()
    if not _ID.fullmatch(provider_id) or not _ID.fullmatch(instance_id):
        raise ValueError("invalid transport identity")
    if type(overlap_seconds) is not int or not 0 <= overlap_seconds <= MAX_OVERLAP:
        raise ValueError("rotation overlap must be between 0 and 300 seconds")
    with _keyring_lock(path):
        old = None
        if rotate:
            old = load_keyring(path)
            if (old["provider_id"], old["instance_id"]) != (provider_id, instance_id):
                raise ValueError("transport identity mismatch")
        elif path.exists():
            raise ValueError("request authentication already configured; use auth-rotate")
        key = _new_key(path.parent)
        keys = [key]
        if old and overlap_seconds:
            previous = next(row for row in old["keys"] if row["key_id"] == old["active_key_id"])
            keys.append({**previous, "valid_until": int(time.time()) + overlap_seconds})
        value = {"profile": PROFILE, "provider_id": provider_id, "instance_id": instance_id,
                 "active_key_id": key["key_id"], "keys": keys}
        _atomic_json(path, value)
    return {"request_key_id": key["key_id"], "request_secret_file": key["secret_file"],
            "transport_profile": PROFILE, "previous_valid_until": keys[-1]["valid_until"] if len(keys) > 1 else None}


def revoke_key(path: Path, key_id: str) -> None:
    with _keyring_lock(path):
        value = load_keyring(path)
        if key_id == value["active_key_id"]:
            raise ValueError("rotate before revoking the active request key")
        if key_id not in {key["key_id"] for key in value["keys"]}:
            raise ValueError("request key is not in the keyring")
        value["keys"] = [key for key in value["keys"] if key["key_id"] != key_id]
        _atomic_json(path, value)


def signing_input(method: str, authority: str, target: str, body: bytes,
                  fields: Mapping[str, str]) -> bytes:
    parts = [fields["Profile"], method, authority, target, fields["Provider"],
             fields["Instance"], fields["Key-Id"], fields["Issued"], fields["Expires"],
             fields["Nonce"], hashlib.sha256(body).hexdigest()]
    if any(not part or any(ord(c) < 33 or ord(c) > 126 for c in part) for part in parts):
        raise AuthenticationError("invalid request authentication fields")
    return ("\n".join(parts) + "\n").encode("ascii")


def sign_headers(*, secret: bytes, provider_id: str, instance_id: str, key_id: str,
                 method: str, authority: str, target: str, body: bytes = b"",
                 now: int | None = None, nonce: str | None = None) -> dict[str, str]:
    issued = int(time.time()) if now is None else now
    fields = dict(zip(FIELDS, (PROFILE, provider_id, instance_id, key_id,
                              str(issued), str(issued + MAX_LIFETIME), nonce or secrets.token_hex(32))))
    signature = hmac.new(secret, signing_input(method, authority, target, body, fields), hashlib.sha256).hexdigest()
    return {**{PREFIX + key: value for key, value in fields.items()}, PREFIX + "Signature": signature}


class ReplayLedger:
    """Atomic durable nonce reservation; errors reject, never reset the ledger."""
    def __init__(self, path: Path, capacity: int = 100_000):
        self.path, self.capacity = path.absolute(), capacity
        _private_directory(self.path.parent)
        marker = self.path.with_name(self.path.name + ".initialized")
        initialized = marker.exists()
        if initialized and private_read(marker) != b"atmem-replay-v1\n":
            raise AuthenticationError("invalid request replay storage marker")
        if initialized and not self.path.exists():
            raise AuthenticationError("request replay storage missing; refusing to reset")
        created = False
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            created = True
        except FileExistsError:
            fd = os.open(self.path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise AuthenticationError("unsafe request replay storage")
        finally:
            os.close(fd)
        schema = {
            "nonces": "CREATE TABLE nonces (scope TEXT, nonce TEXT, expires INTEGER, PRIMARY KEY(scope, nonce))",
            "clock": "CREATE TABLE clock (id INTEGER PRIMARY KEY CHECK(id=1), highwater INTEGER NOT NULL)",
            "nonce_expiry": "CREATE INDEX nonce_expiry ON nonces(expires)",
        }
        try:
            with sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True) as db:
                if created:
                    db.execute("BEGIN IMMEDIATE")
                    for statement in schema.values():
                        db.execute(statement)
                    db.execute("PRAGMA user_version=1")
                else:
                    actual = dict(db.execute("SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL"))
                    if (actual != schema or db.execute("PRAGMA user_version").fetchone()[0] != 1
                            or db.execute("PRAGMA quick_check").fetchall() != [("ok",)]):
                        raise AuthenticationError("request replay storage invalid; refusing to reset")
            if not initialized:
                fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(b"atmem-replay-v1\n")
                    stream.flush()
                    os.fsync(stream.fileno())
        except sqlite3.Error as exc:
            raise AuthenticationError("request replay storage unavailable") from exc

    def reserve(self, scope: str, nonce: str, expires: int, now: int) -> None:
        try:
            with sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=2) as db:
                db.execute("BEGIN IMMEDIATE")
                previous = db.execute("SELECT highwater FROM clock WHERE id=1").fetchone()
                if previous and now < previous[0]:
                    raise AuthenticationError("request clock moved backwards")
                db.execute("INSERT INTO clock VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET highwater=excluded.highwater", (now,))
                db.execute("DELETE FROM nonces WHERE expires <= ?", (now,))
                if db.execute("SELECT COUNT(*) FROM nonces").fetchone()[0] >= self.capacity:
                    raise AuthenticationError("request replay capacity exhausted")
                db.execute("INSERT INTO nonces VALUES (?, ?, ?)", (scope, nonce, expires))
        except sqlite3.IntegrityError as exc:
            raise AuthenticationError("request replay rejected") from exc
        except sqlite3.Error as exc:
            raise AuthenticationError("request replay storage unavailable") from exc


class RequestAuthenticator:
    def __init__(self, keyring: Path, replay_path: Path):
        self.keyring = keyring.absolute()
        value = load_keyring(self.keyring)
        self.identity = (value["provider_id"], value["instance_id"])
        for key in value["keys"]:
            load_secret(key["secret_file"])
        with _keyring_lock(self.keyring):
            self.ledger = ReplayLedger(replay_path)

    def verify(self, *, method: str, target: str, headers: Any, body: bytes) -> None:
        def single(name: str) -> str:
            values = headers.get_all(name, [])
            if len(values) != 1:
                raise AuthenticationError("request authentication required")
            return values[0]
        try:
            fields = {key: single(PREFIX + key) for key in FIELDS}
            signature = single(PREFIX + "Signature")
            authority = single("Host")
            if fields["Profile"] != PROFILE or not _HEX.fullmatch(signature) or not _HEX.fullmatch(fields["Nonce"]):
                raise AuthenticationError("invalid request authentication")
            if any(not _ID.fullmatch(fields[key]) for key in ("Provider", "Instance", "Key-Id")):
                raise AuthenticationError("invalid request identity")
            if any(not re.fullmatch(r"[1-9][0-9]{0,11}", fields[key]) for key in ("Issued", "Expires")):
                raise AuthenticationError("invalid request time")
            issued, expires, now = int(fields["Issued"]), int(fields["Expires"]), int(time.time())
            if not issued < expires <= issued + MAX_LIFETIME or issued > now + MAX_SKEW or now >= expires:
                raise AuthenticationError("request expired or outside time window")
            with _keyring_lock(self.keyring):
                now = int(time.time())
                if issued > now + MAX_SKEW or now >= expires:
                    raise AuthenticationError("request expired while awaiting authentication")
                ring = load_keyring(self.keyring)
                if (fields["Provider"], fields["Instance"]) != self.identity or (ring["provider_id"], ring["instance_id"]) != self.identity:
                    raise AuthenticationError("request identity mismatch")
                key = next((row for row in ring["keys"] if row["key_id"] == fields["Key-Id"]), None)
                if key is None or (key["valid_until"] is not None and now >= key["valid_until"]):
                    raise AuthenticationError("request key unavailable")
                expected = hmac.new(load_secret(key["secret_file"]), signing_input(method, authority, target, body, fields), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(signature, expected):
                    raise AuthenticationError("request authentication failed")
                # Length-safe encoding prevents provider/instance delimiter collisions.
                scope = json.dumps(self.identity, separators=(",", ":"))
                self.ledger.reserve(scope, fields["Nonce"], expires, now)
                if int(time.time()) >= expires:
                    raise AuthenticationError("request expired while reserving nonce")
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError("request authentication rejected") from exc
