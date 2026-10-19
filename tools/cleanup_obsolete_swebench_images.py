"""Remove only identified old AtMem benchmark image caches, never results.

Requires a completed current campaign and an idle Docker executor. Public image
digests and deletion outcomes remain in a receipt for exact re-pulling.
"""
import argparse
import json
from pathlib import Path
from benchmarks.code_replay.external_qualify_worker import TASK_BINDINGS, CONFIRMATION_BINDINGS
from benchmarks.code_replay.swebench_pilot import remote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--completed-campaign', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if json.loads((args.completed_campaign / 'results.json').read_text())['status'] != 'completed':
        raise ValueError('wait for current benchmark to finish before cache cleanup')
    protected_root = args.completed_campaign.parent / 'swebench-lite-official-runtime-20261019'
    protected = {row['instance_id'] for row in json.loads((protected_root / 'manifest.json').read_text())['selected']}
    old = sorted((set(TASK_BINDINGS) | set(CONFIRMATION_BINDINGS)) - protected)
    program = '''import subprocess,json,shutil
from pathlib import Path
def run(argv):return subprocess.run(argv,capture_output=True,text=True,check=True)
if run(['docker','ps','-q']).stdout.strip():raise ValueError('benchmark executor is not idle')
repos={'swebench/sweb.eval.x86_64.'+identity.replace('__','_1776_'):identity for identity in job['payload']['old']}
ids=sorted(set(run(['docker','images','-q','--no-trunc']).stdout.split()))
images=json.loads(run(['docker','image','inspect',*ids]).stdout) if ids else []
targets=[]
for image in images:
 refs=(image.get('RepoDigests') or [])+(image.get('RepoTags') or [])
 matches=[repo for repo in repos if any(ref.startswith(repo+'@') for ref in refs)]
 if len(matches)!=1:continue
 repo=matches[0]
 if any(not(ref.startswith(repo+'@') or ref.startswith(repo+':')) for ref in refs):continue
 if run(['docker','ps','-aq','--filter','ancestor='+image['Id']]).stdout.strip():continue
 targets.append({'task':repos[repo],'Id':image['Id'],'RepoDigests':image.get('RepoDigests'),
  'RepoTags':image.get('RepoTags'),'Size':image['Size']})
receipt={'old_atmem_task_bindings':job['payload']['old'],'targets':targets,'apply':job['payload']['apply'],
 'before_windows_free_bytes':shutil.disk_usage('/mnt/c').free,'results_or_checkpoints_deleted':False}
if job['payload']['apply']:
 path=Path('/home/user/atmem-swebench-20261019/cleanup-obsolete-task-caches-confirmation-20261019.json')
 with path.open('x') as stream:json.dump(receipt,stream,indent=2)
 for target in targets:
  if run(['docker','ps','-q']).stdout.strip():raise ValueError('executor became active; stopping cleanup')
  result=subprocess.run(['docker','image','rm',target['Id']],capture_output=True,text=True)
  target.update(deletion_exit=result.returncode,deletion_stdout=result.stdout,deletion_stderr=result.stderr)
  path.write_text(json.dumps(receipt,indent=2))
  if result.returncode:raise RuntimeError('exact old image removal failed; receipt retained')
 subprocess.run(['fstrim','/'],capture_output=True,check=True)
 receipt['after_windows_free_bytes']=shutil.disk_usage('/mnt/c').free
 path.write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
'''
    result = remote(program, {'old': old, 'apply': args.apply}, timeout=240)
    print(result.stdout, flush=True)
    if result.returncode:
        raise RuntimeError('scoped cleanup failed: ' + result.stderr[-1500:])


if __name__ == '__main__':
    main()
