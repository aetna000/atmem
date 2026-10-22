import pytest

from research.retrieval_2310.evidence_control import control_packet


def test_evaluator_control_selects_only_literal_sources_or_normalized_facts():
    data={'facts':{1:{'statement':'A normalized source fact.','source_session_ids':['000002']}},
          'sessions':[{'id':'000001','narrative_date':'2030-01-01','messages':['Unrelated source.']},
                      {'id':'000002','narrative_date':'2030-01-02','messages':['Original user message.']}]}
    task={'load_bearing_facts':[1],'grade':{'not_input':'secret grading criterion'}}
    sources=control_packet(data,task,kind='sources')
    facts=control_packet(data,task,kind='facts')
    assert 'Original user message.' in sources and 'A normalized source fact.' not in sources
    assert 'A normalized source fact.' in facts and 'Original user message.' not in facts
    assert 'Unrelated source.' not in sources and 'secret grading criterion' not in sources+facts
    assert 'NOT output of AtMem' in sources and 'NOT output of AtMem' in facts


def test_evaluator_control_rejects_overflow_without_truncating():
    data={'facts':{1:{'statement':'X'*33000,'source_session_ids':[]}},'sessions':[]}
    with pytest.raises(ValueError,match='does not fit'):control_packet(data,{'load_bearing_facts':[1]},kind='facts')


def test_control_initialization_writes_run_identity_before_packet_evidence(tmp_path,monkeypatch):
    import contextlib,sys
    from types import SimpleNamespace
    from research.retrieval_2310.evidence_control import initialize_control_run
    @contextlib.contextmanager
    def run_lock(path):yield
    monkeypatch.setitem(sys.modules,'harness.runner',SimpleNamespace(Runner=None,run_lock=run_lock))
    def runner_factory(release,output,adapter,**kwargs):
        assert not list(output.glob('*/**/*.json'))
        (output/'run.json').write_text('{}')
        return SimpleNamespace(allow_paid=False)
    adapter=SimpleNamespace(identity=lambda:{'control_only':True})
    initialize_control_run({},tmp_path,adapter,tmp_path,{'role':'control'},
        {'one':{'context':'not product memory'}},runner_factory=runner_factory)
    assert (tmp_path/'run.json').exists() and (tmp_path/'control-packets/one.json').exists()
