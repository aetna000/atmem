import json

import pytest

from benchmarks.dolphinbench.recording import BudgetLedger
from research.retrieval_2310 import recover_recording


@pytest.mark.parametrize('pending_paid',[False,True])
def test_recovery_settles_mechanical_zero_but_keeps_uncertain_paid_exposure(tmp_path,monkeypatch,pending_paid):
    output=tmp_path/'recovery';output.mkdir()
    config={'plumbing_fixture':True}
    if pending_paid:
        book=BudgetLedger(output/'budget.db',cap_usd=1,identity=config)
        book.reserve('uncertain',phase='judge',request={'model':'fixture'},maximum_usd=.2)
        book.close()
    settled=[]
    monkeypatch.setattr(recover_recording,'settle_budget',lambda *args:settled.append(args))
    recover_recording.settle_recovery_costs(output,config,tmp_path/'master.db')
    assert settled==[(tmp_path/'master.db','recovery',200000 if pending_paid else 0)]
    costs=json.loads((output/'costs-final.json').read_text())
    assert costs==({'judge':{'actual_usd':0,'reserved_usd':.2,'calls':1}} if pending_paid else {})
