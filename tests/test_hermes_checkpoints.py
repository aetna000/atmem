"""Product-owned freeze gates, independent of benchmark implementation."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest
import atmem

from atmem.adapters.hermes.service import HermesService
from atmem.control import ControlPlaneManager
from atmem.service import APIError, APIPrincipal


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr('atmem.control.atbot_companion.AtBotCompanionClient.propose',
                        lambda self, message: {'proposals': [], 'companion': {'available': False}})
    manager = ControlPlaneManager.start(host='generic', state_path=tmp_path / 'state.json',
                                        control_root=tmp_path / 'control', memory_db=tmp_path / 'memory.db')
    workspace = manager.agent_topology()['workspaces'][0]
    admin = APIPrincipal('operator', 'admin', workspace['subject_id'])
    service = HermesService(manager)
    grant = service.provision(admin, profile_id='frozen-test', agent_id='main',
        workspace_id=workspace['workspace_id'], accept_reduced_capture=True)
    service.configure(admin, grant['binding']['binding_id'], enabled=True)
    return service, admin, grant


def observe(service, grant, text='My preferred editor is Neovim.', identity='one'):
    return service.dispatch(grant['credential'], 'observe',
                            {'text': text, 'session_id': 'session', 'observation_id': identity})


def test_freeze_blocks_capture_persists_and_allows_fresh_recall(state):
    service, admin, grant = state
    observe(service, grant)
    for candidate in service.manager.candidates():
        service.manager.review_memory(candidate['id'], 'approve')
    service.manager.activate()
    checkpoint = service.freeze_memory(admin, grant['binding']['binding_id'])
    assert checkpoint['canonical']['record_count'] > 0
    assert service.freeze_memory(admin, grant['binding']['binding_id']) == checkpoint
    assert observe(service, grant, 'My preferred editor is Emacs.', 'two') == {
        'captured': False, 'reason': 'memory_frozen', 'memory_mutated': False}
    recalled = service.dispatch(grant['credential'], 'recall',
        {'query': 'preferred editor', 'session_id': 'new-session', 'turn_id': '1'})
    assert 'Neovim' in recalled['context']
    service.verify_memory_checkpoint(admin, grant['binding']['binding_id'], checkpoint)
    restarted = HermesService(ControlPlaneManager(service.manager.state_path))
    assert restarted.dispatch(grant['credential'], 'status', {})['memory_frozen']
    assert not observe(restarted, grant, identity='three')['memory_mutated']
    restarted.verify_memory_checkpoint(admin, grant['binding']['binding_id'], checkpoint)


def test_agent_cannot_freeze_or_override_and_rotation_does_not_unfreeze(state):
    service, admin, grant = state
    binding_id = grant['binding']['binding_id']
    with pytest.raises(APIError):
        service.freeze_memory(replace(admin, role='agent'), binding_id)
    with pytest.raises(PermissionError):
        service.freeze_memory(replace(admin, subject_id='other'), binding_id)
    service.freeze_memory(admin, binding_id)
    with pytest.raises(ValueError):
        service.dispatch(grant['credential'], 'observe',
            {'text': 'x', 'session_id': 's', 'observation_id': 'o', 'memory_frozen': False})
    service.configure_mode(admin, binding_id, mode='active')
    rotated = service.rotate(admin, binding_id)
    service.configure(admin, binding_id, enabled=True)
    grant = {**grant, 'credential': rotated['credential']}
    assert observe(service, grant)['reason'] == 'memory_frozen'


def test_accepted_observation_finishes_before_freeze(state, monkeypatch):
    service, admin, grant = state
    entered, release = threading.Event(), threading.Event()
    original = service.manager.capture

    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(service.manager, 'capture', slow)
    errors = []
    def writer():
        try:
            observe(service, grant)
        except Exception as exc:
            errors.append(exc)
    thread = threading.Thread(target=writer)
    thread.start()
    assert entered.wait(5)
    try:
        with pytest.raises(RuntimeError, match='busy'):
            service.freeze_memory(admin, grant['binding']['binding_id'])
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and not errors
    service.freeze_memory(admin, grant['binding']['binding_id'])


def test_checkpoint_cannot_be_forged_or_canonical_change_hidden(state):
    service, admin, grant = state
    binding_id = grant['binding']['binding_id']
    checkpoint = service.freeze_memory(admin, binding_id)
    with pytest.raises(ValueError):
        service.verify_memory_checkpoint(admin, binding_id, {**checkpoint, 'profile_id': 'forged'})
    # Administrative edits remain possible, but cannot pass frozen verification.
    service.manager.capture('My preferred editor is Neovim.', authenticated_user=True)
    for candidate in service.manager.candidates():
        service.manager.review_memory(candidate['id'], 'approve')
    with pytest.raises(ValueError):
        service.verify_memory_checkpoint(admin, binding_id, checkpoint)


def test_fresh_process_verifies_persisted_checkpoint(state):
    service, admin, grant = state
    checkpoint = service.freeze_memory(admin, grant['binding']['binding_id'])
    program = '''
import json,sys
from atmem.adapters.hermes.service import HermesService
from atmem.control import ControlPlaneManager
from atmem.service import APIPrincipal
p=json.load(sys.stdin)
s=HermesService(ControlPlaneManager(p['state_path']))
s.verify_memory_checkpoint(APIPrincipal('operator','admin',p['subject']),p['binding'],p['checkpoint'])
print('checkpoint_verified')
'''
    result = subprocess.run([sys.executable, '-c', program], input=json.dumps({
        'state_path': str(service.manager.state_path), 'subject': admin.subject_id,
        'binding': grant['binding']['binding_id'], 'checkpoint': checkpoint}),
        text=True, capture_output=True, timeout=30,
        env={**os.environ, 'PYTHONPATH': str(Path(atmem.__file__).parents[1])})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'checkpoint_verified'
