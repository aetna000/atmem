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


# Routed profile: the ordinary inventory (terminal, skills, files) stays visible and
# the AtMem action guard plugin refuses detours instead of hiding local tools. All
# tools are eager (tool search off, as in the MCP-only profile), so the only
# difference from that profile is that local tools remain available. A separate
# experimental condition with its own qualification receipts.
ROUTED_PROFILE = 'dolphin-routed-v2'
# Same routed inventory plus the commit checkpoint: the first call to each connected
# write tool is held once for a remembered-constraints check.
CHECKPOINT_PROFILE = 'dolphin-routed-v3'
ROUTED_PROFILES = {
    ROUTED_PROFILE: {'checkpoint': False, 'route_context': False, 'completion_notice': False,
                     'pending_reminder': False},
    CHECKPOINT_PROFILE: {'checkpoint': True, 'route_context': False, 'completion_notice': False,
                         'pending_reminder': True},
}
ROUTED_SETTINGS = ROUTED_PROFILES[ROUTED_PROFILE]
PROFILES = (PROFILE, *ROUTED_PROFILES)
ROUTE_NOTE_MARKER = 'AtMem action routing:'


def _load_repo_module(relative, name):
    # The frozen installed memory product predates this execution-only plugin.
    # Load pinned repository code without replacing the installed AtMem package.
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[2] / relative)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


def route_note(request, app_tools, *, checkpoint=False):
    """Request-specific routing note naming the connected write tools, or ''."""
    policy = _load_repo_module('atmem/action_guard.py', 'dolphin_guard_policy')
    guard = policy.ActionGuard(checkpoint=checkpoint)
    visible = {APP + t for t in app_tools} | ({MEMORY + 'memory_search'} if checkpoint else set())
    guard.begin_turn('profile', request, visible)
    return guard.turn_context('profile')


def routed_profile(config, *, home, request=None, app_tools=(), name=ROUTED_PROFILE):
    """Return a fresh config that stages and enables the action guard in ``home``."""
    module = _load_repo_module('atmem/adapters/hermes/action_guard_plugin.py', 'dolphin_guard_stage')
    if 'dolphinbench-apps' not in config['toolsets']:
        raise ValueError('Execution profile requires simulated application tools')
    value = deepcopy(config)
    # The harness requires the native user turn to equal the dataset request and
    # grades the agent's own final answer, so the plugin must not inject the route
    # note or append completion notices; the note goes into the system prompt instead.
    settings = ROUTED_PROFILES[name]
    module.stage(home, settings=settings)
    plugins = value.setdefault('plugins', {})
    plugins['enabled'] = sorted(set(plugins.get('enabled', [])) | {module.PLUGIN})
    value.setdefault('tools', {})['tool_search'] = {'enabled': 'off'}
    note = route_note(request, app_tools, checkpoint=settings['checkpoint']) if request else ''
    if note:
        agent = value.setdefault('agent', {})
        agent['system_prompt'] = '\n\n'.join(filter(None, (agent.get('system_prompt', ''), note)))
    value['execution_profile'] = name
    return value


def apply_profile(name, config, *, home, skill_roots=(), request=None, app_tools=()):
    if name == PROFILE:
        return isolated_profile(config, skill_roots=skill_roots)
    if name in ROUTED_PROFILES:
        return routed_profile(config, home=home, request=request, app_tools=app_tools, name=name)
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
    if name in ROUTED_PROFILES:
        return validate_routed_request(body)
    raise ValueError('Unknown execution profile')
