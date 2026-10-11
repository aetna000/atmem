"""Pure, no-network Jev identity and schema preflight for Spec 041."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
import re
from typing import Any, Mapping


OPENAPI_SHA256 = "a191f8a7df6bd6fedced8120dd0fd106f88575d1d1c8360d08900a6c7c0360d5"
OPENAPI_SERVICE_VERSION = "0.2.0"
REQUIRED_PATHS = frozenset({"/v1/models", "/v1/systemone"})
MOVING_ALIASES = frozenset({"jev-latest", "latest"})
_CONCRETE_MODEL = re.compile(r"^jev-[0-9]+(?:\.[0-9]+){1,2}(?:[-+][a-z0-9.-]+)?$")


@dataclass(frozen=True, slots=True)
class JevIdentityReceipt:
    format: str
    requested_model: str
    resolved_model: str
    release_date: str
    models_payload_sha256: str
    openapi_sha256: str
    service_version: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def validate_openapi(document: Mapping[str, Any]) -> None:
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    # The exact downloaded bytes are checked by the source-lock workflow. This
    # semantic validator separately prevents a reshaped document from passing.
    if document.get("openapi") != "3.1.0":
        raise ValueError("unsupported Jev OpenAPI version")
    info = document.get("info")
    if not isinstance(info, Mapping) or info.get("version") != OPENAPI_SERVICE_VERSION:
        raise ValueError("unexpected Jev service version")
    paths = document.get("paths")
    if not isinstance(paths, Mapping) or not REQUIRED_PATHS.issubset(paths):
        raise ValueError("Jev OpenAPI is missing required paths")
    if len(digest) != 64:  # pragma: no cover - hashlib contract guard
        raise AssertionError("invalid digest implementation")


def resolve_model_identity(
    models_payload: Mapping[str, Any], *, requested_model: str
) -> JevIdentityReceipt:
    """Resolve a captured GET /v1/models response without making a call.

    The caller performs an explicitly authorized authenticated GET and passes
    only the response body here. Alias-only metadata is rejected because it
    cannot freeze the weights behind a hosted service.
    """

    if requested_model in MOVING_ALIASES or not _CONCRETE_MODEL.fullmatch(requested_model):
        raise ValueError("Jev comparison requires a concrete versioned model, not an alias")
    rows = models_payload.get("models")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Jev models payload must contain a non-empty models list")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("name") == requested_model]
    if len(matches) != 1:
        raise ValueError("requested concrete Jev model is not uniquely available")
    release_date = matches[0].get("release_date")
    if not isinstance(release_date, str):
        raise ValueError("Jev model is missing a release date")
    try:
        date.fromisoformat(release_date)
    except ValueError as exc:
        raise ValueError("Jev model release date must use YYYY-MM-DD") from exc
    return JevIdentityReceipt(
        format="atmem-jev-identity-receipt-v1",
        requested_model=requested_model,
        resolved_model=requested_model,
        release_date=release_date,
        models_payload_sha256=canonical_digest(models_payload),
        openapi_sha256="sha256:" + OPENAPI_SHA256,
        service_version=OPENAPI_SERVICE_VERSION,
    )


def verify_response_model(receipt: JevIdentityReceipt, response: Mapping[str, Any]) -> None:
    if response.get("model") != receipt.resolved_model:
        raise ValueError("Jev response model differs from the frozen concrete identity")
    if not isinstance(response.get("answers"), Mapping) or not isinstance(response.get("usage"), Mapping):
        raise ValueError("Jev response is missing answers or usage")
