"""Read-only stdio MCP server exposing ``fact_search`` over source-linked statements.

Standard-library-only so it can be staged beside a native agent:
``python -I facts_stdio.py STORE.json`` (``standing_facts.py`` must sit beside it).
Results carry each fact's date, kind, verbatim source quote and session id.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import standing_facts  # noqa: E402

TOOL = {'name': 'fact_search',
        'description': ('Search source-linked model-generated statements about the user (rules, preferences, defaults, policies, '
                        'thresholds, commitments, people) distilled from earlier conversations. Each result has a '
                        'date and a source quote; quotation occurrence does not verify the statement. Check the source and current authority. Use short queries about the '
                        'kind of activity, person, place or limit involved.'),
        'inputSchema': {'type': 'object', 'properties': {
            'query': {'type': 'string'}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20}},
            'required': ['query'], 'additionalProperties': False},
        'annotations': {'readOnlyHint': True}}


def handle(store, request):
    method = request.get('method')
    if method == 'initialize':
        return {'protocolVersion': (request.get('params') or {}).get('protocolVersion', '2024-11-05'),
                'capabilities': {'tools': {}}, 'serverInfo': {'name': 'atmem-facts', 'version': '1'}}
    if method == 'tools/list':
        return {'tools': [TOOL]}
    if method == 'tools/call':
        params = request.get('params') or {}
        arguments = params.get('arguments') or {}
        if params.get('name') != 'fact_search' or not isinstance(arguments.get('query'), str):
            return {'content': [{'type': 'text', 'text': 'fact_search requires a string query.'}], 'isError': True}
        limit = arguments.get('limit') if isinstance(arguments.get('limit'), int) else 8
        results = standing_facts.search(store, arguments['query'], limit=max(1, min(20, limit)))
        return {'content': [{'type': 'text', 'text': json.dumps({'results': results}, ensure_ascii=False)}]}
    return {}


def main():
    store = json.loads(Path(sys.argv[1]).read_text())
    for line in sys.stdin:
        request = json.loads(line)
        if 'id' not in request:
            continue
        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': handle(store, request)}) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
