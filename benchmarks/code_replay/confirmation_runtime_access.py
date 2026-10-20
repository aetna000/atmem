"""Narrow benchmark install traversal repair; no candidate or source changes."""
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

RUN = 'external-windows-confirmation-runtime-access-v1-20261018'
RUNTIME = Path('/home/jt/atmem-benchmark-runtime-20261018/product-build-arw_zz8r')
PYTHON = str(RUNTIME / 'venv/bin/python')


def validate_directory(metadata):
    if (not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700
            or metadata.st_uid != 0 or metadata.st_gid != 0):
        raise ValueError('exact root-owned private benchmark install required')


def fingerprint(root):
    """Bind package source/metadata and executable bytes, excluding mutable caches."""
    package = root / 'venv/lib/python3.12/site-packages'
    paths = sorted(p for p in package.rglob('*') if p.is_file() and
                   '__pycache__' not in p.parts and
                   (p.suffix == '.py' or p.name in {'METADATA', 'RECORD', 'WHEEL'}))
    if not paths or not any(p.name == 'projections.py' for p in paths):
        raise ValueError('installed product source missing')
    rows = [{'path':p.relative_to(root).as_posix(), 'bytes':p.stat().st_size,
             'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    rows.append({'path':'resolved-python', 'sha256':hashlib.sha256(
        (root/'venv/bin/python').resolve(strict=True).read_bytes()).hexdigest()})
    return {'files':len(rows), 'sha256':hashlib.sha256(
        json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()}


def main():
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.confirmation_bridge_readiness import RUN as READINESS
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):
        raise ValueError('runtime repair already recorded; inspect rather than repeat')
    ends=[e['envelope']['payload'] for e in vault.inspect(principal,READINESS)
          if e['envelope']['event_type']=='external.confirmation_bridge_readiness_completed']
    if len(ends)!=1 or len(ends[0]['results'])!=28 or ends[0]['model_calls']!=0:
        raise ValueError('completed no-model readiness required')
    failures=[r for r in ends[0]['results'] if not r['qualified']]
    if len(failures)!=14 or any(r['arm']!='tools' for r in failures):
        raise ValueError('only the fourteen original tools startup failures may be repaired')
    for row in failures:
        results=[e['envelope']['payload'] for e in vault.inspect(principal,row['task_run'])
                 if e['envelope']['event_type']=='external.bridge_readiness_case_result']
        if len(results)!=1 or results[0]['transport_exit']!=1:
            raise ValueError('exact original startup failure required')
        stderr=base64.b64decode(results[0]['stderr_base64'],validate=True).decode()
        if "PermissionError: [Errno 13] Permission denied: '"+PYTHON+"'" not in stderr:
            raise ValueError('failure was not the frozen interpreter startup permission')
    fd=os.open(RUNTIME,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd); validate_directory(before)
        if RUNTIME.lstat().st_ino!=before.st_ino:
            raise ValueError('runtime directory identity changed')
        frozen=fingerprint(RUNTIME)
        probe=[PYTHON,'-I','-c',"import atmem,json;print(json.dumps({'imported':True,'path':atmem.__file__}))"]
        options={'capture_output':True,'timeout':30,'user':1000,'group':1000,
                 'extra_groups':[],'env':{'PATH':'/usr/bin:/bin','LANG':'C.UTF-8',
                                         'PYTHONDONTWRITEBYTECODE':'1'}}
        try:
            subprocess.run(probe,**options)
        except PermissionError:
            pass
        else:
            raise ValueError('expected pre-repair traversal denial absent')
        def save(kind,payload):
            return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
        save('external.runtime_access_repair_planned',{
            'source':Path(__file__).read_text() if '__file__' in globals() else job['repair_source'],
            'path':str(RUNTIME),'device':before.st_dev,'inode':before.st_ino,
            'before':{'uid':before.st_uid,'gid':before.st_gid,'mode':'0700'},
            'after':{'uid':0,'gid':1000,'mode':'0710'},'frozen_bytes':frozen,
            'readiness_run':READINESS,'model_calls':0,
            'recursive_change':False,'group_read_or_write':False})
        os.fchown(fd,-1,1000)
        os.fchmod(fd,0o710)
        after=os.fstat(fd)
        if (RUNTIME.lstat().st_ino!=before.st_ino or after.st_uid!=0
                or after.st_gid!=1000 or stat.S_IMODE(after.st_mode)!=0o710
                or fingerprint(RUNTIME)!=frozen):
            raise ValueError('runtime access repair differs from the planned metadata-only change')
        result=subprocess.run(probe,**options)
        payload={'exit_code':result.returncode,
                 'stdout_base64':base64.b64encode(result.stdout).decode(),
                 'stderr_base64':base64.b64encode(result.stderr).decode(),
                 'package_and_interpreter_bytes_unchanged':True,
                 'model_calls':0,'qualified':result.returncode==0}
        save('external.runtime_access_repair_completed',payload)
        print(json.dumps(payload),flush=True)
    finally:
        os.close(fd)


if __name__=='__main__':main()
