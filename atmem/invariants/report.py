"""Content-minimized invariant conformance reports."""
from __future__ import annotations
import json, platform, time, uuid
from pathlib import Path
from .models import AssertionResult, InvariantRegistry
from .verdict import evaluate_registry

def build_report(registry: InvariantRegistry, results: list[AssertionResult]) -> dict:
    verdicts=evaluate_registry(registry,results)
    return {"format":"atmem-invariant-report-v1","run_id":f"inv_{uuid.uuid4().hex}","created_at":time.time(),"python":platform.python_version(),"offline":True,"verdicts":[v.to_dict() for v in verdicts],"blocking":any(v.status.value=="unproven" for v in verdicts)}
def write_report(path: str|Path, report: dict) -> None:
    # The contract contains IDs, status codes and evidence paths only. Reject
    # obvious accidental credentials before committing a CI artifact.
    encoded=json.dumps(report,indent=2,sort_keys=True)+"\n"
    lowered=encoded.lower()
    if any(marker in lowered for marker in ("authorization: bearer ","api_key=","private key-----","raw_prompt","memory_content")): raise ValueError("report contains forbidden scoped or secret content")
    Path(path).write_text(encoded,encoding="utf-8")
