"""Isolated encrypted product repository for installed-agent protocol fixtures."""
from pathlib import Path
import sys
from types import SimpleNamespace


def project(tmp_path, monkeypatch, agent):
    from atmem.code.application import CodeApplication
    from atmem.code.identity import CodeIdentity
    from atmem.core import keys
    from atmem.knowledge.projections import CodeKnowledge
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    from tests.test_knowledge_lifecycle import init_repository, FixtureWorker
    home = tmp_path / 'atmem-home'
    monkeypatch.setenv('ATMEM_HOME', str(home))
    monkeypatch.setattr(keys, 'DEFAULT_KEY_PATH', home / 'identity/keys/db.key')
    database = tmp_path / 'memory.db'
    HouseholdApplication.initialize(database, encrypted=True)
    root = tmp_path / 'repo'
    root.mkdir()
    memory = Memory(database, auto_vectors=False)
    scope = CodeIdentity(memory.store).resolve(root, subject_id='local', profile_id='shared', agent_id=agent)
    app = CodeApplication(memory, subject_id='local')
    env = SimpleNamespace(memory=memory, root=root, scope=scope, app=app, project=scope.project_id,
                          home=home, database=database)
    init_repository(env)
    CodeKnowledge(app, scope).index(str(root), FixtureWorker())
    return env


def mcp_server(env):
    source = 'import sys;sys.path.insert(0,' + repr(str(Path(__file__).resolve().parents[2])) + ');from atmem.knowledge.code.mcp import main;main()'
    return {'type': 'local', 'command': sys.executable,
        'args': ['-I', '-c', source, '--db', str(env.database), '--root', str(env.root),
                 '--subject', 'local', '--project-id', env.project, '--agent', env.scope.agent_id,
                 '--tool-profile', 'navigation'], 'env': {'ATMEM_HOME': str(env.home)}, 'tools': ['*']}


def navigation_plan(value, index, *, native_root=None):
    tools = value.get('tools', [])
    names = [tool.get('name', tool.get('function', {}).get('name', '')) for tool in tools]
    name = next((n for n in names if n.endswith('repository_discover')), None)
    if index >= 2 and native_root is not None:
        source = Path(native_root) / 'main.py'
        functions = [tool.get('function', tool) for tool in tools]
        by_name = {tool.get('name'): tool for tool in functions}
        if index == 2 and 'view' in by_name:
            return 'view', {'path': str(source)}
        if index == 3 and 'edit' in by_name:
            return 'edit', {'path': str(source), 'old_str': 'return 1', 'new_str': 'return 2'}
        command = ({
            2: "python3 -c \"from pathlib import Path; print(Path('main.py').read_text())\"",
            3: "python3 -c \"from pathlib import Path; p=Path('main.py'); p.write_text(p.read_text().replace('return 1','return 2'))\"",
            4: "python3 -c \"from pathlib import Path; assert 'return 2' in Path('main.py').read_text(); print('discovery-native-test-ok')\"",
        }).get(index)
        if command:
            for native_name in ('bash', 'exec_command', 'shell_command', 'shell'):
                definition = by_name.get(native_name)
                if not definition:
                    continue
                schema = definition.get('parameters', definition.get('input_schema', {}))
                properties = schema.get('properties', {})
                field = 'cmd' if 'cmd' in properties else 'command' if 'command' in properties else None
                if field:
                    arg = ['/bin/sh', '-c', command] if properties[field].get('type') == 'array' else command
                    arguments = {field: arg}
                    for required in schema.get('required', []):
                        if required == 'description':
                            arguments[required] = 'Local original-source boundary fixture'
                    return native_name, arguments
    if index >= 2 or name is None:
        return None
    arguments = {'format': 'atmem-repository-discovery-request-v1',
        'request_id': 'probe-request-' + str(index), 'turn_id': 'probe-turn',
        'query': 'main implementation', 'limit': 5, 'budget': 4096}
    if index == 1:
        arguments['root'] = '/outside-scope'
    return name, arguments
