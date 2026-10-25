"""Capture the actual native Hermes first request; never forward to a model."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sys
import tempfile
import threading

from .app_bridge import bridge, stage_client
from .execution_profile import isolated_profile, validate_request
from .readiness import qualification_sources, save, read, pin
from .runtime import NativeRuntime


def qualify(upstream, app_python, runtime_root, output, *, options_path):
    upstream, output = Path(upstream).resolve(), Path(output).resolve()
    sys.path.insert(0, str(upstream))
    output.mkdir(parents=True, exist_ok=False)
    runtime = NativeRuntime(runtime_root, source=Path.home() / '.hermes/hermes-agent',
        python=Path.home() / '.hermes/tools/python-3.14.7+20260901-darwin-arm64/bin/python3',
        dependency_facts=Path.home() / '.hermes/installs/7f16443560343fb8/facts.json')
    runtime.stage()
    runtime.verify_native_dependencies()
    name = 'db-' + secrets.token_hex(12)
    home = runtime.root / 'profiles' / name
    home.mkdir()
    capture = output / 'model-request.json'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if not capture.exists():
                save(capture, body)
            # There is deliberately no provider route or fabricated model reply.
            raw = b'{"error":{"message":"Qualification capture complete; no provider request sent"}}'
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    save(output / 'state.json', {'docs': []})
    save(output / 'manifest.json', {'persona_id': 'synthetic', 'tools': ['create_doc']})
    save(output / 'directory.json', {'users': [], 'channels': []})
    save(output / 'tools.json', {'active_tools': ['create_doc']})
    apps = {'command': str(app_python), 'args': [str(upstream / 'mock_mcp/repair_server.py')],
            'env': {'DOLPHINBENCH_PERSONA': 'synthetic', 'DOLPHINBENCH_MOCK_MANIFEST': str(output / 'manifest.json'),
                    'DOLPHINBENCH_WORKSPACE_DIRECTORY': str(output / 'directory.json'),
                    'DOLPHINBENCH_TOOL_CONFIG_PATH': str(output / 'tools.json'),
                    'DOLPHINBENCH_STATE_PATH': str(output / 'state.json'),
                    'DOLPHINBENCH_LOG_PATH': str(output / 'calls.jsonl')}}
    from .adapter import AtMemAdapter
    options = read(options_path)
    adapter = AtMemAdapter(options, output)
    host = adapter.host('morgan')
    try:
        with tempfile.TemporaryDirectory(prefix='dp-', dir='/private/tmp') as short:
            socket = Path(short) / 'a.sock'
            with bridge(apps, socket):
                stage_client(upstream, home / 'app_client.py', socket)
                host.configure_profile(home,
                    base_url=f'http://127.0.0.1:{server.server_port}/v1',
                    local_token='local-preflight-no-provider',
                    mcp={'command': str(runtime.python), 'args': ['-I', str(home / 'app_client.py')]},
                    governed_context='', reader_model=options['campaign_identity']['agent']['model'],
                    reader_reasoning=options['campaign_identity']['agent']['reasoning'],
                    reader_max_turns=60, reader_context_length=1050000,
                    discovery_query='Synthetic qualification', discovery_python=str(runtime.python),
                    application_workflow=True, strict_application_contracts=True, initial_status='authorized')
                config = isolated_profile(read(home / 'config.yaml'),
                    skill_roots=(runtime.source / 'skills', Path.home() / '.hermes/skills', runtime.root / 'skills'))
                config['providers']['custom'].update(request_timeout_seconds=36000, stale_timeout_seconds=36000)
                config['agent']['api_max_retries'] = 0
                # configure_profile already wrote the private file; replace only the isolated settings.
                (home / 'config.yaml').write_text(json.dumps(config))
                save(output / 'profile.json', config)
                process = runtime.invoke(name, ['chat', '-q', 'Acknowledge this synthetic qualification.',
                    '-Q', '--yolo', '--format', 'stream-json', '--max-turns', '60'],
                    ports=[server.server_port, host.server.server_port], sockets=[socket], timeout=120,
                    environment={'CUSTOM_API_KEY': 'local-preflight-no-provider'})
        save(output / 'process.json', {'returncode': process.returncode,
                                      'stdout': process.stdout, 'stderr': process.stderr})
        if not capture.exists():
            raise ValueError('Native Hermes made no request; inspect process.json')
        names = validate_request(json.loads(capture.read_text()))
        if 'mcp__dolphinbench_apps__create_doc' not in names:
            raise ValueError('Synthetic app tool not exposed to native reader')
        save(output / 'qualification.json', {'mcp_only': True, 'eager_tools': True,
            'skills_disabled': True, 'actual_native_request': True,
            'source': qualification_sources(), 'model_calls': 0, 'provider_forwarding_exists': False, 'tools': names,
            'options': pin(options_path), 'upstream_manifest': pin(upstream / 'manifest.json'),
            'app_python': pin(Path(app_python).resolve()), 'same_adapter_profile_builder': True})
        return names
    finally:
        adapter.stop()
        server.shutdown()
        server.server_close()
        thread.join(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--app-python', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--options', type=Path, required=True)
    args = parser.parse_args()
    names = qualify(args.upstream, args.app_python, args.runtime_root, args.output, options_path=args.options)
    print(json.dumps({'qualified': True, 'model_calls': 0, 'tools': names}))


if __name__ == '__main__':
    main()
