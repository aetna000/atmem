import pytest

from research.retrieval_2310.dolphin_stage import resume_selection,verify_checkpoint_retry


def test_only_transient_read_lock_is_retried(monkeypatch):
    import research.retrieval_2310.dolphin_stage as stage
    monkeypatch.setattr(stage.time,'sleep',lambda _:None)
    class Adapter:
        calls=0
        def verify_checkpoint(self,*args):
            self.calls+=1
            if self.calls==1:raise RuntimeError('Hermes authority is busy; retry the operation')
    adapter=Adapter();verify_checkpoint_retry(adapter,'fixture',{})
    assert adapter.calls==2
    class Bad:
        def verify_checkpoint(self,*args):raise RuntimeError('canonical source changed')
    with pytest.raises(RuntimeError,match='source changed'):verify_checkpoint_retry(Bad(),'fixture',{})


def test_working_set_expansion_is_explicit_and_preserves_the_entire_frozen_subset():
    frozen={'working_60':{'fixture':['1','2','3']},'recurring_stage_18':{'fixture':['2']}}
    selected=frozen['working_60']
    assert resume_selection('recurring-18','working-60',frozen,selected,
        expand_working_set=True)=={('fixture','002')}
    with pytest.raises(ValueError,match='sample role changed'):
        resume_selection('recurring-18','working-60',frozen,selected)
    assert resume_selection('working-60','working-60',frozen,selected) is None
    with pytest.raises(ValueError,match='only fixed'):
        resume_selection('working-60','recurring-18',frozen,selected,expand_working_set=True)
    with pytest.raises(ValueError,match='differs from frozen'):
        resume_selection('recurring-18','working-60',frozen,{'fixture':['2','3']},expand_working_set=True)
    with pytest.raises(ValueError,match='explicit'):
        resume_selection('recurring-18','working-60',frozen,selected,expand_working_set=1)
    frozen['recurring_stage_18']['fixture']=['4']
    with pytest.raises(ValueError,match='not a frozen subset'):
        resume_selection('recurring-18','working-60',frozen,selected,expand_working_set=True)
