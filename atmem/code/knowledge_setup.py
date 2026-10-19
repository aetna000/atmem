"""AtMem-owned optional graph onboarding; never builds or downloads silently."""
from importlib.resources import files
from pathlib import Path
import sys

from atmem.knowledge.projections import CodeKnowledge
from atmem.knowledge.worker import ExtractionWorker


def configure(application, scope, root, *, image_id=None):
    knowledge = CodeKnowledge(application, scope)
    knowledge.graph._root(root)
    if image_id is not None:
        worker = ExtractionWorker(image_id)
        application.store.put_code_document(scope.subject_id, scope.project_id, 'knowledge-runtime', 'approved',
            {'image_id': worker.image_id, 'network': 'none', 'selection': 'explicit_user_configuration'})
        application.store.append_audit_event(subject_id=scope.subject_id, actor='user', event_type='code.knowledge_runtime_configured',
            payload={'project_id': scope.project_id, 'image_id': worker.image_id})
    value = application.store.code_document(scope.subject_id, scope.project_id, 'knowledge-runtime', 'approved')
    return {'format': 'atmem-code-runtime-config-v1', 'configured': value is not None,
            'runtime': value, 'automatic_download': False, 'graph_enabled': application.settings(scope.project_id)['graph_enabled']}


def worker_context(destination):
    root = Path(destination).expanduser()
    if root.is_symlink() or root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError('choose a new or empty build-context directory')
    # Never follow a symlink in a caller-selected output ancestry.
    if any(p.is_symlink() for p in [root, *root.parents]):
        raise ValueError('build context cannot have a symlink ancestor')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    resources = files('atmem.knowledge').joinpath('runtime_resources')
    for name in ('Dockerfile', 'entrypoint.py'):
        with (root / name).open('xb') as stream:
            stream.write(resources.joinpath(name).read_bytes())
    return {'format': 'atmem-code-worker-context-v1', 'directory': str(root.resolve()),
            'files': ['Dockerfile', 'entrypoint.py'], 'extractor': 'enola-cli==0.4.26',
            'build_requires_explicit_network': True, 'runtime_network': 'none',
            'next_step': 'Build this context explicitly, inspect the local sha256 image ID, then run knowledge-config --image-id ID.'}


def mcp_configuration(application, scope, root, *, tool_profile='expanded'):
    from dataclasses import asdict
    from atmem.code.discovery_hosts import unprobed_matrix
    if tool_profile not in {'expanded', 'compact', 'curated', 'navigation'}:
        raise ValueError('unknown Code tool profile')
    knowledge = CodeKnowledge(application, scope)
    root = str(knowledge.graph._root(root))
    database = application.store.path
    if database == ':memory:':
        raise ValueError('MCP configuration requires an existing persistent encrypted household')
    args = ['-I', '-m', 'atmem.knowledge.code.mcp', '--db', str(Path(database).resolve()), '--root', root,
        '--subject', scope.subject_id, '--project-id', scope.project_id, '--profile', scope.profile_id,
        '--agent', scope.agent_id]
    if tool_profile != 'navigation':
        args.append('--experience')
    if tool_profile != 'expanded':
        args.extend(['--tool-profile', tool_profile])
    return {'format': 'atmem-code-mcp-config-v1', 'configuration': {'mcpServers': {
        'atmem_code': {'command': sys.executable, 'args': args}}},
        'automatic_host_configuration_changed': False, 'mode': 'explicit_read_only_tools',
        'tool_profile': tool_profile,
        'automatic_recall_enabled': application.settings(scope.project_id)['auto_recall'],
        'navigation_context_warning': ('Existing automatic recall is still enabled; explicitly disable auto_recall for a discovery-only session.'
            if tool_profile == 'navigation' and application.settings(scope.project_id)['auto_recall'] else None),
        'discovery_routing': 'unqualified_optional_tool_only' if tool_profile == 'navigation' else 'not_requested',
        'discovery_hosts': [asdict(cell) for cell in unprobed_matrix()] if tool_profile == 'navigation' else [],
        'tools': ['repository_discover'] if tool_profile == 'navigation' else ['code_query'] if tool_profile != 'expanded' else
                 ['code_context', 'code_search', 'code_explore', 'code_source', 'code_experience'],
        'graph_current': knowledge.current(root) is not None}
