"""Supported isolated Hermes profile; validate actual provider-bound tools."""
from copy import deepcopy
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
