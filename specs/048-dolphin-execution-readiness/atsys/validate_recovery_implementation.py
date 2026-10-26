"""Independent acceptance: focused tests AND real retained offline export. No workload."""
from pathlib import Path
import json
import os
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
checks = ["tests/benchmarking/test_dolphin_parent_controller.py", "tests/benchmarking/test_dolphin_tool_defaults.py", "tests/benchmarking/test_dolphinbench_export.py", "tests/benchmarking/test_dolphin_pilot_recovery.py", "tests/benchmarking/test_execution_readiness.py", "tests/benchmarking/test_dolphinbench_campaign_gate.py", "tests/benchmarking/test_dolphin_campaign_resume.py", "tests/benchmarking/test_dolphinbench_gateway.py"]
subprocess.run([sys.executable,"-m","pytest","-q",*checks],check=True,cwd=ROOT,env={**os.environ,"PYTEST_DISABLE_PLUGIN_AUTOLOAD":"1"})
inputs=json.loads((ROOT/"specs/048-dolphin-execution-readiness/recovery-inputs.json").read_text())
from benchmarks.dolphinbench.pilot_recovery import historical_condition,reconstruct_129
from benchmarks.dolphinbench.readiness import read
bundle=Path(inputs["historical_bundle"])
old,_=historical_condition(bundle)
sys.path.insert(0,old["bindings"]["upstream_root"])
from harness.submission import read_release
release=read_release(Path(old["bindings"]["upstream_root"]))
spec=next(s for s in release["morgan"]["tests"] if str(s["id"]).zfill(3)=="129")
parent=Path("/Volumes/MEM/atmem-dolphinbench-20261020/readiness-pilot20-atsys-20261026-v2")
evidence,proof=reconstruct_129(parent,read(inputs["proofs_129"]),Path(inputs["budget_backup"]),spec,sorted((Path(old["bindings"]["upstream_root"])/"mock_mcp").glob("repair*.py")))
assert proof["provider_calls"]==0 and proof["app_calls_dispatched"]==0
assert evidence["row"]["test_id"]=="129"
assert read(parent/"native/tests/morgan/129/app-evidence/outcome.json")["completed"] is False
print("Validated focused tests and actual retained task129 offline reconstruction; no workload or replay.")
