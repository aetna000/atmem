"""Supported native context configuration, not generated training examples."""
import json
from pathlib import Path
import sys
import pytest
from types import SimpleNamespace


@pytest.mark.parametrize('effort,turns', [('medium', 20), ('high', 60)])
@pytest.mark.parametrize('reader_model',['openai/gpt-5.6-luna','openai/gpt-5.6-sol'])
def test_system_context_preserves_payload_and_disables_second_injection(tmp_path, monkeypatch, effort, turns,reader_model):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from benchmarks.dolphinbench import driver
    monkeypatch.setattr(driver, 'install', lambda *_a, **_k: None)
    host = object.__new__(driver.AtMemHost)
    host.binding = {'memory_engine': 'context-v3', 'profile_id': 'fixture'}
    host.credential = 'fixture-scoped-credential'
    host.server = SimpleNamespace(server_port=12345)
    context = 'Authorized product context: 中文\nunchanged'
    context_length = 1050000 if effort == 'high' else 1000000
    host.configure_profile(tmp_path / 'profile', base_url='http://127.0.0.1:1/v1',
                           local_token='fixture-local', governed_context=context,
                           reader_reasoning=effort, reader_max_turns=turns,
                           reader_context_length=context_length,reader_model=reader_model)
    config = json.loads((tmp_path / 'profile/config.yaml').read_text())
    assert config['agent']['system_prompt'] == context
    assert config['agent']['reasoning_effort'] == effort
    assert config['agent']['max_turns'] == turns
    assert config['model']['context_length'] == context_length
    assert config['model']['default']==reader_model
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
    assert config['model']['default']=='openai/gpt-5.6-luna'


def test_configured_native_identity_is_preserved_and_not_silently_overwritten(tmp_path,monkeypatch):
    from benchmarks.dolphinbench import driver
    import pytest
    monkeypatch.setattr(driver,'install',lambda *_a,**_k:None)
    host=object.__new__(driver.AtMemHost)
    host.binding={'memory_engine':'context-v3','profile_id':'fixture'}
    host.credential='fixture-scoped-credential';host.server=SimpleNamespace(server_port=12345)
    host.native_soul='# Identity\nPersonal assistant for Hana.\n'
    home=tmp_path/'profile'
    host.configure_profile(home,base_url='http://127.0.0.1:1/v1',local_token='fixture',governed_context='source text')
    assert (home/'SOUL.md').read_text()==host.native_soul
    host.native_soul='different identity'
    with pytest.raises(ValueError,match='identity changed'):
        host.configure_profile(home,base_url='http://127.0.0.1:1/v1',local_token='fixture')


def test_discovery_is_separate_from_native_auto_capture(tmp_path,monkeypatch):
    from benchmarks.dolphinbench import driver
    monkeypatch.setattr(driver,'install',lambda *_a,**_k:None)
    host=object.__new__(driver.AtMemHost)
    host.binding={'memory_engine':'context-v3','profile_id':'fixture','binding_id':'binding'}
    host.credential='hermes_fixture'
    host.admin=object()
    host.server=SimpleNamespace(server_port=12345)
    host.service=SimpleNamespace(open_discovery=lambda *a,**k:{'lease_id':'a'*32})
    host.configure_profile(tmp_path/'profile',base_url='http://127.0.0.1:1/v1',local_token='fixture',
        governed_context='',discovery_query='actual task',application_workflow=True,
        initial_status='contradicted',discovery_python='/explicit/native/python')
    config=json.loads((tmp_path/'profile/config.yaml').read_text())
    assert config['memory']['provider']=='' and config['memory']['memory_enabled'] is False
    assert config['mcp_servers']['atmem-discovery']['command']=='/explicit/native/python'
    assert 'atmem-discovery' in config['toolsets']
    assert 'memory' not in config['toolsets']
    assert 'Connected application workflow' in config['agent']['system_prompt']
    assert 'initial context could not establish' in config['agent']['system_prompt']
    assert (tmp_path/'profile/.atmem/mcp_transport.py').is_file()


def test_in_process_preparation_keeps_authentication_and_sdk_validation(tmp_path, monkeypatch):
    from benchmarks.dolphinbench import driver
    from atmem.adapters.hermes import provider, client
    host = object.__new__(driver.AtMemHost)
    host.binding = {'profile_id': 'fixture'}
    host.credential = 'hermes_fixture-only'
    host.server = SimpleNamespace(server_port=12345)
    seen = []
    response = {'context': 'original product context', 'candidate_ids': ('evidence-1',),
                'reason': 'authorized', 'lifecycle_recorded': True,
                'profile': 'authorized-at-recall-context-v3'}

    def dispatch(credential, operation, body):
        assert credential == host.credential
        if operation == 'status':
            assert body == {}
            return {'enabled': True}
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
            assert self.rpc.enabled
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
