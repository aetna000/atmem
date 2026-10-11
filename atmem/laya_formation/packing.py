"""Shared tokenizer-exact packing for training and runtime decisions.

The module is dependency-free. A Laya adapter is constructed lazily only when
the optional package is installed; dataset and runtime callers use this exact
packing function to avoid train/serve skew.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

from atmem.core.canonical import canonical_json, sha256_hex


@dataclass(frozen=True, slots=True)
class AuthorizedRange:
    range_id: str
    source_id: str
    start: int
    end: int
    text: str

    def __post_init__(self) -> None:
        if not self.range_id or not self.source_id or not self.text:
            raise ValueError("authorized range identifiers and text are required")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("authorized range offsets must be non-empty")


class PackingAdapter(Protocol):
    revision: str

    def head_token_count(self, question: Mapping[str, Any], head_max_len: int) -> tuple[int, int]: ...

    def serialize_and_encode_state(self, state: Mapping[str, Any]) -> tuple[str, list[int]]: ...


@dataclass(frozen=True, slots=True)
class PackedDecisionInput:
    format: str
    packer_version: str
    tokenizer_revision: str
    state: str
    state_digest: str
    included_range_ids: tuple[str, ...]
    lost_range_ids: tuple[str, ...]
    head_tokens: int
    state_tokens: int
    max_len: int
    head_max_len: int
    closing_tokens_reserved: int
    total_tokens: int
    overflow: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LayaPackingAdapter:
    """Lazy adapter around the pinned Laya serializer/head implementation."""

    def __init__(self, tokenizer: Any, *, revision: str) -> None:
        from laya.common import build_head, encode_text, serialize_state

        self.tokenizer = tokenizer
        self.revision = revision
        self._build_head: Callable[..., Any] = build_head
        self._encode_text: Callable[..., Any] = encode_text
        self._serialize_state: Callable[..., str] = serialize_state

    def head_token_count(self, question: Mapping[str, Any], head_max_len: int) -> tuple[int, int]:
        ids, markers, stats = self._build_head(self.tokenizer, dict(question), head_max_len)
        expected = len(question.get("crit") or {}) if question.get("t") != "noul" else 2
        if len(markers) != expected or int(stats.get("options_distinct", expected)) != expected:
            raise ValueError("the complete finite-choice head does not fit head_max_len")
        return len(ids), len(markers)

    def serialize_and_encode_state(self, state: Mapping[str, Any]) -> tuple[str, list[int]]:
        serialized = self._serialize_state(dict(state))
        encoded = self._encode_text(
            self.tokenizer,
            serialized.replace(self.tokenizer.mask_token, " "),
            add_special_tokens=False,
        )["input_ids"]
        return serialized, list(encoded)


def pack_authorized_ranges(
    *,
    adapter: PackingAdapter,
    question: Mapping[str, Any],
    ranges: Sequence[AuthorizedRange],
    max_len: int = 512,
    head_max_len: int = 192,
    closing_tokens_reserved: int = 1,
) -> PackedDecisionInput:
    """Admit whole authorized ranges until the exact state-token budget is full."""

    if max_len < 1 or head_max_len < 1 or closing_tokens_reserved < 1:
        raise ValueError("token budgets must be positive")
    if len({item.range_id for item in ranges}) != len(ranges):
        raise ValueError("authorized range IDs must be unique")
    head_tokens, marker_count = adapter.head_token_count(question, head_max_len)
    if marker_count < 1:
        raise ValueError("a typed decision requires at least one complete choice marker")
    room = max_len - head_tokens - closing_tokens_reserved
    if room < 0:
        raise ValueError("question and complete choices exceed max_len")

    included: list[AuthorizedRange] = []
    lost: list[str] = []
    selected_state = {"authorized_ranges": []}
    selected_serialized, selected_ids = adapter.serialize_and_encode_state(selected_state)
    if len(selected_ids) > room:
        raise ValueError("mandatory empty state envelope exceeds available token room")

    for item in ranges:
        candidate_ranges = [
            {"range_id": row.range_id, "source_id": row.source_id, "start": row.start, "end": row.end, "text": row.text}
            for row in (*included, item)
        ]
        candidate_state = {"authorized_ranges": candidate_ranges}
        serialized, token_ids = adapter.serialize_and_encode_state(candidate_state)
        if len(token_ids) <= room:
            included.append(item)
            selected_state = candidate_state
            selected_serialized = serialized
            selected_ids = token_ids
        else:
            lost.append(item.range_id)

    return PackedDecisionInput(
        format="atmem-laya-packed-decision-input-v1",
        packer_version="1.0.0",
        tokenizer_revision=adapter.revision,
        state=selected_serialized,
        state_digest="sha256:" + sha256_hex(selected_serialized),
        included_range_ids=tuple(row.range_id for row in included),
        lost_range_ids=tuple(lost),
        head_tokens=head_tokens,
        state_tokens=len(selected_ids),
        max_len=max_len,
        head_max_len=head_max_len,
        closing_tokens_reserved=closing_tokens_reserved,
        total_tokens=head_tokens + len(selected_ids) + closing_tokens_reserved,
        overflow=bool(lost),
    )


def structural_parity_bytes(packed: PackedDecisionInput) -> bytes:
    """Canonical bytes used by dataset/runtime parity tests and receipts."""

    return canonical_json(packed.to_dict()).encode("utf-8")
