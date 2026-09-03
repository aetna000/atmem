"""Bounded loopback transport for delegated context providers."""

from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from atmem.delegated.config import DelegatedRegistration
from atmem.delegated.contracts import (
    DelegatedBinding,
    DelegatedContextRequest,
    MAX_RESULT_BYTES,
)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise HTTPError(req.full_url, code, "delegated provider redirects are prohibited", headers, fp)


def request_context(
    registration: DelegatedRegistration,
    *,
    binding: DelegatedBinding,
    query: str,
) -> bytes:
    body = DelegatedContextRequest.create(
        binding=binding,
        query=query,
        max_context_bytes=registration.max_context_bytes,
        timeout_ms=registration.timeout_ms,
    ).to_dict()
    request = Request(
        registration.endpoint,
        data=json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    opener = build_opener(_NoRedirect())
    with opener.open(request, timeout=registration.timeout_ms / 1000) as response:
        if response.status != 200:
            raise ValueError(f"delegated provider returned HTTP {response.status}")
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError as exc:
                raise ValueError("delegated provider returned invalid Content-Length") from exc
            if declared_length < 0:
                raise ValueError("delegated provider returned invalid Content-Length")
            if declared_length > MAX_RESULT_BYTES:
                raise ValueError("delegated provider response exceeds policy")
        raw = response.read(MAX_RESULT_BYTES + 1)
    if len(raw) > MAX_RESULT_BYTES:
        raise ValueError("delegated provider response exceeds policy")
    return raw
