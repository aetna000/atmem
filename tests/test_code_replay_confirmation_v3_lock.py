from copy import deepcopy
import pytest
from benchmarks.code_replay.confirmation_v3_lock import require_cases


def fixture():
    blocks=[{'slot':i,'instance_id':'repo-'+str(i//2),'repeat':i%2+1,'order':['native','tools']} for i in range(38)]
    rows=[{'slot':b['slot'],'instance_id':b['instance_id'],'repeat':b['repeat'],'arm':a,
           'qualified':True,'model_calls':0} for b in blocks for a in b['order']]
    return rows,blocks


def test_complete_exact_case_matrix_required():
    rows,blocks=fixture();assert len(require_cases(rows,blocks))==76


@pytest.mark.parametrize('change',[
    lambda r:r.pop(),lambda r:r.__setitem__(1,r[0]),lambda r:r[0].update(qualified=False),
    lambda r:r[0].update(instance_id='wrong'),lambda r:r[0].update(repeat=9),lambda r:r[0].update(model_calls=1),
])
def test_missing_duplicated_or_mismatched_cases_cannot_authorize_inference(change):
    rows,blocks=fixture();change(rows)
    with pytest.raises(ValueError):require_cases(rows,blocks)
