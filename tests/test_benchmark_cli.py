from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from atmem.cli import main


FIXTURES = Path(__file__).parent / "fixtures" / "benchmarks"


def test_benchmark_help_is_discoverable(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["atmem", "benchmark"])
    main()
    output = capsys.readouterr().out
    assert "benchmark run" in output
    assert "import-longmemeval" in output


def test_cli_writes_passing_report(monkeypatch, tmp_path, capsys) -> None:
    output = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["atmem", "benchmark", "run", "--output", str(output)])
    main()
    assert json.loads(output.read_text())["passed"] is True
    assert "PASSED" in capsys.readouterr().out


def test_cli_optional_skip_exits_two(monkeypatch) -> None:
    monkeypatch.delenv("ATMEM_BENCHMARK_LOCAL_ATBOT", raising=False)
    monkeypatch.setattr(sys, "argv", ["atmem", "benchmark", "run", "--profile", "local-atbot", "--json"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_cli_import_and_compare(monkeypatch, tmp_path) -> None:
    imported = tmp_path / "imported.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["atmem", "benchmark", "import-longmemeval", str(FIXTURES / "longmemeval-small.jsonl"), "--output", str(imported)],
    )
    main()
    assert json.loads(imported.read_text())["counts"]["supported"] == 1

    left = json.loads((FIXTURES / "external-result-small.json").read_text())
    right = {**left, "system": "mem0-oss"}
    right_path = tmp_path / "right.json"
    right_path.write_text(json.dumps(right))
    comparison = tmp_path / "comparison.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["atmem", "benchmark", "compare", str(FIXTURES / "external-result-small.json"), str(right_path), "--output", str(comparison)],
    )
    main()
    compared = json.loads(comparison.read_text())
    assert compared["fair_comparison"] is True
    assert compared["overall"]["outcome"] == "equal"


def test_cli_json_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["atmem", "benchmark", "profiles", "--json"])
    main()
    assert len(json.loads(capsys.readouterr().out)["profiles"]) == 4
