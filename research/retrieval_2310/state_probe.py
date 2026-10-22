"""Qualify product source-state classification on already-recorded evidence.

No answer keys, new reader run or application action. This is contract/transport
qualification, not a scored task result. All generated artifacts stay private.
"""
from pathlib import Path
import argparse
import json

from atmem.context_engine.state_assessment import validate_state_assessment
from benchmarks.dolphinbench.gateway import Gateway,save_new
from benchmarks.dolphinbench.recording import BudgetLedger
from scripts.openrouter_azure_sol import load_key
from .assessor_provider import AtBotStateAssessor
from .grade_run import claim_budget,settle_budget


def find_evidence(value):
    if isinstance(value,str):
        if value.startswith('<untrusted_tool_result ') and value.rstrip().endswith('</untrusted_tool_result>'):
            value=value.split('\n\n',1)[1].rsplit('</untrusted_tool_result>',1)[0].strip()
        try:return find_evidence(json.loads(value))
        except (ValueError,TypeError):return None
    if isinstance(value,dict):
        if value.get('format')=='atmem-evidence-discovery-v1':return value.get('evidence')
        for child in value.values():
            result=find_evidence(child)
            if result:return result
    if isinstance(value,list):
        for child in value:
            result=find_evidence(child)
            if result:return result
    return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--env-file',type=Path,required=True)
    args=parser.parse_args()
    args.output.resolve().relative_to(Path('/Volumes/AtMemDolphin'))
    if args.output.exists():raise ValueError('fresh probe output required')
    root=args.case.resolve()
    result=None;query=None
    for file in sorted((root/'calls').rglob('request.json'),key=lambda p:p.stat().st_mtime):
        request=json.loads(file.read_text())
        query=next((m['content'] for m in request['messages'] if m['role']=='user'),None)
        result=find_evidence(request['messages'])
        if result:break
    if not result or not isinstance(query,str):raise ValueError('recorded authorized source evidence required')
    identity={'format':'source-state-probe-v1','role':'classification-not-reader-or-grader',
              'provider':'Azure-only OpenRouter','model':'openai/gpt-5.6-sol',
              'cap_usd':1,'literal_quote_validation':True,'scored_quality_claim':False}
    master=Path('/Volumes/AtMemDolphin/retrieval-2310-budget.db')
    claim_budget(master,args.output.name,cap_usd='1')
    save_new(args.output/'identity.json',identity)
    save_new(args.output/'input.json',{'query':query,'evidence':result})
    book=BudgetLedger(args.output/'budget.db',cap_usd=1,identity=identity);book.close()
    gateway=Gateway(key=load_key(args.env_file),output=args.output/'calls',
        ledger_path=args.output/'budget.db',campaign_identity=identity,cap_usd=1,
        phase='state-assessment',model='openai/gpt-5.6-sol',input_per_million=5,
        output_per_million=30,output_token_cap=4000).start()
    try:
        value=AtBotStateAssessor(gateway)(query,result)
        validate_state_assessment(value,result)
        save_new(args.output/'result.json',value)
        print(json.dumps({'literal_quote_contract_passed':True,'rows':len(value['rows']),
                          'labels':[r['applicability'] for r in value['rows']],
                          'scored_task_success':False}))
    finally:
        gateway.stop()
        book=BudgetLedger(args.output/'budget.db',cap_usd=1,identity=identity)
        try:
            save_new(args.output/'costs.json',book.totals())
            amount=book.connection.execute("SELECT COALESCE(SUM(CASE WHEN state IN ('completed','overrun') THEN actual WHEN state='reserved' THEN reserved ELSE 0 END),0) FROM calls").fetchone()[0]
            settle_budget(master,args.output.name,amount)
        finally:book.close()


if __name__=='__main__':main()
