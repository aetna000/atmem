"""Gate arithmetic fixtures only; no model or performance claims."""
from benchmarks.code_replay.efficiency import metrics, implementation_present
import pytest


def rows():
    return [{"arm": arm, "task_order": order, "passed": True, "functional_pass": True,
             "infra_invalid": False, "stage_ms": {"setup": 1, "index": 0, "retrieval": 0, "solver": 1, "grading": 1},
             "tool_calls": 1, "context_bytes": 0, "tokens": {"input_tokens": 100 if arm == "A" else 80,
             "output_tokens": 1, "cached_tokens": 0}} for order in range(1, 6) for arm in "AC"]


def test_exact_twenty_percent_is_accepted_without_float_boundary_error():
    result = metrics(rows(), required_passes=5)
    assert result["fallback_20"] and not result["target_50"]


def test_quality_floor_and_unknown_usage_cannot_be_bought_with_token_saving():
    data = rows()
    data[1]["functional_pass"] = False
    assert not metrics(data, required_passes=5)["fallback_20"]
    data = rows()
    data[1]["tokens"]["input_tokens"] = None
    assert not metrics(data)["fallback_20"]


def test_heading_only_context_is_not_implementation_readiness():
    with pytest.raises(ValueError, match="implementation"):
        implementation_present("1: # Prompts\n2: ## Hidden input\n")
    implementation_present("4: def render(value):\n5:     return value\n")


def test_progressive_cannot_win_without_observed_atmem_source():
    data = rows()
    assert not metrics(data, required_passes=5, required_mcp_source=True)["fallback_20"]
    for row in data:
        if row["arm"] == "C":
            row["mcp_source_observed"] = True
    assert metrics(data, required_passes=5, required_mcp_source=True)["fallback_20"]
    data[1]["mcp_source_observed"] = False
    result = metrics(data, required_passes=5, required_mcp_source=True)
    assert not result["capability_gate"] and result["summary"]["C"]["functional_pass"] == 5


def test_focused_initial_source_requires_real_submission_in_every_trial():
    data = rows()
    assert not metrics(data, required_passes=5, required_initial_source=True)["fallback_20"]
    for row in data:
        if row["arm"] == "C":
            row["atmem_source_submitted"] = True
    assert metrics(data, required_passes=5, required_initial_source=True)["fallback_20"]
    data[1]["atmem_source_submitted"] = False
    assert not metrics(data, required_passes=5, required_initial_source=True)["capability_gate"]


def test_p11_requires_exact_corrected_qualification_and_source_profile():
    from benchmarks.code_replay.efficiency import validate
    from benchmarks.code_replay.control import SCHEDULE
    from benchmarks.code_replay.freeze import digest
    package = dict(format="atmem-code-structural-efficiency-cohort-v1", schedule=SCHEDULE,
        experience=False, tasks=[{}] * 5, cohort_id="efficiency-p11c1-20261017",
        run_prefix="efficiency-p11c1", delivery_mode="focused_progressive",
        initial_context_bytes=4096, required_initial_source=True,
        localization_qualification="implementation-localization-p11r1-logging",
        host_qualification="progressive-host-p11", budgets={"context_bytes": 4096},
        code_sha256={}, runtime_sha256={})
    validate(package, digest(package))
    for key, wrong in (("localization_qualification", "implementation-localization-p11-logging"),
                       ("host_qualification", "progressive-host-p10"),
                       ("required_initial_source", False), ("initial_context_bytes", 8192)):
        invalid = {**package, key: wrong}
        with pytest.raises(ValueError, match="qualification mandatory"):
            validate(invalid, digest(invalid))
