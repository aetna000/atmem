"""Linux benchmark-only descendant containment; no PID-reuse group signaling."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

ROOT=Path('/sys/fs/cgroup/atmem-code-confirmation-v3-20261018')
RUN='external-windows-confirmation-v3-process-scope-v1-20261018'
CHILD_BOOTSTRAP=r'''
import os,sys,json
from pathlib import Path
job=json.load(sys.stdin)
group=Path(job['process_scope'])
if (group.parent!=Path('/sys/fs/cgroup/atmem-code-confirmation-v3-20261018')
 or group.is_symlink() or not group.is_dir()):raise ValueError('exact benchmark process scope required')
(group/'cgroup.procs').write_text(str(os.getpid()))
os.setgroups([]);os.setgid(1000);os.setuid(1000)
exec(job['program'])
'''


def group_path(leaf):
    if type(leaf) is not str or re.fullmatch(r'(control-v1|block-(?:[0-9]|[12][0-9]|3[0-7])-(?:native|tools))',leaf) is None:
        raise ValueError('one exact benchmark case process scope required')
    return ROOT/leaf


def create_group(leaf):
    if os.geteuid()!=0 or not Path('/sys/fs/cgroup/cgroup.controllers').is_file():
        raise RuntimeError('authorized WSL root and unified process groups required')
    if not ROOT.exists():ROOT.mkdir(mode=0o755,exist_ok=False)
    metadata=ROOT.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid!=0 or stat.S_IMODE(metadata.st_mode)&0o022:
        raise ValueError('root-owned benchmark process-scope parent required')
    group=group_path(leaf);group.mkdir(mode=0o755,exist_ok=False)
    if not (group/'cgroup.kill').is_file():raise RuntimeError('kernel descendant termination unavailable')
    return group


def populated(group):
    if group.parent!=ROOT or group!=group_path(group.name) or group.is_symlink():
        raise ValueError('exact created case group required')
    events=dict(line.split() for line in (group/'cgroup.events').read_text().splitlines())
    if events.get('populated') not in {'0','1'}:raise ValueError('kernel process-scope state unavailable')
    return events['populated']=='1'


def quiesce(group):
    before=populated(group)
    # The kernel targets only members of this still-existing root-owned case
    # group, never a reaped PID/process-group number that might be reused.
    (group/'cgroup.kill').write_text('1')
    start=time.monotonic()
    while populated(group) and time.monotonic()-start<5:
        time.sleep(.02)
    if populated(group):raise RuntimeError('case descendants remain live; capture prohibited')
    return {'scope':str(group),'populated_before_termination':before,'populated_after_termination':False}


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('process-scope control already attempted')
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    source=r'''import os,json,subprocess
from pathlib import Path
assert os.geteuid()==1000
try:Path('/sys/fs/cgroup/cgroup.procs').write_text(str(os.getpid()))
except PermissionError:pass
else:raise RuntimeError('ordinary benchmark actor escaped its process scope')
child=subprocess.Popen(['/usr/bin/python3','-I','-c',"import os,time;os.chdir('/');time.sleep(50)"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print(json.dumps({'uid':os.geteuid(),'child_pid':child.pid,'escape_refused':True,'model_calls':0}),flush=True)
'''
    save('external.v3_process_scope_planned',{'driver_source':job['driver_source'],'child_bootstrap':CHILD_BOOTSTRAP,
        'actor_source':source,'model_calls':0,'no_cpu_memory_or_model_budget_change':True})
    group=create_group('control-v1')
    process=subprocess.run(['/usr/bin/python3','-I','-c',CHILD_BOOTSTRAP],input=json.dumps({'process_scope':str(group),'program':source}).encode(),capture_output=True,timeout=15,
                           env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    import base64
    result={'exit_code':process.returncode,'stdout_base64':base64.b64encode(process.stdout).decode(),
            'stderr_base64':base64.b64encode(process.stderr).decode(),'descendant_present':populated(group),'model_calls':0}
    if process.returncode==0:result['actor']=json.loads(process.stdout)
    result['termination']=quiesce(group)
    result['qualified']=bool(process.returncode==0 and result['descendant_present']
        and result.get('actor',{}).get('escape_refused') is True and result['termination']['populated_after_termination'] is False)
    save('external.v3_process_scope_completed',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
