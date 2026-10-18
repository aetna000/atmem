"""Read-only diagnosis of source-boundary failures; never retries tests or models."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.external_qualification import worker_command
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT, PREFLIGHT
from benchmarks.code_replay.windows_confirmation_reference import RUN as REFERENCE_RUN
from benchmarks.code_replay.windows_transport import command, worker_program

RUN = 'external-windows-confirmation-source-diagnostic-v1-20261018'
PROGRAM = r'''
import hashlib,json,os,stat,subprocess,sys
from pathlib import Path
job=json.load(sys.stdin);base=job['base_commit']
listing=subprocess.check_output(['git','-C','/testbed','ls-tree','-r','-z',base])
counts={};exceptions=[];total=0;files=0
for entry in listing.split(b'\0'):
 if not entry:continue
 header,name=entry.split(b'\t',1);mode,kind,blob=header.decode().split();name=name.decode()
 path=Path('/testbed')/name;info=os.lstat(path);files+=1
 if mode not in ('100644','100755') or not stat.S_ISREG(info.st_mode):
  reason='non_regular';details={'mode':mode,'file_type':stat.S_IFMT(info.st_mode)}
 else:
  total+=info.st_size;digest=hashlib.sha1();digest.update(b'blob '+str(info.st_size).encode()+b'\0')
  with path.open('rb') as stream:
   while True:
    chunk=stream.read(65536)
    if not chunk:break
    digest.update(chunk)
  reason='worktree_blob_differs' if digest.hexdigest()!=blob else 'large_file' if info.st_size>1000000 else None
  details={'bytes':info.st_size,'blob_matches':digest.hexdigest()==blob}
 if reason:
  counts[reason]=counts.get(reason,0)+1
  if len(exceptions)<500:exceptions.append({'path':name,'reason':reason,**details})
print(json.dumps({'instance_id':job['instance_id'],'tracked_files':files,'regular_bytes':total,
 'exceptions':exceptions,'exception_counts':counts,'exception_list_complete':sum(counts.values())==len(exceptions),
 'repo_code_executed':False,'tests_repeated':False,'network':False}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eligibility-v2', action='store_true', help='Diagnose the fixed new pool using length-framed transport, never rerun tests')
    args = parser.parse_args()
    preflight, reference_run, run_id = PREFLIGHT, REFERENCE_RUN, RUN
    if args.eligibility_v2:
        from benchmarks.code_replay.windows_eligibility_images import PREFLIGHT as NEW_PREFLIGHT
        preflight = NEW_PREFLIGHT
        reference_run = 'external-windows-confirmation-eligibility-reference-v2-20261018'
        run_id = 'external-windows-eligibility-source-diagnostic-v2-20261018'
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope)
    if vault.inspect(principal, run_id):
        raise ValueError('diagnostic already recorded; inspect its handle rather than restart')
    events = vault.inspect(principal, reference_run)
    planned = next(e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'external.confirmation_reference_planned')
    if not any(e['envelope']['event_type'] == 'external.confirmation_reference_completed' for e in events):
        raise ValueError('reference controls must be terminal before diagnosis')
    metadata = json.loads((preflight / 'metadata.json').read_bytes())
    tasks = {r['instance_id']: r['metadata'] for r in metadata['reports']}
    images = {}  # Exact immutable images from retained reference dispatches.
    for event in events:
        if event['envelope']['event_type'] == 'external.confirmation_reference_dispatch':
            row = event['envelope']['payload']; cmd = row['job']['command']
            images[row['instance_id']] = next(v for v in cmd if v.startswith('swebench/') and '@sha256:' in v)
    def save(kind, payload):
        return vault.capture(run_id=run_id, kind=kind, principal=principal, payload=payload)
    workers = 4 if args.eligibility_v2 else 2
    save('external.confirmation_source_diagnostic_planned', {'program': PROGRAM,
        'driver_source': Path(__file__).read_text(), 'identities': planned['runtime_eligible'],
        'models_run': 0, 'tests_repeated': 0, 'source_modified': False, 'max_workers': workers,
        'length_framed_transport': args.eligibility_v2})
    jobs = []
    for identity in planned['runtime_eligible']:
        name = 'atmem-reference-control-' + uuid4().hex
        cmd = worker_command(images[identity], name, PROGRAM)
        cmd.insert(3, '--read-only')
        job = {'program': worker_program(), 'name': name, 'command': cmd,
            'payload': {'instance_id': identity, 'base_commit': tasks[identity]['base_commit']}}
        save('external.confirmation_source_diagnostic_dispatch', {'instance_id': identity, 'job': job})
        jobs.append((identity, job))
    def execute(item):
        identity, job = item
        try:
            if args.eligibility_v2:
                from benchmarks.code_replay.windows_transport import framed_command, framed_input
                return identity, subprocess.run(framed_command(), input=framed_input(job), capture_output=True, timeout=205), None
            return identity, subprocess.run(command(), input=json.dumps(job).encode(), capture_output=True, timeout=205), None
        except subprocess.TimeoutExpired as exc:
            from types import SimpleNamespace
            return identity, SimpleNamespace(returncode=None, stdout=exc.stdout or b'', stderr=exc.stderr or b''), 'transport_timeout'
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(execute, job) for job in jobs]):
            identity, proc, failure = future.result()
            row = {'instance_id': identity, 'transport_exit': proc.returncode,
                'transport_failure': failure,
                'stdout_base64': base64.b64encode(proc.stdout).decode(), 'stderr_base64': base64.b64encode(proc.stderr).decode()}
            if proc.returncode == 0:
                row['controller'] = json.loads(proc.stdout)
            save('external.confirmation_source_diagnostic_result', row)
            print(json.dumps({'instance_id': identity, 'result': row.get('controller', {}).get('worker')}), flush=True)
    save('external.confirmation_source_diagnostic_completed', {'cases': len(jobs), 'tests_repeated': 0, 'models_run': 0})


if __name__ == '__main__':
    main()
