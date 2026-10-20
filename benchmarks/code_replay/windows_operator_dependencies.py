"""Install the operator-only YAML dependency into a separate benchmark directory."""
import base64
import json
from pathlib import Path
import subprocess

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.windows_execute import ROOT
from benchmarks.code_replay.windows_operator_host import PYTHON
from benchmarks.code_replay.windows_transport import framed_command, framed_input


PROGRAM = r'''
import hashlib,json,os,shutil,subprocess
from pathlib import Path
base=Path('/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1')
if base.parent.resolve()!=base.parent or base.parent.is_symlink():
 raise ValueError('exact benchmark dependency parent required')
if min(shutil.disk_usage('/tmp').free,shutil.disk_usage('/mnt/c').free)<8*1024**3:
 raise ValueError('physical/WSL disk guard')
if Path('/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1/confirmation-v1/run-vaults-v1').exists():
 raise ValueError('dependency import repair requires zero remote operational runs started')
python=job['python']
inspection="import importlib.metadata as m,json;print(json.dumps(sorted([{'name':d.metadata['Name'].lower(),'version':d.version} for d in m.distributions()],key=lambda r:r['name'])))"
before=json.loads(subprocess.check_output([python,'-I','-c',inspection],timeout=30))
base.mkdir(mode=0o700,exist_ok=False)
command=[python,'-I','-m','pip','--isolated','install','--only-binary=:all:',
 '--no-deps','--no-cache-dir','--disable-pip-version-check','--index-url','https://pypi.org/simple',
 '--target',str(base),'--report',str(base/'install-report.json'),'PyYAML==6.0.2']
process=subprocess.run(command,capture_output=True,timeout=120)
if process.returncode:
 print(json.dumps({'qualified':False,'pip_exit':process.returncode,
  'stdout':process.stdout.decode(errors='replace'),'stderr':process.stderr.decode(errors='replace')}))
else:
 after=json.loads(subprocess.check_output([python,'-I','-c',inspection],timeout=30))
 probe="import sys;sys.path.insert(0,"+repr(str(base))+");import yaml,json;print(json.dumps({'version':yaml.__version__,'file':yaml.__file__}))"
 actual=json.loads(subprocess.check_output([python,'-I','-c',probe],timeout=30))
 if before!=after or actual['version']!='6.0.2' or not Path(actual['file']).is_relative_to(base):
  raise ValueError('operator dependency isolated-version proof failed')
 print(json.dumps({'qualified':True,'operator_dependency':actual,'preview_dependencies_before':before,
  'preview_dependencies_after':after,'preview_dependency_versions_unchanged':True,
  'pip_stdout':process.stdout.decode(errors='replace'),'pip_stderr':process.stderr.decode(errors='replace'),
  'install_report':json.loads((base/'install-report.json').read_text()),'model_calls':0}))
'''


def main():
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / "operator-copy-v1/vault", vault_id="operator-copy-v1", scope=scope)
    run = "external-windows-operator-dependency-v1-20261018"
    if vault.inspect(principal, run):
        raise ValueError("operator dependency preparation already recorded")
    vault.capture(run_id=run, kind="external.operator_dependency_planned", principal=principal, payload={
        "driver_source": Path(__file__).read_text(), "program": PROGRAM,
        "python": PYTHON, "dependency": "PyYAML==6.0.2",
        "reason": "three launch wrappers failed at import before any operational run began",
        "product_preview_dependency_change_authorized": False})
    process = subprocess.run(framed_command(), input=framed_input({"program": PROGRAM, "python": PYTHON}),
                             capture_output=True, timeout=180)
    row = {"transport_exit": process.returncode, "stdout_base64": base64.b64encode(process.stdout).decode(),
           "stderr_base64": base64.b64encode(process.stderr).decode()}
    if process.returncode == 0:
        row["result"] = json.loads(process.stdout)
    vault.capture(run_id=run, kind="external.operator_dependency_completed", principal=principal, payload=row)
    result = row.get("result", {})
    print(json.dumps({"transport_exit": process.returncode, "qualified": result.get("qualified"),
                     "preview_dependency_versions_unchanged": result.get("preview_dependency_versions_unchanged")}), flush=True)
    if result.get("qualified") is not True:
        raise ValueError("isolated operator dependency did not qualify")


if __name__ == "__main__":
    main()
