"""Supported native context configuration, not generated training examples."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace


def test_system_context_preserves_payload_and_disables_second_injection(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from benchmarks.dolphinbench import driver
    monkeypatch.setattr(driver, 'install', lambda *_a, **_k: None)
    host = object.__new__(driver.AtMemHost)
    host.binding = {'memory_engine': 'context-v3', 'profile_id': 'fixture'}
    host.credential = 'fixture-scoped-credential'
    host.server = SimpleNamespace(server_port=12345)
    context = 'Authorized product context: 中文\nunchanged'
    host.configure_profile(tmp_path / 'profile', base_url='http://127.0.0.1:1/v1',
                           local_token='fixture-local', governed_context=context)
    config = json.loads((tmp_path / 'profile/config.yaml').read_text())
    assert config['agent']['system_prompt'] == context
    assert config['memory']['provider'] == ''
    assert config['memory']['memory_enabled'] is False
    assert set(config['agent']['disabled_toolsets']) == {'memory', 'delegation'}
    assert 'session_search' in config['toolsets']
    assert 'memory' not in config['platform_toolsets']['cli']


def test_default_native_provider_configuration_is_unchanged(tmp_path, monkeypatch):
    from benchmarks.dolphinbench import driver
    monkeypatch.setattr(driver, 'install', lambda *_a, **_k: None)
    host = object.__new__(driver.AtMemHost)
    host.binding = {'memory_engine': 'context-v3', 'profile_id': 'fixture'}
    host.credential = 'fixture-scoped-credential'
    host.server = SimpleNamespace(server_port=12345)
    host.configure_profile(tmp_path / 'profile', base_url='http://127.0.0.1:1/v1', local_token='fixture-local')
    config = json.loads((tmp_path / 'profile/config.yaml').read_text())
    assert config['memory']['provider'] == 'atmem'
    assert config['memory']['memory_enabled'] is True
    assert 'system_prompt' not in config['agent']


def test_in_process_preparation_keeps_authentication_and_sdk_validation(tmp_path, monkeypatch):
    from benchmarks.dolphinbench import driver
    from atmem.adapters.hermes import provider, client
    host = object.__new__(driver.AtMemHost)
    host.binding = {'profile_id': 'fixture'}
    host.credential = 'hermes_fixture-only'
    host.server = SimpleNamespace(server_port=12345)
    seen = []
    response = {'context': 'original product context', 'candidate_ids': ['evidence-1'],
                'reason': 'authorized', 'lifecycle_recorded': True,
                'profile': 'authorized-at-recall-context-v3'}

    def dispatch(credential, operation, body):
        assert credential == host.credential
        assert operation == 'prepare-turn'
        assert body['query'] == 'unchanged query'
        seen.append(body)
        return response

    host.service = SimpleNamespace(dispatch=dispatch)
    monkeypatch.setattr(client.HermesRPCClient, '_call',
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError('network dispatch')))

    class FixtureProvider:
        def __init__(self, rpc):
            self.rpc = rpc
        def initialize(self, *_a, **_k):
            pass
        def on_turn_start(self, _turn, query, **_k):
            self.value = self.rpc.prepare_turn(query, session_id='fixture', turn_id='turn',
                model='fixture', platform='cli', prompt_sha256='0' * 64, prompt_chars=len(query))
        def prefetch(self, *_a, **_k):
            return self.value.context
        def shutdown(self):
            pass

    monkeypatch.setattr(provider, 'create_provider', lambda rpc, **_k: FixtureProvider(rpc))
    ruling, text = host.prepare_native_context('unchanged query', home=tmp_path,
        session_id='fixture', native_source=tmp_path, in_process=True)
    assert text == response['context'] and ruling['reason'] == 'authorized'
    assert len(seen) == 1
    response['candidate_ids'] = [None]  # The ordinary SDK validator still rejects it.
    ruling, text = host.prepare_native_context('unchanged query', home=tmp_path,
        session_id='fixture', native_source=tmp_path, in_process=True)
    assert ruling['reason'] == 'unavailable_or_denied' and not text
