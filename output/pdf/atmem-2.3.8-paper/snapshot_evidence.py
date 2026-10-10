"""Export the exact repository evidence used by the manuscript, without checkout changes."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
REV = "267c5b3ac08e8cac26dfee13c6eac2842d4bb876"
FILES = [
    "docs/releases/v2.3.8.md",
    "docs/releases/v2.3.7-to-v2.3.8-technical-report.md",
    "benchmarks/retrieval_quality/baselines/five-percent-results-20261010.json",
    "benchmarks/retrieval_quality/baselines/dolphinbench-final-b97d35e.json",
    "benchmarks/retrieval_quality/baselines/agmi-2.3.8-20261010.json",
    "benchmarks/retrieval_quality/reports/five-percent-results-20261010.md",
    "benchmarks/retrieval_quality/reports/benchmark-3pct-complete-20260930.md",
    "benchmarks/retrieval_quality/protocols/longmemeval-v2-development-5pct-v1.json",
    "benchmarks/retrieval_quality/protocols/dolphinbench-development-5pct-v1.json",
    "research/reference_parity/sources.json",
    "research/production_benchmarks/adapters/longmemeval_mem0.py",
    "research/production_benchmarks/prepare_longmem_memories.py",
    "research/production_benchmarks/local_embedding_proxy.py",
    "research/production_benchmarks/dolphinbench.py",
    "atmem/memory.py",
] + ["atmem/context_engine/"+p+".py" for p in
     ["contracts","formation","planner","pools","retrieval","packing","sufficiency","service","profiles"]]

inventory=[]
for relative in FILES:
    content=subprocess.check_output(["git","show",f"{REV}:{relative}"],cwd=REPO)
    dest=ROOT/"evidence"/relative
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(content)
    inventory.append({"revision":REV,"path":relative,"sha256":hashlib.sha256(content).hexdigest()})
old=subprocess.check_output(["git","show","v2.3.7:atmem/memory.py"],cwd=REPO)
(ROOT/"evidence"/"atmem-2.3.7-memory.py").write_bytes(old)
inventory.append({"revision":"cb1cf0fc6e3e12dd0a52140bc0eda4797d2e887b","path":"atmem-2.3.7-memory.py","sha256":hashlib.sha256(old).hexdigest()})
(ROOT/"evidence-inventory.json").write_text(json.dumps(inventory,indent=2)+"\n")

data=json.loads((ROOT/"evidence"/FILES[2]).read_text())
assert data["longmemeval_v2"]["arms"]["atmem-typed-local"]["correct"] == 5
assert data["longmemeval_v2"]["arms"]["agentrunbook-r"]["correct"] == 4
assert data["longmemeval_v2"]["arms"]["mem0-oss"]["correct"] == 1
assert data["dolphinbench_final_b97d35e"]["arms"]["atmem"]["tasks_passed"] == 9
assert data["dolphinbench_final_b97d35e"]["arms"]["mem0-oss"]["tasks_passed"] == 7
print(f"Exported and hashed {len(inventory)} evidence files; displayed counts agree.")
