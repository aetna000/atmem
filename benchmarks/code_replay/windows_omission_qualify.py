"""Installed real-source omission/freshness controls; no agent or repair scoring."""
import argparse
import ast
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import zlib

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT, RUN as IMAGES_RUN
from benchmarks.code_replay.windows_omission_build import STRICT_RUN
from benchmarks.code_replay.windows_transport import framed_command, framed_input

RUN = 'external-windows-omission-installed-qualification-v1-20261018'
EXTRACTOR = 'sha256:62e15650d96e24eb4c5adce548ee711425e4a91f1a87ab9f9a8772a78ed724f3'
DICTIONARY = """import hashlib,json,base64,subprocess
from pathlib import Path
path='pydicom/sr/_concepts_dict.py'
raw=subprocess.check_output(['git','-C','/testbed','show',job_base+':'+path])
assert raw==Path('/testbed',path).read_bytes()
print(json.dumps({'path':path,'base':job_base,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'content_base64':base64.b64encode(raw).decode()}))
"""

PROGRAM = r'''
import base64,hashlib,json,os,subprocess,tempfile,zlib
from pathlib import Path
root=Path(tempfile.mkdtemp(prefix='atmem-omission-qualified-',dir='/dev/shm'))
os.environ['ATMEM_HOME']=str(root/'home')
os.environ.update({'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null','GIT_TERMINAL_PROMPT':'0'})
workspace=root/'repository';workspace.mkdir(mode=0o700)
source_program='job_base='+repr(job['dictionary_base'])+'\n'+job['dictionary_program']
cmd=['docker','run','--rm','--pull=never','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=256m','--cpus=1','--pids-limit=64','--entrypoint','/opt/miniconda3/envs/testbed/bin/python',job['dictionary_image'],'-I','-S','-c',source_program]
process=subprocess.run(cmd,capture_output=True,timeout=30,check=True)
dictionary=json.loads(process.stdout);large=base64.b64decode(dictionary['content_base64'],validate=True)
assert len(large)==dictionary['bytes']>2000000 and hashlib.sha256(large).hexdigest()==dictionary['sha256']
inputs={'generated.py':large}
for name in ('__init__.py','config.py','handlers.py'):
 inputs['logging/'+name]=Path('/usr/lib/python3.12/logging',name).read_bytes()
for name,raw in inputs.items():
 target=workspace/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
def git(*args):return subprocess.check_output(['git','-C',str(workspace),'-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false',*args],stderr=subprocess.STDOUT).decode().strip()
git('init','--quiet');git('add','--all');git('-c','user.name=AtMem Benchmark','-c','user.email=benchmark@invalid','commit','--quiet','-m','Real-source control fixture, not a coding task')
from atmem.memory import Memory
from atmem.service.household import HouseholdApplication
from atmem.code.identity import CodeIdentity
from atmem.code.application import CodeApplication
from atmem.code.experience import CodeExperience
from atmem.knowledge.projections import CodeKnowledge,SourceFileBudgetExceeded
from atmem.knowledge.worker import ExtractionWorker
from atmem.knowledge.code.mcp import CodeKnowledgeMCP
db=root/'home/memory.db';HouseholdApplication.initialize(db,encrypted=True)
memory=Memory(db,auto_vectors=False)
try:
 scope=CodeIdentity(memory.store).resolve(workspace,subject_id='benchmark-operator',profile_id='shared',agent_id='codex')
 app=CodeApplication(memory,subject_id=scope.subject_id);app.settings(scope.project_id,{'graph_enabled':True})
 knowledge=CodeKnowledge(app,scope)
 indexed=knowledge.index(str(workspace),ExtractionWorker(job['extractor']))
 generation=knowledge.current(str(workspace));assert indexed['excluded_counts']['file_budget']==1
 assert 'generated.py' not in generation['source_bytes']
 snapshot,files,excluded=knowledge.capture(str(workspace),'a'*64,omit_oversized_files=True)
 assert excluded['file_budget']==1 and all(len(raw)<=262144 for raw in files.values())
 server=CodeKnowledgeMCP(app,scope,str(workspace))
 context=server.query('code_context',{'query':'getLogger','budget':4096})
 assert context['status']=='current' and context['excluded_counts']['file_budget']==1 and 'getLogger' in context['content']
 assert len(context['content'].encode())<=4096
 exact=server.query('code_source',{'path':'logging/__init__.py','start_line':1,'line_count':3})
 assert exact['content']=='\n'.join(inputs['logging/__init__.py'].decode().splitlines()[:3])
 strict=False
 try:CodeExperience(app,scope,producer_keys={'fixture':b'0'*32},environment_sha256='a'*64).capture_snapshot(str(workspace))
 except SourceFileBudgetExceeded:strict=True
 assert strict
 lane_result=None
 if job.get('lane_source'):
  namespace={};exec(compile(job['lane_source'],'benchmark_lane.py','exec'),namespace)
  lane=namespace['ProductLane'](memory,workspace,environment_sha256='a'*64,experience=False)
  prepared=lane.prepare(run_id='installed-structure-omissions',task='getLogger',image_id=job['extractor'],max_context_bytes=4096)
  assert prepared['state_identity']=='covered_structure_source' and prepared['previous_candidates']==0
  assert prepared['package'].memory_ids==() and 'getLogger' in prepared['package'].content
  lane_result={**{k:v for k,v in prepared.items() if k not in ('request','package')},
   'request':prepared['request'].to_dict(),'package':prepared['package'].to_dict()}
 extra=workspace/'additional-generated.py';extra.write_bytes(large)
 omission_change_withheld=knowledge.current(str(workspace)) is None;assert omission_change_withheld
 extra.unlink() # Only this newly created public-data fixture copy.
 assert knowledge.current(str(workspace)) is not None
 outside=root/'outside.py';outside.write_bytes(inputs['logging/__init__.py'])
 link=workspace/'escape.py';link.symlink_to(outside)
 denied=False
 try:knowledge.capture(str(workspace),'a'*64,omit_oversized_files=True)
 except ValueError:denied=True
 assert denied;link.unlink()
 target=workspace/'logging/__init__.py';target.write_bytes(inputs['logging/__init__.py']+b'\n')
 source_change_withheld=knowledge.current(str(workspace)) is None;assert source_change_withheld
 result={'root':str(root),'indexed':indexed,'dictionary':dictionary,'lane_prepared':lane_result,
  'input_files_base64':{n:base64.b64encode(raw).decode() for n,raw in inputs.items()},
  'input_sha256':{n:hashlib.sha256(raw).hexdigest() for n,raw in inputs.items()},
  'context':context,'exact_source_response':exact,'generation':generation,
  'strict_execution_capture_preserved':strict,'new_omission_withheld':omission_change_withheld,
  'outside_symlink_denied':denied,'source_change_withheld':source_change_withheld,
  'audit_chain_verified':memory.store.verify_audit_chain(scope.subject_id),
  'scope':scope.to_dict(),'solver_calls':0,'owner_install_changed':False,
  'assurance':'real-source installed boundary control, not repair quality or token benefit'}
finally:memory.close()
raw=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
print(json.dumps({'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'zlib_base64':base64.b64encode(zlib.compress(raw)).decode()}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-lane-v2', action='store_true', help='Separate full production-turn bridge control; no model or repair retry')
    args = parser.parse_args()
    run_id = RUN.replace('-v1-', '-v2-') if args.full_lane_v2 else RUN
    ast.parse(PROGRAM); ast.parse(DICTIONARY)
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope)
    if vault.inspect(principal, run_id):
        raise ValueError('installed control already dispatched; inspect handle, no implicit retry')
    builds = vault.inspect(principal, STRICT_RUN)
    built = next(e['envelope']['payload'] for e in builds if e['envelope']['event_type'] == 'external.windows_omission_build_result')
    assert built['qualified_installed_source_identity']
    assert any(e['envelope']['event_type'] == 'external.windows_omission_dependencies_verified'
        and e['envelope']['payload']['exact_dependency_versions_match_prior_preview'] for e in builds)
    images = vault.inspect(principal, IMAGES_RUN)
    dictionary = next(e['envelope']['payload'] for e in images if e['envelope']['event_type'] == 'external.confirmation_registry_descriptor'
        and e['envelope']['payload']['instance_id'] == 'pydicom__pydicom-1194')
    job = {'program': PROGRAM, 'dictionary_program': DICTIONARY, 'dictionary_image': dictionary['image'],
        'dictionary_base': '5e70c1dfe09820023fec519dac4c51bebcb7f60d', 'extractor': EXTRACTOR}
    if args.full_lane_v2:
        job['lane_source'] = Path('benchmarks/code_replay/history.py').read_text()
    cmd = framed_command(); cmd[-1] = cmd[-1].replace('python3 -c', built['python'] + ' -I -c')
    def save(kind, payload):
        return vault.capture(run_id=run_id, kind=kind, principal=principal, payload=payload)
    save('external.omission_installed_qualification_planned', {'driver_source': Path(__file__).read_text(),
        'job': job, 'transport': cmd, 'wheel_sha256': built['wheel_sha256'], 'solver_calls': 0})
    proc = subprocess.run(cmd, input=framed_input(job), capture_output=True, timeout=240)
    save('external.omission_installed_qualification_transport', {'exit_code': proc.returncode,
        'stdout_base64': base64.b64encode(proc.stdout).decode(), 'stderr_base64': base64.b64encode(proc.stderr).decode()})
    if proc.returncode:
        raise RuntimeError('installed source control failed; retained, no automatic retry')
    packed = json.loads(proc.stdout); raw = zlib.decompress(base64.b64decode(packed['zlib_base64'], validate=True))
    if len(raw) != packed['bytes'] or sha256(raw).hexdigest() != packed['sha256']:
        raise ValueError('full installed control transport digest differs')
    result = json.loads(raw)
    save('external.omission_installed_qualification_result', result)
    print(json.dumps({k: result[k] for k in ('indexed', 'strict_execution_capture_preserved', 'new_omission_withheld',
        'outside_symlink_denied', 'source_change_withheld', 'audit_chain_verified', 'solver_calls')}), flush=True)


if __name__ == '__main__':
    main()
