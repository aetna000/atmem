"""Freeze 60 DolphinBench tasks and an 18-task recurring development check.

Selection uses IDs/personas and fixed seeds only, never scores or answer content.
Original history, tasks, tools and upstream grading are unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

from benchmarks.dolphinbench.gateway import save_new
from .protocol import digest


def select(release: dict) -> dict:
    working, quick = {}, {}
    for persona in sorted(release):
        ids=sorted(str(row['id']) for row in release[persona]['tests'])
        if len(ids)!=200 or len(set(ids))!=200:
            raise ValueError('expected original 200 unique tasks per persona')
        working[persona]=sorted(random.Random('2310-working-'+persona).sample(ids,20))
        quick[persona]=sorted(random.Random('2310-stage-'+persona).sample(working[persona],6))
    if len(working)!=3:
        raise ValueError('expected all three personas')
    return {'working_60':working,'recurring_stage_18':quick,
            'stage_check_is_reused_development_not_sealed_test':True,
            'sampling_did_not_use_scores':True,'ready_for_600':False}


def freeze(upstream: Path, baseline: Path, output: Path) -> None:
    sys.path.append(str(upstream))
    from harness.submission import read_release
    release=read_release(upstream)
    selected=select(release)
    selected['corpus_digest']=digest(release)
    selected['upstream_commit']='81cb6f8405b40a9e76089cef650806a80af06ea2'
    selected['baseline_root']=str(baseline)
    selected['baseline_run_sha256']=hashlib.sha256((baseline/'run.json').read_bytes()).hexdigest()
    save_new(output/'sample.json',selected)
    results={}
    for name in ('working_60','recurring_stage_18'):
        records=[]
        for persona,ids in selected[name].items():
            for identity in ids:
                path=baseline/'grades'/persona/(str(identity).zfill(3)+'.json')
                grade=json.loads(path.read_text())
                if not grade['checks'] or any(type(c['passed']) is not bool for c in grade['checks']):
                    raise ValueError('invalid original grade')
                records.append({'persona':persona,'task_id':identity,
                    'passed':all(c['passed'] for c in grade['checks']),
                    'original_grade_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        results[name]={'passed':sum(r['passed'] for r in records),'tasks':len(records),'records':records}
    save_new(output/'baseline.json',{'baseline_reused_not_regenerated':True,'results':results,'ready_for_600':False})
    print(json.dumps({name:{k:v for k,v in value.items() if k!='records'} for name,value in results.items()}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('upstream','baseline','output'):
        parser.add_argument(name,type=Path)
    args=parser.parse_args()
    freeze(args.upstream,args.baseline,args.output)


if __name__=='__main__':
    main()
