"""Bounded derived evaluator images; no product change or model invocation."""
import base64
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.derived_runtime import distribution_change_qualified, vtk_recipe
from benchmarks.code_replay.external_qualification import worker_command
from benchmarks.code_replay.runtime_projection_control import projected_control_source, projection_modules
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
from benchmarks.code_replay.windows_pyvista_wheels import RUN as WHEELS_RUN
from benchmarks.code_replay.windows_runtime_projection import PRIOR
from benchmarks.code_replay.windows_transport import controller_source, framed_command, framed_input


RUN = "external-windows-pyvista-vtk931-build-v1-20261018"
OPERATOR_RUN = "external-windows-pyvista-vtk931-build-operator-v2-20261018"


def audit_program(source):
    return (
        "import sys,types,json,importlib.metadata,subprocess\n"
        "from pathlib import Path\n"
        "for name in ('benchmarks','benchmarks.code_replay'):\n"
        " module=types.ModuleType(name);module.__path__=[];sys.modules[name]=module\n"
        "for name,source in " + repr(projection_modules()) + ":\n"
        " module=types.ModuleType(name);sys.modules[name]=module\n"
        " exec(compile(source,name+'.py','exec'),module.__dict__)\n"
        "control={'__name__':'operator_package_source_audit'}\n"
        "exec(compile(" + repr(source) + ",'operator_package_source_audit.py','exec'),control)\n"
        "job=json.load(sys.stdin)\n"
        "summary=control['tracked_base'](job['base_commit'])\n"
        "site=str(Path(sys.prefix)/'lib'/('python%d.%d'%sys.version_info[:2])/'site-packages')\n"
        "versions=sorted([{'name':d.metadata['Name'],'version':d.version}\n"
        " for d in importlib.metadata.distributions(path=[site])],key=lambda r:r['name'].lower())\n"
        "check=subprocess.run([sys.executable,'-I','-m','pip','check'],capture_output=True,timeout=30)\n"
        "emit=sys.modules['benchmarks.code_replay.result_transport'].result_printer()\n"
        "emit(json.dumps({'instance_id':job['instance_id'],'summary':summary,\n"
        " 'distributions':versions,'pip_check':{'exit_code':check.returncode,\n"
        " 'stdout':check.stdout.decode(errors='replace'),'stderr':check.stderr.decode(errors='replace')},\n"
        " 'runtime_manifest':control['RUNTIME_MANIFEST'],'model_calls':0,'task_tests_run':0}),flush=True)\n"
    )


def build_program():
    return controller_source() + r'''
import hashlib,os,re,signal
from pathlib import Path
codec={}
exec(compile(job['codec_source'],'operator_codec.py','exec'),codec)
def guard():
 if min(shutil.disk_usage('/tmp').free,shutil.disk_usage('/mnt/c').free)<8*1024**3:
  raise ValueError('physical/WSL disk below 8GiB')
def audit(command,name):
 row=execute_worker(command,job['audit_payload'],name)
 if row.get('reason') or row.get('exit_code')!=0 or row.get('raw_output_truncated'):
  raise ValueError('installed package/source audit failed: '+str(row))
 row['worker']=codec['decode_result'](base64.b64decode(row['raw_output_base64'],validate=True))
 return row
result={'instance_id':job['instance_id'],'qualified':False,'model_calls':0}
try:
 guard()
 base=Path('/home/jt/atmem-benchmark-runtime-20261018/pyvista-vtk931-v1')
 if base.is_symlink() or base.resolve()!=base or not base.is_dir():
  raise ValueError('exact verified benchmark wheel directory required')
 for item in job['wheels']:
  path=base/item['filename']
  if path.is_symlink() or not path.is_file() or path.stat().st_size!=item['bytes']:
   raise ValueError('wheel member differs')
  digest=hashlib.sha256()
  with path.open('rb') as reader:
   for chunk in iter(lambda:reader.read(65536),b''):digest.update(chunk)
  if digest.hexdigest()!=item['sha256']:raise ValueError('wheel digest differs')
 case=base/(job['instance_id']+job.get('case_suffix',''))
 if case.parent!=base:raise ValueError('exact benchmark case directory required')
 case.mkdir(mode=0o700,exist_ok=False)
 recipe=job['recipe']
 recipe=recipe.replace('\nCOPY ','\nLABEL atmem.benchmark.build='+job['owner_label']+'\nCOPY ',1)
 recipe_path=case/'Dockerfile';recipe_path.write_text(recipe)
 result.update(recipe=recipe,recipe_sha256=hashlib.sha256(recipe.encode()).hexdigest(),
  original_image=job['image'],before=audit(job['audit_before_command'],job['audit_before_name']))
 versions={re.sub('[-_.]+','-',r['name']).lower():r['version'] for r in result['before']['worker']['distributions']}
 if any(versions.get(k)!=v for k,v in {'vtk':'9.4.2','setuptools':'78.1.1','wheel':'0.45.1'}.items()):
  raise ValueError('original dependency versions differ from fixed protocol')
 inspected=subprocess.run(['docker','image','inspect',job['tag']],capture_output=True,timeout=20)
 if inspected.returncode==0 or b'No such image' not in inspected.stderr:
  raise ValueError('unique unoccupied benchmark image tag required')
 command=['docker','build','--network=none','--pull=false','--force-rm',
  '--memory=2g','--cpu-period=100000','--cpu-quota=100000','--platform=linux/amd64',
  '--iidfile',str(case/'image-id'),'--tag',job['tag'],'--file',str(recipe_path),str(base)]
 result['build_command']=command
 with tempfile.TemporaryFile(dir='/dev/shm') as log:
  process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
   start_new_session=True,env={**os.environ,'DOCKER_BUILDKIT':'0'})
  started=time.monotonic();reason=None
  try:
   while process.poll() is None:
    if time.monotonic()-started>300:reason='build_timeout'
    elif os.fstat(log.fileno()).st_size>8000000:reason='build_output_budget'
    elif min(shutil.disk_usage('/tmp').free,shutil.disk_usage('/mnt/c').free)<8*1024**3:reason='build_disk_guard'
    if reason:
     os.killpg(process.pid,signal.SIGTERM)
     try:process.wait(timeout=5)
     except subprocess.TimeoutExpired:
      os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
     break
    time.sleep(.25)
  finally:
   process.wait()
  size=os.fstat(log.fileno()).st_size;log.seek(0);raw=log.read(8000000)
  result['build']={'exit_code':process.returncode,'reason':reason,'elapsed_s':time.monotonic()-started,
   'output_base64':base64.b64encode(raw).decode(),'output_bytes':size,'output_truncated':size>len(raw)}
 if reason or process.returncode or size>len(raw):raise ValueError('derived image build failed')
 image=(case/'image-id').read_text().strip()
 if re.fullmatch('sha256:[0-9a-f]{64}',image) is None:raise ValueError('exact derived local image ID required')
 inspected=subprocess.run(['docker','image','inspect',job['tag']],capture_output=True,timeout=20,check=True)
 info=json.loads(inspected.stdout)[0]
 if info['Id']!=image or info['Architecture']!='amd64' or info['Os']!='linux':
  raise ValueError('derived image content/platform identity differs')
 result['derived_image_id']=image
 result['derived_image']={k:info[k] for k in ('Id','Architecture','Os','Size','Config')}
 after_command=[image if value==job['image'] else value for value in job['audit_after_command']]
 result['after']=audit(after_command,job['audit_after_name'])
 before,after=result['before']['worker'],result['after']['worker']
 verifier={}
 exec(compile(job['verifier_source'],'fixed_distribution_check.py','exec'),verifier)
 if not verifier['distribution_change_qualified'](before['distributions'],after['distributions']):
  raise ValueError('unexpected installed distribution change')
 if before['summary']!=after['summary'] or before['runtime_manifest']!=after['runtime_manifest']:
  raise ValueError('repository source/runtime identity changed')
 if before['pip_check']!=after['pip_check']:
  raise ValueError('dependency check changed unexpectedly')
 if info['Config'].get('Env',[]).count('PIP_NO_INDEX=1')!=1 or info['Config'].get('Env',[]).count('PIP_FIND_LINKS=/opt/atmem-benchmark-wheels')!=1:
  raise ValueError('derived offline setup environment absent')
 result.update(qualified=True,installed_distributions_verified=True,source_runtime_unchanged=True,
  tests_changed=False,original_image_retained=True)
except Exception as exc:
 result['failure']=type(exc).__name__+': '+str(exc)
finally:
 # Only containers carrying this new build's unique owner label are in scope.
 listing=subprocess.run(['docker','ps','-a','--no-trunc','--filter',
  'label=atmem.benchmark.build='+job['owner_label'],'--format','{{.ID}}'],capture_output=True,timeout=20)
 leftovers=listing.stdout.decode().split()
 if listing.returncode or any(re.fullmatch('[0-9a-f]{64}',value) is None for value in leftovers):
  result.update(qualified=False,cleanup_error='build_container_inventory_failed')
 else:
  for container in leftovers:
   removed=subprocess.run(['docker','rm','-f',container],capture_output=True,timeout=20)
   if removed.returncode:result.update(qualified=False,cleanup_error='owned_build_container_cleanup_failed')
 result['owned_build_containers_removed']=leftovers
print(json.dumps(result),flush=True)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-v2", action="store_true",
                        help="Explicit Windows-local per-run bookkeeping after the recorded Mac resource stop")
    args = parser.parse_args()
    run_id = OPERATOR_RUN if args.operator_v2 else RUN
    if args.operator_v2 and (os.environ.get("ATMEM_BENCHMARK_LOCAL_WSL") != "1"
                            or os.environ.get("ATMEM_BENCHMARK_PER_RUN_VAULTS") != "1"):
        raise ValueError("operator-v2 requires Windows-local per-run evidence")
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    from benchmarks.code_replay.run_evidence import operational_evidence
    vault = operational_evidence(EVIDENCE_ROOT, vault_id="confirmation-v1", scope=scope, writing_run=run_id)
    if vault.inspect(principal, run_id):
        raise ValueError("derived builds already dispatched; inspect original handles")
    prior = [event["envelope"] for event in vault.inspect(principal, PRIOR)]
    plan = next(row["payload"] for row in prior if row["event_type"] == "external.confirmation_reference_planned")
    images, materials = {}, {}
    for row in prior:
        item = row["payload"]
        if row["event_type"] == "external.confirmation_reference_dispatch" and item["instance_id"].startswith("pyvista__"):
            images[item["instance_id"]] = next(value for value in item["job"]["command"] if value.startswith("swebench/") and "@sha256:" in value)
        elif row["event_type"] == "external.confirmation_private_material" and item["instance_id"].startswith("pyvista__"):
            materials[item["instance_id"]] = item
    wheels_events = [event["envelope"] for event in vault.inspect(principal, WHEELS_RUN)]
    wheel_rows = [row["payload"] for row in wheels_events if row["event_type"] == "external.pyvista_wheels_completed"]
    if len(wheel_rows) != 1 or wheel_rows[0].get("transport_exit") != 0:
        raise ValueError("complete verified wheel preparation required")
    wheel_transport = json.loads(base64.b64decode(wheel_rows[0]["stdout_base64"], validate=True))
    if wheel_transport != wheel_rows[0]["result"] or wheel_transport.get("all_wheels_verified") is not True:
        raise ValueError("wheel metadata differs from retained transport")
    wheels = [{key: item[key] for key in ("package", "version", "filename", "bytes", "sha256")}
              for item in wheel_transport["artifacts"]]
    if set(images) != set(materials) or len(images) != 8:
        raise ValueError("all eight original PyVista images/materials required")
    source, registration = projected_control_source(plan["worker_source"], plan["operator_task_registration"])
    audit = audit_program(source)
    if len(audit.encode()) > 110_000:
        raise ValueError("audit program exceeds the bounded container argument budget")
    program = build_program()
    # verifier is self-contained: imports needed only by other module functions
    # are harmless host imports unless stripped for the isolated WSL namespace.
    verifier = Path(__file__).with_name("derived_runtime.py").read_text()
    verifier = verifier.replace("from benchmarks.code_replay.external_qualification import worker_command\n", "")
    def save(kind, payload):
        return vault.capture(run_id=run_id, kind=kind, principal=principal, payload=payload)
    save("external.pyvista_build_planned", {
        "driver_source": Path(__file__).read_text(), "program": program, "audit_program": audit,
        "registration": registration, "wheels": wheels, "images": images,
        "protocol": Path("specs/042-atmem-code/windows-pyvista-runtime-compatibility-v1.md").read_text(),
        "max_parallel_builds": 2, "model_calls": 0, "original_images_retained": True})
    jobs = []
    for identity, image in images.items():
        before_name, after_name = ("atmem-reference-control-" + uuid4().hex for _ in range(2))
        before_command, after_command = worker_command(image, before_name, audit), worker_command(image, after_name, audit)
        before_command.insert(3, "--read-only")
        after_command.insert(3, "--read-only")
        job = {
            "program": program, "instance_id": identity, "image": image, "wheels": wheels,
            "tag": "atmem-benchmark-pyvista-vtk931:" + identity.rsplit("-", 1)[-1] + ("-v2" if args.operator_v2 else "-v1"),
            "case_suffix": "-operator-v2" if args.operator_v2 else "",
            "owner_label": uuid4().hex, "recipe": vtk_recipe(image, wheels),
            "codec_source": Path(__file__).with_name("result_transport.py").read_text(),
            "verifier_source": verifier, "audit_before_name": before_name, "audit_after_name": after_name,
            "audit_before_command": before_command, "audit_after_command": after_command,
            "audit_payload": {"instance_id": identity, "base_commit": materials[identity]["base_commit"]},
        }
        save("external.pyvista_build_dispatch", {"instance_id": identity, "job": job})
        jobs.append(job)
    def execute(job):
        try:
            proc = subprocess.run(framed_command(), input=framed_input(job), capture_output=True, timeout=730)
            row = {"instance_id": job["instance_id"], "transport_exit": proc.returncode,
                   "stdout_base64": base64.b64encode(proc.stdout).decode(),
                   "stderr_base64": base64.b64encode(proc.stderr).decode()}
            if proc.returncode == 0:
                row["result"] = json.loads(proc.stdout)
        except subprocess.TimeoutExpired as exc:
            row = {"instance_id": job["instance_id"], "transport_exit": None, "failure": "transport_timeout",
                   "stdout_base64": base64.b64encode(exc.stdout or b"").decode(),
                   "stderr_base64": base64.b64encode(exc.stderr or b"").decode()}
        return row
    qualified = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(execute, job) for job in jobs]):
            row = future.result()
            save("external.pyvista_build_result", row)
            result = row.get("result", {})
            if row["transport_exit"] == 0 and result.get("qualified") is True:
                qualified.append(row["instance_id"])
            print(json.dumps({"instance_id": row["instance_id"], "transport_exit": row["transport_exit"],
                              "qualified": result.get("qualified"), "failure": result.get("failure"),
                              "derived_image_id": result.get("derived_image_id")}), flush=True)
    summary = {"original_candidates": 8, "qualified_identities": sorted(qualified),
               "model_calls": 0, "task_tests_run": 0, "confirmation_complete": False}
    save("external.pyvista_build_completed", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
