"""Owner-amended prospective sampling and balanced paired execution schedule."""
from hashlib import sha256


QUOTAS = {'pallets/flask':4,'mwaskom/seaborn':4,'pydata/xarray':4,
          'pylint-dev/pylint':4,'pyvista/pyvista':3}
SEED = 'atmem-windows-confirmation-amended19-20261018-v1'


def select_tasks(selection, eligibility):
    """Only first qualifying candidates in each original eight-identity pool."""
    selected=selection['selected']
    identities=[row['instance_id'] for row in selected]
    if (len(identities)!=40 or len(set(identities))!=40 or set(eligibility)!=set(identities)
        or set(selection['ordered_candidate_pools'])!=set(QUOTAS)):
        raise ValueError('complete unchanged forty-candidate eligibility report required')
    chosen=[]
    for repo,quota in QUOTAS.items():
        original=[row['instance_id'] for row in selected if row['repo']==repo]
        frozen=selection['ordered_candidate_pools'][repo][:8]
        if len(original)!=8 or set(original)!=set(frozen):
            raise ValueError('original repository pool differs')
        for identity in frozen:
            if type(eligibility[identity].get('qualified')) is not bool:
                raise ValueError('terminal explicit eligibility required')
        eligible=[i for i in frozen if eligibility[i]['qualified']]
        if len(eligible)<quota:
            raise ValueError('insufficient fully qualified candidates: '+repo)
        chosen.extend(eligible[:quota])
    return chosen


def paired_blocks(identities):
    if len(identities)!=19 or len(set(identities))!=19:
        raise ValueError('exact amended nineteen distinct tasks required')
    counts={repo:sum(i.rsplit('-',1)[0].replace('__','/')==repo for i in identities) for repo in QUOTAS}
    if counts!=QUOTAS:
        raise ValueError('owner-amended repository quotas differ')
    pairs=[(identity,repeat) for identity in identities for repeat in (1,2)]
    pairs.sort(key=lambda pair:sha256((SEED+'\0'+pair[0]+'\0'+str(pair[1])).encode()).hexdigest())
    return [{'slot':slot,'instance_id':identity,'repeat':repeat,
             'order':['native','tools'] if slot%2==0 else ['tools','native']}
            for slot,(identity,repeat) in enumerate(pairs)]
