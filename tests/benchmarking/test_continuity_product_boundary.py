"""Structural tripwires complement installed external-fault acceptance.

Not a sandbox and not sufficient alone: review public data flow and actual effects.
"""
import ast
from pathlib import Path

import pytest


FORBIDDEN = {'update_state', 'bulk_update_state', 'get_state_history', 'outcome', 'begin', 'renew', 'snapshot', 'reconcile', 'repair', 'retry'}


def inspect_workload(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(part in (node.module or '').split('.') for part in ['runtime', 'destination', 'oracle', 'service', 'store']):
            raise ValueError('private recovery or oracle import')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN:
            raise ValueError('workload contains authority/recovery or oracle call')


def test_workload_has_no_recovery_or_oracle_operations():
    path = Path(__file__).resolve().parents[2] / 'benchmarks/agent_continuity/retail_graph.py'
    inspect_workload(path.read_text())


def test_worker_has_no_private_recovery_or_oracle_operations():
    path = Path(__file__).resolve().parents[2] / 'benchmarks/agent_continuity/retail_worker.py'
    inspect_workload(path.read_text())


@pytest.mark.parametrize('planted', ['from .runtime import recover', 'graph.update_state(config, repaired)', 'oracle.snapshot()'])
def test_boundary_tripwire_rejects_planted_compensation(planted):
    with pytest.raises(ValueError):
        inspect_workload(planted)


def test_shipped_continuity_has_no_benchmark_dependency():
    root = Path(__file__).resolve().parents[2] / 'atmem/continuity'
    for file in root.glob('*.py'):
        for node in ast.walk(ast.parse(file.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith(('benchmarks', 'tests'))
            elif isinstance(node, ast.Import):
                assert all(not name.name.startswith(('benchmarks', 'tests')) for name in node.names)
