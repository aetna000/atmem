"""Local protocol fixture, not an Anthropic model or usage measurement."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread


class DiscoveryAnthropicEndpoint:
    def __init__(self, source_path):
        self.requests = []
        self.source_path = str(source_path)
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if 'count_tokens' in self.path:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"input_tokens":100}')
                    return
                parent.requests.append(value)
                index = len(parent.requests) - 1
                tools = value.get('tools', [])
                nav = next((t['name'] for t in tools if t['name'].endswith('repository_discover')), None)
                query = {'format': 'atmem-repository-discovery-request-v1', 'request_id': 'probe-nav',
                         'turn_id': 'probe-turn', 'query': 'main implementation', 'limit': 5, 'budget': 4096}
                operations = [(nav, query),
                              (nav, {**query, 'request_id': 'probe-invalid', 'root': '/outside-scope'}),
                              ('Read', {'file_path': parent.source_path}),
                              ('Edit', {'file_path': parent.source_path, 'old_string': 'return 1', 'new_string': 'return 2'}),
                              ('Bash', {'command': "python3 -c \"from pathlib import Path; assert 'return 2' in Path('main.py').read_text(); print('discovery-native-test-ok')\""})]
                action = operations[index] if index < len(operations) else None
                if action and not action[0]:
                    action = None
                message = {'id': 'msg-discovery-' + str(index), 'type': 'message', 'role': 'assistant',
                    'model': value.get('model', 'fixture'), 'content': [], 'stop_reason': None,
                    'stop_sequence': None, 'usage': {'input_tokens': 100, 'output_tokens': 1}}
                events = [('message_start', {'type': 'message_start', 'message': message})]
                if action:
                    block = {'type': 'tool_use', 'id': 'probe-tool-' + str(index), 'name': action[0], 'input': {}}
                    events.extend([
                        ('content_block_start', {'type': 'content_block_start', 'index': 0, 'content_block': block}),
                        ('content_block_delta', {'type': 'content_block_delta', 'index': 0,
                            'delta': {'type': 'input_json_delta', 'partial_json': json.dumps(action[1])}})])
                else:
                    events.extend([
                        ('content_block_start', {'type': 'content_block_start', 'index': 0,
                            'content_block': {'type': 'text', 'text': ''}}),
                        ('content_block_delta', {'type': 'content_block_delta', 'index': 0,
                            'delta': {'type': 'text_delta', 'text': 'Local discovery boundary probe complete.'}})])
                events.extend([
                    ('content_block_stop', {'type': 'content_block_stop', 'index': 0}),
                    ('message_delta', {'type': 'message_delta', 'delta': {
                        'stop_reason': 'tool_use' if action else 'end_turn', 'stop_sequence': None},
                        'usage': {'output_tokens': 3}}),
                    ('message_stop', {'type': 'message_stop'})])
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                for event, data in events:
                    self.wfile.write(('event: ' + event + '\ndata: ' + json.dumps(data) + '\n\n').encode())
                    self.wfile.flush()

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
