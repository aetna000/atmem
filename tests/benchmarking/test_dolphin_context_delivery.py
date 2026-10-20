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
