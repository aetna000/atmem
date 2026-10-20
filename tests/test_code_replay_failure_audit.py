import base64

import pytest

from benchmarks.code_replay.failure_audit import audit_trial


def events(raw, *, output=b"", infra=False, passed=False):
    return [{"envelope": {"event_type": kind, "payload": payload}} for kind, payload in [
        ("agent.attempt", {"patch_source_bytes": {"src/click/example.py": base64.b64encode(raw).decode()}}),
        ("trial.completed", {"result": {"run_id": "example", "infra_invalid": infra, "functional_pass": passed},
                             "grade_output_base64": base64.b64encode(output).decode()})]]


def test_invalid_candidate_is_not_excused_or_regraded():
    proof = audit_trial(events(b"else:\n    pass\n", output=b"src/click/example.py SyntaxError", infra=True))
    assert proof["classification"] == "candidate_syntax_error_corroborated_by_grader"
    assert proof["changed_source_syntax_errors"][0]["line"] == 1
    assert proof["historical_score_changed"] is False and proof["exclude_from_denominator"] is False


def test_candidate_is_never_executed():
    proof = audit_trial(events(b"raise RuntimeError('would execute')\n", passed=True))
    assert proof["classification"] == "passed" and not proof["candidate_code_executed"]


def test_environment_error_not_explained_by_syntax_stays_unresolved():
    proof = audit_trial(events(b"pass\n", output=b"missing pytest dependency", infra=True))
    assert proof["classification"] == "environment_flag_requires_separate_investigation"


def test_uncorroborated_syntax_not_assumed_grader_cause():
    assert audit_trial(events(b"else:", infra=True))["classification"] == "changed_source_syntax_error_requires_attribution"


def test_missing_or_duplicate_terminal_cannot_be_scored():
    with pytest.raises(ValueError, match="exactly one"):
        audit_trial([])
    data = events(b"pass")
    with pytest.raises(ValueError, match="exactly one"):
        audit_trial(data + data)
