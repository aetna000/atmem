"""Operator-only verified wheels for the fixed no-model PyVista runtime correction."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
from benchmarks.code_replay.windows_transport import framed_command, framed_input


RUN = "external-windows-pyvista-offline-wheels-v1-20261018"
PROGRAM = r'''
import base64,hashlib,json,os,re,shutil,sys,time,urllib.parse,urllib.request
from pathlib import Path
base=Path('/home/jt/atmem-benchmark-runtime-20261018/pyvista-vtk931-v1')
parent=base.parent
if parent.is_symlink() or not parent.is_dir() or parent.resolve()!=parent:
 raise ValueError('exact existing benchmark runtime parent required')
def guard():
 if min(shutil.disk_usage('/tmp').free,shutil.disk_usage('/mnt/c').free)<8*1024**3:
  raise ValueError('physical/WSL free space below 8GiB')
guard()
base.mkdir(mode=0o700,exist_ok=False)
packages=[('vtk','9.3.1',r'vtk-9\.3\.1-cp39-cp39-manylinux[^/]*x86_64\.whl'),
 ('setuptools','78.1.1',r'setuptools-78\.1\.1-py3-none-any\.whl'),
 ('wheel','0.45.1',r'wheel-0\.45\.1-py3-none-any\.whl')]
results=[]
for package,version,pattern in packages:
 metadata_url='https://pypi.org/pypi/'+package+'/'+version+'/json'
 with urllib.request.urlopen(metadata_url,timeout=60) as response:
  if urllib.parse.urlparse(response.geturl()).hostname!='pypi.org':
   raise ValueError('metadata origin changed')
  raw=response.read(2000001)
 if len(raw)>2000000:raise ValueError('metadata byte cap')
 metadata=json.loads(raw)
 if metadata['info']['version']!=version:raise ValueError('PyPI version differs')
 candidates=[item for item in metadata['urls'] if item['packagetype']=='bdist_wheel'
  and re.fullmatch(pattern,item['filename']) and not item.get('yanked')]
 if len(candidates)!=1:raise ValueError('one fixed platform wheel required')
 item=candidates[0];filename=item['filename'];url=item['url'];expected=item['digests']['sha256']
 if (urllib.parse.urlparse(url).hostname!='files.pythonhosted.org' or not url.startswith('https://')
  or type(item['size']) is not int or not 1<=item['size']<=128000000
  or re.fullmatch('[0-9a-f]{64}',expected) is None):
  raise ValueError('bounded PyPI artifact identity required')
 digest=hashlib.sha256();size=0;started=time.monotonic()
 with urllib.request.urlopen(url,timeout=60) as response,(base/filename).open('xb') as target:
  if urllib.parse.urlparse(response.geturl()).hostname!='files.pythonhosted.org':
   raise ValueError('wheel origin changed')
  while True:
   guard()
   if time.monotonic()-started>180:raise ValueError('download time budget')
   chunk=response.read(min(65536,item['size']+1-size))
   if not chunk:break
   size+=len(chunk)
   if size>item['size']:raise ValueError('download byte budget')
   digest.update(chunk);target.write(chunk)
 if size!=item['size'] or digest.hexdigest()!=expected:
  raise ValueError('downloaded wheel identity differs')
 results.append({'package':package,'version':version,'filename':filename,'url':url,
  'bytes':size,'sha256':expected,'metadata_url':metadata_url,
  'metadata_sha256':hashlib.sha256(raw).hexdigest(),'metadata_base64':base64.b64encode(raw).decode()})
print(json.dumps({'directory':str(base),'artifacts':results,'all_wheels_verified':True,
 'host_packages_installed':False,'images_built':0,'model_calls':0,
 'free_physical_windows_bytes':shutil.disk_usage('/mnt/c').free}))
'''


def main():
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(EVIDENCE_ROOT, vault_id="confirmation-v1", scope=scope)
    if vault.inspect(principal, RUN):
        raise ValueError("wheel preparation already recorded; inspect handle, no implicit repeat")
    vault.capture(run_id=RUN, kind="external.pyvista_wheels_planned", principal=principal, payload={
        "driver_source": Path(__file__).read_text(), "program": PROGRAM,
        "program_sha256": sha256(PROGRAM.encode()).hexdigest(),
        "protocol": Path("specs/042-atmem-code/windows-pyvista-runtime-compatibility-v1.md").read_text(),
        "model_calls": 0, "owner_packages_changed": False})
    try:
        proc = subprocess.run(framed_command(), input=framed_input({"program": PROGRAM}),
                              capture_output=True, timeout=300)
        row = {"transport_exit": proc.returncode,
               "stdout_base64": base64.b64encode(proc.stdout).decode(),
               "stderr_base64": base64.b64encode(proc.stderr).decode()}
        if proc.returncode == 0:
            row["result"] = json.loads(proc.stdout)
    except subprocess.TimeoutExpired as exc:
        row = {"transport_exit": None, "failure": "transport_timeout",
               "stdout_base64": base64.b64encode(exc.stdout or b"").decode(),
               "stderr_base64": base64.b64encode(exc.stderr or b"").decode()}
    vault.capture(run_id=RUN, kind="external.pyvista_wheels_completed", principal=principal, payload=row)
    result = row.get("result", {})
    print(json.dumps({"transport_exit": row["transport_exit"], "failure": row.get("failure"),
        "all_wheels_verified": result.get("all_wheels_verified"),
        "artifacts": [{key: item[key] for key in ("package", "version", "filename", "bytes", "sha256")}
                      for item in result.get("artifacts", [])]}), flush=True)


if __name__ == "__main__":
    main()
