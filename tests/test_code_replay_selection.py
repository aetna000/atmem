"""Selection plumbing fixtures, not real Click eligibility records."""

from copy import deepcopy

import pytest

from benchmarks.code_replay.select import CHECKS, SelectionCandidate, SelectionLedger, select_candidates


def candidate(index, *, change_kind="functional", rejected=None):
    return SelectionCandidate.from_dict({
        "format": SelectionCandidate.format,
        "commit": f"{200 - index:040x}", "mainline_parent": f"{199 - index:040x}",
        "change_kind": change_kind,
        "checks": {name: {"eligible": name != rejected, "evidence_sha256": "a" * 64} for name in CHECKS},
    })


def test_latest_five_eligible_replayed_oldest_first_with_complete_exclusions():
    candidates = [candidate(0, change_kind="docs_only"), candidate(1, rejected="pre_solution_requirements")]
    candidates += [candidate(i) for i in range(2, 10)]
    ledger = select_candidates(candidates[0].to_dict()["commit"], candidates)
    row = ledger.to_dict()
    assert row["selected_commits"] == [candidate(i).to_dict()["commit"] for i in (6, 5, 4, 3, 2)]
    assert len(row["entries"]) == 10
    assert row["entries"][0]["reason_codes"] == ["docs_only"]
    assert row["entries"][1]["reason_codes"] == ["pre_solution_requirements"]
    assert row["entries"][-1]["disposition"] == "eligible_older_than_latest_five"
    assert row["qualification"] == "declared_not_execution_verified"
    assert SelectionLedger.from_json(ledger.canonical_json) == ledger


def test_insufficient_candidates_block_without_silently_reducing_or_expanding():
    candidates = [candidate(i) for i in range(4)]
    row = select_candidates(candidates[0].to_dict()["commit"], candidates).to_dict()
    assert row["status"] == "blocked_insufficient_eligible"
    assert row["selected_commits"] == []
    assert len(row["entries"]) == 4


@pytest.mark.parametrize("change", ["wrong_anchor", "gap", "reversed", "duplicate", "too_many"])
def test_history_must_be_contiguous_and_bounded(change):
    candidates = [candidate(i) for i in range(6)]
    anchor = candidates[0].to_dict()["commit"]
    if change == "wrong_anchor":
        anchor = "f" * 40
    elif change == "gap":
        candidates.pop(2)
    elif change == "reversed":
        candidates.reverse()
    elif change == "duplicate":
        candidates[2] = candidates[1]
    else:
        candidates = [candidate(i) for i in range(101)]
    with pytest.raises(ValueError):
        select_candidates(anchor, candidates)


@pytest.mark.parametrize("mutate", [
    lambda r: r.__setitem__("memory_helpfulness", 1),
    lambda r: r["checks"]["tractable_scope"].__setitem__("eligible", "true"),
    lambda r: r["checks"].pop("discriminating_tests"),
    lambda r: r["checks"]["discriminating_tests"].__setitem__("evidence_sha256", "later"),
])
def test_selection_does_not_accept_outcome_scores_or_missing_evidence(mutate):
    row = candidate(0).to_dict()
    mutate(row)
    with pytest.raises(ValueError):
        SelectionCandidate.from_dict(row)


def test_ledger_cannot_be_edited_to_hide_exclusions_or_select_different_tasks():
    candidates = [candidate(i) for i in range(8)]
    original = select_candidates(candidates[0].to_dict()["commit"], candidates).to_dict()
    for key, value in (("entries", []), ("selected_commits", original["selected_commits"][::-1]),
                       ("search_horizon", 101), ("search_horizon", 100.0), ("qualification", "verified")):
        row = deepcopy(original)
        row[key] = value
        with pytest.raises(ValueError, match="selection rule"):
            SelectionLedger.from_dict(row)
