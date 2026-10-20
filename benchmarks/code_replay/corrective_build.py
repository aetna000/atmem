"""One-file corrective preview from the exact frozen source; no owner upgrade."""
import ast
import base64
from hashlib import sha256
import json
import subprocess

RUN='external-windows-product-build-typed-query-v1-20261018'
PRIOR='external-windows-product-build-source-storage-v1-20261018'
REPLAY='external-windows-typed-query-pack-replay-v1-20261018'
PATH='atmem/knowledge/code/packing.py'
BASELINE_SHA='b826ed52def004d7b5d9185dfea11cd8fa98bd954f84706db1977a72947d15b4'
BASELINE_WHEEL='e8d98dadfa98554ba38311096a7b90dac815bbbe03c6c35dae430bed54ee7bf6'


def candidate_job(original,raw):
    if type(raw) is not bytes or set(original['files'])!=set(original['manifest']):
        raise ValueError('full exact original source manifest required')
    for name,encoded in original['files'].items():
        if sha256(base64.b64decode(encoded,validate=True)).hexdigest()!=original['manifest'][name]:
            raise ValueError('original source identity differs')
    if original['manifest'].get(PATH)!=BASELINE_SHA:raise ValueError('frozen packer base differs')
    ast.parse(raw.decode('utf-8'),feature_version=(3,10))
    if sha256(raw).hexdigest()==BASELINE_SHA:raise ValueError('actual corrective source change required')
    result=json.loads(json.dumps(original))
    result['files'][PATH]=base64.b64encode(raw).decode()
    result['manifest'][PATH]=sha256(raw).hexdigest()
    if {n for n in result['manifest'] if result['manifest'][n]!=original['manifest'][n]}!={PATH}:
        raise ValueError('only the declared packer may change')
    return result


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.windows_transport import framed_command,framed_input
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('corrective build already attempted; inspect its handle')
    def only(run,kind):
        rows=[e['envelope']['payload'] for e in vault.inspect(principal,run) if e['envelope']['event_type']==kind]
        if len(rows)!=1:raise ValueError('exact frozen prerequisite required: '+kind)
        return rows[0]
    prior=only(PRIOR,'external.compatibility_build_planned')
    qualified=only(PRIOR,'external.compatibility_build_completed')
    replay=only(REPLAY,'external.strict_identifier_replay_completed')
    replay_plan=only(REPLAY,'external.strict_identifier_replay_planned')
    raw=job['candidate_source'].encode()
    if (qualified['qualified'] is not True or qualified['wheel_sha256']!=BASELINE_WHEEL
            or replay['identities']!=19 or replay['all_original_packs_reproduced'] is not True
            or replay_plan['candidate_packing_sha256']!=sha256(raw).hexdigest()):
        raise ValueError('qualified frozen base and complete matching corrective replay required')
    build=candidate_job(prior['job'],raw)
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.corrective_build_planned',{'driver_source':job['driver_source'],'job':build,
        'prior_build':PRIOR,'baseline_wheel_sha256':BASELINE_WHEEL,'changed_product_files':[PATH],
        'prior_dependency_versions':qualified['dependency_versions'],'candidate_packing_sha256':sha256(raw).hexdigest(),
        'model_calls':0,'owner_install_changed':False,'frozen_candidate_replaced':False,'protocol':job['protocol']})
    proc=subprocess.run(framed_command(),input=framed_input(build),capture_output=True,timeout=1100)
    save('external.corrective_build_transport',{'exit_code':proc.returncode,
        'stdout_base64':base64.b64encode(proc.stdout).decode(),'stderr_base64':base64.b64encode(proc.stderr).decode()})
    if proc.returncode:raise RuntimeError('corrective build failure retained; no automatic retry')
    result=json.loads(proc.stdout);save('external.corrective_build_result',result)
    if result['qualified_installed_source_identity'] is not True:raise ValueError('installed source identity failed')
    program="import importlib.metadata as m,json;print(json.dumps(sorted([{'name':d.metadata['Name'].lower(),'version':d.version} for d in m.distributions()],key=lambda r:r['name'])))"
    dep=subprocess.run([result['python'],'-I','-c',program],capture_output=True,timeout=30)
    actual=json.loads(dep.stdout) if dep.returncode==0 else None
    program="from atmem.knowledge.code.packing import _compound_terms,_references,_named;import json;assert not _compound_terms('decorated_with_property',{'proper','rated'});assert _named('src/vendor/api.process',_references('import vendor as v\\nv.process()'));print(json.dumps({'corrective_import':True}))"
    user=subprocess.run([result['python'],'-I','-c',program],capture_output=True,timeout=30,
        user=1000,group=1000,extra_groups=[],env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
    proof={'dependency_versions':actual,'dependencies_equal':actual==qualified['dependency_versions'],
        'ordinary_user_exit':user.returncode,'ordinary_stdout_base64':base64.b64encode(user.stdout).decode(),
        'ordinary_stderr_base64':base64.b64encode(user.stderr).decode(),'wheel_sha256':result['wheel_sha256'],
        'python':result['python'],'qualified':actual==qualified['dependency_versions'] and user.returncode==0,
        'candidate_packing_sha256':sha256(raw).hexdigest(),'model_calls':0,'preview_not_release':True,
        'real_extractor_qualification':'still required'}
    save('external.corrective_build_completed',proof);print(json.dumps(proof),flush=True)


if __name__=='__main__':main()
