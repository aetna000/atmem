from __future__ import annotations

import json
import sys

import pytest

from atmem import Memory
from atmem import cli
from atmem.semantic import SemanticIndex


class LocalSemanticEmbedder:
    @property
    def identity(self):
        return {
            "provider": "sentence-transformers",
            "model": "fixture/local-model",
            "version": "fixture-1",
            "normalization": "l2",
        }

    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, _text):
        return [1.0, 0.0]


def test_semantic_setup_requires_download_consent_and_keeps_fallback(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "memory.db"
    memory = Memory(database)
    memory.remember("u1", "I prefer aisle seats.")
    memory.close()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "atmem", "semantic", "setup", str(database), "--subject", "u1",
            "--provider", "sentence-transformers", "--model", "fixture/local-model",
            "--json",
        ],
    )

    cli.main()

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "cancelled"
    assert result["fallback"] == "hashing-diagnostic"
    assert "No download or egress occurred" in result["message"]


def test_semantic_setup_builds_and_passes_paraphrase_smoke_test(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "memory.db"
    memory = Memory(database)
    memory.remember("u1", "I prefer aisle seats.")
    memory.close()
    monkeypatch.setattr(
        "atmem.semantic.create_embedder", lambda *_args, **_kwargs: LocalSemanticEmbedder()
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "atmem", "semantic", "setup", str(database), "--subject", "u1",
            "--provider", "sentence-transformers", "--model", "fixture/local-model",
            "--model-version", "fixture-1", "--allow-download",
            "--smoke-query", "Which kind of seat should be booked?", "--json",
        ],
    )

    cli.main()

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "complete"
    assert result["health"]["status"] == "healthy"
    assert result["smoke_test"]["passed"] is True
    # SC-005 bounds real operator decisions, so the count must be derived from
    # the decisions the flow actually consumed rather than a fixed literal.
    assert result["decision_count"] == len(result["decisions"])
    assert result["decisions"] == ["download_consent_flag"]
    assert result["decision_count"] <= 6
    checked = Memory(database, auto_vectors=False)
    try:
        assert any(
            row["event_type"] == "semantic.setup_approved"
            for row in checked.audit("u1")["audit_log"]
        )
    finally:
        checked.close()


def test_interactive_setup_counts_every_real_operator_decision(
    tmp_path, monkeypatch, capsys
) -> None:
    """A prompted run must report more decisions than a fully flagged run."""

    database = tmp_path / "memory.db"
    memory = Memory(database)
    memory.remember("u1", "I prefer aisle seats.")
    memory.close()
    monkeypatch.setattr(
        "atmem.semantic.create_embedder", lambda *_args, **_kwargs: LocalSemanticEmbedder()
    )
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    answers = iter(["2", "y"])
    monkeypatch.setattr("builtins.input", lambda *_args: next(answers))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "atmem", "semantic", "setup", str(database), "--subject", "u1",
            "--model-version", "fixture-1",
            "--smoke-query", "Which kind of seat should be booked?", "--json",
        ],
    )

    cli.main()

    # The interactive flow prints the recommendation list before the payload.
    output = capsys.readouterr().out
    result = json.loads(output[output.index("{") :])
    assert result["decisions"] == ["model_selection", "download_consent"]
    assert result["decision_count"] == 2
    assert result["decision_count"] <= 6


def test_base_install_hashing_setup_never_imports_optional_runtime(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "memory.db"
    memory = Memory(database)
    memory.remember(
        "u1",
        "I prefer aisle seats.",
        interpreted_fact="I prefer aisle seats.",
        interpreted_fact_key="travel.seat",
    )
    memory.close()
    real_import = __import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith("sentence_transformers"):
            raise AssertionError("optional semantic runtime was imported")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded_import)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "atmem", "semantic", "setup", str(database), "--subject", "u1",
            "--provider", "hashing", "--model", "64", "--json",
        ],
    )

    cli.main()

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "complete"
    assert result["health"]["status"] == "weak"
    assert result["smoke_test"]["passed"] is True


def test_provider_failure_preserves_existing_hashing_epoch(
    tmp_path, monkeypatch
) -> None:
    database = tmp_path / "memory.db"
    memory = Memory(database)
    memory.remember(
        "u1",
        "I prefer aisle seats.",
        interpreted_fact="I prefer aisle seats.",
        interpreted_fact_key="travel.seat",
    )
    memory.close()
    before_memory = Memory(database, auto_vectors=False)
    before_index = SemanticIndex(f"{database}.vectors.db", policy=before_memory.policy)
    try:
        previous_epoch = before_index.active_epoch("u1")["epoch_id"]
    finally:
        before_index.close()
        before_memory.close()
    monkeypatch.setattr(
        "atmem.semantic.create_embedder",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("provider failed")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "atmem", "semantic", "setup", str(database), "--subject", "u1",
            "--provider", "sentence-transformers", "--model", "fixture/local-model",
            "--allow-download", "--json",
        ],
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        cli.main()

    checked = Memory(database, auto_vectors=False)
    index = SemanticIndex(f"{database}.vectors.db", policy=checked.policy)
    try:
        assert index.active_epoch("u1")["epoch_id"] == previous_epoch
    finally:
        index.close()
        checked.close()
