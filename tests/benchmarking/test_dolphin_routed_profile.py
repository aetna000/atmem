import json

import pytest

from benchmarks.dolphinbench import readiness as gate
from benchmarks.dolphinbench.execution_profile import (PROFILE, ROUTED_PROFILE, apply_profile, validate)

BASE = {'toolsets': ['hermes-cli', 'memory', 'session_search', 'dolphinbench-apps', 'atmem-discovery'],
        'platform_toolsets': {'cli': ['hermes-cli']}, 'agent': {}}


def request(*names):
    return {'tools': [{'type': 'function', 'function': {'name': n}} for n in names], 'messages': []}


def test_routed_profile_keeps_ordinary_inventory_and_enables_the_staged_guard(tmp_path):
    config = apply_profile(ROUTED_PROFILE, BASE, home=tmp_path)
    assert config['toolsets'] == BASE['toolsets'] and 'disabled_toolsets' not in config['agent']
    assert config['plugins']['enabled'] == ['atmem-action-guard']
    assert config['execution_profile'] == ROUTED_PROFILE and 'plugins' not in BASE
    assert (tmp_path / 'plugins/atmem-action-guard/action_guard.py').is_file()
    assert json.loads((tmp_path / 'plugins/atmem-action-guard/settings.json').read_text())['checkpoint'] is False
    with pytest.raises(FileExistsError):
        apply_profile(ROUTED_PROFILE, BASE, home=tmp_path)


def test_profiles_dispatch_and_reject_unknown_names(tmp_path):
    assert apply_profile(PROFILE, BASE, home=tmp_path)['execution_profile'] == PROFILE
    with pytest.raises(ValueError, match='Unknown execution profile'):
        apply_profile('other', BASE, home=tmp_path)
    with pytest.raises(ValueError, match='requires simulated application tools'):
        apply_profile(ROUTED_PROFILE, {**BASE, 'toolsets': ['hermes-cli']}, home=tmp_path)


def test_routed_request_validation_allows_local_tools_but_needs_an_app_surface():
    names = validate(ROUTED_PROFILE, request('terminal', 'skill_view', 'mcp__dolphinbench_apps__create_doc'))
    assert 'terminal' in names
    assert validate(ROUTED_PROFILE, request('terminal', 'tool_search'))
    with pytest.raises(ValueError, match='missing application surface'):
        validate(ROUTED_PROFILE, request('terminal'))
    with pytest.raises(ValueError, match='duplicate'):
        validate(ROUTED_PROFILE, request('terminal', 'terminal', 'tool_search'))
    with pytest.raises(ValueError, match='unsupported model-visible tool'):
        validate(PROFILE, request('terminal', 'mcp__dolphinbench_apps__create_doc'))


def test_profile_checks_are_separate():
    assert gate.checks_for({'profile': PROFILE}, 'profile') == gate.CHECKS['profile']
    assert gate.checks_for({'profile': ROUTED_PROFILE}, 'profile') == gate.ROUTED_CHECKS
    assert gate.CHECKS['profile'] == {'mcp_only', 'eager_tools', 'skills_disabled'}


@pytest.mark.parametrize('mutation', [None, 'plugin', 'checkpoint', 'detour', 'state', 'log', 'runtime', 'boundary'])
def test_routed_raw_evidence_is_recomputed(tmp_path, mutation):
    from pathlib import Path
    from benchmarks.dolphinbench.qualify_routed import QUESTION, verify_evidence
    root = Path(__file__).parents[2]
    (tmp_path / 'staged-__init__.py').write_bytes((root / 'atmem/adapters/hermes/action_guard_plugin.py').read_bytes())
    (tmp_path / 'staged-action_guard.py').write_bytes((root / 'atmem/action_guard.py').read_bytes())
    def put(name, value): (tmp_path / name).write_text(json.dumps(value))
    put('staged-settings.json', {'checkpoint': False, 'route_context': False, 'completion_notice': False})
    put('profile.json', {'plugins': {'enabled': ['atmem-action-guard']}})
    put('model-request.json', request('terminal', 'skill_view', 'tool_search', 'tool_call'))
    outcome = {'verdict': {'status': 'completed'}, 'decisions': [{'action': 'block'}], 'memory_query_count': 0}
    (tmp_path / 'guard-outcomes.jsonl').write_text(json.dumps(outcome) + '\n')
    (tmp_path / 'calls.jsonl').write_text(json.dumps({'tool': 'create_doc', 'result': {'ok': True}}) + '\n')
    put('state.json', {'docs': [{'body': 'Synthetic durable routing text'}]})
    user = {'role': 'user', 'content': QUESTION}
    for i in range(3): put(f'request-{i:02}.json', {'messages': [user, {'role': 'tool', 'content': 'Not run: memo; use create_doc'}]})
    put('process.json', {'returncode': 0})
    if mutation == 'plugin': (tmp_path / 'staged-action_guard.py').write_text('changed')
    if mutation == 'checkpoint': put('staged-settings.json', {'checkpoint': True, 'route_context': False, 'completion_notice': False})
    if mutation == 'boundary':
        put('request-01.json', {'messages': [{'role': 'user', 'content': QUESTION + '\n\nAtMem action routing: ...'},
                                             {'role': 'tool', 'content': 'Not run: memo; use create_doc'}]})
    if mutation == 'detour':
        outcome['decisions'] = []; (tmp_path / 'guard-outcomes.jsonl').write_text(json.dumps(outcome) + '\n')
    if mutation == 'state': put('state.json', {'docs': []})
    if mutation == 'log': (tmp_path / 'calls.jsonl').write_text('')
    if mutation == 'runtime': put('process.json', {'returncode': 1})
    if mutation:
        with pytest.raises(ValueError): verify_evidence(tmp_path)
    else:
        assert set(verify_evidence(tmp_path)) == gate.ROUTED_CHECKS
