"""Exercise native routed hooks with scripted responses; never contact a model."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sys
import threading

from .app_bridge import bridge, stage_client, short_socket
from .execution_profile import APP, MEMORY, ROUTED_PROFILE, ROUTED_PROFILES, ROUTE_NOTE_MARKER, apply_profile, validate

QUESTION = 'Create a document with synthetic routing qualification text.'
from .readiness import qualification_sources, save, read, pin
from .runtime import NativeRuntime


def qualify(upstream, app_python, runtime_root, output, *, options_path, profile=ROUTED_PROFILE):
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
            index = len(list(output.glob('request-*.json')))
            save(output / f'request-{index:02}.json', body)
            write = ('mcp__dolphinbench_apps__create_doc',
                     {'title': 'Synthetic routing qualification', 'body': 'Synthetic durable routing text'})
            scripted = [('terminal', {'command': 'memo notes -a'}), write]
            if ROUTED_PROFILES[profile]['checkpoint']:
                # Held once, then a remembered-constraints search, then the same write again.
                scripted += [(MEMORY + 'memory_search', {'query': 'synthetic routing preference'}), write]
            message = {'role': 'assistant', 'content': 'Synthetic qualification complete.'}
            finish = 'stop'
            if index < len(scripted):
                name, args = scripted[index]
                message = {'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': f'synthetic-{index}', 'type': 'function',
                     'function': {'name': name, 'arguments': json.dumps(args)}}]}
                finish = 'tool_calls'
            reply = {'id': f'qualification-{index}', 'object': 'chat.completion',
                     'model': body.get('model'), 'choices': [{'index': 0, 'message': message,
                     'finish_reason': finish}], 'usage': {'prompt_tokens': 0, 'completion_tokens': 0}}
            if body.get('stream'):
                chunk = {**reply, 'object': 'chat.completion.chunk', 'choices': [
                    {'index': 0, 'delta': {**message, **({'tool_calls': [
                        {**message['tool_calls'][0], 'index': 0}]} if 'tool_calls' in message else {})},
                     'finish_reason': finish}]}
                raw = ('data: ' + json.dumps(chunk) + '\n\ndata: [DONE]\n\n').encode()
                content_type = 'text/event-stream'
            else:
                raw = json.dumps(reply).encode()
                content_type = 'application/json'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
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
        with short_socket() as socket:
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
                config = apply_profile(profile, read(home / 'config.yaml'), home=home,
                    request=QUESTION, app_tools=['create_doc'],
                    skill_roots=(runtime.source / 'skills', Path.home() / '.hermes/skills', runtime.root / 'skills'))
                config['providers']['custom'].update(request_timeout_seconds=36000, stale_timeout_seconds=36000)
                config['agent']['api_max_retries'] = 0
                # configure_profile already wrote the private file; replace only the isolated settings.
                (home / 'config.yaml').write_text(json.dumps(config))
                save(output / 'profile.json', config)
                process = runtime.invoke(name, ['chat', '-q', QUESTION,
                    '-Q', '--yolo', '--format', 'stream-json', '--max-turns', '60'],
                    ports=[server.server_port, host.server.server_port], sockets=[socket], timeout=120,
                    environment={'CUSTOM_API_KEY': 'local-preflight-no-provider'})
        save(output / 'process.json', {'returncode': process.returncode,
                                      'stdout': process.stdout, 'stderr': process.stderr})
        if not capture.exists():
            raise ValueError('Native Hermes made no request; inspect process.json')
        names = validate(profile, read(capture))
        plugin = home / 'plugins/atmem-action-guard'
        for filename in ('settings.json', '__init__.py', 'action_guard.py', 'plugin.yaml'):
            (output / ('staged-' + filename)).write_bytes((plugin / filename).read_bytes())
        records = home / '.atmem/action-guard/outcomes.jsonl'
        (output / 'guard-outcomes.jsonl').write_bytes(records.read_bytes())
        evidence = verify_evidence(output)
        save(output / 'qualification.json', {**evidence, 'actual_native_request': True,
            'profile': profile, 'runtime_root': str(runtime.root),
            'native_python': pin(runtime.python), 'source': qualification_sources(), 'model_calls': 0,
            'provider_forwarding_exists': False, 'tools': names,
            'options': pin(options_path), 'upstream_manifest': pin(upstream / 'manifest.json'),
            'app_python': pin(Path(app_python).resolve()), 'same_adapter_profile_builder': True})
        return names
    finally:
        adapter.stop()
        server.shutdown()
        server.server_close()
        thread.join(5)


def verify_evidence(output):
    """Recompute routed assertions from retained native requests, outcomes and app bytes."""
    output = Path(output)
    from .readiness import sha
    root = Path(__file__).parents[2]
    for staged, source in [('staged-__init__.py', 'atmem/adapters/hermes/action_guard_plugin.py'),
                           ('staged-action_guard.py', 'atmem/action_guard.py')]:
        if sha(output / staged) != sha(root / source):
            raise ValueError('Native plugin payload differs from pinned source')
    settings = read(output / 'staged-settings.json')
    config = read(output / 'profile.json')
    profile = config.get('execution_profile', ROUTED_PROFILE)
    if profile not in ROUTED_PROFILES:
        raise ValueError('Unknown routed profile in qualification evidence')
    checkpoint = ROUTED_PROFILES[profile]['checkpoint']
    names = validate(profile, read(output / 'model-request.json'))
    if (settings != {**ROUTED_PROFILES[profile]}
            or config.get('plugins', {}).get('enabled') != ['atmem-action-guard']
            or not {'terminal', 'skill_view', APP + 'create_doc'} <= set(names)
            or config.get('tools', {}).get('tool_search', {}).get('enabled') != 'off'):
        raise ValueError('Routed inventory/plugin/checkpoint mismatch')
    outcomes = [json.loads(line) for line in (output / 'guard-outcomes.jsonl').read_text().splitlines()]
    calls = [json.loads(line) for line in (output / 'calls.jsonl').read_text().splitlines()]
    state = read(output / 'state.json')
    requests = [read(p) for p in sorted(output.glob('request-*.json'))]
    tool_messages = [m for r in requests for m in r.get('messages', []) if m.get('role') == 'tool']
    if (len(outcomes) != 1 or outcomes[0].get('verdict', {}).get('status') != 'completed'
            or len(calls) != 1 or calls[0]['tool'] != 'create_doc'
            or calls[0]['result'].get('ok') is not True
            or len(state.get('docs', [])) != 1
            or state['docs'][0].get('body') != 'Synthetic durable routing text'
            or not any('memo' in json.dumps(m) and 'create_doc' in json.dumps(m) for m in tool_messages)):
        raise ValueError('Native plugin detour/write/state/log qualification failed')
    # The pilot export requires the native user turn to equal the request byte for byte
    # (adapter user-boundary check); every actual model request must carry it unchanged.
    for request in requests:
        users = [m.get('content') for m in request.get('messages', []) if m.get('role') == 'user']
        if users != [QUESTION]:
            raise ValueError('Native plugin changed the user boundary: ' + json.dumps(users)[:300])
    # The request-specific route note must reach the model through the system prompt.
    system = ' '.join(str(m.get('content', '')) for m in requests[0].get('messages', [])
                      if m.get('role') in ('system', 'developer'))
    if ROUTE_NOTE_MARKER not in system or APP + 'create_doc' not in system:
        raise ValueError('Route note missing from the actual native system prompt')
    # Guard outcome and the next actual request must both witness the refused detour.
    routes = [d.get('route', '') for d in outcomes[0].get('decisions', [])]
    if (not any(r.startswith('command:') for r in routes)
            or outcomes[0].get('memory_query_count') != (1 if checkpoint else 0)
            or len(requests) != (5 if checkpoint else 3) or read(output / 'process.json')['returncode'] != 0):
        raise ValueError('Native plugin did not record a refused local detour')
    if checkpoint and (routes.count('checkpoint:' + APP + 'create_doc') != 1 or 'Held once' not in system):
        raise ValueError('Commit checkpoint was not held exactly once and stated in the system prompt')
    return {k: True for k in ('ordinary_inventory', 'plugin_loaded', 'checkpoint_held_once' if checkpoint else 'checkpoint_disabled',
                              'user_boundary_unchanged', 'route_note_in_system_prompt',
                              'native_write_state_log_agree', 'local_detour_refused')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--app-python', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--options', type=Path, required=True)
    parser.add_argument('--profile', default=ROUTED_PROFILE, choices=sorted(ROUTED_PROFILES))
    args = parser.parse_args()
    names = qualify(args.upstream, args.app_python, args.runtime_root, args.output, options_path=args.options,
                    profile=args.profile)
    print(json.dumps({'qualified': True, 'model_calls': 0, 'tools': names}))


if __name__ == '__main__':
    main()
