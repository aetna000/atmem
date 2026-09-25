"""Small real tools demonstrating destination-owned receipts, not recovery logic."""
from hashlib import sha256
import os
from pathlib import Path
import tempfile
import json
from urllib.request import Request, build_opener, ProxyHandler

from .client import Tool, _base, _NoRedirect
from .service import identifier


class DirectoryPublisher:
    """Publish UTF-8 documents into an explicitly selected local directory.

    The published file is the effect. Query reads that file and checks its bytes;
    neither a hidden recovery journal nor a guessed success receipt is used.
    Use capability='query'. The directory must not be writable by untrusted users.
    """

    def __init__(self, directory):
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _content(self, arguments):
        if arguments.get("destination") != str(self.directory):
            raise ValueError("destination differs from the reviewed workflow definition")
        text = arguments.get("text")
        if not isinstance(text, str):
            raise ValueError("document text must be UTF-8 text")
        data = text.encode("utf-8")
        if len(data) > 131072:
            raise ValueError("document exceeds 128 KiB")
        return data

    def _path(self, operation_id):
        return self.directory / (identifier(operation_id) + ".md")

    def query(self, arguments, operation_id, idempotency_key, timeout_seconds):
        data = self._content(arguments)
        target = self._path(operation_id)
        if not target.exists():
            return {"outcome": "unknown", "reason": "destination_has_no_receipt"}
        if target.is_symlink() or not target.is_file():
            raise ValueError("published destination must be a regular file")
        if target.read_bytes() != data:
            return {"outcome": "unknown", "reason": "destination_content_conflict"}
        return {"outcome": "confirmed_succeeded", "operation_id": operation_id,
                "effect_id": target.name,
                "result": {"path": str(target), "sha256": sha256(data).hexdigest(), "bytes": len(data)}}

    def execute(self, arguments, operation_id, idempotency_key, timeout_seconds):
        data = self._content(arguments)
        target = self._path(operation_id)
        descriptor, temporary = tempfile.mkstemp(prefix=".publishing-", dir=self.directory)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            # No replace: an existing external effect is never silently overwritten.
            os.link(temporary, target)
            if os.name != "nt":
                directory_fd = os.open(self.directory, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return self.query(arguments, operation_id, idempotency_key, timeout_seconds)

    def tool(self):
        return Tool(self.execute, self.query)


class JsonResponseTool:
    """Adapter for synchronous JSON tools with id-correlated success responses.

    Endpoint contract: `error: false` certifies the requested invocation finished,
    not merely that an asynchronous job was accepted. Preserve the original body.
    No retry, query, idempotency or business-goal success is inferred. Configure
    capability='none'. Other endpoint semantics require their own trusted adapter.
    """
    def __init__(self, url, token):
        self.url, self.token = _base(url), token
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def execute(self, arguments, operation_id, idempotency_key, timeout_seconds):
        request_id = arguments.get("id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("endpoint requests require a stable string id")
        request = Request(self.url, data=json.dumps(arguments, allow_nan=False).encode(), method="POST",
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.token})
        with self.opener.open(request, timeout=timeout_seconds) as response:
            data = response.read(60001)
        if len(data) > 60000:
            raise ValueError("tool response exceeds this adapter's 60 KB bound")
        result = json.loads(data)
        if not isinstance(result, dict) or result.get("id") != request_id:
            raise ValueError("tool response does not match its request identity")
        if result.get("error") is not False:
            return {"outcome": "unknown", "result": result}
        return {"outcome": "confirmed_succeeded", "operation_id": operation_id,
                "effect_id": request_id, "result": result}

    def tool(self):
        return Tool(self.execute)
