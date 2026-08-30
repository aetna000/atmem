"""Versioned canonicalization for untrusted fact-key grouping hints."""

from __future__ import annotations

import re
import unicodedata


FACT_KEY_VERSION = "atmem-fact-key-v1"
_PART = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def canonicalize_fact_key(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    parts = [part.strip() for part in normalized.split("::")]
    if not 1 <= len(parts) <= 8 or any(not _PART.fullmatch(part) for part in parts):
        raise ValueError(
            "fact_key must contain 1-8 safe namespace parts separated by ::"
        )
    result = "::".join(parts)
    if len(result) > 256:
        raise ValueError("fact_key exceeds 256 characters")
    return result
