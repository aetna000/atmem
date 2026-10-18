"""Separate, exact-delta encoding/storage preview; never replace frozen installs."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess

RUN='external-windows-product-build-source-storage-v1-20261018'
PRIOR='external-windows-product-build-explicit-omissions-v2-20261018'
INSPECTION='external-windows-compatibility-build-inspection-v1-20261018'
CHANGED=('atmem/knowledge/source_text.py','atmem/knowledge/projections.py','atmem/knowledge/worker.py',
         'atmem/knowledge/code/packing.py','atmem/code/application.py','atmem/code/portable.py',
         'atmem/store/code_documents.py','atmem/store/sqlite.py','atmem/code/bundle_transport.py')
ADDED={'atmem/knowledge/source_text.py','atmem/store/code_documents.py','atmem/code/bundle_transport.py'}


def candidate_job(original,replacements,inspection):
    if set(replacements)!=set(CHANGED) or {r['path'] for r in inspection['rows']}!=set(CHANGED):
        raise ValueError('exact nine-file compatibility correction required')
    result=json.loads(json.dumps(original))
    rows={r['path']:r for r in inspection['rows']}
    for name,raw in replacements.items():
        if type(raw) is not bytes or sha256(raw).hexdigest()!=rows[name]['new_sha256']:
            raise ValueError('candidate differs from inspected compatibility source')
        if name in ADDED:
            if name in result['files'] or name in result['manifest'] or rows[name]['old_sha256'] is not None:
                raise ValueError('new module already exists in prior candidate')
        elif (name not in result['files'] or name not in result['manifest'] or
              sha256(base64.b64decode(result['files'][name],validate=True)).hexdigest()!=result['manifest'][name]
              or result['manifest'][name]!=rows[name]['old_sha256']):
            raise ValueError('prior candidate differs from inspected base')
        result['files'][name]=base64.b64encode(raw).decode()
        result['manifest'][name]=sha256(raw).hexdigest()
    before="root=Path(tempfile.mkdtemp(prefix='product-build-',dir=runtime));root.chmod(0o700)"
    if result['program'].count(before)!=1:
        raise ValueError('exact previously qualified builder required')
    result['program']=result['program'].replace(before,
        "root=Path(tempfile.mkdtemp(prefix='product-build-',dir=runtime));os.chown(root,0,1000);root.chmod(0o710)")
    return result


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.windows_transport import framed_command,framed_input
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('compatibility build already dispatched; inspect original handle')
    def events(run,kind):
        return [e['envelope']['payload'] for e in vault.inspect(principal,run) if e['envelope']['event_type']==kind]
    plans=events(PRIOR,'external.windows_omission_build_planned')
    inspected=events(INSPECTION,'external.compatibility_build_inspected')
    if len(plans)!=1 or len(inspected)!=1 or inspected[0]['program']!=plans[0]['job']['program']:
        raise ValueError('exact prior source/build inspection required')
    replacements={n:base64.b64decode(v,validate=True) for n,v in job['candidate_files'].items()}
    build=candidate_job(plans[0]['job'],replacements,inspected[0])
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.compatibility_build_planned',{'driver_source':job['driver_source'],'job':build,
        'prior_build':PRIOR,'inspection_run':INSPECTION,'changed_product_files':list(CHANGED),
        'prior_dependency_versions':plans[0]['prior_dependency_versions'],'model_calls':0,
        'frozen_candidate_replaced':False,'owner_install_changed':False})
    proc=subprocess.run(framed_command(),input=framed_input(build),capture_output=True,timeout=1100)
    save('external.compatibility_build_transport',{'exit_code':proc.returncode,
        'stdout_base64':base64.b64encode(proc.stdout).decode(),'stderr_base64':base64.b64encode(proc.stderr).decode()})
    if proc.returncode:raise RuntimeError('compatibility build transport failed; preserve original result')
    result=json.loads(proc.stdout)
    save('external.compatibility_build_result',result)
    if result['qualified_installed_source_identity'] is not True:raise RuntimeError('installed source identity failed')
    program="import importlib.metadata as m,json;print(json.dumps(sorted([{'name':d.metadata['Name'].lower(),'version':d.version} for d in m.distributions()],key=lambda r:r['name'])))"
    dep=subprocess.run([result['python'],'-I','-c',program],capture_output=True,timeout=30)
    actual=json.loads(dep.stdout) if dep.returncode==0 else None
    source="import atmem,json;print(json.dumps({'module':atmem.__file__}))"
    ordinary=subprocess.run([result['python'],'-I','-c',source],capture_output=True,timeout=30,
        user=1000,group=1000,extra_groups=[],env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
    proof={'dependency_versions':actual,'dependencies_equal':actual==plans[0]['prior_dependency_versions'],
        'ordinary_user_exit':ordinary.returncode,'ordinary_stdout_base64':base64.b64encode(ordinary.stdout).decode(),
        'ordinary_stderr_base64':base64.b64encode(ordinary.stderr).decode(),'wheel_sha256':result['wheel_sha256'],
        'python':result['python'],'qualified':actual==plans[0]['prior_dependency_versions'] and ordinary.returncode==0,
        'model_calls':0,'preview_not_release':True}
    save('external.compatibility_build_completed',proof)
    print(json.dumps(proof),flush=True)


if __name__=='__main__':main()
