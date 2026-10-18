from collections import Counter
import pytest

from benchmarks.code_replay.confirmation_design import QUOTAS, select_tasks, paired_blocks


def fixture():
    pools={repo:[repo.replace('/','__')+'-'+str(i) for i in range(8)] for repo in QUOTAS}
    selection={'selected':[{'repo':repo,'instance_id':i} for repo,ids in pools.items() for i in ids],
               'ordered_candidate_pools':pools}
    eligibility={row['instance_id']:{'qualified':True} for row in selection['selected']}
    return selection,eligibility


def test_original_order_and_owner_amended_quotas_without_outcome_selection():
    selection,eligibility=fixture()
    eligibility['pallets__flask-0']['qualified']=False
    chosen=select_tasks(selection,eligibility)
    assert len(chosen)==19 and chosen[:4]==['pallets__flask-'+str(i) for i in (1,2,3,4)]
    assert chosen[-3:]==['pyvista__pyvista-'+str(i) for i in (0,1,2)]
    blocks=paired_blocks(chosen)
    assert len(blocks)==38 and sum(len(b['order']) for b in blocks)==76
    assert Counter(b['order'][0] for b in blocks)=={'native':19,'tools':19}
    assert all(n==2 for n in Counter(b['instance_id'] for b in blocks).values())
    assert blocks==paired_blocks(list(reversed(chosen)))


def test_incomplete_or_smaller_success_cohort_cannot_freeze():
    selection,eligibility=fixture()
    for i in range(2,8): eligibility['pyvista__pyvista-'+str(i)]['qualified']=False
    with pytest.raises(ValueError,match='insufficient'): select_tasks(selection,eligibility)
    eligibility.pop('pallets__flask-0')
    with pytest.raises(ValueError,match='forty-candidate'): select_tasks(selection,eligibility)
    with pytest.raises(ValueError): paired_blocks(['task-1']*19)
