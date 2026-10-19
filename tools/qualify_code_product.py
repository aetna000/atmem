"""Installed-only public-source command/experience/graph qualification.

No model, benchmark solve, private owner database or registry publication. Run
with the preview's installed Python, outside the source tree, against an explicit
public checkout/revision. All generated state stays in a new operator directory.
"""
import argparse
from dataclasses import replace
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--image-id')
    parser.add_argument('--retain-experience', action='store_true',
                        help='retain the formed control experience for an explicit cross-machine bundle check')
    args = parser.parse_args()
    if args.state_root.exists() or args.state_root.is_symlink():
        raise ValueError('choose a fresh qualification directory')
    args.state_root.mkdir(parents=True, mode=0o700)
    root = args.state_root / 'click-source'
    root.mkdir()
    os.environ['ATMEM_HOME'] = str(args.state_root / 'home')
    # Environment set before importing modules which resolve key locations.
    import atmem
    from atmem.memory import Memory
    from atmem.code.application import CodeApplication
    from atmem.code.contracts import CodeContextRequest
    from atmem.code.context import build_context
    from atmem.code.identity import CodeIdentity
    from atmem.code.execution import run_command
    from atmem.code.experience_view import experiences, execution_evidence
    from atmem.code.knowledge_setup import worker_context, mcp_configuration
    from atmem.service.household import HouseholdApplication
    if '/site-packages/atmem/' not in str(Path(atmem.__file__).resolve()):
        raise RuntimeError('qualification requires the installed wheel')
    archive = subprocess.check_output(['git', '-C', str(args.checkout), 'archive', args.revision])
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as stream:
        for member in stream.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():
                raise ValueError('unsafe public source member')
            if member.isdir():
                continue
            if not member.isfile() or member.size > 2_000_000:
                raise ValueError('unexpected public source member')
            target = root / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(stream.extractfile(member).read())
    for command in (['git', 'init', str(root)], ['git', '-C', str(root), 'add', '.'],
        ['git', '-C', str(root), '-c', 'user.name=AtMem Qualification', '-c', 'user.email=qualification@localhost',
         'commit', '-m', 'Authorized public source snapshot']):
        subprocess.run(command, check=True, capture_output=True)
    db = args.state_root / 'memory.db'
    HouseholdApplication.initialize(db, encrypted=True)
    memory = Memory(db, auto_vectors=False)
    try:
        scope = CodeIdentity(memory.store).resolve(root, subject_id='qualification', profile_id='shared', agent_id='claude')
        app = CodeApplication(memory, subject_id=scope.subject_id)
        worker_context(args.state_root / 'worker')
        command = [sys.executable, '-I', '-c', 'import sys;sys.path.insert(0,' + repr(str(root / 'src')) +
                   ');import click;assert callable(click.command);print("Public Click command decorator imported successfully")']
        observed = subprocess.run([sys.executable, '-I', str(Path(sys.executable).with_name('atmem')), 'code', 'run', '--db', str(db),
            '--subject', scope.subject_id, '--project', str(root), '--host', scope.agent_id,
            '--intent', 'Inspect Click command decorator behavior', '--anchor', 'src/click/core.py',
            '--anchor', 'src/click/decorators.py', '--', *command], capture_output=True, text=True, timeout=60)
        if observed.returncode:
            raise RuntimeError('installed command producer failed: ' + observed.stderr)
        run = json.loads(observed.stdout)
        assert run['exit_code'] == 0 and run['formation']['formed'], run
        other = replace(scope, agent_id='copilot')
        request = CodeContextRequest('qualified-handoff', 'new-session', 'turn', 'Click command decorator behavior', 4096, other)
        context = build_context(memory, request, repository_root=str(root))
        assert run['formation']['record_ids'][0] in context.memory_ids
        assert experiences(app, other, str(root))['items'][0]['applicability']['status'] == 'applicable'
        (root / 'qualification_unrelated.py').write_text('unrelated = True\n')
        assert experiences(app, other, str(root))['items'][0]['applicability']['status'] == 'applicable'
        anchored = root / 'src/click/core.py'
        original = anchored.read_bytes()
        anchored.write_bytes(original + b'\n# Source-change applicability qualification\n')
        assert experiences(app, other, str(root))['items'][0]['applicability']['status'] == 'withheld'
        assert not build_context(memory, replace(request, request_id='changed'), repository_root=str(root)).memory_ids
        anchored.write_bytes(original)
        evidence = execution_evidence(app, scope.project_id, run['formation']['record_ids'][0], run['experience_id'])
        assert evidence['stdout'] == run['stdout']
        graph = None
        if args.image_id:
            app.settings(scope.project_id, {'graph_enabled': True})
            app.dispatch('knowledge-config', {'project_id': scope.project_id, 'root': str(root), 'agent': scope.agent_id,
                'image_id': args.image_id})
            graph = app.dispatch('knowledge-index', {'project_id': scope.project_id, 'root': str(root), 'agent': scope.agent_id})
        config = mcp_configuration(app, other, str(root))
        server = config['configuration']['mcpServers']['atmem_code']
        requests = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-03-26', 'capabilities': {}, 'clientInfo': {'name': 'installed-control', 'version': '1'}}},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'code_experience', 'arguments': {}}}]
        if graph:
            found = app.dispatch('knowledge-query', {'project_id': scope.project_id, 'root': str(root),
                'agent': scope.agent_id, 'operation': 'query_facts', 'options': {'name': 'get_help_option', 'limit': 1}})
            seed = found['result']['facts'][0]['id']
            operations = [('query_facts', {'name': 'get_help_option', 'limit': 3}), ('explore', {'id': seed, 'max_nodes': 8}),
                ('traverse', {'node_ids': [seed], 'max_depth': 3, 'max_nodes': 8}),
                ('find_path', {'source_id': seed, 'target_id': seed, 'max_nodes': 8}),
                ('impact_analysis', {'id': seed, 'max_depth': 2, 'max_nodes': 8}),
                ('architecture', {'max_nodes': 8}), ('delta', {}), ('insights', {'limit': 3})]
            for operation, options in operations:
                requests.append({'jsonrpc': '2.0', 'id': len(requests) + 1, 'method': 'tools/call', 'params': {
                    'name': 'code_search', 'arguments': {'operation': operation, 'arguments': options, 'budget': 131072}}})
        checked = subprocess.run([server['command'], *server['args']], input='\n'.join(map(json.dumps, requests)) + '\n',
            cwd=args.state_root, capture_output=True, text=True, timeout=30)
        replies = [json.loads(line) for line in checked.stdout.splitlines()]
        assert checked.returncode == 0 and len(replies) == len(requests) and all('error' not in r for r in replies), checked.stderr
        assert json.loads(replies[2]['result']['content'][0]['text'])['items']
        for reply in replies[3:]:
            assert not reply['result']['isError'], reply
            assert json.loads(reply['result']['content'][0]['text'])['status'] == 'current', reply
        deleted = None
        if not args.retain_experience:
            deleted = app.forget(scope.project_id, run['formation']['record_ids'][0])
            assert not experiences(app, other, str(root))['items']
        report = {'format': 'atmem-code-installed-qualification-v1', 'package': str(atmem.__file__),
            'python': sys.version, 'public_revision': args.revision, 'source_archive_sha256': sha256(archive).hexdigest(),
            'command': run, 'producer_boundary': 'actual_installed_cli', 'shared_agent_recall': True, 'unrelated_edit_recall': True,
            'changed_anchor_withheld': True, 'exact_output_inspected': True, 'mcp_replies': replies,
            'graph': graph, 'forget': deleted, 'deleted_experience_unavailable': deleted is not None,
            'experience_retained_for_bundle_control': args.retain_experience,
            'classification': 'installed_product_control_not_task_benefit_or_normal_host_qualification'}
        path = args.state_root / 'qualification.json'
        path.write_text(json.dumps(report, indent=2))
        print(json.dumps({'completed': True, 'report': str(path), 'graph': graph, 'mcp_tools': len(replies[1]['result']['tools'])}))
    finally:
        memory.close()


if __name__ == '__main__':
    main()
