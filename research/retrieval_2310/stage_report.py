"""Read-only fixed-sample accounting; missing executions never disappear."""
from __future__ import annotations

import math
from pathlib import Path
import json

from .evaluate import quantile


def execution_metrics(execution):
    row=execution['row']
    duration=row.get('duration_ms')
    if duration is not None and (type(duration) not in (int,float)
            or not math.isfinite(duration) or duration<0):
        raise ValueError('invalid execution duration')
    usage=[m.get('usage') for m in row['messages'] if m.get('role')=='assistant']
    known=bool(usage) and all(isinstance(u,dict)
        and all(type(u.get(k)) is int and u[k]>=0
                for k in ('prompt_tokens','completion_tokens')) for u in usage)
    # The product's terminal pre-reader refusal has its own zero-call receipt,
    # not provider usage. Do not invent token usage without that exact proof.
    attempts=execution.get('attempts',[])
    gate_zero=(len(usage)==1 and usage[0]=={'input_tokens':0,'output_tokens':0}
        and len(attempts)==1 and attempts[0].get('gate_blocked') is True
        and attempts[0].get('provider_calls')==0 and attempts[0].get('cost_usd')==0)
    return {'duration_ms':duration,
        'reader_input_tokens':sum(u['prompt_tokens'] for u in usage) if known else 0 if gate_zero else None,
        'reader_output_tokens':sum(u['completion_tokens'] for u in usage) if known else 0 if gate_zero else None,
        'reader_usage_known':known or gate_zero,
        'reader_usage_basis':'provider_reported' if known else 'terminal_zero_call_receipt' if gate_zero else 'unknown'}


def read_stage(root: Path):
    """Use only saved grades and executions, never rerun or reinterpret them."""
    results={}
    recovery=root/'recovery-receipt.json'
    comparable=(not recovery.is_file() or json.loads(recovery.read_text()).get(
        'latency_comparable_to_complete_task_wall_time') is True)
    for path in sorted((root/'grades').glob('*/*.json')):
        grade=json.loads(path.read_text())
        checks=grade.get('checks')
        if not checks or any(type(c.get('passed')) is not bool for c in checks):
            raise ValueError('invalid retained grade')
        execution=root/'tests'/path.parent.name/path.name
        if not execution.is_file():raise ValueError('grade without execution')
        saved=json.loads(execution.read_text())
        metrics=execution_metrics(saved)
        recovered_time_unknown=any(a.get('recording_recovery') is True
            and a.get('latency_comparable_to_complete_task_wall_time') is not True
            for a in saved.get('attempts',[]))
        if not comparable or recovered_time_unknown:
            metrics['duration_ms']=None
            metrics['duration_exclusion_reason']='recovery excludes unrecorded preparation'
        results[(path.parent.name,path.stem)]={
            'passed':all(c['passed'] for c in checks),
            **metrics,
            'grade_path':str(path),'execution_path':str(execution)}
    return results


def summarize(records, expected):
    expected=set(expected)
    if not expected or set(records)-expected:raise ValueError('unknown or empty fixed sample')
    for record in records.values():
        if type(record.get('passed')) is not bool:raise ValueError('grade must be boolean')
    passed=sum(r['passed'] for r in records.values())
    durations=[r['duration_ms'] for r in records.values() if r.get('duration_ms') is not None]
    def tokens(key):
        values=[r.get(key) for r in records.values()]
        if any(v is not None and (type(v) is not int or v<0) for v in values):
            raise ValueError('invalid token usage')
        unknown=len(expected)-sum(v is not None for v in values)
        return {'known_lower_bound':sum(v for v in values if v is not None),
                'unknown_tasks':unknown}
    return {'requested':len(expected),'graded':len(records),'passed':passed,
        'graded_failures':len(records)-passed,'ungraded_or_not_executed':len(expected)-len(records),
        'complete':set(records)==expected,
        'requested_denominator_success_rate':passed/len(expected),
        'latency':{'p50_ms':quantile(durations,.5) if durations else None,
                   'p95_ms':quantile(durations,.95) if durations else None,
                   'known_tasks':len(durations),'unknown_tasks':len(expected)-len(durations)},
        'reader_input_tokens':tokens('reader_input_tokens'),
        'reader_output_tokens':tokens('reader_output_tokens'),
        'latency_scope':'recorded interaction wall time, not invented for recovered executions',
        'ready_for_600':False}


def compare(baseline,candidate,expected):
    expected=set(expected)
    a,b=summarize(baseline,expected),summarize(candidate,expected)
    shared=set(baseline)&set(candidate)
    return {'baseline':a,'candidate':b,'paired_tasks':len(shared),
        'paired_wins':sum(not baseline[k]['passed'] and candidate[k]['passed'] for k in shared),
        'paired_losses':sum(baseline[k]['passed'] and not candidate[k]['passed'] for k in shared),
        'complete_paired_comparison':a['complete'] and b['complete'],
        'ungraded_not_dropped':True,'ready_for_600':False}
