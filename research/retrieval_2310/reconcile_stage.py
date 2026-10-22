"""Build a checked resume-input bundle; never execute a task or alter originals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from benchmarks.dolphinbench.gateway import save_new


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_reconciled_parent(parent, recovery_roots, output, *, expected):
    parent,output=Path(parent).resolve(),Path(output).resolve()
    if output.exists() or not (parent/'costs-final.json').is_file():
        raise ValueError('fresh output and terminal original required')
    manifest=json.loads((parent/'stage-manifest.json').read_text())
    if manifest.get('sample_role')!='working-60':
        raise ValueError('only the frozen working-set continuation is supported')
    entries={}
    def add(persona,item,execution,grade,*,expected_execution=None,expected_grade=None):
        key=(persona,str(item).zfill(3))
        if key not in expected or key in entries:
            raise ValueError('duplicate or non-frozen execution in reconciliation')
        execution,grade=Path(execution),Path(grade)
        eh,gh=sha(execution),sha(grade)
        if ((expected_execution is not None and eh!=expected_execution)
                or (expected_grade is not None and gh!=expected_grade)):
            raise ValueError('original inherited evidence changed')
        checks=json.loads(grade.read_text()).get('checks')
        if not checks or any(type(c.get('passed')) is not bool for c in checks):
            raise ValueError('invalid original grade')
        entries[key]={'execution':str(execution),'grade':str(grade),
            'execution_sha256':eh,'grade_sha256':gh}
    for entry in manifest.get('inherited_executions',[]):
        rel=Path(entry['persona'])/(str(entry['task_id']).zfill(3)+'.json')
        source=Path(entry['inherited_from'])
        add(entry['persona'],entry['task_id'],source/'tests'/rel,source/'grades'/rel,
            expected_execution=entry['execution_sha256'],expected_grade=entry['grade_sha256'])
    for execution in (parent/'tests').glob('*/*.json'):
        add(execution.parent.name,execution.stem,execution,
            parent/'grades'/execution.parent.name/execution.name)
    markers={(p.parent.name,p.stem):p for p in (parent/'tests').glob('*/*.inflight')}
    seen=set()
    recovery_receipts={}
    for root in map(Path,recovery_roots):
        receipt=json.loads((root/'recovery-receipt.json').read_text())
        originals=receipt['original_files_sha256']
        if (receipt.get('model_or_tool_replay') is not False
                or receipt.get('original_evidence_modified') is not False
                or receipt.get('upstream_structural_validation_passed') is not True
                or not (root/'result.json').is_file()
                or (root/'failure.json').exists()
                or originals.get(str(parent/'stage-manifest.json'))!=sha(parent/'stage-manifest.json')):
            raise ValueError('completed original-execution recovery proof required')
        files=list((root/'tests').glob('*/*.json'))
        if len(files)!=1:raise ValueError('one recovered marker per recovery required')
        execution=files[0];key=(execution.parent.name,execution.stem)
        if key not in markers or key in seen:
            raise ValueError('recovery must uniquely reconcile an original inflight marker')
        if originals.get(str(markers[key]))!=sha(markers[key]):
            raise ValueError('original interrupted marker changed')
        for name,value in originals.items():
            if sha(name)!=value:raise ValueError('original recovery dependency changed')
        add(*key,execution,root/'grades'/execution.parent.name/execution.name)
        seen.add(key);recovery_receipts[str(root/'recovery-receipt.json')]=sha(root/'recovery-receipt.json')
    if seen!=set(markers):raise ValueError('every interrupted execution must be reconciled before resume')
    # Validate everything before creating the separate input bundle. No result
    # file is invented: this is not a newly executed or completed campaign.
    for (persona,item),entry in entries.items():
        for folder,field in [('tests','execution'),('grades','grade')]:
            destination=output/folder/persona/(item+'.json')
            destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            shutil.copyfile(entry[field],destination)
            destination.chmod(0o600)
            if sha(destination)!=entry[field+'_sha256']:
                raise ValueError('copied input differs from retained original')
    save_new(output/'stage-manifest.json',manifest)
    receipt={'format':'reconciled-resume-inputs-v1','original_parent':str(parent),
        'original_parent_manifest_sha256':sha(parent/'stage-manifest.json'),
        'entries':[{'persona':p,'task_id':i,**e} for (p,i),e in sorted(entries.items())],
        'recovery_receipts':recovery_receipts,'original_markers_preserved':True,
        'completed_actions_reexecuted':False,'new_model_or_tool_calls':0,
        'remaining_unexecuted':len(expected)-len(entries),'not_a_new_campaign_result':True}
    save_new(output/'reconciled-inputs.json',receipt)
    return receipt
