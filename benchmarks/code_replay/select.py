"""Answer-blind, first-parent selection ledger; no repository or model access.

Eligibility evidence is supplied by evaluator preparation. This module validates
its shape and selection rule, not whether a test or environment really passed.
"""

from __future__ import annotations

import json
from typing import Any

from benchmarks.code_replay.contracts import Manifest, closed, commit, digest, sequence


CHECKS = (
    "pre_solution_requirements", "reproducible_environment", "discriminating_tests",
    "tractable_scope", "single_feature",
)
KINDS = frozenset({"functional", "docs_only", "dependency_only", "packaging_only", "ambiguous_multi_feature"})


class SelectionCandidate(Manifest):
    format = "atmem-click-selection-candidate-v1"

    @classmethod
    def validate(cls, value: Any) -> None:
        row = cls.envelope(value, {"commit", "mainline_parent", "change_kind", "checks"})
        commit(row["commit"], "commit")
        commit(row["mainline_parent"], "mainline_parent")
        if row["commit"] == row["mainline_parent"]:
            raise ValueError("self-parent commit")
        if not isinstance(row["change_kind"], str) or row["change_kind"] not in KINDS:
            raise ValueError("unsupported change kind")
        checks = closed(row["checks"], set(CHECKS), "checks")
        for name, check in checks.items():
            closed(check, {"eligible", "evidence_sha256"}, name)
            if type(check["eligible"]) is not bool:
                raise ValueError("eligibility must be boolean")
            digest(check["evidence_sha256"], name)


def _build(anchor: str, candidates: list[dict]) -> dict:
    commit(anchor, "anchor_commit")
    sequence(candidates, "candidates", minimum=1, maximum=100)
    for row in candidates:
        SelectionCandidate.from_dict(row)
    if candidates[0]["commit"] != anchor:
        raise ValueError("selection must start at pinned anchor")
    seen = {row["commit"] for row in candidates}
    if len(seen) != len(candidates) or candidates[-1]["mainline_parent"] in seen:
        raise ValueError("repeated or cyclic first-parent history")
    if any(a["mainline_parent"] != b["commit"] for a, b in zip(candidates, candidates[1:])):
        raise ValueError("first-parent history has gaps or wrong order")
    entries, selected = [], []
    for candidate in candidates:
        reasons = []
        if candidate["change_kind"] != "functional":
            reasons.append(candidate["change_kind"])
        reasons.extend(name for name, check in candidate["checks"].items() if not check["eligible"])
        eligible = not reasons
        if eligible and len(selected) < 5:
            selected.append(candidate["commit"])
            disposition = "selected"
        elif eligible:
            disposition = "eligible_older_than_latest_five"
        else:
            disposition = "excluded"
        entries.append({"commit": candidate["commit"], "eligible": eligible,
                        "disposition": disposition, "reason_codes": sorted(reasons)})
    # Do not present fewer than five as a completed selection. Keep the complete
    # inspected ledger so a blocker cannot silently widen the discovery horizon.
    complete = len(selected) == 5
    return {
        "format": SelectionLedger.format, "anchor_commit": anchor, "search_horizon": 100,
        "qualification": "declared_not_execution_verified", "candidates": candidates,
        "entries": entries, "selected_commits": list(reversed(selected)) if complete else [],
        "status": "selected" if complete else "blocked_insufficient_eligible",
    }


class SelectionLedger(Manifest):
    format = "atmem-click-selection-ledger-v1"

    @classmethod
    def validate(cls, value: Any) -> None:
        row = cls.envelope(value, {"anchor_commit", "search_horizon", "qualification", "candidates",
                                  "entries", "selected_commits", "status"})
        expected = _build(row["anchor_commit"], row["candidates"])
        if json.dumps(row, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
            raise ValueError("ledger does not match frozen selection rule")


def select_candidates(anchor: str, candidates: list[SelectionCandidate]) -> SelectionLedger:
    if type(candidates) is not list or any(not isinstance(item, SelectionCandidate) for item in candidates):
        raise ValueError("candidates must be validated SelectionCandidate objects")
    return SelectionLedger.from_dict(_build(anchor, [item.to_dict() for item in candidates]))
