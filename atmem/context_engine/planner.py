"""Deterministic information-need routing for Context Engine V3."""

from __future__ import annotations

import re

from atmem.core.canonical import sha256_hex

from .contracts import EvidenceObligation, QueryPlan


class DeterministicPlanner:
    identity = "context-planner-deterministic-v1"

    def plan(self, query: str) -> QueryPlan:
        normalized = " ".join(query.split())
        if not normalized:
            raise ValueError("query is required")
        obligations: list[EvidenceObligation] = []
        comparison = re.search(
            r"\bcompare\s+(?:the\s+)?([A-Za-z0-9_-]+)\s+and\s+(?:the\s+)?([A-Za-z0-9_-]+)",
            normalized,
            re.IGNORECASE,
        )
        if comparison:
            for index, entity in enumerate(comparison.groups(), 1):
                obligations.append(EvidenceObligation(
                    obligation_id=f"comparison-{index}", kind="comparison_side",
                    entity=entity.title(), relation_or_action="compare",
                ))
        else:
            lowered = normalized.casefold()
            if lowered.startswith("how "):
                kind = "ordered_steps"
            elif "what changed" in lowered or "before" in lowered or "after" in lowered:
                kind = "before_action_after"
            elif re.search(r"\b(wireless-only|without|no\s+\w+)\b", lowered):
                kind = "premise_check"
            elif lowered.startswith("why "):
                kind = "claim_support"
            else:
                kind = "subject_relation_value"
            significant = [
                token for token in re.findall(r"[A-Za-z0-9#_-]+", normalized)
                if token.casefold() not in {"the", "a", "an", "is", "are", "what", "which", "where", "when", "how", "do", "does"}
            ]
            obligations.append(EvidenceObligation(
                obligation_id="need-1", kind=kind,
                entity=significant[-1] if significant else "query",
                relation_or_action=" ".join(significant[:4]) or "lookup",
                polarity="negative" if kind == "premise_check" else "unknown",
            ))
        pools = {
            "raw_state": (normalized,),
            "fact": (normalized,),
            "entity": (normalized,),
            "transition": (normalized,) if any(o.kind == "before_action_after" for o in obligations) else (),
            "procedure": (normalized,) if any(o.kind == "ordered_steps" for o in obligations) else (),
            "rule": (normalized,),
            "gotcha": (normalized,) if any(o.kind == "claim_support" for o in obligations) else (),
            "premise": (normalized,) if any(o.kind == "premise_check" for o in obligations) else (),
        }
        digest = "sha256:" + sha256_hex(normalized)
        return QueryPlan(
            plan_id="plan3_" + digest[7:39], query_sha256=digest,
            obligations=tuple(obligations), pool_queries=pools,
            planner_identity=self.identity, deterministic_fallback=True,
        )
