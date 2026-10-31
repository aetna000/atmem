"""Real synthetic MCP bridge/state/log/crash qualification; zero model calls."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .app_bridge import bridge, stage_client, short_socket
from .readiness import qualification_sources, CHECKS, pin, read, receipt, save, sha
from .safe_runner import InteractionJournal, protected_runner_class
from .sandbox import policy, run

CLIENT = r'''
import asyncio,json,os,sys
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    tasks=json.loads(sys.argv[2]); results=[]
    async with stdio_client(StdioServerParameters(command=sys.executable,args=['-I',sys.argv[1]])) as streams:
      async with ClientSession(*streams) as session:
        await session.initialize()
        listing=await session.list_tools()
        schemas=[t.model_dump(mode='json') for t in listing.tools]
        for task in tasks:
          response=await session.call_tool(task['name'],task['arguments'])
          if response.isError: raise RuntimeError(str(response))
          parts=[c.text for c in response.content if c.type=='text']
          parsed=json.loads(parts[0])
          for _ in range(3):
            if isinstance(parsed,str): parsed=json.loads(parsed)
          results.append({'name':task['name'],'arguments':task['arguments'],'result':parsed})
        if sys.argv[3]=='crash': os._exit(73)
        print(json.dumps({'schemas':schemas,'results':results}),flush=True)
asyncio.run(main())
'''


def qualify(upstream, output, *, python=sys.executable):
    upstream, output = Path(upstream).resolve(), Path(output).resolve()
    # Use an authenticated public release, not a modified local mock server.
    manifest = read(upstream / 'manifest.json')
    for relative, expected in manifest['files'].items():
        if relative.startswith(('mock_mcp/', 'harness/', 'reference/execution/')):
            if sha(upstream / relative) != expected:
                raise ValueError('Changed upstream qualification source: ' + relative)
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(upstream))
    from harness.runner import Runner
    positive = [
        {'name': 'create_doc', 'arguments': {'title': 'Synthetic qualification', 'body': 'Synthetic durable text'}},
        {'name': 'send_email', 'arguments': {'to': 'synthetic@example.test', 'subject': 'Qualification', 'body': 'Synthetic email'}},
        {'name': 'send_slack_dm', 'arguments': {'user': 'probe', 'message': 'Synthetic Slack message'}},
    ]
    outcomes = []
    for name, tasks, crash in [('apps', positive, False),
                                ('crash', [positive[0]], True)]:
        case = output / name
        case.mkdir()
        state, log = case / 'state.json', case / 'calls.jsonl'
        save(state, {'docs': [], 'sent_emails': [], 'slack_log': []})
        save(case / 'manifest.json', {'persona_id': 'synthetic', 'tools': [t['name'] for t in positive]})
        save(case / 'directory.json', {'users': [{'key': 'probe', 'name': 'Synthetic Probe'}], 'channels': []})
        save(case / 'tools.json', {'active_tools': [t['name'] for t in tasks]})
        log.touch()
        apps = {'command': str(python), 'args': [str(upstream / 'mock_mcp/repair_server.py')],
                'env': {'DOLPHINBENCH_PERSONA': 'synthetic',
                        'DOLPHINBENCH_MOCK_MANIFEST': str(case / 'manifest.json'),
                        'DOLPHINBENCH_WORKSPACE_DIRECTORY': str(case / 'directory.json'),
                        'DOLPHINBENCH_STATE_PATH': str(state), 'DOLPHINBENCH_LOG_PATH': str(log),
                        'DOLPHINBENCH_TOOL_CONFIG_PATH': str(case / 'tools.json')}}
        journal = InteractionJournal(case / 'journal', apps)
        with short_socket() as sock:
            with bridge(apps, sock):
                client = case / 'app_client.py'
                stage_client(upstream, client, sock)
                # Agent-side client runs under the same policy as campaign apps.
                probe = subprocess.run([str(python), '-I', '-c',
                    'import sys,json; print(json.dumps([sys.prefix,sys.base_prefix]))'],
                    check=True, capture_output=True, text=True)
                boundary = policy(readable=[*map(Path, json.loads(probe.stdout)), Path(python).resolve().parent.parent],
                                  writable=[case], ports=[], sockets=[sock])
                process = run([str(python), '-I', '-c', CLIENT, str(client), json.dumps(tasks),
                               'crash' if crash else 'normal'], profile=boundary,
                              environment={'PATH': '/usr/bin:/bin', 'HOME': str(case), 'TMPDIR': str(case)},
                              cwd=case, timeout=90)
        save(case / 'process.json', {'returncode': process.returncode,
                                     'stdout': process.stdout, 'stderr': process.stderr})
        if process.returncode != (73 if crash else 0):
            raise ValueError('Synthetic client failed; inspect ' + str(case / 'process.json'))
        journal.snapshot(completed=not crash)
        calls = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
        persisted = read(state)
        if len(calls) != len(tasks) or not persisted.get('docs'):
            raise ValueError('App write/log/state mismatch')
        if not crash:
            result = json.loads(process.stdout)
            for task, observed, recorded in zip(tasks, result['results'], calls):
                if observed['result'].get('ok') is not True or recorded['tool'] != task['name']:
                    raise ValueError('Unsuccessful synthetic mutation')
                if observed['result'] != recorded['result']:
                    raise ValueError('Independent log differs from client result')
            if persisted['docs'][0]['body'] != positive[0]['arguments']['body']:
                raise ValueError('Persisted document differs')
            # Every returned send entry must actually occur in persisted state.
            state_text = json.dumps(persisted, sort_keys=True)
            for task, observed in zip(tasks[1:], result['results'][1:]):
                entry = observed['result']
                if not any(task['arguments'][k] and task['arguments'][k] in state_text
                           for k in ('message', 'body') if k in task['arguments']):
                    raise ValueError('Sent artifact missing from persisted state')
            save(case / 'result.json', result)
        else:
            before = {str(p): sha(p) for p in (state, log)}
            try:
                InteractionJournal(case / 'journal', apps)
            except FileExistsError:
                pass
            else:
                raise ValueError('Uncertain action was allowed to repeat')
            protected = protected_runner_class(Runner).__new__(protected_runner_class(Runner))
            protected.directory = output
            # Create the workspace through the original implementation itself.
            protected.release_root = upstream
            protected.release = {}
            protected.adapter = None
            original_apps = Runner._apps(protected, 'tests', 'synthetic', 'crash',
                                         {'mock_state': {'docs': []}, 'tools': ['create_doc']})
            workspace = Path(original_apps['env']['DOLPHINBENCH_LOG_PATH']).parent
            (workspace / 'calls.jsonl').write_bytes(log.read_bytes())
            protected_before = sha(workspace / 'calls.jsonl')
            try:
                protected._apps('tests', 'synthetic', 'crash', {})
            except ValueError:
                pass
            else:
                raise ValueError('Restart allowed destructive app setup')
            if before != {str(p): sha(p) for p in (state, log)} or sha(workspace / 'calls.jsonl') != protected_before:
                raise ValueError('Crash recovery changed original evidence')
        outcomes.append({'name': name, 'returncode': process.returncode,
                         'calls': len(calls), 'artifacts': [pin(state), pin(log), pin(case / 'process.json')]})
    report = {'schema': 'dolphin-synthetic-app-qualification-v1', 'synthetic_only': True,
              'upstream_manifest': pin(upstream / 'manifest.json'), 'app_python': pin(Path(python).resolve()),
              'source': qualification_sources(), 'model_calls': 0, 'same_macos_sandbox_and_upstream_bridge': True,
              'result_state_log_agree': True, 'uncertain_replay_refused': True,
              'evidence_preserved': True, 'outcomes': outcomes}
    save(output / 'qualification.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python', default=sys.executable)
    args = parser.parse_args()
    result = qualify(args.upstream, args.output, python=args.python)
    print(json.dumps({'passed': True, 'model_calls': result['model_calls'], 'synthetic_only': True}))


if __name__ == '__main__':
    main()
