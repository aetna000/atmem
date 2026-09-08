"""Spec 009 graph retrieval extension for Spec 008's signal registry."""

from __future__ import annotations

from typing import Any

from atmem.retrieve.signals import register_signal, unregister_signal
from atmem.graph.traverse import traverse_authorized


NAME = "extension.entity_graph"
VERSION = "evidence-bounded-path-v1"


def graph_candidates(store: Any, subject_id: str, query: str, **budgets: Any):
    return [path.to_dict() for path in traverse_authorized(store, subject_id, query, **budgets)]


def register() -> None:
    unregister_signal(NAME)
    register_signal(NAME, VERSION, graph_candidates)
