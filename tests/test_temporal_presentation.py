from collections import Counter

import pytest

from atmem.benchmark.exact_history import make_fixture, score
from tools.benchmark_temporal_presentation import compare, newest_first


def test_presentation_preserves_all_spans_and_bytes_including_duplicate_times():
    spans = ["At 08:00 café", "untimed µ", "At 11:00 one", "At 11:00 two", "At 08:00 café"]
    native = "\n\n".join(spans)
    presented = newest_first(native)
    assert presented.split("\n\n") == [spans[2], spans[3], spans[0], spans[4], spans[1]]
    assert len(presented.encode()) == len(native.encode())
    assert newest_first("") == ""


def test_reader_can_choose_stale_after_retrieval_pass_and_receives_only_delivered_text():
    history, cases = make_fixture("development")
    first, second = [case for case in cases if case.cohort == "latest"][:2]
    native_rows = []
    for case in (first, second):
        spans = [line.text for line in history if case.literal in line.text]
        # Only the stale span reached the model in the second case.
        context = "\n\n".join(spans if case == first else spans[:1])
        row = score(case, context, source_available=True, status="sufficient", elapsed_ns=0)
        native_rows.append(dict(row, context=context))
    retrieval = {"split": "development", "fixture_sha256": "fixture", "native_context_service_sha256": "service",
                 "output_budget_bytes": 512, "arms": {"atmem_v3": {"cases": native_rows}}}
    replies = iter([first.outdated, first.expected, second.outdated, f"{second.expected} or {second.outdated}"])
    prompts = []

    def reader(prompt):
        prompts.append(prompt)
        return next(replies)

    report = compare(retrieval, reader)
    assert len(prompts) == report["reader_calls"] == 4
    assert all(second.expected not in prompt for prompt in prompts)
    assert report["retrieval_passes"] == 1
    assert report["summary"]["native_order"] == {"stale": 1, "other": 1, "current": 0, "stale_on_retrieval_pass": 1}
    assert report["summary"]["newest_first"] == {"stale": 1, "other": 0, "current": 1, "stale_on_retrieval_pass": 0}
    assert report["native_to_newest_first"] == {"stale->current": 1, "other->stale": 1}
    for row in report["cases"]:
        control, candidate = (row["arms"][arm]["context"] for arm in ("native_order", "newest_first"))
        assert Counter(control.split("\n\n")) == Counter(candidate.split("\n\n"))

    retrieval["output_budget_bytes"] = native_rows[0]["bytes"] - 1
    with pytest.raises(ValueError, match="size"):
        compare(retrieval, lambda _: pytest.fail("over-budget evidence reached reader"))
