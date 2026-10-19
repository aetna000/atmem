"""Cloud lifecycle safety checks; API calls are fixtures, never real rentals."""
import json

import pytest

from tools import vast_pruner_rental as rental


def test_teardown_refuses_unrelated_label(monkeypatch):
    monkeypatch.setattr(rental, 'instances', lambda: [{'id': 3, 'label': 'other-project'}])
    calls = []
    monkeypatch.setattr(rental, 'api', lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match='ownership label'):
        rental.destroy({'instance_id': 3, 'label': 'owned'}, 'finished')
    assert not calls


def test_already_absent_does_not_delete_other_instances(monkeypatch, tmp_path):
    monkeypatch.setattr(rental, 'STATE', tmp_path / 'rental.json')
    monkeypatch.setattr(rental, 'instances', lambda: [{'id': 99, 'label': 'other-project'}])
    calls = []
    def api(method, path):
        calls.append((method, path))
        assert method == 'GET'
        return {'credit': 8}
    monkeypatch.setattr(rental, 'api', api)
    closed = rental.destroy({'instance_id': 3, 'label': 'owned'}, 'finished')
    assert closed['destroyed'] and closed['destroy_response']['already_absent']
    assert len(calls) == 1


def test_budget_rejection_occurs_before_create(monkeypatch, tmp_path):
    root = tmp_path / 'owned'
    monkeypatch.setattr(rental, 'ROOT', root)
    monkeypatch.setattr(rental, 'STATE', root / 'rental.json')
    monkeypatch.setattr(rental.sys, 'argv', ['rental', 'rent'])
    monkeypatch.setattr(rental, 'instances', lambda: [])
    monkeypatch.setattr(rental, 'search', lambda: [{'id': 1, 'dph_total': 2,
        'storage_cost': 0, 'inet_down_cost': 0, 'inet_up_cost': 0}])
    calls = []
    def api(method, path, payload=None):
        calls.append(method)
        return {'credit': 10}
    monkeypatch.setattr(rental, 'api', api)
    with pytest.raises(RuntimeError, match='ceiling'):
        rental.main()
    assert calls == ['GET']


def test_rental_response_credentials_not_retained(monkeypatch, tmp_path, capsys):
    root = tmp_path / 'owned'
    monkeypatch.setattr(rental, 'ROOT', root)
    monkeypatch.setattr(rental, 'STATE', root / 'rental.json')
    monkeypatch.setattr(rental.sys, 'argv', ['rental', 'rent'])
    monkeypatch.setattr(rental, 'instances', lambda: [])
    monkeypatch.setattr(rental, 'search', lambda: [{'id': 1, 'gpu_name': 'fixture-GPU', 'dph_total': .1,
        'storage_cost': 0, 'inet_down_cost': 0, 'inet_up_cost': 0}])
    def api(method, path, payload=None):
        if method == 'GET':return {'credit': 10}
        if method == 'PUT':return {'success': True, 'new_contract': 7, 'instance_api_key': 'fixture-secret-not-for-receipts'}
        return {'success': True, 'unneeded_private_payload': 'fixture-secret-not-for-receipts'}
    monkeypatch.setattr(rental, 'api', api)
    class Process:
        pid = 123
    monkeypatch.setattr(rental.subprocess, 'Popen', lambda *args, **kwargs: Process())
    def keygen(argv, **kwargs):
        (root / 'ssh_key.pub').write_text('ssh-ed25519 fixture-public-key')
    monkeypatch.setattr(rental.subprocess, 'run', keygen)
    rental.main()
    output = capsys.readouterr().out
    state = (root / 'rental.json').read_text()
    assert 'fixture-secret-not-for-receipts' not in state + output
    assert json.loads(state)['create_response'] == {'success': True, 'new_contract': 7}
