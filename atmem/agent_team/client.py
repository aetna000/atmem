"""Scoped loopback client for host tools. A host binding is never a tool argument."""

from __future__ import annotations

from http.client import HTTPConnection
import json
import os
from pathlib import Path
import stat
from typing import Any
from urllib.parse import urlsplit

from .portable import FIELDS, host_identity


def address(endpoint):
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use the local AtMem control service HTTP origin.")
    return parsed.hostname, parsed.port or 80


class TeamClient:
    def __init__(self, binding, expected_host):
        self.host, _ = host_identity(binding["principal_id"])
        if self.host != expected_host or binding.get("format") != "atmem-team-binding-v1":
            raise PermissionError("Credential is bound to a different host or format.")
        self.address = address(binding["endpoint"])
        self._token = binding["token"]
        if not isinstance(self._token, str) or not self._token.startswith("atmem_"):
            raise PermissionError("Invalid team binding.")

    @classmethod
    def from_file(cls, path, expected_host, *, account=None):
        fd = os.open(
            Path(path).expanduser(),
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_size > 8192
                or (os.name == "posix" and (info.st_mode & 0o077 or info.st_uid != os.geteuid()))
            ):
                raise PermissionError("Use an owner-only, regular host binding file.")
            data = stream.read(8193)
            if len(data) > 8192:
                raise ValueError("Binding exceeds size limit.")
            binding = json.loads(data)
        if account is not None and binding.get("account") != account:
            raise PermissionError("Account binding does not match.")
        return cls(binding, expected_host)

    def call(self, operation, args):
        if operation not in FIELDS:
            raise ValueError("Unknown team operation.")
        connection = HTTPConnection(*self.address, timeout=30)
        try:
            connection.request(
                "POST",
                "/v1/agent-team/" + operation,
                json.dumps(args).encode(),
                {
                    "Authorization": "Bearer " + self._token,
                    "Content-Type": "application/json",
                    "X-AtMem-Team-Host": self.host,
                },
            )
            response = connection.getresponse()
            payload = response.read(128_001)
            if len(payload) > 128_000:
                raise ValueError("Team service response exceeds the size limit.")
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise ValueError("Invalid team service response.")
            if response.status in {401, 403}:
                raise PermissionError(data.get("error", "Access denied."))
            if response.status != 200:
                raise ValueError(data.get("error", "Team operation failed."))
            return data
        finally:
            connection.close()


def tool_functions(call):
    def team_review(question: str) -> dict[str, Any]:
        """Read this sender's currently authorized passages to prepare a source-bound reviewer quotation."""
        return call("review", {"question": question})

    def team_offer(
        question: str,
        recipient: str,
        request_id: str,
        rerun_of: str | None = None,
        review: dict | None = None,
        reader_model: str | None = None,
        reader_pricing: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Offer source references to team:<host>:<agent>. Reuse request_id for an identical retry.

        For a reviewed offer, pass team_review's generation and evidence_sha256 plus an exact quote and optional usage
        in review. For a corrected rerun, set rerun_of to the original run ID and use a fresh request_id.
        An optional reader_model names the required model. Its reader_pricing accepts decimal strings
        input_usd_per_million and output_usd_per_million.
        """
        args = {"question": question, "recipient": recipient, "request_id": request_id}
        if reader_model is not None:
            args["reader_model"] = reader_model
        if reader_pricing is not None:
            args["reader_pricing"] = reader_pricing
        if review is not None:
            args["review"] = review
        if rerun_of is not None:
            args["rerun_of"] = rerun_of
        return call("offer", args)

    def team_receive(run_id: str) -> dict[str, Any]:
        """Independently verify a handoff and receive authorized passages as untrusted data."""
        return call("receive", {"run_id": run_id})

    def team_complete(
        run_id: str, delivery_id: str, quote: str, usage: dict | None = None
    ) -> dict[str, Any]:
        """Return an exact quote from the delivery, or an empty string to abstain.

        Usage may contain metered input_tokens, output_tokens, model_calls, model and cost_microusd.
        Omit unknown values. A reviewed handoff accepts a substring of the verified reviewer quote.
        """
        args = {"run_id": run_id, "delivery_id": delivery_id, "quote": quote}
        if usage is not None:
            args["usage"] = usage
        return call("complete", args)

    def team_inbox() -> dict[str, Any]:
        """List pending run IDs addressed to this registered team identity."""
        return call("inbox", {})

    return (team_review, team_offer, team_receive, team_complete, team_inbox)


def pydantic_tools(binding):
    from pydantic_ai import Tool

    client = TeamClient.from_file(binding, "pydantic-ai")
    return [Tool(fn) for fn in tool_functions(client.call)]


def langgraph_tools(binding):
    from langchain_core.tools import StructuredTool

    client = TeamClient.from_file(binding, "langgraph")
    return [StructuredTool.from_function(fn) for fn in tool_functions(client.call)]
