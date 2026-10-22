"""Describe observable failure boundaries from retained execution traces.

No answer labels, new model calls or source mutation. The output belongs in
private experiment storage. These categories are observations, not inferred
semantic root causes: a called application can still receive wrong content.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from benchmarks.dolphinbench.gateway import save_new


def audit(root: Path) -> dict:
    rows=[]
    for path in sorted((root/'tests').rglob('*.json')):
        relative=path.relative_to(root/'tests')
        grade_path=root/'grades'/relative
        if not grade_path.is_file():
            continue
        execution=json.loads(path.read_text())
        grade=json.loads(grade_path.read_text())
        checks=grade.get('checks')
        if not isinstance(checks,list) or not checks or any(type(c.get('passed')) is not bool for c in checks):
            raise ValueError('unusable saved upstream grade')
        passed=all(c['passed'] for c in checks)
        record=execution['row']
        attempts=execution.get('attempts',[])
        blocked=any(a.get('gate_blocked') is True for a in attempts)
        app_calls=record.get('app_calls')
        app_trace=root/'apps'/path.parent.name/path.stem/'calls.jsonl'
        if app_trace.is_file():
            retained=[json.loads(line) for line in app_trace.read_text().splitlines() if line.strip()]
            if app_calls is not None and len(app_calls)!=len(retained):
                raise ValueError('native row and retained application trace disagree')
            app_calls=retained
        if not isinstance(app_calls,list):
            raise ValueError('missing native application call trace')
        tools=execution.get('settings',{}).get('tools',[])
        names=[t.get('function',{}).get('name','') for t in tools]
        names+= [t.get('name','') for t in tools if 'function' not in t]
        boundary=('passed' if passed else 'blocked_before_reader' if blocked
                  else 'no_application_call' if not app_calls else 'application_called_but_failed')
        rows.append({'interaction':str(relative.with_suffix('')),
            'passed':passed,'observable_boundary':boundary,'application_calls':len(app_calls),
            'memory_search_tool_exposed':any(n.endswith('memory_search') for n in names),
            'execution_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'grade_sha256':hashlib.sha256(grade_path.read_bytes()).hexdigest()})
    return {'format':'private-execution-boundary-audit-v1','tasks':len(rows),
        'passed':sum(r['passed'] for r in rows),
        'observable_boundaries':dict(Counter(r['observable_boundary'] for r in rows)),
        'semantic_failure_cause_not_inferred':True,'records':rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    result=audit(args.root)
    # Refuse accidental output into versioned source directories.
    output=args.output.resolve()
    approved=(Path('/Volumes/AtMemDolphin'),Path('/Volumes/MEM'),
              Path(__file__).resolve().parent/'private')
    if not any(output.is_relative_to(parent) for parent in approved):
        raise ValueError('trace audit output must remain in private evidence storage')
    save_new(output,result)
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__':main()
