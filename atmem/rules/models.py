from dataclasses import dataclass

from atmem.contracts.feedback import RuleCandidate, RulePredicate


@dataclass(frozen=True)
class CompiledRule:
    rule_id: str
    candidate_sha256: str
    tool: str
    schema_version: str
    predicates: tuple[RulePredicate, ...]
    compiler_version: str = "atmem-data-rules-v1"


@dataclass(frozen=True)
class RuleDecision:
    allowed: bool
    reason: str
    applicable_rule_ids: tuple[str, ...]
    approval_required: bool = False
