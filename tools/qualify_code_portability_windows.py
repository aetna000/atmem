"""Cross-machine installed-product bundle check using only public Click controls.

Run using the installed Mac preview Python. Recipient secrets stay on Windows;
no owner memory, CLI credentials, source checkout imports or model calls are used.
"""
import base64
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('swebench_transport', REPO / 'benchmarks/code_replay/swebench_pilot.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
MAC = Path('/Users/javadtaghia/Library/Application Support/AtMem Builds/code-benefits-source-20261019')
REMOTE = '/home/user/atmem-swebench-20261019/product-benefits-portable-20261019'
PYTHON = '/home/user/atmem-swebench-20261019/candidate-bounded-graph-20261019/venv/bin/python'


def installed_remote(program, payload=None):
    wrapper = ('import subprocess,json; p=job["payload"];r=subprocess.run([' + repr(PYTHON)
        + ',"-I","-c",p["program"]],input=json.dumps(p["payload"]),capture_output=True,text=True,timeout=180);'
        'print(r.stdout);print(r.stderr[-1000:]);raise SystemExit(r.returncode)')
    result = transport.remote(wrapper, {'program': program, 'payload': payload}, timeout=200)
    if result.returncode:
        raise RuntimeError(result.stdout[-2000:] + result.stderr[-1000:])
    return json.loads(result.stdout)


def main():
    created = installed_remote('''import os,json,base64
from pathlib import Path
state=Path(''' + repr(REMOTE) + ''');state.mkdir(mode=0o700,exist_ok=False)
os.environ['ATMEM_HOME']=str(state/'home')
from atmem.evidence.crypto import generate_recipient_keypair
public,secret=generate_recipient_keypair()
p=state/'recipient-secret.bin';p.write_bytes(secret);p.chmod(0o600)
print(json.dumps({'recipient_public':base64.b64encode(public).decode()}))
''')
    os.environ['ATMEM_HOME'] = str(MAC / 'home')
    import atmem
    if '/site-packages/' not in atmem.__file__:
        raise RuntimeError('installed preview required')
    from atmem.memory import Memory
    from atmem.code.identity import CodeIdentity
    from atmem.code.application import CodeApplication
    from atmem.code.portable import CodePortable
    from atmem.evidence.crypto import generate_signing_keypair
    memory = Memory(MAC / 'memory.db', auto_vectors=False)
    try:
        scope = CodeIdentity(memory.store).resolve(MAC / 'click-source', subject_id='qualification',
            profile_id='shared', agent_id='claude')
        app = CodeApplication(memory, subject_id=scope.subject_id)
        before = app.records(scope.project_id, status=None)
        public, secret = generate_signing_keypair()
        bundle = CodePortable(app).export(scope.project_id,
            recipient_public_key=base64.b64decode(created['recipient_public']),
            signing_public_key=public, signing_secret_key=secret)
        signer = base64.b64encode(public).decode()
        raw = json.dumps(bundle).encode()
        (MAC / 'portable-windows-bundle.json').write_bytes(raw)
        archive = subprocess.check_output(['git', '-C', str(MAC / 'click-source'), 'archive', 'HEAD'])
        qualification = json.loads((MAC / 'qualification.json').read_text())
    finally:
        memory.close()
    result = installed_remote('''import sys,os,json,base64,io,tarfile,subprocess,hashlib
from pathlib import Path,PurePosixPath
p=json.load(sys.stdin);state=Path(''' + repr(REMOTE) + ''');os.environ['ATMEM_HOME']=str(state/'home')
from atmem.memory import Memory
from atmem.service.household import HouseholdApplication
from atmem.code.application import CodeApplication
from atmem.code.portable import CodePortable
from atmem.code.identity import CodeIdentity
from atmem.code.experience_view import experiences,execution_evidence
source=state/'click-source';source.mkdir()
raw=base64.b64decode(p['source_archive'],validate=True)
if hashlib.sha256(raw).hexdigest()!=p['source_sha256']:raise ValueError('public source differs')
with tarfile.open(fileobj=io.BytesIO(raw)) as t:
 for m in t.getmembers():
  path=PurePosixPath(m.name)
  if path.is_absolute() or '..' in path.parts or m.issym() or m.islnk():raise ValueError('unsafe member')
  if m.isdir():continue
  if not m.isfile() or m.size>2000000:raise ValueError('oversized source')
  target=source/m.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(t.extractfile(m).read())
for argv in [['git','init','-q',str(source)],['git','-C',str(source),'add','.'],
 ['git','-C',str(source),'-c','user.name=Qualification','-c','user.email=qualification@localhost','commit','-qm','public snapshot']]:
 subprocess.run(argv,check=True,capture_output=True)
HouseholdApplication.initialize(state/'memory.db',encrypted=True)
m=Memory(state/'memory.db',auto_vectors=False)
try:
 app=CodeApplication(m,subject_id='qualification');portable=CodePortable(app)
 secret=(state/'recipient-secret.bin').read_bytes();signer=base64.b64decode(p['signer'])
 (state/'bundle.json').write_text(json.dumps(p['bundle']))
 value=portable.open(p['bundle'],recipient_secret_key=secret,trusted_signing_public_key=signer)
 preview=portable.preview(value,root=str(source));assert preview['can_import']
 restored=portable.restore(value,root=str(source),preview_token=preview['preview_token']);assert restored['imported']
 scope=CodeIdentity(m.store).resolve(source,subject_id='qualification',profile_id='shared',agent_id='copilot')
 records=app.records(scope.project_id,status=None)
 assert sorted((x['id'],x['content'],x['status']) for x in records)==sorted(tuple(x) for x in p['records'])
 observed=execution_evidence(app,scope.project_id,p['record_id'],p['receipt_id'])
 assert observed['stdout']==p['stdout']
 listed=experiences(app,scope,str(source));assert listed['items']
 denied=False
 try:CodePortable(CodeApplication(m,subject_id='unrelated')).open(p['bundle'],recipient_secret_key=secret,trusted_signing_public_key=signer)
 except PermissionError:denied=True
 assert denied
 deleted=app.forget(scope.project_id,p['record_id']);assert not experiences(app,scope,str(source))['items']
 result={'status':'passed','source_machine':'macOS','destination':'Windows/WSL Linux',
  'canonical_records_equal':True,'exact_execution_output_equal':True,'other_subject_denied':denied,
  'destination_experience_applicability':listed['items'][0]['applicability'],
  'forget_verified':True,'hosts_enabled':restored['hosts_enabled'],
  'source_archive_sha256':p['source_sha256'],'original_agent_or_database_access_required':False}
 (state/'qualification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
finally:m.close()
''', {'bundle': bundle, 'signer': signer, 'source_archive': base64.b64encode(archive).decode(),
        'source_sha256': sha256(archive).hexdigest(),
        'records': [(r['id'], r['content'], r['status']) for r in before],
        'record_id': qualification['command']['formation']['record_ids'][0],
        'receipt_id': qualification['command']['experience_id'], 'stdout': qualification['command']['stdout']})
    (MAC / 'windows-portability-result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
