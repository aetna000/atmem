import json
from atmem.invariants import AssertionResult,build_report,load_registry,write_report
def test_offline_content_minimized_report(tmp_path):
    registry=load_registry(); results=[AssertionResult(i.assertions[0],"base",True,True,"synthetic") for i in registry.invariants]; report=build_report(registry,results); target=tmp_path/"r.json"; write_report(target,report); text=target.read_text(); assert not report["blocking"] and "raw_prompt" not in text and "api_key" not in text
