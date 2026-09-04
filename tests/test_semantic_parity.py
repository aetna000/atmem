"""CLI and dashboard must project identical semantic-health semantics.

SC-002 requires fixtures for every health state to agree across surfaces. The
dashboard endpoint and the CLI both project `inspect_semantic_health`, so these
tests compare the real payloads rather than asserting that the HTML asset
mentions the endpoint.
"""

from __future__ import annotations

import json
import sys

import pytest

from atmem import Memory
from atmem import cli
from atmem.semantic import SemanticIndex, default_index_path, inspect_semantic_health


class FixtureEmbedder:
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


def _seeded(tmp_path):
    database = tmp_path / "memory.db"
    memory = Memory(database)
    memory.remember(
        "u1",
        "I prefer aisle seats.",
        interpreted_fact="I prefer aisle seats.",
        interpreted_fact_key="travel.seat",
    )
    memory.close()
    return database


def _dashboard_payload(database, subject="u1"):
    """The exact projection `ControlPlaneManager.semantic_health` returns."""

    memory = Memory(database, retain_query_text=False, auto_vectors=False)
    index_path = default_index_path(database)
    if not index_path.exists():
        from atmem.semantic import evaluate_semantic_health

        memory.close()
        return evaluate_semantic_health(subject, active_epoch=None).to_dict()
    index = SemanticIndex(index_path, policy=memory.policy)
    try:
        return inspect_semantic_health(index, memory, subject).to_dict()
    finally:
        index.close()
        memory.close()


def _cli_payload(database, monkeypatch, capsys, subject="u1"):
    monkeypatch.setattr(
        sys,
        "argv",
        ["atmem", "semantic", "status", str(database), "--subject", subject, "--json"],
    )
    cli.main()
    return json.loads(capsys.readouterr().out)


def _make_stale(database) -> None:
    memory = Memory(database, auto_vectors=False)
    index = SemanticIndex(default_index_path(database), policy=memory.policy)
    try:
        epoch = index.active_epoch("u1")
        index._conn.execute(
            "UPDATE vector_epochs SET dirty = 1 WHERE epoch_id = ?",
            (epoch["epoch_id"],),
        )
        index._conn.commit()
    finally:
        index.close()
        memory.close()


@pytest.mark.parametrize(
    ("state", "mutate"),
    [
        ("weak", None),
        ("stale", _make_stale),
    ],
)
def test_cli_and_dashboard_agree_for_each_state(
    tmp_path, monkeypatch, capsys, state, mutate
) -> None:
    database = _seeded(tmp_path)
    if mutate is not None:
        mutate(database)

    dashboard = _dashboard_payload(database)
    cli_result = _cli_payload(database, monkeypatch, capsys)

    assert cli_result["status"] == state
    assert cli_result == dashboard


def test_cli_and_dashboard_agree_when_no_index_exists(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "memory.db"
    memory = Memory(database, auto_vectors=False)
    memory.remember("u1", "I prefer aisle seats.")
    memory.close()

    dashboard = _dashboard_payload(database)
    cli_result = _cli_payload(database, monkeypatch, capsys)

    assert cli_result["status"] == "missing"
    assert cli_result == dashboard


def test_cli_and_dashboard_agree_for_a_healthy_index(
    tmp_path, monkeypatch, capsys
) -> None:
    database = _seeded(tmp_path)
    memory = Memory(database, auto_vectors=False)
    index = SemanticIndex(default_index_path(database), policy=memory.policy)
    try:
        index.build(memory, "u1", FixtureEmbedder())
    finally:
        index.close()
        memory.close()

    dashboard = _dashboard_payload(database)
    cli_result = _cli_payload(database, monkeypatch, capsys)

    assert cli_result["status"] == "healthy"
    assert cli_result == dashboard
