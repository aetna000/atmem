"""Test-only Codex app-server dynamic-call client for a loopback provider."""
import json

from benchmarks.code_replay.appserver_probe import ConfigRPC


class DiscoveryRPC(ConfigRPC):
    ALLOWED = ConfigRPC.ALLOWED | {'turn/start', 'turn/interrupt'}

    def __init__(self, command, *, cwd, env, callback, on_written=None):
        self.callback = callback
        self.on_written = on_written
        self.calls = []
        super().__init__(command, cwd=cwd, env=env)

    def pump(self, timeout=.2):
        try:
            super().pump(timeout)
        except PermissionError:
            # Keep the original no-server-request diagnostic unchanged. Only
            # this explicit local fixture handles dynamic calls, never approvals.
            message = self.messages[-1]
            if message.get('method') != 'item/tool/call' or 'id' not in message:
                raise
            params = message['params']
            self.calls.append(params)
            try:
                if params['tool'] != 'repository_discover':
                    raise ValueError('unexpected dynamic tool')
                value = self.callback(params['arguments'])
                success = True
            except (ValueError, PermissionError):
                value = {'error': 'discovery request refused'}
                success = False
            response = {'id': message['id'], 'result': {'success': success,
                'contentItems': [{'type': 'inputText', 'text': json.dumps(value)}]}}
            self.sent.append(response)
            wire = json.dumps(response) + '\n'
            self.process.stdin.write(wire.encode())
            self.process.stdin.flush()
            if success and self.on_written is not None:
                self.on_written(params, value, wire)
