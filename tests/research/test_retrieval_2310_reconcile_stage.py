import json
from pathlib import Path

import pytest

from research.retrieval_2310.reconcile_stage import build_reconciled_parent,sha


def write(root,name,value):
    path=root/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def stopped_stage(tmp_path):
    parent=tmp_path/'parent';recovery=tmp_path/'recovery';output=tmp_path/'resume-inputs'
    manifest=write(parent,'stage-manifest.json',{'sample_role':'working-60','inherited_executions':[]})
    write(parent,'costs-final.json',{})
    write(parent,'failure.json',{'all_evidence_preserved':True})
    write(parent,'tests/scope/001.json',{'row':{'duration_ms':10,'messages':[]}})
    write(parent,'grades/scope/001.json',{'checks':[{'passed':False}]})
    marker=write(parent,'tests/scope/002.inflight',{'source_sha256':'fixture'})
    write(recovery,'tests/scope/002.json',{'row':{'duration_ms':20,'messages':[]},
        'attempts':[{'recording_recovery':True,'latency_comparable_to_complete_task_wall_time':False}]})
    write(recovery,'grades/scope/002.json',{'checks':[{'passed':False}]})
    write(recovery,'result.json',{'tasks':1,'passed':0})
    write(recovery,'recovery-receipt.json',{'model_or_tool_replay':False,
        'original_evidence_modified':False,'upstream_structural_validation_passed':True,
        'original_files_sha256':{str(manifest):sha(manifest),str(marker):sha(marker)}})
    return parent,recovery,output


def test_reconciliation_preserves_failures_unknown_time_and_original_markers(stopped_stage):
    from research.retrieval_2310.stage_report import read_stage
    parent,recovery,output=stopped_stage
    receipt=build_reconciled_parent(parent,[recovery],output,
        expected={('scope','001'),('scope','002'),('scope','003')})
    assert receipt['remaining_unexecuted']==1
    assert (parent/'tests/scope/002.inflight').is_file()
    assert not (output/'result.json').exists()
    records=read_stage(output)
    assert not records[('scope','001')]['passed'] and not records[('scope','002')]['passed']
    assert records[('scope','002')]['duration_ms'] is None


@pytest.mark.parametrize('mutation',['missing','duplicate','changed','new_task','replayed'])
def test_reconciliation_refuses_ambiguous_incomplete_or_changed_originals(stopped_stage,mutation):
    parent,recovery,output=stopped_stage
    roots=[recovery]
    expected={('scope','001'),('scope','002'),('scope','003')}
    if mutation=='missing':roots=[]
    elif mutation=='duplicate':roots.append(recovery)
    elif mutation=='changed':write(parent,'tests/scope/002.inflight',{'changed':True})
    elif mutation=='new_task':expected.remove(('scope','002'))
    elif mutation=='replayed':
        path=recovery/'recovery-receipt.json';value=json.loads(path.read_text())
        value['model_or_tool_replay']=True;path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        build_reconciled_parent(parent,roots,output,expected=expected)
    assert not output.exists()
