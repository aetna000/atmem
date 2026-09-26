"""Standard-library-only client copied into the Hermes directory plugin."""
from __future__ import annotations

from http.client import HTTPConnection, HTTPException
import json
import time
from types import SimpleNamespace
from urllib.parse import urlsplit


class HermesRPCError(RuntimeError):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(f"AtMem Hermes RPC {code}; inspect atmem status")


class HermesRPCClient:
    def __init__(self, endpoint: str, credential: str, *, profile_id: str,
                 user_id: str | None = None, timeout: float = 5.0):
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
                or parsed.username or parsed.password or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment or not parsed.port):
            raise ValueError("Hermes requires an explicit loopback HTTP endpoint and port")
        if not isinstance(credential, str) or not credential.startswith("hermes_") or len(credential) > 256:
            raise ValueError("a scoped Hermes credential is required")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 10:
            raise ValueError("RPC timeout must be between zero and ten seconds")
        self.endpoint = endpoint.rstrip("/")
        self._credential = credential
        self.profile_id = profile_id
        self.identity = SimpleNamespace(user_id=user_id)
        self.timeout = timeout
        self._port = parsed.port

    def _call(self, operation, payload):
        encoded = json.dumps(payload, ensure_ascii=False).encode()
        if len(encoded) > 300_000:
            raise ValueError("Hermes request exceeds its byte limit")
        deadline = time.monotonic() + self.timeout
        connection = HTTPConnection("127.0.0.1", self._port, timeout=self.timeout)
        try:
            connection.connect()
            sock = connection.sock
            def remaining():
                value = deadline - time.monotonic()
                if value <= 0:
                    raise TimeoutError("Hermes deadline elapsed")
                sock.settimeout(value)
            remaining()
            connection.request("POST", "/v1/hermes/" + operation, body=encoded,
                               headers={"Authorization": "Bearer " + self._credential,
                                        "Content-Type": "application/json"})
            remaining()
            response = connection.getresponse()
            chunks, size = [], 0
            while not response.isclosed():
                remaining()
                chunk = response.read1(min(16384, 300_001 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > 300_000:
                    raise ValueError("Hermes response exceeds its byte limit")
            value = json.loads(b"".join(chunks))
            if response.status != 200:
                code = value.get("error") if isinstance(value, dict) else None
                allowed = {"observation_uncertain", "idempotency_conflict", "operation_in_progress", "inactive", "unauthenticated"}
                raise HermesRPCError(response.status, code if isinstance(code, str) and code in allowed else "unavailable_or_denied")
            if not isinstance(value, dict) or "error" in value:
                raise ValueError("invalid Hermes response")
            return value
        except (HTTPException, OSError, ValueError):
            # Never include URL, credentials, user content or server error bodies.
            raise HermesRPCError(None, "transport_outcome_unknown") from None
        finally:
            connection.close()

    @property
    def enabled(self):
        try:
            return self.status().get("enabled") is True
        except RuntimeError:
            return False

    def _session(self, session_id):
        """Validate only; the service owns authoritative session namespacing."""
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 512:
            raise ValueError("invalid Hermes session identifier")
        return session_id

    def status(self):
        return self._call("status", {})

    def recall(self, query, *, session_id, turn_id):
        try:
            value = self._call("recall", {"query": query, "session_id": session_id, "turn_id": turn_id})
            context = value.get("context", "")
            candidates = value.get("candidate_ids", [])
            if (not isinstance(context, str) or len(context) > 4096 or
                    not isinstance(candidates, list) or len(candidates) > 1024 or
                    any(not isinstance(candidate, str) or len(candidate) > 512 for candidate in candidates)):
                raise ValueError("invalid context")
            return SimpleNamespace(context=context, candidate_ids=candidates)
        except (RuntimeError, ValueError):
            return SimpleNamespace(context="", candidate_ids=[])

    def observe_user(self, text, *, session_id, observation_id):
        return self._call("observe", {"text": text, "session_id": session_id,
                                      "observation_id": observation_id})
