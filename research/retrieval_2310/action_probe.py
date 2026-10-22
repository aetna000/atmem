"""Blind, retrospective qualification of product draft-to-evidence findings.

No repairs, new reader executions or task-success claims. Only saved request,
retrieved sources and recorded action arguments reach the model. Grades are
read only after every review is retained, and are never put in model input.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

from benchmarks.dolphinbench.gateway import Gateway, save_new
from benchmarks.dolphinbench.recording import BudgetLedger
from scripts.openrouter_azure_sol import load_key
from .grade_run import claim_budget, settle_budget
from .preflight import Review,validate_review


def configuration(roots,*,material_profile,reference_identity):
    """Freeze terminal original records and the exact read-only probe profile."""
    if material_profile not in {'legacy-followup-v1','observed-pre-action-v2'}:
        raise ValueError('unknown review material profile')
    if material_profile=='observed-pre-action-v2' and not reference_identity:
        raise ValueError('observed original host identity required')
    pinned={}
    for root in roots:
        root=Path(root).resolve()
        if not any(root.is_relative_to(base) for base in (
                Path('/Volumes/AtMemDolphin'),Path('/Volumes/AtMemBenchRuntime'))):
            raise ValueError('retained private benchmark root required')
        if str(root) in pinned:raise ValueError('duplicate probe root')
        result=root/'result.json';manifest=root/'stage-manifest.json'
        if not result.is_file() or not manifest.is_file():
            raise ValueError('completed original runs required')
        if list((root/'tests').rglob('*.inflight')):
            raise ValueError('uncertain original action; reconcile before review')
        if material_profile=='observed-pre-action-v2' and json.loads(manifest.read_text()).get(
                'reference_host_identity')!=reference_identity:
            raise ValueError('original reference identity differs')
        paths=[result,manifest,*sorted((root/'tests').glob('*/*.json')),
            *sorted((root/'native/tests').glob('*/*/pre-action-ruling.json'))]
        pinned[str(root)]={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in paths}
    if not pinned:raise ValueError('at least one terminal original run required')
    return {'stage':'retrospective-action-grounding-qualification',
        'format':'retrospective-grounding-probe-v1','model':'openai/gpt-5.6-sol',
        'reasoning':'medium','provider':'Azure-only OpenRouter','cap_usd':2,
        'explicit_remote_egress':True,'grades_not_model_input':True,
        'application_actions_reexecuted':False,'task_success_claim':False,
        'material_profile':material_profile,'reference_identity':reference_identity,
        'action_coverage':('final-recorded-action-with-observed-prior-results'
            if material_profile=='observed-pre-action-v2' else 'legacy-all-recorded-actions'),
        'original_records':pinned}


def pre_action_material(record,initial_ruling,*,observed_host_identity=None,action_index=None):
    """One recorded app action, with all observed sources before its decision.

    Unlike the legacy probe, include the initial memory packet. Never add facts
    from annotations or later tool responses, nor silently trim sources to fit.
    This creates a retrospective input, not an execution hook or repaired task.
    """
    from .exposure_audit import _discovery_name,_payloads
    messages=record['row']['messages']
    requests=[m['content'] for m in messages if m.get('role')=='user']
    calls=record['row'].get('app_calls') or []
    if len(requests)!=1 or not 1<=len(calls)<=8 or (action_index is None and len(calls)!=1):
        raise ValueError('one original request and one recorded app action required')
    if action_index is None:action_index=0
    if type(action_index) is not int or not -len(calls)<=action_index<len(calls):
        raise ValueError('selected original action index required')
    action_index%=len(calls)
    action=calls[action_index]
    name=action.get('tool',action.get('name'))
    arguments=action.get('args',action.get('arguments'))
    if not isinstance(name,str) or not isinstance(arguments,dict):
        raise ValueError('recorded app action required')
    instructions=[m.get('content') for m in messages
        if m.get('role') in {'system','developer'} and isinstance(m.get('content'),str)]
    evidence={}
    if observed_host_identity is not None:
        if not observed_host_identity or not any(observed_host_identity in s for s in instructions):
            raise ValueError('host identity not observed in model input')
        evidence['observed-host-identity']={'unit_id':'observed-host-identity','text':observed_host_identity}
    initial=initial_ruling.get('context')
    if initial:
        if not isinstance(initial,str) or not any(initial in s for s in instructions):
            raise ValueError('initial memory packet not observed in model input')
        evidence['observed-initial-memory-packet']={'unit_id':'observed-initial-memory-packet','text':initial}
    def matches(call,target,args):
        name=call.get('tool',call.get('name'))
        arguments=call.get('args',call.get('arguments'))
        return (isinstance(name,str) and target=='mcp__dolphinbench_apps__'+name
            and isinstance(args,dict) and isinstance(arguments,dict)
            and all(k in arguments and json.dumps(arguments[k],sort_keys=True,allow_nan=False)
                ==json.dumps(v,sort_keys=True,allow_nan=False) for k,v in args.items())
            and all(v is None for k,v in arguments.items() if k not in args))
    pending={};app_pending={};matched=False;next_app=0
    for message in messages:
        if message.get('role')=='assistant':
            functions=[]
            for call in message.get('tool_calls',[]) or []:
                function=call.get('function',call)
                args=function.get('arguments',{})
                if isinstance(args,str):
                    try:args=json.loads(args)
                    except ValueError:continue
                target=function.get('name')
                if target=='tool_call' and isinstance(args,dict):
                    if set(args)=={'name','arguments'}:
                        proposed=[args]
                    elif set(args)=={'calls'} and isinstance(args['calls'],list):
                        proposed=args['calls']
                    else:proposed=[]
                else:proposed=[{'name':target,'arguments':args}]
                for proposed_call in proposed:
                    if not isinstance(proposed_call,dict):continue
                    target=proposed_call.get('name');args=proposed_call.get('arguments')
                    if next_app>action_index or not matches(calls[next_app],target,args):continue
                    # The app recorder may materialize omitted optional defaults.
                    # Use that only to locate the original decision boundary;
                    # never rewrite the retained application action itself.
                    if next_app==action_index:matched=True
                    else:
                        if len(proposed)!=1 or not isinstance(call.get('id'),str):
                            raise ValueError('ambiguous original application-result attribution')
                        if call['id'] in app_pending:
                            raise ValueError('unique original application call identifier required')
                        app_pending[call['id']]=next_app
                    next_app+=1
                functions.append(call)
            if matched:break  # Same-turn tool results were not known at decision time.
            for call in functions:
                target=_discovery_name(call)
                if target:
                    if not isinstance(call.get('id'),str) or call['id'] in pending:
                        raise ValueError('unique native discovery call identifier required')
                    pending[call['id']]=target
        elif message.get('role')=='tool':
            prior_action=app_pending.pop(message.get('tool_call_id'),None)
            if prior_action is not None:
                content=message.get('content')
                if not isinstance(content,str) or not content:
                    raise ValueError('original application result bytes unavailable')
                identity=f'observed-application-result-{prior_action}'
                evidence[identity]={'unit_id':identity,'text':content}
            target=pending.pop(message.get('tool_call_id'),None)
            if target is None:continue
            for payload in _payloads(message.get('content'),source=target):
                for source in payload.get('evidence',[]):
                    row={'unit_id':source['unit_id'],'text':source['text']}
                    if row['unit_id'] in evidence and evidence[row['unit_id']]!=row:
                        raise ValueError('source ID changed content')
                    evidence[row['unit_id']]=row
    if not matched or not evidence:
        raise ValueError('original action boundary or observed evidence unavailable')
    value={'query':requests[0],'evidence':list(evidence.values()),
        'actions':[{'action_id':'action-0','tool_name':name,'arguments':arguments}]}
    # Match the product review contract; an oversized case remains unreviewed,
    # not a selectively pruned source packet or a replacement selected case.
    if len(evidence)>128 or len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())>48000:
        raise ValueError('complete pre-action evidence exceeds review input bound')
    return value


def discoveries(value):
    if isinstance(value,str):
        if value.startswith('<untrusted_tool_result ') and value.rstrip().endswith('</untrusted_tool_result>'):
            value=value.split('\n\n',1)[1].rsplit('</untrusted_tool_result>',1)[0].strip()
        try: yield from discoveries(json.loads(value))
        except (ValueError,TypeError): pass
    elif isinstance(value,dict):
        if value.get('format')=='atmem-evidence-discovery-v1':
            yield value
            return
        for child in value.values(): yield from discoveries(child)
    elif isinstance(value,list):
        for child in value: yield from discoveries(child)


def material(record):
    row=record['row']
    requests=[m['content'] for m in row['messages'] if m.get('role')=='user']
    if len(requests)!=1:raise ValueError('one original request required')
    evidence={}
    for message in row['messages']:
        if message.get('role')!='tool':continue
        for result in discoveries(message.get('content','')):
            for source in result['evidence']:
                previous=evidence.pop(source['unit_id'],None)
                if previous is not None and previous!=source:
                    raise ValueError('same evidence ID changed content')
                evidence[source['unit_id']]=source
    calls=row.get('app_calls') or []
    actions=[]
    for i,call in enumerate(calls):
        name=call.get('tool',call.get('name'))
        arguments=call.get('args',call.get('arguments'))
        if not isinstance(name,str) or not isinstance(arguments,dict):
            raise ValueError('original recorded application action shape required')
        actions.append({'action_id':f'action-{i}', 'tool_name':name,'arguments':arguments})
    if not evidence or not 1<=len(actions)<=8:
        raise ValueError('retrieved evidence and 1..8 recorded actions required')
    packed=[{'unit_id':row['unit_id'],'text':row['text']} for row in evidence.values()][-128:]
    def size():return len(json.dumps({'question':requests[0],'evidence':packed,'actions':actions},
                                     ensure_ascii=False,separators=(',',':')).encode())
    while packed and size()>48000:packed.pop(0)
    if not packed:raise ValueError('whole-record evidence cannot fit review input')
    return {'query':requests[0],'evidence':packed,'actions':actions},len(evidence)-len(packed)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--roots',type=Path,nargs='+',required=True)
    parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--review-path',type=Path,required=True)
    parser.add_argument('--material-profile',choices=('legacy-followup-v1','observed-pre-action-v2'),
                        default='legacy-followup-v1')
    parser.add_argument('--upstream',type=Path,
                        help='Pinned original reference identity source for the pre-action profile')
    args=parser.parse_args()
    output=args.output.resolve();output.relative_to(Path('/Volumes/AtMemDolphin'))
    if output.exists():raise ValueError('fresh probe required; do not retry completed reviews')
    for root in args.roots:
        if not any(root.resolve().is_relative_to(base) for base in (
                Path('/Volumes/AtMemDolphin'),Path('/Volumes/AtMemBenchRuntime'))):
            raise ValueError('retained private benchmark root required')
        if not (root/'result.json').is_file():raise ValueError('completed original runs required')
    souls={};identity_receipt=None
    if args.material_profile=='observed-pre-action-v2':
        if args.upstream is None:raise ValueError('original reference identity source required')
        from .reference_host import reference_souls
        souls,identity_receipt=reference_souls(args.upstream)
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'packages/atbot/src'))
    from atbot.action_review import review_action
    from atbot.providers.openai_compatible import OpenAICompatibleProvider
    identity=configuration(args.roots,material_profile=args.material_profile,
                           reference_identity=identity_receipt)
    review=Review(**json.loads(args.review_path.read_text()))
    validate_review(Path(__file__).resolve().parents[2],identity,review,stage=identity['stage'],
        required_specs={'specs/046-retrieval-performance-2310/spec.md',
            'specs/046-retrieval-performance-2310/plan.md',
            'specs/046-retrieval-performance-2310/architecture.md',
            'specs/040-atmem-context-engine/spec.md'})
    master=Path('/Volumes/AtMemDolphin/retrieval-2310-budget.db')
    claim_budget(master,output.name,cap_usd='2')
    save_new(output/'identity.json',identity)
    save_new(output/'review.json',json.loads(args.review_path.read_text()))
    BudgetLedger(output/'budget.db',cap_usd=2,identity=identity).close()
    gateway=Gateway(key=load_key(args.env_file),output=output/'calls',ledger_path=output/'budget.db',
        campaign_identity=identity,cap_usd=2,phase='action-review',model=identity['model'],
        input_per_million=5,output_per_million=30,output_token_cap=4000).start()
    os.environ['ATMEM_DRAFT_REVIEW_PROXY_TOKEN']=gateway.local_token
    provider=OpenAICompatibleProvider(name='azure-openrouter-draft-review',model=identity['model'],
        endpoint=gateway.base_url,api_key_env='ATMEM_DRAFT_REVIEW_PROXY_TOKEN',egress_class='remote',
        timeout=100,reasoning_effort='medium',strict_schema=True)
    paths=[]
    try:
        for root in args.roots:
            for path in sorted((root/'tests').rglob('*.json')):
                key=path.parent.name+'-'+path.stem
                if any(prior[0]==key for prior in paths):raise ValueError('duplicate probe case')
                try:
                    if args.material_profile=='observed-pre-action-v2':
                        ruling=root/'native/tests'/path.parent.name/path.stem/'pre-action-ruling.json'
                        value=pre_action_material(json.loads(path.read_text()),json.loads(ruling.read_text()),
                            observed_host_identity=souls[path.parent.name],action_index=-1)
                        omitted=0
                    else:value,omitted=material(json.loads(path.read_text()))
                    save_new(output/'inputs'/f'{key}.json',{**value,'omitted_evidence_records':omitted})
                    result=review_action(provider,**value)
                    save_new(output/'reviews'/f'{key}.json',result)
                    paths.append((key,root,path,True))
                    print(json.dumps({'reviewed':len(paths),'findings':len(result['findings']),
                                      'abstained':result['abstained'],'task_success_claim':False}),flush=True)
                except Exception as exc:
                    save_new(output/'reviews'/f'{key}.error.json',{'error_class':type(exc).__name__,
                        'detail':str(exc)[:200],'review_retried':False,'no_task_success_claim':True})
                    paths.append((key,root,path,False))
        # All model responses are now retained. No grade, criterion or expected
        # answer has been used in material(), provider prompts or selection.
        counts=Counter();rows=[]
        for key,root,path,reviewed in paths:
            grade=json.loads((root/'grades'/path.parent.name/path.name).read_text())
            passed=all(c['passed'] for c in grade['checks'])
            result=json.loads((output/'reviews'/f'{key}.json').read_text()) if reviewed else None
            label=('passed' if passed else 'failed')
            status=('unreviewed' if result is None else 'abstained' if result['abstained']
                    else 'flagged' if result['findings'] else 'no_issue_detected')
            counts[label+':'+status]+=1
            rows.append({'case':key,'original_upstream_passed':passed,'review_status':status})
        save_new(output/'result.json',{'cases':len(paths),'counts':dict(counts),'rows':rows,
            'flagged_passes_are_potential_false_alarms_not_proven_errors':True,
            'task_actions_not_repaired_or_reexecuted':True,'ready_for_600':False})
        print(json.dumps({'counts':dict(counts),'task_success_claim':False}),flush=True)
    finally:
        gateway.stop()
        book=BudgetLedger(output/'budget.db',cap_usd=2,identity=identity)
        try:
            save_new(output/'costs.json',book.totals())
            exposure=book.connection.execute("SELECT COALESCE(SUM(CASE WHEN state IN ('completed','overrun') THEN actual WHEN state='reserved' THEN reserved ELSE 0 END),0) FROM calls").fetchone()[0]
            settle_budget(master,output.name,exposure)
        finally:book.close()


if __name__=='__main__':main()
