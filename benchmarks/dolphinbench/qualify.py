"""No-cost installed native-agent qualification. Fixture responses are not benchmark results."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import threading
import sys
from contextlib import nullcontext

from .driver import AtMemHost
from .gateway import Gateway, save_new
from .runtime import NativeRuntime
from .app_bridge import bridge, stage_client
from .export import export_interaction


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        value = {'id': 'offline-plumbing-fixture', 'object': 'chat.completion', 'created': 0,
                 'model': body['model'], 'provider': 'Azure',
                 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'PLUMBING_FIXTURE_ONLY'},
                              'finish_reason': 'stop'}],
                 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2, 'cost': 0}}
        catalog = json.dumps(body.get('tools', []))
        if ('mcp__dolphinbench_apps__list_inbox' in catalog
                and not any(m.get('role') == 'tool' for m in body.get('messages', []))):
            value['choices'][0]['message'] = {'role': 'assistant', 'content': None,
                'tool_calls': [{'id': 'offline-mcp-read-only', 'type': 'function',
                    'function': {'name': 'tool_call', 'arguments': json.dumps({'calls': [
                        {'name': 'mcp__dolphinbench_apps__list_inbox', 'arguments': {}}]})}}]}
            value['choices'][0]['finish_reason'] = 'tool_calls'
        if body.get('stream'):
            value['object'] = 'chat.completion.chunk'
            value['choices'][0]['delta'] = value['choices'][0].pop('message')
            for index, call in enumerate(value['choices'][0]['delta'].get('tool_calls', [])):
                call['index'] = index
            raw = ('data: ' + json.dumps(value) + '\n\ndata: [DONE]\n\n').encode()
            kind = 'text/event-stream'
        else:
            raw, kind = json.dumps(value).encode(), 'application/json'
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/Volumes/AtMemDolphin/qualification-native'))
    parser.add_argument('--apps', action='store_true', help='Qualify the real upstream simulated app MCP bridge')
    args = parser.parse_args()
    root = args.output.resolve()
    if not root.is_relative_to(Path('/Volumes/AtMemDolphin')):
        raise ValueError('Qualification artifacts must stay on the external benchmark workspace')
    if root.exists():
        raise ValueError('Qualification directory exists; preserve it and use an explicitly new run')
    root.mkdir(mode=0o700)
    upstream = Path('/Volumes/AtMemDolphin/upstream')
    sys.path.append(str(upstream))
    if args.apps:
        from harness.submission import read_release
        from harness.runner import Runner
        release = read_release(upstream)
        runner = Runner(release, root / 'controller', None, identity={'fixture_only': True}, release_root=upstream)
        persona = next(iter(release))
        apps = runner._apps('ingestion', persona, '000000', release[persona]['sessions'][0])
        apps['command'] = '/Volumes/AtMemDolphin/venv/bin/python'
    runtime = NativeRuntime('/Volumes/AtMemDolphin/runtime-home',
        source='/Users/javadtaghia/.hermes/hermes-agent',
        python='/Users/javadtaghia/.hermes/tools/python-3.14.7+20260901-darwin-arm64/bin/python3',
        dependency_facts='/Users/javadtaghia/.hermes/installs/7f16443560343fb8/facts.json')
    runtime.stage()
    observers = runtime.root / 'observers'
    observers.mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__).with_name('observe_native.py'), observers / 'observe_native.py')
    fixture = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    thread = threading.Thread(target=fixture.serve_forever, daemon=True)
    thread.start()
    host = AtMemHost(root / 'atmem', 'qualification')
    try:
        for number, message in enumerate(('My preferred editor is Neovim.', 'What is my preferred editor?')):
            profile_name = f'{root.name}-{number}'
            home = runtime.root / 'profiles' / profile_name
            gateway = Gateway(key='offline-not-a-real-key', output=root / f'calls-{number}',
                ledger_path=root / 'fixture-budget.db', campaign_identity={'offline_fixture': True},
                cap_usd=1, phase='qualification', model='openai/gpt-5.6-luna',
                input_per_million=1, output_per_million=5,
                endpoint=f'http://127.0.0.1:{fixture.server_port}/chat/completions').start()
            try:
                socket = root / f'app-{number}.sock'
                with bridge(apps, socket) if args.apps else nullcontext():
                    home.mkdir(parents=True, exist_ok=True)
                    mcp = None
                    if args.apps:
                        client = home / 'app_client.py'
                        stage_client(upstream, client, socket)
                        mcp = {'command': str(runtime.python), 'args': ['-I', str(client)]}
                    host.configure_profile(home, base_url=gateway.base_url, local_token=gateway.local_token, mcp=mcp)
                    witness = home / 'shutdown-witness.jsonl'
                    result = runtime.invoke(profile_name,
                        ['chat', '-q', message, '-Q', '--yolo', '--format', 'stream-json', '--max-turns', '2'],
                        ports=[gateway.server_port, host.server.server_port], sockets=[socket] if args.apps else [], timeout=120,
                        environment={'CUSTOM_API_KEY': gateway.local_token,
                                     'ATMEM_BENCH_OBSERVER': str(observers / 'observe_native.py'),
                                     'ATMEM_BENCH_WITNESS': str(witness)})
                save_new(root / f'process-{number}.json', {'exit_code': result.returncode,
                    'stdout': result.stdout, 'stderr': result.stderr, 'offline_fixture': True})
                if result.returncode != 0:
                    raise RuntimeError(f'Native agent qualification failed; inspect {root / f"process-{number}.json"}')
                if not witness.is_file():
                    raise RuntimeError('Native shutdown witness missing')
                observations = [json.loads(line) for line in witness.read_text().splitlines()]
                providers = [p for event in observations for p in event['providers']]
                if not providers or any(p['name'] != 'atmem' or p['pending_writes'] != 0 or p['write_errors'] != 0 for p in providers):
                    raise RuntimeError('Native AtMem provider did not drain cleanly')
                exported = export_interaction(root / f'calls-{number}', home / 'api-witness.jsonl')
                save_new(root / f'export-{number}.json', exported)
                if args.apps:
                    catalog = json.dumps(exported['settings'].get('tools', []))
                    if 'mcp__dolphinbench_apps__list_inbox' not in catalog:
                        raise RuntimeError('Actual simulated app tools are missing from the model request')
                    app_calls = Path(apps['env']['DOLPHINBENCH_LOG_PATH'])
                    if not app_calls.exists() or 'list_inbox' not in app_calls.read_text():
                        raise RuntimeError('Sandboxed native agent did not execute the read-only simulated app call')
                if number == 0:
                    checkpoint = host.freeze()
                    save_new(root / 'checkpoint.json', checkpoint)
                    if checkpoint['canonical']['record_count'] == 0:
                        raise RuntimeError('Ordinary active product capture stored no canonical memory')
                else:
                    host.verify_checkpoint(checkpoint)
                    requests = list((root / f'calls-{number}').rglob('request.json'))
                    if not any('Neovim' in path.read_text() for path in requests):
                        raise RuntimeError('New-session request did not contain recalled memory')
            finally:
                gateway.stop()
        save_new(root / 'result.json', {'passed': True, 'paid_provider_calls': 0,
            'fixture_only': True, 'native_provider': 'atmem', 'new_process_recall': True,
            'frozen_memory_unchanged': True, 'upstream_app_tools': args.apps})
        print(json.dumps({'passed': True, 'fixture_only': True, 'evidence': str(root)}), flush=True)
    finally:
        host.stop()
        fixture.shutdown()
        fixture.server_close()
        thread.join(5)


if __name__ == '__main__':
    main()
