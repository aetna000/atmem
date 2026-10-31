"""Trusted recovery parent rejects control drift before any workload subprocess."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'specs/048-dolphin-execution-readiness/atsys/run_recovery_epoch.py'
spec = importlib.util.spec_from_file_location('recovery_parent_test', PATH)
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)


def contract(tmp_path):
    sentinel = tmp_path / 'validator.py'
    sentinel.write_text('raise RuntimeError("must not run until accepted")\n')
    path = tmp_path / 'contract.json'
    manifest = tmp_path / 'source.json'
    manifest.write_text(json.dumps([{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (ROOT / 'benchmarks/dolphinbench').glob('*.py')]))
    bundle = tmp_path / 'bundle.json'
    bundle.write_text(json.dumps({'source_manifest': {'path': str(manifest), 'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()}}))
    value = {'trusted_files': [{'path': str(PATH), 'sha256': hashlib.sha256(PATH.read_bytes()).hexdigest()}, {'path': str(sentinel), 'sha256': hashlib.sha256(sentinel.read_bytes()).hexdigest()}],
        'pilot_tasks': 20, 'cumulative_cap_usd': 10, 'full600_authorized': False,
        'implementation_task': 'task-test', 'control_directory': str(tmp_path / 'private'),
        'independent_validator': str(sentinel), 'descriptor': str(sentinel),
        'historical_bundle': str(bundle), 'proofs': str(sentinel)}
    for p in [ROOT / 'specs/048-dolphin-execution-readiness/atsys/run_pilot.py', ROOT / 'specs/048-dolphin-execution-readiness/atsys/validate_pilot.py', bundle]:
        value['trusted_files'].append({'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    path.write_text(json.dumps(value))
    return path, value, sentinel


def test_changed_validator_blocks_before_any_subprocess(tmp_path, monkeypatch):
    path, _, sentinel = contract(tmp_path)
    sentinel.write_text('print("weakened acceptance")\n')
    monkeypatch.setattr(parent.subprocess, 'run', lambda *a, **k: pytest.fail('dispatched before trusted-file verification'))
    with pytest.raises(ValueError, match='Trusted controller/validator changed'):
        parent.controller(path)
    assert not (tmp_path / 'private').exists()


def test_changed_budget_or_full_authority_blocks_before_any_subprocess(tmp_path, monkeypatch):
    path, value, _ = contract(tmp_path)
    monkeypatch.setattr(parent.subprocess, 'run', lambda *a, **k: pytest.fail('dispatched with changed benchmark authority'))
    for field, invalid in [('cumulative_cap_usd', 11), ('pilot_tasks', 60), ('full600_authorized', True)]:
        modified = dict(value, **{field: invalid}); path.write_text(json.dumps(modified))
        with pytest.raises(ValueError, match='benchmark authority'):
            parent.controller(path)
    assert not (tmp_path / 'private').exists()


def test_failed_real_evidence_acceptance_never_creates_epoch_or_launch(tmp_path, monkeypatch):
    path, _, _ = contract(tmp_path)
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        if argv[:3] == ['atsys', 'task', 'show']:
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({'status': 'completed'}))
        raise subprocess.CalledProcessError(1, argv)
    monkeypatch.setattr(parent.subprocess, 'run', run)
    with pytest.raises(subprocess.CalledProcessError):
        parent.controller(path)
    assert len(calls) == 2
    assert not (tmp_path / 'private/launch.json').exists()


def test_parent_source_allowlist_is_independent_of_repair_writable_policy(tmp_path):
    path, value, _ = contract(tmp_path)
    sentinel = tmp_path / 'unchangeable-science.txt'
    sentinel.write_text('frozen')
    bundle = json.loads(Path(value['historical_bundle']).read_text())
    manifest = Path(bundle['source_manifest']['path'])
    entries = json.loads(manifest.read_text())
    entries.append({'path': str(sentinel), 'sha256': hashlib.sha256(sentinel.read_bytes()).hexdigest()})
    manifest.write_text(json.dumps(entries))
    bundle['source_manifest']['sha256'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    Path(value['historical_bundle']).write_text(json.dumps(bundle))
    parent.parent_source_guard(value)
    sentinel.write_text('changed')
    with pytest.raises(ValueError, match='fixed source allowlist'):
        parent.parent_source_guard(value)


def test_controller_requires_all_trusted_control_pins(tmp_path):
    path, value, _ = contract(tmp_path)
    value['trusted_files'] = [p for p in value['trusted_files'] if not p['path'].endswith('run_pilot.py')]
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='pin missing'):
        parent.checked_contract(path)
