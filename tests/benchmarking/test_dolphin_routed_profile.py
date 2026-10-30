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


def test_launch_admission_stays_bound_to_the_qualified_profile():
    # The routed condition needs its own qualification receipts before any scored dispatch.
    assert gate.PROFILE == PROFILE != ROUTED_PROFILE
