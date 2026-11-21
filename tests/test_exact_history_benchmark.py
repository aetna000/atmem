import pytest

from atmem.benchmark.exact_history import (
    OUTPUT_BYTES,
    SUMMARY,
    HistoryLine,
    RecallCase,
    fixture_digest,
    literal_history,
    make_fixture,
    run_benchmark,
    score,
)


def test_fixture_splits_are_disjoint_and_answers_stay_out_of_queries():
    development = make_fixture("development")
    holdout = make_fixture("holdout")
    assert fixture_digest(*development) == fixture_digest(*make_fixture("development"))
    assert fixture_digest(*development) != fixture_digest(*holdout)
    assert {line.text for line in development[0]}.isdisjoint(line.text for line in holdout[0])
    for history, cases in (development, holdout):
        assert len(cases) == 24
        for case in cases:
            assert case.literal in case.question
            for target in filter(None, (case.expected, case.outdated, case.forbidden)):
                assert target not in case.question and target not in SUMMARY
            if case.expected:
                assert case.expected in literal_history(history, case.literal)
            if case.forbidden:
                assert any(case.forbidden in line.text for line in history)
                assert not literal_history(history, case.literal)


def test_literal_comparator_preserves_punctuation_bytes_and_scope():
    history = [HistoryLine("k+[1] old"), HistoryLine("k+[1] foreign", foreign=True),
               HistoryLine("k+[1] µ"), HistoryLine("k+1 unrelated")]
    assert literal_history(history, "k+[1]", budget=8) == "k+[1] µ"
    assert literal_history(history, "k+[1]", budget=7) == ""
    result = literal_history(history, "k+[1]")
    assert result == "k+[1] µ\nk+[1] old"
    assert len(result.encode()) <= OUTPUT_BYTES


def test_grader_separates_evidence_hits_from_stale_and_forbidden_delivery():
    case = RecallCase("case", "latest", "What is the value of x?", "x",
                      expected="current", outdated="earlier", forbidden="secret")
    delivered = score(case, "earlier, current", source_available=True, status="sufficient", elapsed_ns=1)
    assert delivered["target_delivered"] and delivered["stale_delivered"]
    assert not delivered["forbidden_delivered"]
    missed = score(case, "secret", source_available=True, status="partial", elapsed_ns=1)
    assert not missed["passed"] and missed["source_available"] and missed["forbidden_delivered"]


def test_native_context_returns_safe_empty_result_under_tight_budget():
    pytest.importorskip("sqlcipher3")
    report = run_benchmark("development", output_bytes=512)
    assert report["model_calls"] == 0
    native = report["arms"]["atmem_v3"]
    assert native["summary"]["errors"] == native["summary"]["forbidden_deliveries"] == 0
    for case in native["cases"]:
        assert case["bytes"] <= 512
        if case["cohort"] in {"missing", "scope"}:
            assert case["passed"] and case["bytes"] == 0
