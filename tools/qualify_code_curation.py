"""Zero-model curation boundary qualification on an explicitly owned project.

Full response artifacts remain in encrypted curation-exposure documents. Stdout
is a machine-readable measurement, not a SWE-bench or token-saving claim.
"""
import argparse
from io import StringIO
import json
from pathlib import Path
import time

from atmem.code.application import CodeApplication
from atmem.code.contracts import CodeScope
from atmem.knowledge.code.mcp import CodeKnowledgeMCP
from atmem.memory import Memory


def qualify(instance, query):
    measurements = []
    def call(operation, arguments):
        start = time.perf_counter()
        reply = instance._call_tool(len(measurements) + 1, 'code_query',
                                    {'operation': operation, 'arguments': arguments})
        if reply.get('result', {}).get('isError') or 'error' in reply:
            raise RuntimeError('curation qualification request failed')
        stream = StringIO()
        instance._write(stream, reply)
        text = json.loads(stream.getvalue())['result']['content'][0]['text']
        response = json.loads(text)
        if response['status'] != 'ready':
            raise RuntimeError('curation evidence unavailable during qualification')
        measurements.append({'operation': operation, 'serialized_response_bytes': len(text.encode()),
                             'seconds': time.perf_counter() - start, 'item_count': len(response['items'])})
        return response
    capabilities = call('capabilities', {})
    index = call('discover', {'query': query, 'kind': 'both', 'budget': 4096})
    if not index['items']:
        raise RuntimeError('no matching evidence; qualification cannot silently pass empty')
    args = {'ids': [index['items'][0]['id']], 'session': 'qualification', 'epoch': 'epoch1', 'budget': 8192}
    detail = call('fetch', args)
    if not detail['items'] or 'version' not in detail['items'][0]:
        raise RuntimeError('selected evidence could not be fetched')
    known = [{key: detail['items'][0][key] for key in ('id', 'version')}]
    refs = call('changes', {**args, 'references': True, 'known': known})
    if refs['items'][0].get('status') != 'reference':
        raise RuntimeError('delivered unchanged evidence did not yield explicit reference')
    full = call('fetch', args)
    if full['items'] != detail['items']:
        raise RuntimeError('explicit full fetch changed unchanged evidence')
    return {'format': 'atmem-code-curation-qualification-v1', 'status': 'passed',
            'evidence': 'encrypted curation-exposure documents in supplied database',
            'kind': 'zero_model_boundary_not_coding_efficacy', 'model_calls': 0,
            'capabilities': capabilities, 'measurements': measurements}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--project-id', required=True)
    parser.add_argument('--subject', default='local')
    parser.add_argument('--profile', default='shared')
    parser.add_argument('--agent', default='codex')
    parser.add_argument('--query', required=True)
    args = parser.parse_args()
    if not Path(args.db).is_file():
        parser.error('use an existing initialized encrypted database')
    memory = Memory(args.db, auto_vectors=False)
    try:
        app = CodeApplication(memory, subject_id=args.subject)
        scope = CodeScope(args.subject, args.project_id, args.profile, args.agent)
        instance = CodeKnowledgeMCP(app, scope, args.project, experience=True, tool_profile='curated')
        print(json.dumps(qualify(instance, args.query), sort_keys=True))
    finally:
        memory.close()


if __name__ == '__main__':
    main()
