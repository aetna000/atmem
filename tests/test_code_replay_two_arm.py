import pytest

from benchmarks.code_replay.contracts import StructureExperienceProtocol, StructureExperienceRun, ProtocolManifest, RunManifest
from benchmarks.code_replay.cli import preflight
from tests.test_code_replay_contracts import protocol_row, run_row


def paired_row():
    row = protocol_row()
    row.update(format=StructureExperienceProtocol.format, arms=["C", "D"], repetitions=2, schedule=[["C", "D"], ["D", "C"]])
    return row


def test_distinct_two_arm_protocol_retains_blocking_readiness_and_twenty_sessions():
    row = paired_row()
    protocol = StructureExperienceProtocol.from_dict(row)
    assert preflight(protocol)["expected_sessions"] == 20
    assert not preflight(protocol)["can_dispatch"]
    with pytest.raises(ValueError):
        ProtocolManifest.from_dict(row)
    with pytest.raises(ValueError):
        StructureExperienceProtocol.from_dict(protocol_row())


def test_run_binding_rejects_excluded_arm_and_repetition():
    protocol = StructureExperienceProtocol.from_dict(paired_row())
    row = run_row(protocol)
    with pytest.raises(ValueError, match="arm/repetition"):
        RunManifest.from_dict(row).bind(protocol)
    row.update(arm="C", repetition=2)
    RunManifest.from_dict(row).bind(protocol)
    row.update(repetition=3)
    with pytest.raises(ValueError, match="arm/repetition"):
        RunManifest.from_dict(row).bind(protocol)


def test_zero_additional_spend_cap_is_valid_only_in_distinct_reduced_protocol():
    row = paired_row()
    row["budgets"]["cost_microusd"] = 0
    row["total_cost_microusd"] = 0
    protocol = StructureExperienceProtocol.from_dict(row)
    run = run_row(protocol)
    run.update(format=StructureExperienceRun.format, arm="C")
    StructureExperienceRun.from_dict(run).bind(protocol)
    with pytest.raises(ValueError):
        RunManifest.from_dict(run)
