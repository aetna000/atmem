"""Copy a whitelisted operator source bundle; launch bookkeeping on Windows."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tarfile

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.windows_execute import ROOT
from benchmarks.code_replay.windows_operator_copy import DESTINATION
from benchmarks.code_replay.windows_transport import framed_command, framed_input


SOURCE_ROOT = "/home/jt/atmem-benchmark-runtime-20261018/operator-source-v1"
PYTHON = "/home/jt/atmem-benchmark-runtime-20261018/product-build-arw_zz8r/venv/bin/python"
UPLOAD_PROGRAM = r'''
import hashlib,json,os,sys,tarfile
from pathlib import Path,PurePosixPath
base=Path(job['source_root'])
if str(base) not in {'/home/jt/atmem-benchmark-runtime-20261018/operator-source-v1',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v2',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v3',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v4',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v5',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v6',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v7',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v8',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v9',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v10',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v11',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v12',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13'}:
 raise ValueError('fixed benchmark source target required')
base.mkdir(mode=0o700,exist_ok=False)
seen=set();total=0
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
 for member in archive:
  name=member.name;path=PurePosixPath(name)
  if (name not in job['manifest'] or name in seen or not member.isfile()
   or path.is_absolute() or '..' in path.parts or str(path)!=name
   or not 0<=member.size<=10000000 or member.size!=job['manifest'][name]['bytes']):
   raise ValueError('source bundle member differs')
  target=base/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  digest=hashlib.sha256();size=0
  with archive.extractfile(member) as source,target.open('xb') as output:
   os.chmod(target,0o600)
   while True:
    raw=source.read(65536)
    if not raw:break
    digest.update(raw);size+=len(raw);output.write(raw)
  if size!=member.size or digest.hexdigest()!=job['manifest'][name]['sha256']:
   raise ValueError('source bundle bytes differ')
  seen.add(name);total+=size
  if total>32000000:raise ValueError('source bundle byte budget')
if seen!=set(job['manifest']):raise ValueError('source bundle incomplete')
print(json.dumps({'source_root':str(base),'files':len(seen),'bytes':total,
 'source_bundle_verified':True,'owner_config_changed':False,'model_calls':0}),flush=True)
'''
LAUNCH_PROGRAM = r'''
import os,subprocess,sys
from pathlib import Path
root=Path(job['source_root'])
if str(root) not in {'/home/jt/atmem-benchmark-runtime-20261018/operator-source-v1',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v2',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v3',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v4',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v5',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v6',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v7',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v8',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v9',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v10',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v11',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v12',
 '/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13'} or root.is_symlink():
 raise ValueError('fixed copied operator source root required')
os.chdir(root)
environment={**os.environ,'ATMEM_BENCHMARK_ROOT':job['state_root'],
 'ATMEM_BENCHMARK_PREFLIGHT':str(root/'preflight'),
 'ATMEM_BENCHMARK_LOCAL_WSL':'1','ATMEM_BENCHMARK_PER_RUN_VAULTS':'1',
 'PYTHONDONTWRITEBYTECODE':'1'}
dependencies=job.get('operator_dependencies')
prefix=''
if dependencies is not None:
 if dependencies!='/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1' or not Path(dependencies).is_dir():
  raise ValueError('qualified separate operator dependency directory required')
 prefix="sys.path.insert(0,"+repr(dependencies)+");"
bootstrap="import runpy,sys;"+prefix+"sys.path.insert(0,"+repr(str(root))+");runpy.run_module("+repr(job['module'])+",run_name='__main__')"
command=[job['python'],'-I','-c',bootstrap,*job['arguments']]
print('WINDOWS_OPERATOR_STARTED '+job['action'],flush=True)
process=subprocess.run(command,env=environment)
sys.exit(process.returncode)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("upload", "build", "boundary", "boundary-oci",
                                          "pyvista-inventory", "pyvista-reference", "pyvista-boundary", "exports", "checks", "stage", "readiness"))
    parser.add_argument("--dependency-repair-v2", action="store_true",
                        help="Explicit second launch after the proved import-only operator dependency failure")
    parser.add_argument("--source-bundle-v2", action="store_true",
                        help="Immutable operator-only terminal-pool correction; no product change")
    parser.add_argument("--source-bundle-v3", action="store_true",
                        help="Explicit lossless encoding repair, no changed tests or product")
    parser.add_argument('--source-bundle-v4', action='store_true',
                        help='Explicit zero-worker codec-guard correction')
    parser.add_argument('--source-bundle-v5', action='store_true',
                        help='Verified public source exports, not another scored candidate')
    parser.add_argument('--source-bundle-v6', action='store_true',
                        help='Public isolation and private proposal controls')
    parser.add_argument('--source-bundle-v7', action='store_true',
                        help='Exact retained grader preparation after zero-worker source guard stop')
    parser.add_argument('--source-bundle-v8',action='store_true',help='Explicit pre-Docker argv-size repair')
    parser.add_argument('--source-bundle-v9',action='store_true',help='Only zero-worker PyVista compact-program guards')
    parser.add_argument('--source-bundle-v10',action='store_true',help='Reuse completed public phases; only six unstarted private controls')
    parser.add_argument('--source-bundle-v11',action='store_true',help='Prospective 19-task lock and fresh installed staging')
    parser.add_argument('--source-bundle-v12',action='store_true',help='Continue only untouched staging blocks; preserve failures')
    parser.add_argument('--source-bundle-v13',action='store_true',help='Installed bridge checks on successful staged cases; no inference')
    args = parser.parse_args()
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / "operator-copy-v1/vault", vault_id="operator-copy-v1", scope=scope)
    run = "external-windows-operator-" + args.action + ("-v2-20261018" if args.dependency_repair_v2 else "-v1-20261018")
    source_root = SOURCE_ROOT
    if args.source_bundle_v13:
        if any([args.source_bundle_v2,args.source_bundle_v3,args.source_bundle_v4,args.source_bundle_v5,args.source_bundle_v6,args.source_bundle_v7,args.source_bundle_v8,args.source_bundle_v9,args.source_bundle_v10,args.source_bundle_v11,args.source_bundle_v12,args.dependency_repair_v2]) or args.action not in {'upload','readiness'}:
            raise ValueError('source v13 is only the installed no-model bridge readiness check')
        source_root=SOURCE_ROOT.replace('-v1','-v13')
        run=run.replace('-v1-20261018','-source-v13-20261018')
    if args.action=='readiness' and not args.source_bundle_v13:
        raise ValueError('readiness requires its explicit immutable operator source')
    if args.source_bundle_v12:
        if any([args.source_bundle_v2,args.source_bundle_v3,args.source_bundle_v4,args.source_bundle_v5,args.source_bundle_v6,args.source_bundle_v7,args.source_bundle_v8,args.source_bundle_v9,args.source_bundle_v10,args.source_bundle_v11,args.dependency_repair_v2]) or args.action not in {'upload','stage'}:
            raise ValueError('source v12 is only the unattempted-block continuation')
        source_root=SOURCE_ROOT.replace('-v1','-v12')
        run=run.replace('-v1-20261018','-source-v12-20261018')
    if args.source_bundle_v11:
        if any([args.source_bundle_v2,args.source_bundle_v3,args.source_bundle_v4,args.source_bundle_v5,args.source_bundle_v6,args.source_bundle_v7,args.source_bundle_v8,args.source_bundle_v9,args.source_bundle_v10,args.dependency_repair_v2]) or args.action not in {'upload','stage'}:
            raise ValueError('source v11 is only for the prospective fresh cohort staging')
        source_root=SOURCE_ROOT.replace('-v1','-v11')
        run=run.replace('-v1-20261018','-source-v11-20261018')
    if args.action=='stage' and not (args.source_bundle_v11 or args.source_bundle_v12):
        raise ValueError('fresh staging requires its explicit immutable operator source')
    if args.source_bundle_v10:
        if any([args.source_bundle_v2,args.source_bundle_v3,args.source_bundle_v4,args.source_bundle_v5,args.source_bundle_v6,args.source_bundle_v7,args.source_bundle_v8,args.source_bundle_v9,args.dependency_repair_v2]) or args.action not in {'upload','checks'}:
            raise ValueError('source v10 is only the explicit completed-public reuse correction')
        source_root=SOURCE_ROOT.replace('-v1','-v10')
        run=run.replace('-v1-20261018','-source-v10-20261018')
    if args.source_bundle_v9:
        if any([args.source_bundle_v2,args.source_bundle_v3,args.source_bundle_v4,args.source_bundle_v5,args.source_bundle_v6,args.source_bundle_v7,args.source_bundle_v8,args.dependency_repair_v2]) or args.action not in {'upload','checks'}:
            raise ValueError('source v9 is only the proved PyVista compact-program guard correction')
        source_root=SOURCE_ROOT.replace('-v1','-v9')
        run=run.replace('-v1-20261018','-source-v9-20261018')
    if args.source_bundle_v8:
        if args.source_bundle_v2 or args.source_bundle_v3 or args.source_bundle_v4 or args.source_bundle_v5 or args.source_bundle_v6 or args.source_bundle_v7 or args.dependency_repair_v2 or args.action not in {'upload','checks'}:
            raise ValueError('source v8 is only the explicit argv repair')
        source_root=SOURCE_ROOT.replace('-v1','-v8')
        run=run.replace('-v1-20261018','-source-v8-20261018')
    if args.source_bundle_v7:
        if args.source_bundle_v2 or args.source_bundle_v3 or args.source_bundle_v4 or args.source_bundle_v5 or args.source_bundle_v6 or args.dependency_repair_v2 or args.action not in {'upload','checks'}:
            raise ValueError('source v7 is only the retained-grader preparation correction')
        source_root=SOURCE_ROOT.replace('-v1','-v7')
        run=run.replace('-v1-20261018','-source-v7-20261018')
    if args.source_bundle_v6:
        if args.source_bundle_v2 or args.source_bundle_v3 or args.source_bundle_v4 or args.source_bundle_v5 or args.dependency_repair_v2 or args.action not in {'upload','checks'}:
            raise ValueError('source v6 is only for public/proposal controls')
        source_root = SOURCE_ROOT.replace('-v1','-v6')
        run = run.replace('-v1-20261018','-source-v6-20261018')
    if args.action == 'checks' and not (args.source_bundle_v6 or args.source_bundle_v7 or args.source_bundle_v8 or args.source_bundle_v9 or args.source_bundle_v10):
        raise ValueError('public/proposal checks require their immutable source bundle')
    if args.source_bundle_v5:
        if args.source_bundle_v2 or args.source_bundle_v3 or args.source_bundle_v4 or args.dependency_repair_v2 or args.action not in {'upload', 'exports'}:
            raise ValueError('source v5 is only for public source exports')
        source_root = SOURCE_ROOT.replace('-v1', '-v5')
        run = run.replace('-v1-20261018', '-source-v5-20261018')
    if args.action == 'exports' and not args.source_bundle_v5:
        raise ValueError('public exports require their immutable source bundle')
    if args.source_bundle_v4:
        if args.source_bundle_v2 or args.source_bundle_v3 or args.dependency_repair_v2 or args.action not in {'upload', 'pyvista-boundary'}:
            raise ValueError('source v4 is only the zero-worker guard correction')
        source_root = SOURCE_ROOT.replace('-v1', '-v4')
        run = run.replace('-v1-20261018', '-source-v4-20261018')
    if args.source_bundle_v3:
        if args.source_bundle_v2 or args.dependency_repair_v2 or args.action not in {'upload', 'pyvista-boundary'}:
            raise ValueError('source v3 is only the explicit encoding repair and its upload')
        source_root = SOURCE_ROOT.replace('-v1', '-v3')
        run = run.replace('-v1-20261018', '-source-v3-20261018')
    if args.source_bundle_v2:
        if args.dependency_repair_v2 or args.action not in {
            "upload", "pyvista-inventory", "pyvista-reference", "pyvista-boundary"
        }:
            raise ValueError("source v2 is only for first PyVista controls and its immutable upload")
        source_root = SOURCE_ROOT.replace("-v1", "-v2")
        run = run.replace("-v1-20261018", "-source-v2-20261018")
    if vault.inspect(principal, run):
        raise ValueError("operator action already retained; inspect its specific original process handle")
    def save(kind, payload):
        return vault.capture(run_id=run, kind=kind, principal=principal, payload=payload)
    if args.dependency_repair_v2:
        if args.action not in {"build", "boundary", "boundary-oci"}:
            raise ValueError("only the three proved import-only failures may use this repair")
        prior = vault.inspect(principal, "external-windows-operator-" + args.action + "-v1-20261018")
        terminal = [e["envelope"]["payload"] for e in prior
                    if e["envelope"]["event_type"] == "external.operator_launch_terminal"]
        dependency = vault.inspect(principal, "external-windows-operator-dependency-v1-20261018")
        qualified = [e["envelope"]["payload"] for e in dependency
                     if e["envelope"]["event_type"] == "external.operator_dependency_completed"]
        if (len(terminal) != 1 or terminal[0]["transport_exit"] != 1 or len(qualified) != 1
            or qualified[0].get("result", {}).get("qualified") is not True):
            raise ValueError("proved import-only failure and isolated dependency qualification required")
    if args.action == "upload":
        repo = Path.cwd()
        files = {"benchmarks/__init__.py": repo / "benchmarks/__init__.py"}
        for path in (repo / "benchmarks/code_replay").rglob("*.py"):
            if "__pycache__" not in path.parts:
                files[path.relative_to(repo).as_posix()] = path
        for name in ("source-runtime-projection-v2.md", "windows-pyvista-runtime-compatibility-v1.md",
                     "windows-confirmation-v2.md"):
            files["specs/042-atmem-code/" + name] = repo / "specs/042-atmem-code" / name
        preflight = Path("/Volumes/MEM/AtMem-Code-Replay-20261017/cross-repository-confirmation-eligibility-v2")
        for name in ("selection.json", "metadata.json"):
            files["preflight/" + name] = preflight / name
        if args.source_bundle_v11 or args.source_bundle_v12:
            public=Path('/Volumes/MEM/AtMem-Code-Replay-20261017/confirmation-public-issues-v1')
            declared=json.loads((public/'manifest.json').read_bytes())
            if len(declared['results'])!=40 or not all(row['qualified'] for row in declared['results']):
                raise ValueError('complete pinned original public issues required')
            files['public-issues/manifest.json']=public/'manifest.json'
            for row in declared['results']:
                name=row['instance_id']+'.json'
                if '/' in name or '\\' in name or '..' in name:raise ValueError('bounded issue filename required')
                path=public/name
                if path.stat().st_size!=row['bytes'] or sha256(path.read_bytes()).hexdigest()!=row['sha256']:
                    raise ValueError('public issue input manifest differs')
                files['public-issues/'+name]=path
        if args.source_bundle_v5:
            public = Path('/Volumes/MEM/AtMem-Code-Replay-20261017/confirmation-public-git-v1')
            declared = json.loads((public/'manifest.json').read_bytes())
            if len(declared['results']) != 40 or not all(row['qualified'] for row in declared['results']):
                raise ValueError('complete original public Git metadata required')
            files['public-git/manifest.json'] = public/'manifest.json'
            for row in declared['results']:
                name = row['instance_id']+'.json'
                if '/' in name or '\\' in name or '..' in name:
                    raise ValueError('bounded public metadata filename required')
                path = public/name
                if path.stat().st_size != row['bytes'] or sha256(path.read_bytes()).hexdigest() != row['sha256']:
                    raise ValueError('public metadata manifest differs')
                files['public-git/'+name] = path
        manifest = {}
        for name, path in files.items():
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 10_000_000:
                raise ValueError("bounded regular whitelisted source member required")
            manifest[name] = {"bytes": path.stat().st_size, "sha256": sha256(path.read_bytes()).hexdigest()}
        if sum(item["bytes"] for item in manifest.values()) > 32_000_000:
            raise ValueError("operator source bundle byte budget")
        job = {"program": UPLOAD_PROGRAM, "source_root": source_root, "manifest": manifest}
        save("external.operator_source_planned", {"driver_source": Path(__file__).read_text(),
             "job": job, "credentials_or_personal_files_included": False})
        process = subprocess.Popen(framed_command(), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            process.stdin.write(framed_input(job))
            with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
                for name, path in files.items():
                    info = tarfile.TarInfo(name)
                    info.size, info.mode = manifest[name]["bytes"], 0o600
                    with path.open("rb") as reader:
                        archive.addfile(info, reader)
            process.stdin.close()
            process.stdin = None
            stdout, stderr = process.communicate(timeout=180)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        result = {"transport_exit": process.returncode, "stdout_base64": base64.b64encode(stdout).decode(),
                  "stderr_base64": base64.b64encode(stderr).decode()}
        if process.returncode == 0:
            result["result"] = json.loads(stdout)
        save("external.operator_source_completed", result)
        print(json.dumps(result.get("result", {"transport_exit": process.returncode})), flush=True)
        if process.returncode:
            raise ValueError("source copy failed; original is unchanged")
        return
    module = "benchmarks.code_replay.windows_runtime_projection"
    arguments = ["--operator-v2"]
    if args.action=='readiness':
        module='benchmarks.code_replay.confirmation_bridge_readiness'
        arguments=[]
    elif args.action == 'stage':
        module='benchmarks.code_replay.confirmation_staging'
        arguments=[]
        if args.source_bundle_v12:arguments.append('--continue-unattempted')
    elif args.action == 'checks':
        module = 'benchmarks.code_replay.windows_confirmation_checks'
        arguments = []
        if args.source_bundle_v8:arguments.append('--argv-v2')
        if args.source_bundle_v9 or args.source_bundle_v10:arguments.append('--pyvista-argv-v3')
    elif args.action == 'exports':
        module = 'benchmarks.code_replay.windows_confirmation_exports'
        arguments = []
    elif args.action == "build":
        module = "benchmarks.code_replay.windows_pyvista_build"
    else:
        phase = args.action.replace("pyvista-", "").replace("-oci", "")
        arguments.extend(["--phase", phase])
        if args.action.startswith("pyvista-"):
            arguments.append("--pyvista-derived")
        elif args.action.endswith("-oci"):
            arguments.append("--supplemental-oci")
        if args.source_bundle_v3 or args.source_bundle_v4:
            arguments.append('--lossless-v3')
        if args.source_bundle_v4:
            arguments.append('--codec-guard-v4')
    job = {"program": LAUNCH_PROGRAM, "source_root": source_root, "state_root": DESTINATION,
           "python": PYTHON, "module": module, "arguments": arguments, "action": args.action}
    # Future first launches also use the already-qualified separate operator
    # dependency, without changing the frozen preview site-packages.
    job["operator_dependencies"] = "/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1"
    save("external.operator_launch_planned", {"driver_source": Path(__file__).read_text(), "job": job,
        "new_solver_calls": 0, "large_evidence_processing": "authorized Windows host"})
    process = subprocess.run(framed_command(), input=framed_input(job))
    save("external.operator_launch_terminal", {"transport_exit": process.returncode, "action": args.action})
    if process.returncode:
        raise ValueError("Windows operator failed; inspect retained remote run, never auto-restart")


if __name__ == "__main__":
    main()
