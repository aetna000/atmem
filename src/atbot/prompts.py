"""Byte-stable prompt construction and cache identity."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib


EXTRACTION_PREFIX = """Extract only durable, user-relevant facts explicitly stated
in the current message. Do not infer sensitive attributes, intent, or unstated
facts. Questions and temporary task details are not durable memories.
"""


@dataclass(frozen=True, slots=True)
class PromptBundle:
    system: str
    prompt: str
    cache_key: str


def build_extraction_prompt(message: str) -> PromptBundle:
    prompt = f"<current-message>\n{message.strip()}\n</current-message>"
    digest = hashlib.sha256((EXTRACTION_PREFIX + "\0" + prompt).encode("utf-8")).hexdigest()
    return PromptBundle(EXTRACTION_PREFIX, prompt, f"atbot-extract-v1:{digest}")
