"""Controlled navigation comparators, not stock-native product replacement.

Only the operator selects backend/root. All arms retain the same offline shell.
This module is benchmark tooling, never imported by the ordinary installation.
"""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time

from atmem.code.curation import encoded, terms
from atmem.code.discovery import DiscoveryRequest, RESPONSE
from atmem.knowledge.contracts import SourceAnchor, source_path
from benchmarks.code_replay.claude_click_tools import shell


def definitions():
    from atmem.knowledge.code.mcp import CodeKnowledgeMCP
    navigation = CodeKnowledgeMCP._tool_definitions(type('Profile', (), {'tool_profile': 'navigation'})())[0]
    return [navigation, {'name': 'workspace_command',
        'description': 'Run an offline shell command in the permitted source tree for exact searches, original reads, edits and tests. 35 second limit; output is explicitly bounded. Navigation is optional.',
        'inputSchema': {'type': 'object', 'additionalProperties': False,
            'properties': {'command': {'type': 'string', 'minLength': 1, 'maxLength': 20000}},
            'required': ['command']}}]


class Provider:
    """One trusted subprocess; the model cannot select its method or arguments."""
    def __init__(self, config):
        self.process = subprocess.Popen(config['command'], cwd=config['cwd'], env=config['environment'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, bufsize=1)
        self.counter = 0
        self.call('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
            'clientInfo': {'name': 'atmem-discovery-comparator', 'version': '1'}})
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) + '\n')
        self.process.stdin.flush()

    def call(self, method, params):
        self.counter += 1
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': self.counter, 'method': method, 'params': params}) + '\n')
        self.process.stdin.flush()
        while True:
            line = self.process.stdout.readline(1_000_001)
            if not line or len(line.encode()) > 1_000_000:
                raise RuntimeError('bounded provider stream unavailable')
            response = json.loads(line)
            if response.get('id') == self.counter:
                if 'error' in response:
                    raise RuntimeError('provider rejected request')
                return response['result']

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


class Comparator:
    def __init__(self, config):
        self.config = config
        self.backend = config['backend']
        if self.backend not in {'native', 'cognee', 'atmem'}:
            raise ValueError('unknown operator-selected comparator')
        self.root = Path(config['workspace']).resolve(strict=True)
        self.provider = Provider(config['provider']) if config.get('provider') else None
        if (self.backend == 'native') != (self.provider is None):
            raise ValueError('real provider required for graph comparator')
        self.files = config['source_files']
        self.native = []
        for name, expected in self.files.items():
            path = self.path(name)
            raw = path.read_bytes()
            if sha256(raw).hexdigest() != expected:
                raise ValueError('source differs before comparator construction')
            if self.backend == 'native' and name.endswith('.py'):
                try:
                    tree = ast.parse(raw)
                except (SyntaxError, UnicodeDecodeError):
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        self.native.append({'id': name + ':' + str(node.lineno), 'title': node.name,
                            'path': name, 'start': node.lineno, 'end': node.end_lineno})

    def path(self, name):
        source_path(name)
        if name not in self.files:
            raise PermissionError('source outside frozen comparator snapshot')
        path = self.root / name
        if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file():
            raise PermissionError('unavailable or linked source')
        if not path.resolve().is_relative_to(self.root):
            raise PermissionError('source outside comparator root')
        return path

    def project(self, request, candidates):
        answer = {'format': RESPONSE, 'request_id': request.request_id, 'turn_id': request.turn_id,
            'backend': self.backend, 'status': 'ready', 'items': [], 'non_exhaustive': True,
            'truncated': False, 'freshness': 'not_established',
            'native_fallback': 'available_to_host', 'assurance': 'prepared_only'}
        for row in candidates[:request.limit]:
            name = row['path']
            raw = self.path(name).read_bytes()
            if sha256(raw).hexdigest() != self.files[name]:
                return {**answer, 'status': 'withheld', 'items': [], 'reason': 'source_changed'}
            anchor = SourceAnchor(name, self.files[name], row['start'], row['end']).to_dict()
            item = {'id': 'code:' + sha256(row['id'].encode()).hexdigest()[:32],
                'title': row['title'][:96], 'location': anchor,
                'version': self.files[name], 'match': 'identifier_or_path'}
            candidate = {**answer, 'items': [*answer['items'], item], 'freshness': 'current_at_preparation'}
            if len(encoded(candidate)) <= request.budget:
                answer = candidate
            else:
                answer['truncated'] = True
        if len(candidates) > request.limit:
            answer['truncated'] = True
        if len(encoded(answer)) > request.budget:
            return {'format': RESPONSE, 'request_id': request.request_id, 'turn_id': request.turn_id,
                'backend': self.backend, 'status': 'withheld', 'items': [], 'reason': 'response_budget'}
        return answer

    def discover(self, arguments):
        request = DiscoveryRequest.from_dict(arguments)
        if self.backend == 'atmem':
            result = self.provider.call('tools/call', {'name': 'repository_discover', 'arguments': request.to_dict()})
            if result.get('isError'):
                raise RuntimeError('AtMem discovery withheld')
            return json.loads(result['content'][0]['text'])
        query_terms = terms(request.query)
        candidates = self.native
        if self.backend == 'cognee':
            candidates, seen = [], set()
            # CODE supports substring search, not an embedding query here.
            # Query the exact text and at most six stable query tokens, then
            # rank their union by identifier/path overlap. No target facts.
            searches = list(dict.fromkeys([request.query, *sorted(query_terms, key=lambda x: (-len(x), x))[:6]]))
            for search in searches:
                result = self.provider.call('tools/call', {'name': 'code_search', 'arguments': {
                    'operation': 'query_facts', 'arguments': {'name': search, 'kinds': ['symbol'], 'limit': 100}}})
                if result.get('isError'):
                    raise RuntimeError('Cognee query failed')
                for dataset in json.loads(result['content'][0]['text']):
                    for fact in dataset['search_result']['facts']:
                        if fact['id'] in seen or fact.get('file') not in self.files:
                            continue
                        seen.add(fact['id'])
                        candidates.append({'id': fact['id'], 'title': fact['name'], 'path': fact['file'],
                            'start': fact.get('line', 1), 'end': fact.get('end_line') or fact.get('line', 1)})
        ranked = []
        for row in candidates:
            score = len(query_terms & terms(row['title'])) * 3 + len(query_terms & terms(row['path']))
            if score:
                ranked.append((-score, row['path'], row['start'], row['id'], row))
        return self.project(request, [row[-1] for row in sorted(ranked, key=lambda r: r[:-1])])

    def close(self):
        if self.provider:
            self.provider.close()


def serve(config):
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.atmem_bridge import ReplayEvidence
    scope = EvidenceScope('benchmark', 'local-operator', 'discovery-044')
    principal = EvidencePrincipal('discovery-044-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(Path(config['evidence']), vault_id='discovery-044', scope=scope)
    comparator = Comparator(config)
    calls = 0
    try:
        for line in sys.stdin:
            if len(line.encode()) > 100_000:
                raise ValueError('bounded MCP request required')
            request = json.loads(line)
            if 'id' not in request:
                continue
            tick = time.monotonic()
            try:
                method, params = request['method'], request.get('params', {})
                if method == 'initialize':
                    result = {'protocolVersion': params['protocolVersion'], 'capabilities': {'tools': {}},
                        'serverInfo': {'name': 'controlled-discovery-study', 'version': '1'}}
                elif method == 'tools/list':
                    result = {'tools': definitions()}
                elif method == 'ping':
                    result = {}
                elif method == 'tools/call':
                    calls += 1
                    if calls > 30:
                        raise ValueError('tool-call cap reached')
                    arguments = params.get('arguments', {})
                    if params['name'] == 'repository_discover':
                        value = comparator.discover(arguments)
                    elif params['name'] == 'workspace_command' and set(arguments) == {'command'}:
                        value = shell(config, arguments['command'])
                    else:
                        raise ValueError('unknown tool or fields')
                    result = {'content': [{'type': 'text', 'text': encoded(value).decode()}], 'isError': False}
                else:
                    raise ValueError('unknown read-only MCP method')
                response = {'jsonrpc': '2.0', 'id': request['id'], 'result': result}
            except (ValueError, PermissionError, OSError, RuntimeError) as exc:
                response = {'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -32602, 'message': type(exc).__name__ + ': request unavailable'}}
            payload = {'request': request, 'response': response, 'backend': config['backend'],
                'elapsed_ms': int((time.monotonic() - tick) * 1000), 'assurance': 'prepared_before_write'}
            vault.capture(run_id=config['run_id'], kind='discovery.tool_prepared', payload=payload, principal=principal)
            sys.stdout.write(json.dumps(response) + '\n')
            sys.stdout.flush()
            vault.capture(run_id=config['run_id'], kind='discovery.tool_written',
                payload={**payload, 'assurance': 'server_stream_written_not_model_ack'}, principal=principal)
    finally:
        comparator.close()


if __name__ == '__main__':
    serve(json.loads(sys.argv[1]))
