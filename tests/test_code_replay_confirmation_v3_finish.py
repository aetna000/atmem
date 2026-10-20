import pytest
from benchmarks.code_replay.confirmation_v3_finish import readiness,pregrading_amendment


def event(kind, count=76):
    return {'envelope': {'event_type': kind, 'payload': {'attempts_completed': count}}}


def test_postprocessing_waits_for_complete_terminal_without_restarting_models():
    assert not readiness([])
    assert not readiness([event('external.v3_case_completed')])
    assert readiness([event('external.v3_models_completed')])
    with pytest.raises(ValueError): readiness([event('external.v3_models_completed', 75)])
    with pytest.raises(ValueError): readiness([event('external.v3_models_stopped')])
    with pytest.raises(ValueError): readiness([event('external.v3_models_completed')] * 2)


def test_zero_phase_resume_permits_only_exact_lossless_retention_delta():
    import ast
    from pathlib import Path
    source=Path('benchmarks/code_replay/confirmation_v3_grade.py').read_text()
    helper=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='retain_dispatch')
    previous=source.replace(ast.get_source_segment(source,helper)+'\n\n\n','',1).replace(
        'retain_dispatch(retain,{',"retain('external.v3_grade_dispatch',{")
    name='benchmarks.code_replay.confirmation_v3_grade'
    current={name:source,'report':'unchanged','retain':'unchanged'}
    old={**current,name:previous}
    existing=[{'envelope':{'event_type':'external.v3_postprocessing_planned','payload':{'postprocess_programs':old}}},
              {'envelope':{'event_type':'external.v3_pregrading_transport_pause','payload':{'grading_phases_started':0}}}]
    assert pregrading_amendment(existing,current)
    with pytest.raises(ValueError): pregrading_amendment(existing,{**current,'report':'changed'})
    with pytest.raises(ValueError): pregrading_amendment(existing,{**current,name:source.replace('timeout=205','timeout=300')})
    with pytest.raises(ValueError): pregrading_amendment(existing+[event('external.v3_postprocessing_phase_started')],current)
