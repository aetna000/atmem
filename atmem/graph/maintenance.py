"""Graph repair registration through the shared maintenance interface."""

from __future__ import annotations

from atmem.maintenance import register_maintenance_job


def register_graph_repair(callback):
    register_maintenance_job("graph.rebuild", callback)
