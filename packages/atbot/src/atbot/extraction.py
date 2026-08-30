"""Model-assisted proposal extraction with strict validation."""

from __future__ import annotations

import re
from typing import Any

from atbot.domain import ExtractedFact
from atbot.prompts import build_extraction_prompt
from atbot.providers.base import ModelProvider


FACT_SCHEMA: dict[str, Any] = {
    "title": "AtBotFactExtraction",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "facts": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "required": ["fact", "confidence", "sensitivity", "suggested_action"],
                "properties": {
                    "fact": {"type": "string", "minLength": 1, "maxLength": 2000},
                    "fact_key": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "sensitivity": {
                        "enum": ["public", "internal", "personal", "sensitive", "restricted"]
                    },
                    "entities": {"type": "array", "items": {"type": "object"}},
                    "suggested_action": {
                        "enum": ["add", "duplicate", "supports", "extends", "contradicts", "supersedes", "uncertain"]
                    },
                    "related_record_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
    "required": ["facts"],
}


def extract_facts(provider: ModelProvider, message: str) -> tuple[ExtractedFact, ...]:
    if _looks_like_question(message):
        return ()
    bundle = build_extraction_prompt(message)
    result = provider.complete(system=bundle.system, prompt=bundle.prompt, schema=FACT_SCHEMA)
    value = result.structured or {}
    rows = value.get("facts") if isinstance(value, dict) else []
    facts: list[ExtractedFact] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        fact = " ".join(str(row.get("fact") or "").split())
        confidence = float(row.get("confidence", 0.0))
        sensitivity = str(row.get("sensitivity") or "personal")
        action = str(row.get("suggested_action") or "uncertain")
        if not fact or len(fact) > 2_000 or not 0 <= confidence <= 1:
            continue
        if sensitivity not in {"public", "internal", "personal", "sensitive", "restricted"}:
            continue
        if action not in {"add", "duplicate", "supports", "extends", "contradicts", "supersedes", "uncertain"}:
            continue
        fact_key = str(row["fact_key"]).strip() if row.get("fact_key") else None
        if fact_key and not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}(?:::[A-Za-z0-9][A-Za-z0-9._-]{0,63}){0,7}",
            fact_key,
        ):
            fact_key = None
        facts.append(
            ExtractedFact(
                fact=fact,
                fact_key=fact_key,
                confidence=confidence,
                sensitivity=sensitivity,
                entities=tuple(row.get("entities") or ()),
                suggested_action=action,
                related_record_ids=tuple(str(value) for value in row.get("related_record_ids") or ()),
            )
        )
    return tuple(facts)


def _looks_like_question(message: str) -> bool:
    text = " ".join(message.strip().casefold().split())
    if not text:
        return False
    if text.endswith("?"):
        return True
    return bool(
        re.match(
            r"^(what|when|where|which|who|whom|whose|why|how|do|does|did|is|are|am|can|could|would|should|will|have|has|had)\b",
            text,
        )
    )
