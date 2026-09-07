"""Bounded loopback transport for delegated context providers."""

from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlsplit
from atmem.delegated.transport import sign_headers

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
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    request = Request(
        registration.endpoint,
        data=raw,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 **authentication_headers(registration, "POST", registration.endpoint, raw)},
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


def authentication_headers(registration: DelegatedRegistration, method: str, endpoint: str,
                           body: bytes = b"") -> dict[str, str]:
    parsed = urlsplit(endpoint)
    return sign_headers(secret=registration.request_secret(), provider_id=registration.provider_id,
                        instance_id=registration.provider_instance_id, key_id=str(registration.request_key_id),
                        method=method, authority=parsed.netloc,
                        target=(parsed.path or "/") + ("?" + parsed.query if parsed.query else ""), body=body)


def request_health(registration: DelegatedRegistration) -> dict:
    parsed = urlsplit(registration.endpoint)
    endpoint = f"{parsed.scheme}://{parsed.netloc}/health"
    request = Request(endpoint, headers=authentication_headers(registration, "GET", endpoint), method="GET")
    with build_opener(_NoRedirect()).open(request, timeout=min(registration.timeout_ms / 1000, 1)) as response:
        raw = response.read(16385)
        if response.status != 200 or len(raw) > 16384:
            raise ValueError("provider health response outside policy")
    from atmem.delegated.validation import parse_json_strict
    from atmem.delegated.transport import PROFILE
    value = parse_json_strict(raw)
    if not isinstance(value, dict) or value.get("status") != "ready" or value.get("transport_profile") != PROFILE:
        raise ValueError("provider authenticated health unavailable")
    if (value.get("provider_id"), value.get("instance_id")) != (registration.provider_id, registration.provider_instance_id):
        raise ValueError("provider health identity mismatch")
    return value
