import base64
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from atmem.core.canonical import canonical_json
from benchmarks.code_replay.windows_confirmation_exports import verified_export, recover_export
from tests.test_code_replay_external_solver_source import projected_fixture


def example(root):
    args, manifest, policy = projected_fixture(root)
    original, baseline, commit, tree, expected = args
    worker = {'phase': 'unchanged', 'base_source_verified': True, 'assembled_bytes_verified': True,
        'runtime_fixtures_verified': True, 'original_sha256': 'a'*64,
        'candidate_sha256': 'a'*64, 'assembled_sha256': 'a'*64,
        'source_policy': {'source_roots': list(policy.source_roots), 'test_roots': list(policy.test_roots)},
        'original_files_base64': original, 'tracked_base': baseline, 'runtime_manifest': manifest}
    objects = {}
    for kind, value in [('commits', commit), ('trees', tree)]:
        raw = json.dumps(value).encode()
        objects[kind] = {'raw_base64': base64.b64encode(raw).decode(),
                         'sha256': sha256(raw).hexdigest(), 'parsed': value}
    public = {'qualified': True, 'base_commit': expected, 'objects': objects,
              'instance_id': 'fixture-1', 'repo': 'fixture/repo'}
    return worker, public


def test_source_export_retains_only_verified_public_projection(tmp_path):
    worker, public = example(tmp_path)
    result = verified_export(worker, public)
    assert set(result['files_base64']) == {'package/code.py'}
    assert result['evaluator_material_exported'] is False
    assert result['git_history_exported'] is False
    assert result['runtime_manifest'] == worker['runtime_manifest']


@pytest.mark.parametrize('change', ['phase', 'assembled', 'runtime', 'public_digest', 'parsed_public'])
def test_exports_reject_unbound_or_modified_source(tmp_path, change):
    worker, public = example(tmp_path)
    if change == 'phase': worker['phase'] = 'reference_as_proposal'
    elif change == 'assembled': worker['assembled_sha256'] = 'b'*64
    elif change == 'runtime': worker['runtime_fixtures_verified'] = False
    elif change == 'public_digest': public['objects']['trees']['sha256'] = '0'*64
    else: public['objects']['trees']['parsed'] = deepcopy(public['objects']['trees']['parsed']); public['objects']['trees']['parsed']['truncated'] = True
    with pytest.raises(ValueError):
        verified_export(worker, public)


def test_export_recovery_checks_full_bytes_and_scoped_receipts():
    value={'instance_id':'task-1','evaluator_material_exported':False,'files_base64':{'a.py':'eA=='}}
    raw=canonical_json(value).encode()
    payload={'offset':0,'bytes_base64':base64.b64encode(raw).decode()}
    receipt={'object_id':'obj-1','run_id':'export-1','payload_sha256':sha256(canonical_json(payload).encode()).hexdigest()}
    event={'object_id':'obj-1','envelope':{'run_id':'export-1','event_type':'external.public_source_chunk','payload':payload}}
    descriptor={'receipts':[receipt],'bytes':len(raw),'sha256':sha256(raw).hexdigest(),
                'instance_id':'task-1','export_run':'export-1'}
    assert recover_export([event],descriptor)==value
    with pytest.raises(ValueError): recover_export([event],{**descriptor,'sha256':'0'*64})
    with pytest.raises(ValueError): recover_export([event],{**descriptor,'export_run':'unrelated'})
    with pytest.raises(ValueError): recover_export([event],{**descriptor,'instance_id':'different-task'})
