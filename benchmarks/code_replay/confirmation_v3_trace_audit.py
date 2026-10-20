"""Descriptive all-case trace audit after frozen confirmation; no inference."""
from collections import Counter
from hashlib import sha256
import json
import statistics

RUN='external-windows-confirmation-v3-trace-audit-v1-20261018'


def audit_events(events):
    from atmem.core.canonical import canonical_json
    from benchmarks.code_replay.windows_metrics import trace_summary
    summary=trace_summary(events)
    items={e['item']['id']:e['item'] for e in events if e.get('type')=='item.completed'
           and isinstance(e.get('item',{}).get('id'),str)}
    outputs=Counter();commands=[];duplicates=0
    for item in items.values():
        if item.get('type')!='command_execution':continue
        raw=item.get('aggregated_output')
        if not isinstance(raw,str):continue
        encoded=raw.encode();digest=sha256(encoded).hexdigest()
        if len(encoded)>=1024 and outputs[digest]:duplicates+=len(encoded)
        outputs[digest]+=1
        command=item.get('command')
        text=command if isinstance(command,str) else canonical_json(command)
        commands.append({'item_id':item['id'],'command_preview':text[:320],
            'command_sha256':sha256(text.encode()).hexdigest(),'output_bytes':len(encoded),
            'output_sha256':digest,'exit_code':item.get('exit_code')})
    return {**summary,'command_metadata':commands,'exact_duplicate_output_bytes':duplicates,
            'assurance':'byte-count proxies, not per-tool token attribution; full original commands/output remain in referenced model transport'}


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.windows_metrics import recover_stream
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('trace audit already attempted; inspect retained evidence')
    def es(run):return vault.inspect(principal,run)
    def of(events,kind):return [e['envelope']['payload'] for e in events if e['envelope']['event_type']==kind]
    comparison,=of(es('external-windows-confirmation-v3-comparison-v1-20261018'),'external.v3_comparison_completed')
    lock,=of(es('external-windows-confirmation-v3-execution-lock-v1-20261018'),'external.v3_execution_manifest_frozen')
    if len(comparison['rows'])!=76:raise ValueError('complete comparison required; no success-only subset')
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.v3_trace_audit_planned',{'driver_source':job['driver_source'],'cases':76,
        'selection':'every original cell','relabels_current_confirmation_for_new_candidates':'reused development evidence',
        'model_or_grade_retries':0})
    stages={r['block']['slot']:r for r in lock['staged_blocks']}
    results=[];largest=[]
    for row in comparison['rows']:
        events=es(row['task_run']);model,=of(events,'external.v3_model_result')
        raw=recover_stream({e['object_id']:e for e in events},model['raw_response_transport']['stdout'])
        result=json.loads(raw);analysis=audit_events(result['events'])
        case=stages[row['slot']]['cases'][row['arm']]
        prepared=case.get('prepared')
        pack=prepared['package']['content'] if prepared else None
        item={**{k:row[k] for k in ('slot','instance_id','repeat','arm','task_run','usage','quality')},
              'trace':analysis,'initial_context':pack,'initial_context_bytes':len(pack.encode()) if pack else 0,
              'original_transport':model['raw_response_transport']['stdout']}
        save('external.v3_trace_audit_case',item);results.append(item)
        largest.extend({**{k:row[k] for k in ('slot','instance_id','repeat','arm')},**c} for c in analysis['command_metadata'])
        print(json.dumps({'trace_cases_audited':len(results)}),flush=True)
    summary={'cases':76,'arms':{},'largest_command_outputs':sorted(largest,key=lambda r:-r['output_bytes'])[:20],
             'initial_context_examples':[],'not_causal_attribution':True,'model_or_grade_retries':0}
    for arm in ('native','tools'):
        rows=[r for r in results if r['arm']==arm]
        summary['arms'][arm]={'native_commands':sum(r['trace']['native_commands'] for r in rows),
            'native_output_bytes':sum(r['trace']['native_command_output_bytes'] for r in rows),
            'exact_duplicate_output_bytes':sum(r['trace']['exact_duplicate_output_bytes'] for r in rows),
            'code_mcp_calls':sum(r['trace']['code_mcp_calls'] for r in rows),
            'median_initial_context_bytes':statistics.median(r['initial_context_bytes'] for r in rows),
            'item_types':dict(sum((Counter(r['trace']['completed_item_types']) for r in rows),Counter()))}
    seen=set()
    for row in results:
        repo=row['instance_id'].rsplit('-',1)[0]
        if row['arm']=='tools' and repo not in seen:
            summary['initial_context_examples'].append({'instance_id':row['instance_id'],
                'bytes':row['initial_context_bytes'],'preview':row['initial_context'][:1400]})
            seen.add(repo)
    save('external.v3_trace_audit_completed',summary)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
