"""Bounded, authorized evidence for entity and pronoun interpretation.

Resolution is the step where an extractor is most tempted to reach for more
context than it is allowed to see. This module answers "who is 'she'?" from a
configured recent window plus lifecycle-eligible memory for one subject and
one authority scope, and it returns a receipt naming every piece of evidence
that influenced the answer. Anything it cannot resolve inside those bounds is
reported as unresolved or ambiguous -- never widened, never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from atmem.contracts import AuthorityScope
from atmem.core.canonical import sha256_hex


DEFAULT_WINDOW = 8
MAX_WINDOW = 64

_THIRD_PERSON_RE = re.compile(r"\b(?:he|she|they|him|her|them|his|hers|their)\b", re.I)
_OBJECT_RE = re.compile(r"\b(?:it|its|that|this|the same)\b", re.I)
_OWNER_RE = re.compile(r"\b(?P<owner>[A-Z][a-z][A-Za-z.'-]{1,40})\b")
_STOP_OWNERS = frozenset(
    {
        "Actually",
        "Also",
        "And",
        "But",
        "Forget",
        "From",
        "However",
        "My",
        "No",
        "Now",
        "Ok",
        "Okay",
        "Please",
        "Remember",
        "So",
        "The",
        "Then",
        "Use",
        "User",
        "We",
        "Yes",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceInfluence:
    """One authorized item that influenced a resolution, kept for the receipt."""

    kind: str
    id: str
    sha256: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "sha256": self.sha256,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class Resolution:
    """The outcome of interpreting one candidate against bounded evidence."""

    text: str
    referent: str | None
    resolved: bool
    ambiguous: bool
    reason_codes: tuple[str, ...]
    influences: tuple[EvidenceInfluence, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "referent": self.referent,
            "resolved": self.resolved,
            "ambiguous": self.ambiguous,
            "reason_codes": list(self.reason_codes),
            "influences": [item.to_dict() for item in self.influences],
        }


@dataclass(frozen=True, slots=True)
class ResolutionContext:
    """Everything an extractor is authorized to read for one interpretation."""

    subject_id: str
    scope: AuthorityScope | None
    window: int
    episodes: tuple[dict[str, Any], ...]
    records: tuple[dict[str, Any], ...]
    excluded_record_ids: frozenset[str] = frozenset()

    def eligible_records_for_fact_key(self, fact_key: str | None) -> list[dict[str, Any]]:
        if not fact_key:
            return []
        return [row for row in self.records if row.get("fact_key") == fact_key]

    def resolve(self, text: str) -> Resolution:
        """Interpret pronouns in `text` using only this bounded evidence."""
        influences: list[EvidenceInfluence] = []
        reason_codes: list[str] = []
        third_person = bool(_THIRD_PERSON_RE.search(text))
        object_reference = bool(_OBJECT_RE.search(text))
        if not third_person and not object_reference:
            return Resolution(
                text=text,
                referent=None,
                resolved=True,
                ambiguous=False,
                reason_codes=("no_reference_to_resolve",),
                influences=(),
            )

        if third_person:
            owners = self._owners()
            distinct = {owner for owner, _ in owners}
            for owner, influence in owners:
                if owner in distinct:
                    influences.append(influence)
            if not distinct:
                reason_codes.append("no_referent_in_bounded_window")
                return Resolution(
                    text, None, False, False, tuple(reason_codes), tuple(influences)
                )
            if len(distinct) > 1:
                reason_codes.append("ambiguous_referent")
                return Resolution(
                    text, None, False, True, tuple(reason_codes), tuple(influences)
                )
            referent = next(iter(distinct))
            reason_codes.append("resolved_from_bounded_window")
            return Resolution(
                text, referent, True, False, tuple(reason_codes), tuple(influences)
            )

        slots = self._recent_slots()
        for _, influence in slots:
            influences.append(influence)
        distinct_slots = {slot for slot, _ in slots}
        if not distinct_slots:
            return Resolution(
                text,
                None,
                False,
                False,
                ("no_referent_in_bounded_window",),
                tuple(influences),
            )
        if len(distinct_slots) > 1:
            return Resolution(
                text, None, False, True, ("ambiguous_referent",), tuple(influences)
            )
        return Resolution(
            text,
            next(iter(distinct_slots)),
            True,
            False,
            ("resolved_from_eligible_memory",),
            tuple(influences),
        )

    def receipts(self) -> list[dict[str, Any]]:
        """Every item this context authorized, whether or not it was used."""
        return [
            *(
                EvidenceInfluence(
                    "episode",
                    str(row["id"]),
                    f"sha256:{sha256_hex(str(row.get('message') or ''))}",
                    "bounded_recent_window",
                ).to_dict()
                for row in self.episodes
            ),
            *(
                EvidenceInfluence(
                    "record",
                    str(row["id"]),
                    f"sha256:{sha256_hex(str(row.get('content') or ''))}",
                    "lifecycle_eligible_memory",
                ).to_dict()
                for row in self.records
            ),
        ]

    def _owners(self) -> list[tuple[str, EvidenceInfluence]]:
        found: list[tuple[str, EvidenceInfluence]] = []
        for row in self.episodes:
            message = str(row.get("message") or "")
            for match in _OWNER_RE.finditer(message):
                owner = match.group("owner")
                if owner in _STOP_OWNERS:
                    continue
                found.append(
                    (
                        owner,
                        EvidenceInfluence(
                            "episode",
                            str(row["id"]),
                            f"sha256:{sha256_hex(message)}",
                            "named_entity_in_bounded_window",
                        ),
                    )
                )
        return found

    def _recent_slots(self) -> list[tuple[str, EvidenceInfluence]]:
        found: list[tuple[str, EvidenceInfluence]] = []
        for row in self.records:
            fact_key = row.get("fact_key")
            if not fact_key:
                continue
            found.append(
                (
                    str(fact_key),
                    EvidenceInfluence(
                        "record",
                        str(row["id"]),
                        f"sha256:{sha256_hex(str(row.get('content') or ''))}",
                        "eligible_fact_slot",
                    ),
                )
            )
        return found


def build_resolution_context(
    store: Any,
    subject_id: str,
    *,
    scope: AuthorityScope | None = None,
    window: int = DEFAULT_WINDOW,
) -> ResolutionContext:
    """Collect the bounded, authorized evidence for one subject.

    Only this subject's rows are read. When a scope is supplied, records
    carrying a different workspace are dropped, so a proposer can never see a
    candidate from another authority scope. Records excluded from retrieval
    and non-active records are not eligible evidence.
    """
    bounded = max(0, min(int(window), MAX_WINDOW))
    episodes = store.list_episodes(subject_id)[-bounded:] if bounded else []
    excluded = set(store.excluded_record_ids(subject_id))
    records = [
        row
        for row in store.list_records(subject_id, statuses=("active",))
        if str(row["id"]) not in excluded and _in_scope(row, scope)
    ]
    return ResolutionContext(
        subject_id=subject_id,
        scope=scope,
        window=bounded,
        episodes=tuple(episodes),
        records=tuple(records),
        excluded_record_ids=frozenset(excluded),
    )


def _in_scope(record: dict[str, Any], scope: AuthorityScope | None) -> bool:
    if scope is None:
        return True
    recorded = (record.get("raw") or {}).get("authority_scope") or {}
    if not recorded:
        # Records captured before scoped authority carry no workspace claim.
        # They belong to the subject, so they stay eligible for the subject's
        # own scope; they never widen access to another subject.
        return True
    return str(recorded.get("workspace_id") or "") == scope.workspace_id
