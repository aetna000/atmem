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
    assert config['tools']['tool_search'] == {'enabled': 'off'}  # all tools eager, as in MCP-only
    with pytest.raises(FileExistsError):
        apply_profile(ROUTED_PROFILE, BASE, home=tmp_path)


def test_route_note_goes_to_the_system_prompt_not_the_user_turn(tmp_path):
    base = {**BASE, 'agent': {'system_prompt': 'governed context'}}
    config = apply_profile(ROUTED_PROFILE, base, home=tmp_path, request='[2028-01-01] Create a coaching note about Wes.',
                           app_tools=['create_doc', 'list_docs'])
    prompt = config['agent']['system_prompt']
    assert prompt.startswith('governed context\n\nAtMem action routing:') and 'mcp__dolphinbench_apps__create_doc' in prompt
    assert 'list_docs' not in prompt.split('connected tools for it are:')[1].split('.')[0]
    question = apply_profile(ROUTED_PROFILE, base, home=tmp_path / 'q', request='What did Hema say about Wes?',
                             app_tools=['create_doc'])
    assert question['agent']['system_prompt'] == 'governed context'


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


@pytest.mark.parametrize('mutation', [None, 'plugin', 'checkpoint', 'detour', 'state', 'log', 'runtime', 'boundary', 'note'])
def test_routed_raw_evidence_is_recomputed(tmp_path, mutation):
    from pathlib import Path
    from benchmarks.dolphinbench.qualify_routed import QUESTION, verify_evidence
    root = Path(__file__).parents[2]
    (tmp_path / 'staged-__init__.py').write_bytes((root / 'atmem/adapters/hermes/action_guard_plugin.py').read_bytes())
    (tmp_path / 'staged-action_guard.py').write_bytes((root / 'atmem/action_guard.py').read_bytes())
    def put(name, value): (tmp_path / name).write_text(json.dumps(value))
    put('staged-settings.json', {'checkpoint': False, 'route_context': False, 'completion_notice': False, 'pending_reminder': False})
    put('profile.json', {'plugins': {'enabled': ['atmem-action-guard']}, 'tools': {'tool_search': {'enabled': 'off'}}})
    put('model-request.json', request('terminal', 'skill_view', 'mcp__dolphinbench_apps__create_doc'))
    outcome = {'verdict': {'status': 'completed'}, 'decisions': [{'action': 'block', 'route': 'command:memo'}], 'memory_query_count': 0}
    (tmp_path / 'guard-outcomes.jsonl').write_text(json.dumps(outcome) + '\n')
    (tmp_path / 'calls.jsonl').write_text(json.dumps({'tool': 'create_doc', 'result': {'ok': True}}) + '\n')
    put('state.json', {'docs': [{'body': 'Synthetic durable routing text'}]})
    user = {'role': 'user', 'content': QUESTION}
    system = {'role': 'system', 'content': 'ctx\n\nAtMem action routing: ... mcp__dolphinbench_apps__create_doc ...'}
    for i in range(3): put(f'request-{i:02}.json', {'messages': [system, user, {'role': 'tool', 'content': 'Not run: memo; use create_doc'}]})
    put('process.json', {'returncode': 0})
    if mutation == 'plugin': (tmp_path / 'staged-action_guard.py').write_text('changed')
    if mutation == 'checkpoint': put('staged-settings.json', {'checkpoint': True, 'route_context': False, 'completion_notice': False, 'pending_reminder': False})
    if mutation == 'note':
        put('request-00.json', {'messages': [{'role': 'system', 'content': 'ctx'}, user, {'role': 'tool', 'content': 'Not run: memo; use create_doc'}]})
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


def test_checkpoint_profile_stages_the_hold_and_states_it_in_the_system_prompt(tmp_path):
    from benchmarks.dolphinbench.execution_profile import CHECKPOINT_PROFILE
    base = {**BASE, 'agent': {'system_prompt': 'ctx'}}
    config = apply_profile(CHECKPOINT_PROFILE, base, home=tmp_path, request='Email vendorops@northwind.example a reply.',
                           app_tools=['send_email'])
    settings = json.loads((tmp_path / 'plugins/atmem-action-guard/settings.json').read_text())
    assert settings['checkpoint'] is True and config['execution_profile'] == CHECKPOINT_PROFILE
    assert 'Held once' in config['agent']['system_prompt'] and 'send_email' in config['agent']['system_prompt']
    assert gate.checks_for({'profile': CHECKPOINT_PROFILE}, 'profile') == gate.CHECKPOINT_CHECKS
    assert 'checkpoint_held_once' in gate.CHECKPOINT_CHECKS and 'checkpoint_disabled' not in gate.CHECKPOINT_CHECKS


@pytest.mark.parametrize('mutation', [None, 'not_held', 'no_search', 'no_reminder'])
def test_checkpoint_evidence_requires_one_hold_and_one_search(tmp_path, mutation):
    from pathlib import Path
    from benchmarks.dolphinbench.execution_profile import CHECKPOINT_PROFILE, ROUTED_PROFILES
    from benchmarks.dolphinbench.qualify_routed import QUESTION, verify_evidence
    root = Path(__file__).parents[2]
    (tmp_path / 'staged-__init__.py').write_bytes((root / 'atmem/adapters/hermes/action_guard_plugin.py').read_bytes())
    (tmp_path / 'staged-action_guard.py').write_bytes((root / 'atmem/action_guard.py').read_bytes())
    def put(name, value): (tmp_path / name).write_text(json.dumps(value))
    put('staged-settings.json', ROUTED_PROFILES[CHECKPOINT_PROFILE])
    put('profile.json', {'plugins': {'enabled': ['atmem-action-guard']}, 'tools': {'tool_search': {'enabled': 'off'}},
                         'execution_profile': CHECKPOINT_PROFILE})
    put('model-request.json', request('terminal', 'skill_view', 'mcp__dolphinbench_apps__create_doc'))
    decisions = [{'action': 'block', 'route': 'command:memo'},
                 {'action': 'block', 'route': 'checkpoint:mcp__dolphinbench_apps__create_doc'}]
    if mutation == 'not_held': decisions = decisions[:1]
    outcome = {'verdict': {'status': 'completed'}, 'decisions': decisions, 'memory_query_count': 0 if mutation == 'no_search' else 1}
    (tmp_path / 'guard-outcomes.jsonl').write_text(json.dumps(outcome) + '\n')
    (tmp_path / 'calls.jsonl').write_text(json.dumps({'tool': 'create_doc', 'result': {'ok': True}}) + '\n')
    put('state.json', {'docs': [{'body': 'Synthetic durable routing text'}]})
    user = {'role': 'user', 'content': QUESTION}
    system = {'role': 'system', 'content': 'AtMem action routing: mcp__dolphinbench_apps__create_doc ... "Held once" ...'}
    reminder = {'role': 'tool', 'content': 'evidence\n\n[AtMem: still pending — ...]'}
    for i in range(5):
        tools = [{'role': 'tool', 'content': 'Not run: memo; use create_doc'}] + ([reminder] if mutation != 'no_reminder' else [])
        put(f'request-{i:02}.json', {'messages': [system, user, *tools]})
    put('process.json', {'returncode': 0})
    if mutation:
        with pytest.raises(ValueError): verify_evidence(tmp_path)
    else:
        assert set(verify_evidence(tmp_path)) == gate.CHECKPOINT_CHECKS


def test_facts_profile_stages_store_server_and_profile(tmp_path, monkeypatch):
    from benchmarks.dolphinbench import execution_profile as ep
    store = tmp_path / 'morgan.json'
    store.write_text(json.dumps({'facts': [{'id': 0, 'fact': 'Morgan avoids vendor calls on Fridays.', 'as_of': '2023-01-31',
                                            'kind': 'rule', 'quote': 'q', 'session': 's'}], 'profile': [0]}))
    real_lookup = ep.standing_facts_store
    monkeypatch.setattr(ep, 'standing_facts_store', lambda persona: store)
    base = {**BASE, 'agent': {'system_prompt': 'ctx'}, 'mcp_servers': {'dolphinbench-apps': {'command': '/py', 'args': []}}}
    config = apply_profile(ep.FACTS_PROFILE, base, home=tmp_path / 'home', request='Email vendorops a reply.',
                           app_tools=['send_email'], persona='morgan')
    prompt = config['agent']['system_prompt']
    assert prompt.index('AtMem standing profile') < prompt.index('AtMem action routing:')
    assert 'Morgan avoids vendor calls on Fridays.' in prompt and 'fact_search' in prompt
    server = config['mcp_servers']['atmem-facts']
    assert server['command'] == '/py' and server['args'][1].endswith('facts_stdio.py')
    assert 'atmem-facts' in config['toolsets'] and (tmp_path / 'home/facts/standing_facts.py').is_file()
    assert gate.checks_for({'profile': ep.FACTS_PROFILE}, 'profile') == gate.FACTS_CHECKS
    with pytest.raises(ValueError, match='No verified standing-fact store'):
        real_lookup('nobody')
