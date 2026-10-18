import json

import pytest

from benchmarks.code_replay.cli import main, preflight
from benchmarks.code_replay.contracts import ProtocolManifest
from tests.test_code_replay_contracts import protocol_row
from tests.test_code_replay_selection import candidate


def test_preflight_is_blocked_even_when_metadata_has_qualification_hashes():
    result = preflight(ProtocolManifest.from_dict(protocol_row()))
    assert result["metadata_valid"]
    assert not result["ready"] and not result["can_dispatch"]
    assert result["expected_sessions"] == 60
    assert {r["code"] for r in result["blockers"]} >= {
        "execution_authorization_not_integrated", "product_capability_verification_not_integrated",
        "experience_applicability_not_qualified", "rich_structure_not_qualified",
    }


def test_cli_validation_and_preflight_write_no_side_files_or_network(tmp_path, capsys, monkeypatch):
    import socket
    import subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError("read-only phase must not dispatch or contact network")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    source = tmp_path / "protocol.json"
    source.write_text(json.dumps(protocol_row()))
    before = list(tmp_path.iterdir())
    assert main(["validate", "protocol", str(source)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["metadata_valid"] and not result["evidence_verified"] and not result["authorized"]
    assert main(["preflight", str(source)]) == 2
    assert not json.loads(capsys.readouterr().out)["can_dispatch"]
    assert list(tmp_path.iterdir()) == before


@pytest.mark.parametrize("payload", ['{"secret":"do-not-echo"}', '{"bad":"do-not-echo"', 'not-json-do-not-echo'])
def test_cli_does_not_echo_malformed_payloads(payload, tmp_path, capsys):
    source = tmp_path / "bad.json"
    source.write_text(payload)
    assert main(["validate", "protocol", str(source)]) == 1
    result = capsys.readouterr()
    assert "do-not-echo" not in result.out + result.err
    assert json.loads(result.out)["code"] == "invalid_metadata_input"


def test_cli_selection_surfaces_blockers_without_reducing_task_count(tmp_path, capsys):
    source = tmp_path / "discovery.json"
    row = {"format": "atmem-click-discovery-input-v1", "anchor_commit": candidate(0).to_dict()["commit"],
           "candidates": [candidate(i).to_dict() for i in range(4)]}
    source.write_text(json.dumps(row))
    assert main(["select", str(source)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked_insufficient_eligible"
    assert result["selected_commits"] == []
    row["candidates"] = [candidate(i).to_dict() for i in range(8)]
    source.write_text(json.dumps(row))
    assert main(["select", str(source)]) == 0
    assert len(json.loads(capsys.readouterr().out)["selected_commits"]) == 5


def test_no_run_or_approval_bypass_command(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["run", "--approve", "--ignore-trust"])
    assert exc.value.code == 2
    capsys.readouterr()


def test_rejects_symlink_and_oversized_metadata(tmp_path, capsys):
    source = tmp_path / "protocol.json"
    source.write_text(json.dumps(protocol_row()))
    link = tmp_path / "link.json"
    link.symlink_to(source)
    assert main(["validate", "protocol", str(link)]) == 1
    source.write_bytes(b" " * 2_000_001)
    assert main(["validate", "protocol", str(source)]) == 1
    capsys.readouterr()
