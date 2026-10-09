"""System-neutral evidence output normalization for reader-free comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


NORMALIZER_VERSION = "v1"


@dataclass(frozen=True, slots=True, order=True)
class NormalizedRange:
    source_id: str
    start: int
    end: int


def _collapsed(value: str) -> str:
    return " ".join(value.split()).casefold()


def normalize_evidence(
    outputs: Iterable[object],
    sources: Sequence[Mapping[str, str]],
) -> tuple[NormalizedRange, ...]:
    """Map IDs, exact ranges, or quoted text to canonical source ranges.

    The function is intentionally ignorant of system identity. Ambiguous or
    unverifiable prose receives no evidence credit.
    """
    by_id = {str(item["id"]): str(item["text"]) for item in sources}
    normalized: list[NormalizedRange] = []
    seen: set[NormalizedRange] = set()

    def add(value: NormalizedRange) -> None:
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    for output in outputs:
        if isinstance(output, Mapping):
            source_id = str(output.get("source_id", ""))
            if source_id not in by_id:
                continue
            if "start" in output and "end" in output:
                start, end = int(output["start"]), int(output["end"])
                if 0 <= start < end <= len(by_id[source_id]):
                    add(NormalizedRange(source_id, start, end))
                continue
            output = output.get("quote", "")
        if not isinstance(output, str) or not output.strip():
            continue
        needle = _collapsed(output)
        matches: list[NormalizedRange] = []
        for source_id, text in by_id.items():
            collapsed = _collapsed(text)
            index = collapsed.find(needle)
            if index >= 0 and collapsed.find(needle, index + 1) < 0:
                # Fixture sources use normalized single-line text, so collapsed
                # offsets equal source offsets. Non-fixture adapters must emit
                # canonical ranges when whitespace normalization changes length.
                matches.append(NormalizedRange(source_id, index, index + len(needle)))
        if len(matches) == 1:
            add(matches[0])
    return tuple(normalized)


def normalizer_identity() -> str:
    return f"research.reference_parity.normalizer:{NORMALIZER_VERSION}"
