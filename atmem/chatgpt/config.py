"""Explicit, fail-closed service configuration; never selects native stores."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse

SCOPES = ("memory:read", "memory:write", "memory:delete")


@dataclass(frozen=True)
class Settings:
    home: Path
    project: str
    issuer: str
    key: bytes
    clients: dict[str, tuple[str, ...]]
    firebase_api_key: str
    emulator: bool = False
    allowed_uids: tuple[str, ...] = ()
    openai_domain_challenge: str | None = None
    max_snapshot_bytes: int = 8 * 1024 * 1024
    max_records: int = 1000
    requests_per_minute: int = 120
    collection: str = "atmem_chatgpt_v1"
    database: str = "(default)"

    def permits_account(self, uid: str) -> bool:
        return self.emulator or uid in self.allowed_uids

    @property
    def resource(self) -> str:
        return self.issuer + "/mcp"

    def derive(self, purpose: str) -> bytes:
        return hmac.digest(self.key, purpose.encode(), "sha256")

    def opaque_id(self, purpose: str, value: str) -> str:
        return hmac.new(self.derive(purpose), value.encode(), hashlib.sha256).hexdigest()

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        value = json.loads(Path(path).read_text())
        home = Path(value["home"]).expanduser().resolve()
        native = (Path.home() / ".atmem").resolve()
        if home == native or native in home.parents:
            raise ValueError("cloud service requires a dedicated home outside native ~/.atmem")
        issuer = str(value["issuer"]).rstrip("/")
        parsed = urlparse(issuer)
        emulator = value.get("emulator", False) is True
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
            raise ValueError("issuer must be an origin without credentials, path or query")
        if parsed.scheme != "https" and not (emulator and parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}):
            raise ValueError("HTTPS issuer required outside explicit loopback emulator mode")
        project = str(value["project"])
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,62}", project):
            raise ValueError("invalid Firebase project")
        if emulator:
            if not project.startswith("demo-"):
                raise ValueError("emulators require a demo- project; production data is forbidden")
            for name in ("FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST"):
                endpoint = urlparse("http://" + os.environ.get(name, ""))
                if endpoint.hostname not in {"localhost", "127.0.0.1"} or not endpoint.port:
                    raise ValueError(f"{name} must explicitly identify a loopback emulator")
        elif any(os.environ.get(k) for k in ("FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST")):
            raise ValueError("emulator environment is forbidden for production")
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt" and home.stat().st_mode & 0o077:
            raise ValueError("cloud service home must have mode 0700")
        if value.get("key_env"):
            name=str(value["key_env"])
            if not re.fullmatch(r"ATMEM_CLOUD_[A-Z_]+",name):
                raise ValueError("invalid dedicated cloud key environment name")
            # Supports Secret Manager environment injection without logging it.
            key=bytes.fromhex(os.environ.pop(name, ""))
        else:
            supplied_key_path = Path(value["key_file"]).expanduser()
            if supplied_key_path.is_symlink():
                raise ValueError("service key must not be a symlink")
            secret_path = supplied_key_path.resolve()
            if not secret_path.is_file():
                raise ValueError("provision a dedicated service key before startup")
            if os.name != "nt" and secret_path.stat().st_mode & 0o077:
                raise ValueError("service key file must have mode 0600")
            key = bytes.fromhex(secret_path.read_text().strip())
        if len(key) != 32:
            raise ValueError("service key must contain 32 random bytes in hex")
        clients = {}
        for client_id, redirects in value["clients"].items():
            if not client_id or not isinstance(redirects, list) or not redirects:
                raise ValueError("provided OAuth client needs exact redirect URIs")
            for redirect in redirects:
                target = urlparse(redirect)
                if target.fragment or target.username or target.password or (target.scheme != "https" and not (emulator and target.scheme == "http" and target.hostname in {"127.0.0.1", "localhost"})):
                    raise ValueError("invalid client redirect URI")
            clients[client_id] = tuple(redirects)
        if not clients:
            raise ValueError("at least one explicitly registered OAuth client is required")
        if os.environ.get("K_SERVICE") and emulator:
            raise ValueError("Cloud Run cannot start in emulator mode")
        settings = cls(home=home, project=project, issuer=issuer, key=key, clients=clients,
                       firebase_api_key=str(value["firebase_api_key"]), emulator=emulator,
                       allowed_uids=tuple(value.get("allowed_firebase_uids", [])),
                       openai_domain_challenge=value.get("openai_domain_challenge"),
                       max_snapshot_bytes=int(value.get("max_snapshot_bytes", 8 * 1024 * 1024)),
                       max_records=int(value.get("max_records", 1000)),
                       requests_per_minute=int(value.get("requests_per_minute", 120)),
                       collection=str(value.get("collection", "atmem_chatgpt_v1")),
                       database=str(value.get("database", "(default)")))
        if settings.database != "(default)" and not re.fullmatch(r"[a-z][a-z0-9-]{2,61}[a-z0-9]", settings.database):
            raise ValueError("invalid Firestore database ID")
        challenge=settings.openai_domain_challenge
        if challenge is not None and (not isinstance(challenge,str) or not 1<=len(challenge)<=4096 or "\n" in challenge or "\r" in challenge):
            raise ValueError("domain challenge must be the exact single portal token")
        if not emulator and not settings.allowed_uids:
            raise ValueError("initial cloud pilot requires explicit invited Firebase user IDs")
        if len(settings.allowed_uids)>1000 or any(not isinstance(uid,str) or not uid or len(uid)>128 for uid in settings.allowed_uids):
            raise ValueError("invalid invited user allowlist")
        if not 65536 <= settings.max_snapshot_bytes <= 16 * 1024 * 1024 or not 1 <= settings.max_records <= 10000:
            raise ValueError("cloud quota out of supported range")
        if not 1 <= settings.requests_per_minute <= 1000:
            raise ValueError("request limit out of range")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,60}", settings.collection):
            raise ValueError("invalid collection namespace")
        # This entrypoint owns its process. Never redirect an existing native home.
        existing = os.environ.get("ATMEM_HOME")
        if existing and Path(existing).expanduser().resolve() != home:
            raise ValueError("ATMEM_HOME conflicts with dedicated cloud home")
        os.environ["ATMEM_HOME"] = str(home)
        os.environ["ATMEM_DB_KEY"] = settings.derive("sqlcipher-v1").hex()
        return settings
