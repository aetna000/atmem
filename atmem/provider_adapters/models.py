"""Closed, SDK-neutral models used by context-provider adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from atmem.delegated.contracts import DelegatedBinding


def _text(value: Any, label: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise ValueError(f"invalid {label}")
    return value


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    binding: DelegatedBinding
    query: str
    query_sha256: str
    max_context_bytes: int
    deadline: str


@dataclass(frozen=True, slots=True)
class ContextItem:
    text: str
    source_ref: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ContextItem":
        if not isinstance(value, dict) or set(value) != {"text", "source_ref"}:
            raise ValueError("context item fields do not match the contract")
        return cls(
            text=_text(value["text"], "context item text", 100_000),
            source_ref=_text(value["source_ref"], "source reference"),
        )


@dataclass(frozen=True, slots=True)
class ProviderProposal:
    decision: str
    items: tuple[ContextItem, ...] = ()
    source_refs: tuple[str, ...] = ()
    withhold_reason: dict[str, Any] | None = None
    attribution: dict[str, str] = field(default_factory=dict)

    @classmethod
    def inject(
        cls,
        items: list[ContextItem] | tuple[ContextItem, ...],
        *,
        attribution: dict[str, str] | None = None,
    ) -> "ProviderProposal":
        values = tuple(items)
        return cls(
            decision="inject",
            items=values,
            source_refs=tuple(dict.fromkeys(item.source_ref for item in values)),
            attribution=dict(attribution or {}),
        ).validated()

    @classmethod
    def withhold(cls, code: str = "NO_USEFUL_MEMORY", *, retryable: bool = False) -> "ProviderProposal":
        return cls(
            decision="withhold",
            withhold_reason={"code": code, "retryable": retryable},
        ).validated()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProviderProposal":
        allowed = {"decision", "items", "source_refs", "withhold_reason", "attribution"}
        if not isinstance(value, dict) or not set(value).issubset(allowed) or "decision" not in value:
            raise ValueError("provider proposal fields do not match the contract")
        items = value.get("items", [])
        refs = value.get("source_refs", [])
        attribution = value.get("attribution", {})
        if not isinstance(items, list) or not isinstance(refs, list) or not isinstance(attribution, dict):
            raise ValueError("invalid provider proposal collections")
        return cls(
            decision=value["decision"],
            items=tuple(ContextItem.from_dict(item) for item in items),
            source_refs=tuple(refs),
            withhold_reason=value.get("withhold_reason"),
            attribution=attribution,
        ).validated()

    def validated(self) -> "ProviderProposal":
        if self.decision not in {"inject", "withhold"}:
            raise ValueError("provider decision must be inject or withhold")
        if len(self.items) > 32 or len(self.source_refs) > 32 or len(set(self.source_refs)) != len(self.source_refs):
            raise ValueError("invalid provider source references")
        for ref in self.source_refs:
            _text(ref, "source reference")
        if len(self.attribution) > 16 or any(
            not isinstance(k, str) or not isinstance(v, str) or not k or len(k) > 64 or len(v) > 256
            for k, v in self.attribution.items()
        ):
            raise ValueError("provider attribution must contain strings")
        if self.decision == "inject":
            if not self.items or self.withhold_reason is not None:
                raise ValueError("inject proposal requires items and no withholding reason")
        else:
            if self.items or self.source_refs or not isinstance(self.withhold_reason, dict):
                raise ValueError("withhold proposal has invalid content")
            if set(self.withhold_reason) != {"code", "retryable"}:
                raise ValueError("withhold reason fields do not match the contract")
            _text(self.withhold_reason["code"], "withhold code", 64)
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", self.withhold_reason["code"]):
                raise ValueError("invalid withhold code")
            if not isinstance(self.withhold_reason["retryable"], bool):
                raise ValueError("withhold retryable must be boolean")
        return self


@dataclass(frozen=True, slots=True)
class ProviderRuntimeIdentity:
    provider_id: str
    provider_version: str
    instance_id: str
    key_id: str

    def __post_init__(self) -> None:
        for label, value in (
            ("provider id", self.provider_id),
            ("provider version", self.provider_version),
            ("instance id", self.instance_id),
            ("key id", self.key_id),
        ):
            _text(value, label, 256)
