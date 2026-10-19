"""Post-run persistent-MCP latency controls; no model runs or profile changes.

Measure startup/first architecture request and two subsequent identical queries
on the actual indexed stores. Run only after all scored Docker work is idle.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
from benchmarks.code_replay.swebench_pilot import remote, vault, validate_product_runtime


PROBE = '''import os,json,time,subprocess,select,signal,hashlib
from pathlib import Path
if subprocess.check_output(['docker','ps','-q']).strip():raise ValueError('scored executor must be idle')
case=job['payload'];graph=case['graph'];server=graph['server']
env=graph.get('environment') or {'PATH':str(Path(server['command']).parent)+':/usr/bin:/bin',
 'HOME':graph['home'],'ATMEM_HOME':graph['home'],'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
tick=time.monotonic()
p=subprocess.Popen([server['command'],*[a for a in server['args'] if a!='--experience']],env=env,
 stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1,start_new_session=True)
def rpc(request):
 p.stdin.write(json.dumps(request)+'\\n');p.stdin.flush()
 if not select.select([p.stdout],[],[],120)[0]:raise TimeoutError('bounded persistent MCP response timed out')
 answer=json.loads(p.stdout.readline())
 if answer.get('id')!=request['id'] or 'error' in answer:raise ValueError('actual MCP control failed')
 return answer
try:
 initial=rpc({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26',
  'capabilities':{},'clientInfo':{'name':'post-run-warm-control','version':'1'}}})
 p.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\\n');p.stdin.flush()
 listed=rpc({'jsonrpc':'2.0','id':2,'method':'tools/list'})
 startup=time.monotonic()-tick;rows=[]
 for index in range(3):
  request={'jsonrpc':'2.0','id':index+3,'method':'tools/call','params':{'name':'code_search',
   'arguments':{'operation':'architecture','arguments':{'max_nodes':3}}}}
  begin=time.monotonic();answer=rpc(request);elapsed=time.monotonic()-begin
  if answer['result'].get('isError'):raise ValueError('provider returned a tool error')
  text=answer['result']['content'][0]['text'];parsed=json.loads(text)
  if case['arm'].startswith('atmem_') and (not isinstance(parsed,dict) or parsed.get('status')!='current'):
   raise ValueError('AtMem source is no longer current')
  rows.append({'query_number':index+1,'request':request,'response':answer,'seconds':elapsed,
   'result_sha256':hashlib.sha256(json.dumps(answer['result'],sort_keys=True).encode()).hexdigest()})
 print(json.dumps({'arm':case['arm'],'source_tree':case['stage']['source_tree'],'startup_and_listing_seconds':startup,
  'startup_plus_first_query_seconds':startup+rows[0]['seconds'],'queries':rows,
  'result_stable_across_queries':len({row['result_sha256'] for row in rows})==1}))
finally:
 if p.poll() is None:
  os.killpg(p.pid,signal.SIGTERM)
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=10)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--after', type=Path, action='append', required=True,
                        help='all scored confirmation campaigns must already be complete')
    parser.add_argument('--candidate-runtime', type=Path,
                        help='separate unscored reader; compare exact architecture responses to frozen AtMem')
    args = parser.parse_args()
    if any(json.loads((root / 'results.json').read_text())['status'] != 'completed' for root in args.after):
        raise ValueError('finish scored confirmation before warm controls')
    if json.loads((args.source / 'results.json').read_text())['status'] != 'completed':
        raise ValueError('completed source campaign required')
    original_manifest = json.loads((args.source / 'manifest.json').read_text())
    candidate = validate_product_runtime(json.loads(args.candidate_runtime.read_text())) if args.candidate_runtime else None
    os.environ['ATMEM_HOME'] = str(args.source / 'home')
    original, old_principal = vault(args.source)
    cases = []
    for item in original_manifest['selected']:
        events = [event['envelope'] for event in original.inspect(old_principal, item['instance_id'])]
        configs = {event['payload']['arm']: event['payload'] for event in events if event['event_type'] == 'trial.configured'}
        if all(arm in configs for arm in ('atmem_structure', 'cognee_structure')):
            pair = [configs[arm] for arm in ('atmem_structure', 'cognee_structure')]
            if pair[0]['stage']['source_tree'] != pair[1]['stage']['source_tree']:
                raise ValueError('provider source trees differ')
            if candidate:
                optimized = deepcopy(pair[0])
                optimized['arm'] = 'atmem_metadata'
                optimized['graph']['server']['command'] = candidate['python']
                pair = [pair[0], optimized, pair[1]]
            cases.append((item, pair if len(cases) % 2 == 0 else list(reversed(pair))))
    if not cases:
        raise ValueError('at least one matched indexed provider pair required')
    args.root.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.environ['ATMEM_HOME'] = str(args.root / 'home')
    target, principal = vault(args.root)
    manifest = {'format': 'atmem-post-run-warm-query-controls-v1', 'selected': [item for item, _ in cases],
        'source_campaign': args.source.name, 'product_runtime': original_manifest['product_runtime'],
        'after_completed_campaigns': list(map(str, args.after)),
        'cognee_runtime': original_manifest['cognee_runtime'], 'models_run': 0,
        'unscored_candidate_runtime': candidate,
        'definition': 'Fresh provider process with OS caches untouched; then two identical queries in the same process. '
            'Local WSL stdio timing, excluding SSH, indexing and model inference. Post-run diagnostic, not new coding efficacy.'}
    (args.root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    target.capture(run_id='pilot', kind='diagnostic.warm_queries_planned', principal=principal,
                   payload={'manifest': manifest, 'source': Path(__file__).read_text()})
    rows = []
    for item, pair in cases:
        case_rows = []
        for config in pair:
            target.capture(run_id=item['instance_id'], kind='diagnostic.provider_configuration', principal=principal, payload=config)
            observed = remote(PROBE, config, timeout=700)
            if observed.returncode:
                (args.root / 'results.json').write_text(json.dumps({'status': 'stopped', 'rows': rows,
                    'error': 'persistent MCP control failed; inspect retained scoped provider configuration'}, indent=2))
                raise RuntimeError('warm control failed without retries: ' + observed.stderr[-1200:])
            raw = json.loads(observed.stdout)
            target.capture(run_id=item['instance_id'], kind='diagnostic.warm_queries_observed', principal=principal, payload=raw)
            row = {'instance_id': item['instance_id'], **{k: raw[k] for k in ('arm', 'source_tree',
                'startup_and_listing_seconds', 'startup_plus_first_query_seconds', 'result_stable_across_queries')},
                'query_seconds': [query['seconds'] for query in raw['queries']],
                'result_sha256': [query['result_sha256'] for query in raw['queries']]}
            rows.append(row)
            case_rows.append(row)
            (args.root / 'results.json').write_text(json.dumps({'status': 'running', 'rows': rows}, indent=2))
            print(json.dumps(row), flush=True)
        if candidate:
            old = next(row for row in case_rows if row['arm'] == 'atmem_structure')
            new = next(row for row in case_rows if row['arm'] == 'atmem_metadata')
            equivalent = len(set(old['result_sha256'] + new['result_sha256'])) == 1
            target.capture(run_id=item['instance_id'], kind='diagnostic.reader_equivalence', principal=principal,
                payload={'exact_result_equal': equivalent, 'old': old, 'new': new, 'models_run': 0})
            if not equivalent:
                (args.root / 'results.json').write_text(json.dumps({'status': 'stopped', 'rows': rows,
                    'error': 'new reader response differs; no equivalent-performance claim'}, indent=2))
                raise ValueError('reader equivalence failed; retain results without retries')
    (args.root / 'results.json').write_text(json.dumps({'status': 'completed', 'rows': rows}, indent=2))


if __name__ == '__main__':
    main()
