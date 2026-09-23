from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from threading import RLock
import time
from typing import Any
from uuid import uuid4

from atmem.evidence.crypto import open_json, seal_json


_IDENTITY_DOCUMENT_LOCK = RLock()


class EncryptedIdentityDocument:
    """One atomic encrypted document with no semantic plaintext fields."""

    def __init__(self, path: str | Path, key: bytes, object_id: str, empty: dict[str, Any]) -> None:
        self.path = Path(path).expanduser().resolve(strict=False)
        self.key = key
        self.object_id = object_id
        self.empty = empty
        self._lock = _IDENTITY_DOCUMENT_LOCK

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return json.loads(json.dumps(self.empty))
            wrapper = json.loads(self.path.read_text(encoding="utf-8"))
            if wrapper.get("format") != "atmem-encrypted-identity-document-v1":
                raise ValueError("unsupported encrypted identity document")
            return open_json(
                self.key,
                self.object_id,
                base64.b64decode(wrapper["nonce"], validate=True),
                base64.b64decode(wrapper["ciphertext"], validate=True),
            )

    def write(self, value: dict[str, Any]) -> None:
        nonce, ciphertext = seal_json(self.key, self.object_id, value)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        temporary = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{uuid4().hex}.tmp"
        )
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "format": "atmem-encrypted-identity-document-v1",
                        "nonce": base64.b64encode(nonce).decode("ascii"),
                        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
                    },
                    handle,
                    separators=(",", ":"),
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(40):
                try:
                    with self._lock:
                        os.replace(temporary, self.path)
                    break
                except PermissionError:
                    if os.name != "nt" or attempt == 39:
                        raise
                    time.sleep(0.05)
            self.path.chmod(0o600)
        finally:
            if temporary.exists():
                temporary.unlink()
