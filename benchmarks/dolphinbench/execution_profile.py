"""Supported isolated Hermes profile; validate actual provider-bound tools."""
from copy import deepcopy
import json
from pathlib import Path
import re

PROFILE = 'dolphin-mcp-only-v1'
APP = 'mcp__dolphinbench_apps__'
MEMORY = 'mcp__atmem_discovery__'
ALLOWED_MEMORY = {MEMORY + 'memory_search', MEMORY + 'memory_inspect'}
FORBIDDEN = {'terminal', 'execute_code', 'process_manage', 'skill_view', 'skills_list',
             'skill_manage', 'write_file', 'patch', 'delegate_task', 'tool_search',
             'tool_describe', 'tool_call', 'manage_connections'}


def isolated_profile(config, *, skill_roots=()):
    """Return a fresh supported config without changing any user/global profile."""
    value = deepcopy(config)
    toolsets = [name for name in config['toolsets'] if name in
                {'dolphinbench-apps', 'atmem-discovery', 'session_search'}]
    if 'dolphinbench-apps' not in toolsets:
        raise ValueError('Execution profile requires simulated application tools')
    value['toolsets'] = toolsets
    value['platform_toolsets'] = {'cli': toolsets}
    value.setdefault('tools', {})['tool_search'] = {'enabled': 'off'}
    # Disable skill tools themselves as well as every skill offered by the
    # manifest. With no skills toolset the host does not need an OS skill.
    disabled = set(value.setdefault('agent', {}).get('disabled_toolsets', []))
    value['agent']['disabled_toolsets'] = sorted(disabled | {'terminal', 'skills', 'file',
        'browser', 'delegation', 'cronjob'})
    value['execution_profile'] = PROFILE
    names = set()
    for root in skill_roots:
        root = Path(root)
        if root.is_dir():
            for item in root.rglob('SKILL.md'):
                relative = item.parent.relative_to(root).as_posix()
                names.update({item.parent.name, relative, relative.replace('/', ':')})
    value['skills'] = {'disabled': sorted(names), 'external_dirs': []}
    return value


def validate_request(body):
    """Reject unsupported/effectively deferred tools before any provider call."""
    tools = body.get('tools')
    if not isinstance(tools, list) or not tools:
        raise ValueError('Readiness profile: empty model-visible tool array')
    names = []
    for definition in tools:
        if definition.get('type') != 'function':
            raise ValueError('Readiness profile: non-function tool')
        fn = definition.get('function', {})
        name = fn.get('name', '')
        if name in FORBIDDEN or not (name.startswith(APP) or name in ALLOWED_MEMORY
                                    or name == 'session_search'):
            raise ValueError('Readiness profile: unsupported model-visible tool: ' + name)
        names.append(name)
    if len(names) != len(set(names)) or not any(n.startswith(APP) for n in names):
        raise ValueError('Readiness profile: duplicate tools or missing app surface')
    # Skills in prompt would still compete even if their tool were disabled.
    for message in body.get('messages', []):
        if message.get('role') not in {'system', 'developer'}:
            continue
        content = str(message.get('content', ''))
        for match in re.finditer(r'<available_skills>(.*?)</available_skills>', content, re.S):
            if match.group(1).strip():
                raise ValueError('Readiness profile: operational skill catalog still visible')
    return sorted(names)


# Routed profile: the ordinary inventory (terminal, skills, deferred tool search)
# stays visible and the AtMem action guard plugin refuses detours instead. It is
# a separate experimental condition with its own qualification receipts.
ROUTED_PROFILE = 'dolphin-routed-v1'
PROFILES = (PROFILE, ROUTED_PROFILE)
ROUTED_SETTINGS = {'checkpoint': False, 'route_context': False, 'completion_notice': False}


def routed_profile(config, *, home):
    """Return a fresh config that stages and enables the action guard in ``home``."""
    # The frozen installed memory product predates this execution-only plugin.
    # Load its pinned staging code without replacing the installed AtMem package.
    import importlib.util
    path = Path(__file__).parents[2] / 'atmem/adapters/hermes/action_guard_plugin.py'
    spec = importlib.util.spec_from_file_location('dolphin_guard_stage', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    PLUGIN, stage = module.PLUGIN, module.stage
    if 'dolphinbench-apps' not in config['toolsets']:
        raise ValueError('Execution profile requires simulated application tools')
    value = deepcopy(config)
    # The harness requires the native user turn to equal the dataset request and
    # grades the agent's own final answer, so the plugin must not inject the route
    # note or append completion notices here; refusals and outcome records remain.
    stage(home, settings=ROUTED_SETTINGS)
    plugins = value.setdefault('plugins', {})
    plugins['enabled'] = sorted(set(plugins.get('enabled', [])) | {PLUGIN})
    value['execution_profile'] = ROUTED_PROFILE
    return value


def apply_profile(name, config, *, home, skill_roots=()):
    if name == PROFILE:
        return isolated_profile(config, skill_roots=skill_roots)
    if name == ROUTED_PROFILE:
        return routed_profile(config, home=home)
    raise ValueError('Unknown execution profile')


def validate_routed_request(body):
    """The routed profile keeps local tools; it still needs the app surface, once each."""
    tools = body.get('tools')
    if not isinstance(tools, list) or not tools:
        raise ValueError('Routed profile: empty model-visible tool array')
    names = [d.get('function', {}).get('name', '') for d in tools]
    if len(names) != len(set(names)):
        raise ValueError('Routed profile: duplicate model-visible tools')
    visible = ' '.join(names) + json.dumps(body.get('messages', []))[-200000:]
    if not any(n.startswith(APP) for n in names) and 'tool_search' not in names and APP not in visible:
        raise ValueError('Routed profile: missing application surface')
    return sorted(names)


def validate(name, body):
    if name == PROFILE:
        return validate_request(body)
    if name == ROUTED_PROFILE:
        return validate_routed_request(body)
    raise ValueError('Unknown execution profile')
