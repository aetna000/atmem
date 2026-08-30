"""No-download deterministic local degradation provider."""

from __future__ import annotations

import json
from typing import Any

from atbot.domain import ProviderResult


class DeterministicLocalProvider:
    name = "deterministic-local"
    model = "atbot-rules-v1"
    egress_class = "local"

    def available(self) -> bool:
        return True

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> ProviderResult:
        del system
        if schema and schema.get("title") == "AtBotFactExtraction":
            source = prompt.rsplit("<current-message>\n", 1)[-1].split(
                "\n</current-message>", 1
            )[0]
            fact = _explicit_fact(source)
            value = {"facts": [fact] if fact else []}
            return ProviderResult(
                text=json.dumps(value),
                structured=value,
                provider=self.name,
                model=self.model,
                egress_class=self.egress_class,
            )
        if schema and schema.get("title") == "AtBotMemoryQuery":
            payload = json.loads(prompt)
            candidates = payload.get("eligible_memories") or []
            first = candidates[0] if candidates else None
            value = {
                "answer": (
                    f"The closest governed memory is: {first['content']}"
                    if first
                    else "I couldn't find governed memory that answers that question."
                ),
                "ranked_record_ids": [str(first["record_id"])] if first else [],
                "explanation": "Deterministic ranking over AtMem-authorized candidates.",
            }
            return ProviderResult(
                text=json.dumps(value),
                structured=value,
                provider=self.name,
                model=self.model,
                egress_class=self.egress_class,
            )
        return ProviderResult(
            text="AtBot could not interpret the bounded memory operation.",
            structured=None,
            provider=self.name,
            model=self.model,
            egress_class=self.egress_class,
        )


def _explicit_fact(message: str) -> dict[str, Any] | None:
    text = " ".join(message.strip().split())
    lowered = text.casefold()
    if not text or text.endswith("?"):
        return None
    indicators = (
        "remember ",
        "i prefer ",
        "i like ",
        "my favorite ",
        "my timezone ",
        "my name ",
        "i am ",
        "i'm ",
    )
    if not any(value in lowered for value in indicators):
        return None
    return {
        "fact": text,
        "fact_key": None,
        "confidence": 0.75,
        "sensitivity": "personal",
        "entities": [],
        "suggested_action": "add",
        "related_record_ids": [],
    }
