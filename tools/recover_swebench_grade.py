"""Recover a captured model's unavailable grade after a stdin transport stop.

No model rerun. Only exact newline/EOF framing changes are allowed in the frozen
controller; every evaluator, prompt, source, budget and candidate stays fixed.
"""
import argparse
import ast
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
from types import SimpleNamespace

from benchmarks.code_replay.swebench_pilot import vault, worker, remote, usage, patch_allowed, validate_frozen_manifest

OLD_LOADER = 'import json,sys;job=json.load(sys.stdin);exec(job["program"])'
NEW_LOADER = 'import json,sys,os;job=json.loads(sys.stdin.readline());fd=os.open(os.devnull,os.O_RDONLY);os.dup2(fd,0);os.close(fd);exec(job["program"])'


def framing_only(original, current):
    before = "input=json.dumps({'program': program, 'payload': payload}),"
    after = "input=json.dumps({'program': program, 'payload': payload}) + '\\n',"
    if original.count(OLD_LOADER) != 2 or original.count(before) != 2:
        raise ValueError('expected original two stdin transports required')
    expected = original.replace(OLD_LOADER, NEW_LOADER).replace(before, after)
    if current != expected:
        raise ValueError('controller changed beyond exact stdin framing/EOF repair')


def terminal_from_frozen_source(source, values):
    tree = ast.parse(source)
    expressions = [node for node in ast.walk(tree) if isinstance(node, ast.Dict)
        and {'solver_s', 'index_s', 'task_pass', 'automatic_context_bytes', 'exit_code'} <=
        {key.value for key in node.keys if isinstance(key, ast.Constant)}]
    if len(expressions) != 1:
        raise ValueError('one frozen terminal expression required')
    # This expression is the retained trusted controller, never model text.
    return eval(compile(ast.Expression(expressions[0]), '<frozen-terminal>', 'eval'),
                {'__builtins__': {'bool': bool, 'len': len}}, values)


CLEANUP = '''import os,pathlib,json,signal
rows=[]
for directory in pathlib.Path('/proc').iterdir():
 if not directory.name.isdigit():continue
 try:
  cmd=(directory/'cmdline').read_bytes();call=(directory/'syscall').read_text().split()
  if (b'/home/user/atmem-swebench-20261019/' not in cmd or b'job=json.load(sys.stdin)' not in cmd
      or len(call)<2 or call[0]!='0' or int(call[1],16)!=0):continue
  pid=int(directory.name)
  rows.append({'pid':pid,'reason':'own obsolete benchmark EOF loader blocked reading fd0'})
  os.kill(pid,signal.SIGTERM)
 except (OSError,ValueError):pass
print(json.dumps({'terminated_readers':rows,'data_files_deleted':False}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    stopped = json.loads((root / 'results.json').read_text())
    if stopped['status'] != 'stopped' or 'TimeoutExpired' not in stopped.get('error', ''):
        raise ValueError('retained transport-timeout stop required')
    os.environ['ATMEM_HOME'] = str(root / 'home')
    service, principal = vault(root)
    manifest = json.loads((root / 'manifest.json').read_text())
    pilot = service.inspect(principal, 'pilot')
    validate_frozen_manifest(pilot, manifest)
    locked = [e['envelope']['payload'] for e in pilot if e['envelope']['event_type'] == 'execution.locked']
    if len(locked) != 1:
        raise ValueError('single original execution lock required')
    frozen = locked[0]['source_text']
    code = Path('benchmarks/code_replay')
    framing_only(frozen['swebench_pilot.py'], (code / 'swebench_pilot.py').read_text())
    for name in ('swebench_worker.py', 'swebench_tools.py', 'swebench_context.py', 'swebench_cognee.py'):
        if frozen[name] != (code / name).read_text():
            raise ValueError('nontransport execution/evaluator source changed')
    pending, original_rows = [], []
    for item in manifest['selected']:
        identity = item['instance_id']
        events = [e['envelope'] for e in service.inspect(principal, identity)]
        for arm in item['arm_order']:
            terminal = [e['payload'] for e in events if e['event_type'] == 'trial.terminal' and e['payload']['arm'] == arm]
            original_rows.extend(terminal)
            starts = [i for i, e in enumerate(events) if e['event_type'] == 'trial.started' and e['payload']['arm'] == arm]
            captures = [i for i, e in enumerate(events) if e['event_type'] == 'trial.captured' and e['payload']['arm'] == arm]
            grades = [e for e in events if e['event_type'] == 'trial.graded' and e['payload']['arm'] == arm]
            if starts and not terminal:
                if len(starts) != 1 or len(captures) != 1 or grades:
                    raise ValueError('recovery requires one captured model and no prior grade')
                pending.append((identity, arm, events, starts[0], captures[0]))
    if original_rows != stopped['rows'] or len(pending) != 1:
        raise ValueError('exactly one missing grade and unchanged terminal rows required')
    identity, arm, events, first, last = pending[0]
    captured, started = events[last]['payload'], events[first]['payload']
    measured = usage([json.loads(line) for line in base64.b64decode(captured['stdout_base64']).splitlines() if line.startswith(b'{')])
    if measured != captured['usage'] or not measured.get('complete'):
        raise ValueError('original complete usage must reconstruct exactly')
    configured = next(e['payload'] for e in events if e['event_type'] == 'trial.configured' and e['payload']['arm'] == arm)
    stage = next(e['payload']['stage'] for e in events if e['event_type'] == 'trial.source_staged' and e['payload']['arm'] == arm)
    task = next(e['payload'] for e in events if e['event_type'] == 'upstream.task')
    environment = [e['payload'] for e in events if e['event_type'] == 'environment.terminal'][-1]
    calls = [e['payload'] for e in events[first + 1:last] if e['event_type'] == 'tool.exchange'
        and e['payload']['arm'] == arm and e['payload']['request']['method'] == 'tools/call']
    plan = {'instance_id': identity, 'arm': arm, 'original_capture_sha256': sha256(json.dumps(captured, sort_keys=True).encode()).hexdigest(),
        'original_stop': stopped, 'controller_delta': 'newline-framed job and explicit inherited stdin EOF only',
        'frozen_worker_sha256': sha256(frozen['swebench_worker.py'].encode()).hexdigest(), 'model_rerun': False,
        'source': Path(__file__).read_text()}
    service.capture(run_id='pilot', kind='infrastructure.grade_recovery_planned', principal=principal, payload=plan)
    idle = remote("import subprocess;assert not subprocess.check_output(['docker','ps','-q']).strip();print('idle')", {}, timeout=30)
    if idle.returncode:
        raise RuntimeError('wait for idle evaluator before recovery')
    cleaned = remote(CLEANUP, {}, timeout=30)
    if cleaned.returncode:
        raise RuntimeError('stale reader cleanup failed')
    service.capture(run_id='pilot', kind='infrastructure.stdin_readers_cleaned', principal=principal, payload=json.loads(cleaned.stdout))
    graded = worker('grade', {'task': task, 'image_id': environment['image']['Id'], 'patch': captured['patch']['patch']})
    allowed = patch_allowed(captured['patch'], stage)
    service.capture(run_id=identity, kind='trial.graded', principal=principal,
        payload={'arm': arm, 'result': graded, 'patch_policy': allowed, 'recovered_after_transport_stop': True})
    source_pack = None
    prepared = [e['payload'] for e in events[:first] if e['event_type'] == 'trial.context_prepared' and e['payload']['arm'] == arm]
    if prepared:
        from benchmarks.code_replay.swebench_context import validated_context
        source_pack = validated_context(prepared[-1]['response'])
    values = {'identity': identity, 'arm': arm, 'elapsed': captured['solver_s'], 'setup_s': started['setup_s'],
        'graph': configured['graph'], 'measured': measured, 'context_delivery': manifest['context_delivery'],
        'source_pack': source_pack, 'tool_calls': calls,
        'graph_calls': sum(e['request']['params']['name'] != 'workspace_command' for e in calls),
        'graded': graded, 'allowed': allowed, 'stop_reason': captured['stop_reason'],
        'process': SimpleNamespace(returncode=captured['exit_code']),
        'valid_budget': measured.get('complete') and len(calls) <= manifest['tools_per_attempt']
            and measured['total_input_tokens'] + measured['output_tokens'] <= manifest['maximum_total_tokens_per_attempt']}
    row = terminal_from_frozen_source(frozen['swebench_pilot.py'], values)
    service.capture(run_id=identity, kind='trial.terminal', principal=principal, payload=row)
    service.capture(run_id='pilot', kind='infrastructure.grade_recovery_completed', principal=principal,
        payload={'instance_id': identity, 'arm': arm, 'row': row, 'model_rerun': False})
    stopped['rows'].append(row)
    stopped['grade_recovery'] = {'instance_id': identity, 'arm': arm, 'model_rerun': False}
    (root / 'results.json').write_text(json.dumps(stopped, indent=2))
    print(json.dumps({'recovered_captured_model_grade': True, 'model_rerun': False,
        'instance_id': identity, 'arm': arm, 'task_pass': row['task_pass']}), flush=True)


if __name__ == '__main__':
    main()
