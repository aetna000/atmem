"""Qualify a pinned installed Code index against an explicit public checkout.

No model, hidden tests, source edits, network downloads or owner memory. The
fresh state directory holds an encrypted database and a public summary only.
"""
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--image-id', required=True)
    parser.add_argument('--query', default='repository architecture')
    parser.add_argument('--reuse-state', action='store_true', help='explicitly reuse this qualification database')
    parser.add_argument('--retain-artifacts', action='store_true', help='retain unadmitted worker bytes encrypted for diagnosis')
    parser.add_argument('--cached-artifacts', action='store_true', help='revalidate exact snapshot-bound retained worker bytes')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if args.reuse_state:
        if not (args.state_root / 'memory.db').is_file():
            raise ValueError('existing qualification database required')
    else:
        args.state_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.environ['ATMEM_HOME'] = str(args.state_root / 'home')
    import atmem
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    from atmem.code.identity import CodeIdentity
    from atmem.code.application import CodeApplication
    from atmem.knowledge.projections import CodeKnowledge
    from atmem.knowledge.worker import ExtractionWorker
    result = {'source': str(source), 'product_path': atmem.__file__, 'status': 'started',
              'extraction_mode': 'cached_artifact_revalidation' if args.cached_artifacts else 'fresh_worker'}
    if not args.reuse_state:
        HouseholdApplication.initialize(args.state_root / 'memory.db', encrypted=True)
    memory = Memory(args.state_root / 'memory.db', auto_vectors=False)
    started = time.monotonic()
    try:
        scope = CodeIdentity(memory.store).resolve(source, subject_id='index-qualification',
            profile_id='shared', agent_id='qualification')
        app = CodeApplication(memory, subject_id=scope.subject_id)
        app.settings(scope.project_id, {'graph_enabled': True})
        knowledge = CodeKnowledge(app, scope)
        import atmem.knowledge.worker as worker_module
        from atmem.knowledge.code.extractor import ExtractionArtifacts
        real_parse = worker_module.parse_artifacts
        def retain(artifacts):
            app.authorize(scope.project_id)
            jobs = memory.store.code_documents(scope.subject_id, scope.project_id, 'knowledge-job')
            if len(jobs) != 1:
                raise ValueError('one isolated qualification job required')
            manifest = {'snapshot_id': jobs[0]['snapshot_id'], 'image_id': args.image_id, 'artifacts': {},
                        'admission': 'unadmitted_diagnostic_only'}
            for name, raw in (('facts', artifacts.facts_jsonl), ('receipt', artifacts.receipt_json),
                              ('insights', artifacts.insights_json)):
                chunks = []
                for ordinal, start in enumerate(range(0, len(raw), 6_000_000)):
                    identity = f'{name}-{ordinal}'
                    memory.store.put_code_document(scope.subject_id, scope.project_id, 'qualification-artifact', identity,
                        {'payload_base64': base64.b64encode(raw[start:start + 6_000_000]).decode()})
                    chunks.append(identity)
                manifest['artifacts'][name] = {'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'chunks': chunks}
            memory.store.put_code_document(scope.subject_id, scope.project_id, 'qualification-artifact', 'manifest', manifest)
            return real_parse(artifacts)
        class CachedWorker:
            image_id = args.image_id
            def extract(self, snapshot, files, *, authorize):
                authorize(snapshot.scope)
                manifest = memory.store.code_document(scope.subject_id, scope.project_id, 'qualification-artifact', 'manifest')
                if not manifest or manifest['snapshot_id'] != snapshot.snapshot_id or manifest['image_id'] != self.image_id:
                    raise ValueError('cached artifacts do not match current source/worker')
                raw = {}
                for name, item in manifest['artifacts'].items():
                    raw[name] = b''.join(base64.b64decode(memory.store.code_document(scope.subject_id, scope.project_id,
                        'qualification-artifact', identity)['payload_base64'], validate=True) for identity in item['chunks'])
                    if len(raw[name]) != item['bytes'] or sha256(raw[name]).hexdigest() != item['sha256']:
                        raise ValueError('cached artifact integrity failure')
                return ExtractionArtifacts(raw['facts'], raw['receipt'], raw['insights'])
        if args.retain_artifacts:
            worker_module.parse_artifacts = retain
        try:
            result['index'] = knowledge.index(str(source), CachedWorker() if args.cached_artifacts else ExtractionWorker(args.image_id))
            if result['index']['status'] == 'unchanged':
                result['extraction_mode'] = 'existing_generation_revalidation'
        finally:
            worker_module.parse_artifacts = real_parse
        result['index_seconds'] = time.monotonic() - started
        generation = knowledge.current(str(source))
        if generation is None:
            raise RuntimeError('published projection is not current')
        result['source_files'] = len(generation['snapshot']['files'])
        result['facts'] = generation['receipt']['fact_count']
        context = knowledge.context(str(source), args.query, budget=4096)
        result['context'] = {'status': context['status'], 'bytes': len(context['content'].encode()),
            'sha256': sha256(context['content'].encode()).hexdigest()}
        from atmem.code.knowledge_setup import mcp_configuration
        server = mcp_configuration(app, scope, str(source))['configuration']['mcpServers']['atmem_code']
        requests = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
                'protocolVersion': '2025-03-26', 'capabilities': {},
                'clientInfo': {'name': 'index-qualification', 'version': '1'}}},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {
                'name': 'code_context', 'arguments': {'query': args.query, 'budget': 4096}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {
                'name': 'code_search', 'arguments': {'operation': 'architecture', 'arguments': {'max_nodes': 3}}}},
        ]
        checked = subprocess.run([server['command'], *server['args']], input='\n'.join(
            json.dumps(request) for request in requests) + '\n', text=True, capture_output=True, timeout=120)
        responses = [json.loads(line) for line in checked.stdout.splitlines()]
        if checked.returncode or len(responses) != 4 or any('error' in response for response in responses):
            raise RuntimeError('installed MCP transport qualification failed')
        answers = [json.loads(response['result']['content'][0]['text']) for response in responses[2:]]
        if any(response['result'].get('isError') for response in responses[2:]) or any(
                answer.get('status') != 'current' for answer in answers):
            raise RuntimeError('installed MCP context/architecture qualification failed')
        content = answers[0]['content']
        if len(content.encode()) > 4096 or sha256(content.encode()).hexdigest() != answers[0]['content_sha256']:
            raise RuntimeError('installed MCP source pack integrity/budget failed')
        result['mcp'] = {'context_status': answers[0]['status'], 'context_bytes': len(content.encode()),
            'architecture_status': answers[1]['status'], 'server_python': server['command'],
            'tools': [tool['name'] for tool in responses[1]['result']['tools']]}
        result['status'] = 'passed'
    except Exception as exc:
        result.update(status='failed', error_type=type(exc).__name__, error=str(exc))
    finally:
        result['elapsed_seconds'] = time.monotonic() - started
        memory.close()
        report_name = 'summary-recheck-' + uuid4().hex + '.json' if args.reuse_state else 'summary.json'
        (args.state_root / report_name).write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    main()
