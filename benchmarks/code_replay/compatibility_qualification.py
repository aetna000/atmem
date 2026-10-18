"""Real-source qualification of the five failed identities, never solver scoring."""
import base64
from hashlib import sha256
import json
import subprocess

RUN='external-windows-source-storage-qualification-v1-20261018'
IDENTITIES=('pylint-dev__pylint-6358','pylint-dev__pylint-6517','pylint-dev__pylint-6820',
            'pylint-dev__pylint-7277','pyvista__pyvista-4853')
PROGRAM=r'''
import os,json,base64,hashlib,subprocess,zlib,shutil
from pathlib import Path,PurePosixPath
if min(shutil.disk_usage('/tmp').free,shutil.disk_usage('/mnt/c').free)<8*1024**3:raise ValueError('physical disk guard')
root=Path(job['root']);root.mkdir(mode=0o711,exist_ok=False)
workspace=root/'workspace';workspace.mkdir(mode=0o700)
os.environ.clear();os.environ.update(PATH='/usr/bin:/bin',LANG='C.UTF-8',PYTHONDONTWRITEBYTECODE='1',
 GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_SYSTEM='/dev/null',GIT_TERMINAL_PROMPT='0',
 GIT_AUTHOR_DATE='2000-01-01T00:00:00+0000',GIT_COMMITTER_DATE='2000-01-01T00:00:00+0000',ATMEM_HOME=str(root/'atmem-home'))
for name,encoded in job['source']['files_base64'].items():
 p=PurePosixPath(name)
 if p.is_absolute() or '..' in p.parts or '.git' in p.parts:raise ValueError('verified public paths required')
 target=workspace/name;target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(base64.b64decode(encoded,validate=True));target.chmod(0o755 if job['source']['modes'][name]=='100755' else 0o644)
def git(*args):return subprocess.check_output(['git','-C',str(workspace),'-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false',*args],stderr=subprocess.STDOUT,timeout=15).decode().strip()
git('init','--quiet');git('add','--force','--all');git('-c','user.name=AtMem Benchmark','-c','user.email=benchmark@invalid','commit','--quiet','-m','Public base snapshot only; no upstream history')
from atmem.memory import Memory
from atmem.service.household import HouseholdApplication
from atmem.knowledge.code.environment import environment_digest
from atmem.knowledge.source_text import source_text,SourceTextEncodingError
from atmem.code.portable import CodePortable
from atmem.evidence.crypto import generate_recipient_keypair,generate_signing_keypair
(root/'atmem-home').mkdir(mode=0o700)
database=root/'atmem-home/memory.db';HouseholdApplication.initialize(database,encrypted=True)
memory=Memory(database,auto_vectors=False)
try:
 namespace={'__name__':'compatibility_qualification_lane'};exec(job['lane_source'],namespace)
 lane=namespace['ProductLane'](memory,str(workspace),environment_sha256=environment_digest(),experience=False)
 prepared=lane.prepare(run_id=job['identity']+'-compatibility',task=job['issue'],image_id=job['extractor'],max_context_bytes=4096)
 generation=lane.knowledge.current(str(workspace))
 if generation is None or len(prepared['package'].content.encode())>4096:raise ValueError('bounded current context required')
 for name,encoded in generation['source_bytes'].items():
  if encoded!=job['source']['files_base64'][name]:raise ValueError('retained original source differs')
 if job['identity'].startswith('pylint-'):
  probe='tests/functional/i/implicit/implicit_str_concat_latin1.py'
  if probe not in generation['source_bytes'] or generation['excluded_counts'].get('source_encoding')!=3:
   raise ValueError('declared Latin-1 inclusion and three strict exclusions required')
 else:probe=next(n for n in sorted(generation['source_bytes']) if n.startswith('pyvista/') and n.endswith('.py'))
 raw=base64.b64decode(generation['source_bytes'][probe],validate=True)
 expected='\n'.join(source_text(probe,raw).splitlines()[:3])
 answer=lane.app.dispatch('knowledge-source',{'project_id':lane.scope.project_id,'root':str(workspace),'path':probe,'line_count':3})
 if answer['status']!='current' or answer['content']!=expected or answer['source_sha256']!=hashlib.sha256(raw).hexdigest():
  raise ValueError('exact source presentation required')
 from atmem.knowledge.worker import ExtractionWorker
 if lane.knowledge.index(str(workspace),ExtractionWorker(job['extractor']))['status']!='unchanged':raise ValueError('unchanged index not reused')
 public,secret=generate_recipient_keypair();signer,sign_secret=generate_signing_keypair()
 portable=CodePortable(lane.app)
 bundle=portable.export(lane.scope.project_id,recipient_public_key=public,signing_public_key=signer,signing_secret_key=sign_secret)
 reopened=portable.open(bundle,recipient_secret_key=secret,trusted_signing_public_key=signer)
 restored=reopened['state']['documents']['knowledge-generation']
 if len(restored)!=1 or restored[0]['value']!=generation:raise ValueError('encrypted bundle lost original generation data')
 (workspace/probe).write_bytes(raw+b'\n# benchmark compatibility freshness check\n')
 if lane.knowledge.current(str(workspace)) is not None:raise ValueError('changed source was not withheld')
 (workspace/probe).write_bytes(raw)
 if lane.knowledge.current(str(workspace)) is None:raise ValueError('exact restored source not current')
 if not memory.store.verify_audit_chain(lane.scope.subject_id):raise ValueError('product audit chain invalid')
 result={'identity':job['identity'],'scope':lane.scope.to_dict(),'database':str(database),'atmem_home':str(root/'atmem-home'),
  'workspace':str(workspace),'index':prepared['index'],'index_ms':prepared['index_ms'],'context_ms':prepared['context_ms'],
  'package':prepared['package'].to_dict(),'exposure':prepared['exposure'],'source_probe':probe,'source_expected':expected,
  'generation_zlib_base64':base64.b64encode(zlib.compress(json.dumps(generation).encode())).decode(),
  'logical_generation_bytes':len(json.dumps(generation,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()),
  'encrypted_bundle_format':bundle['format'],'bundle_exact_generation':True,'freshness_withholding':True,
  'audit_chain_valid':True,'model_calls':0,'qualified_before_nonroot_mcp':True}
finally:memory.close()
for directory,dirs,files in os.walk(root):
 for name in dirs+files:os.chown(Path(directory)/name,1000,1000,follow_symlinks=False)
from types import SimpleNamespace
helpers={};exec(job['configuration_source'],helpers)
config=helpers['configuration'](job['python'],[],database=str(database),root=str(workspace),scope=SimpleNamespace(**result['scope']),focused=True)
config['args'][2]="import os;os.environ['ATMEM_HOME']="+repr(str(root/'atmem-home'))+';'+config['args'][2]
requests=[{'jsonrpc':'2.0','id':'init','method':'initialize','params':{}},
 {'jsonrpc':'2.0','id':'source','method':'tools/call','params':{'name':'code_source','arguments':{'path':result['source_probe'],'line_count':3}}}]
proc=subprocess.run([config['command'],*config['args']],input=('\n'.join(json.dumps(r) for r in requests)+'\n').encode(),capture_output=True,timeout=90,
 user=1000,group=1000,extra_groups=[],env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
responses=[json.loads(line) for line in proc.stdout.splitlines()]
answer=next((r for r in responses if r.get('id')=='source'),{})
try:actual=json.loads(answer['result']['content'][0]['text'])
except (KeyError,ValueError,IndexError):actual={}
result.update(mcp_exit=proc.returncode,mcp_stdout_base64=base64.b64encode(proc.stdout).decode(),mcp_stderr_base64=base64.b64encode(proc.stderr).decode(),
 qualified=proc.returncode==0 and actual.get('status')=='current' and actual.get('content')==result['source_expected'])
print(json.dumps(result),flush=True)
'''


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.confirmation_staging import RUN as STAGING
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    from benchmarks.code_replay.windows_transport import framed_command,framed_input
    from benchmarks.code_replay.windows_operator_host import PYTHON
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('qualification already attempted; inspect its original handle')
    def only(run,kind):
        values=[e['envelope']['payload'] for e in vault.inspect(principal,run) if e['envelope']['event_type']==kind]
        if len(values)!=1:raise ValueError('exact terminal prerequisite required')
        return values[0]
    build=only('external-windows-product-build-source-storage-v1-20261018','external.compatibility_build_completed')
    manifest=only(STAGING,'external.confirmation_manifest_frozen')
    if build['qualified'] is not True:raise ValueError('installed compatibility preview required')
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.compatibility_qualification_planned',{'driver_source':job['driver_source'],'worker_source':PROGRAM,
        'identities':list(IDENTITIES),'build':build,'staging_run':STAGING,'model_calls':0,'scored_confirmation':False})
    results=[]
    for identity in IDENTITIES:
        descriptor=manifest['source_descriptors'][identity]
        source=recover_export(vault.inspect(principal,descriptor['export_run']),descriptor)
        payload={'program':PROGRAM,'source':{k:source[k] for k in ('base_commit','files_base64','modes')},
            'root':'/home/jt/atmem-benchmark-runtime-20261018/source-storage-qualification-v1/'+identity,
            'identity':identity,'lane_source':manifest['lane_source'],'issue':manifest['issues'][identity],
            'extractor':manifest['extractor'],'python':build['python'],'configuration_source':job['configuration_source']}
        from pathlib import Path
        parent=Path(payload['root']).parent
        if not parent.exists():parent.mkdir(mode=0o711,exist_ok=False)
        task_run=RUN+'-'+identity
        target=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=task_run)
        if target.inspect(principal,task_run):raise ValueError('case already attempted')
        def retain(kind,payload):return target.capture(run_id=task_run,kind=kind,principal=principal,payload=payload)
        retain('external.compatibility_case_planned',{'identity':identity,'source_descriptor':descriptor,
            'worker_source':PROGRAM,'root':payload['root'],'build':build,'model_calls':0})
        wrapper="import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-c',\"import json,sys;job=json.load(sys.stdin);exec(job['program'])\"],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)"
        proc=subprocess.run(framed_command(),input=framed_input({'program':wrapper,'python':build['python'],'payload':payload}),capture_output=True,timeout=420)
        streams={}
        for name,raw in [('stdout',proc.stdout),('stderr',proc.stderr)]:
            receipts=[]
            for offset in range(0,len(raw),3_000_000):
                receipts.append(retain('external.compatibility_case_chunk',{'stream':name,'offset':offset,
                    'bytes_base64':base64.b64encode(raw[offset:offset+3_000_000]).decode()}))
            streams[name]={'bytes':len(raw),'sha256':sha256(raw).hexdigest(),'receipts':receipts}
        retain('external.compatibility_case_transport',{'exit_code':proc.returncode,'streams':streams})
        value=json.loads(proc.stdout) if proc.returncode==0 else {}
        summary={'identity':identity,'task_run':task_run,'exit_code':proc.returncode,
                 'qualified':value.get('qualified') is True,'model_calls':0}
        if value:summary.update({k:v for k,v in value.items() if k not in {'generation_zlib_base64','exposure','mcp_stdout_base64','mcp_stderr_base64'}})
        save('external.compatibility_case_result',summary);results.append(summary)
        print(json.dumps({'identity':identity,'qualified':summary['qualified'],'exit_code':proc.returncode}),flush=True)
    save('external.compatibility_qualification_completed',{'results':results,'model_calls':0,
        'qualified':len(results)==5 and all(r['qualified'] for r in results),'scored_confirmation':False})


if __name__=='__main__':main()
