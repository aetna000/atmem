"""Windows startup cannot depend on POSIX descriptor permission APIs."""
import json
import os
from types import SimpleNamespace

import pytest


def windows_os():
    values = {key: value for key, value in vars(os).items() if key != 'fchmod'}
    values['name'] = 'nt'
    return SimpleNamespace(**values)


def test_home_atomic_write_without_fchmod(tmp_path, monkeypatch):
    from atmem.home import service
    monkeypatch.setattr(service, 'os', windows_os())
    target = tmp_path / 'manifest.json'
    service._atomic_json(target, {'kept': True})
    assert json.loads(target.read_text()) == {'kept': True}
    assert not list(tmp_path.glob('*.tmp'))


def test_control_state_without_fchmod(tmp_path, monkeypatch):
    from atmem.control import state
    from atmem.control.manager import ControlPlaneManager
    monkeypatch.setattr(state, 'os', windows_os())
    manager = ControlPlaneManager.start(host='generic', state_path=tmp_path / 'state.json',
        control_root=tmp_path / 'control', memory_db=tmp_path / 'memory.db')
    assert manager.state_path.exists()
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.skipif(os.name == 'nt', reason='POSIX permission failure path')
def test_permission_error_closes_temporary_before_cleanup(tmp_path, monkeypatch):
    from atmem.home import service
    def deny(*unused):
        raise PermissionError('denied')
    fake = SimpleNamespace(**vars(os))
    fake.fchmod = deny
    monkeypatch.setattr(service, 'os', fake)
    with pytest.raises(PermissionError):
        service._atomic_json(tmp_path / 'manifest.json', {})
    assert not list(tmp_path.glob('*.tmp'))
