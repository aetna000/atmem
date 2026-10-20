from pathlib import Path

import pytest

from benchmarks.code_replay.eligibility_binding import bound_worker_source
from benchmarks.code_replay.public_test_control import public_task_settings, public_bootstrap
from benchmarks.code_replay.public_test_bridge import patch_bootstrap, server_bootstrap
from benchmarks.code_replay.solver_proposal import solver_bootstrap
import ast
from tests.test_code_replay_eligibility_images import fixture


def test_registration_changes_metadata_only_and_keeps_original_grading_worker():
    selection, metadata = fixture()
    by_id = {r['instance_id']: r for r in selection['selected']}
    for row in metadata['reports']:
        row['metadata'].update(repo=by_id[row['instance_id']]['repo'], base_commit='a' * 40, log_parser='parse_log_pytest')
    source, proof = bound_worker_source(selection, metadata)
    original = Path('benchmarks/code_replay/external_qualify_worker.py').read_text()
    assert source.replace(proof['registration_source'], '') == original
    namespace = {'__name__': 'control_definition_fixture'}
    exec(compile(source, 'private-worker-fixture.py', 'exec'), namespace)
    for identity, pair in proof['bindings'].items():
        assert namespace['task_binding'](identity, pair[0]) == pair
        assert namespace['task_source_roots'](identity, pair[0]) == proof['source_profiles'][identity]
        with pytest.raises(ValueError, match='preselected'):
            namespace['task_binding'](identity, 'b' * 40)
    with pytest.raises(ValueError, match='preselected'):
        namespace['task_binding']('unknown__task-1', 'a' * 40)
    metadata['reports'][0]['metadata']['repo'] = 'unregistered/project'
    with pytest.raises(ValueError, match='exact repository'):
        bound_worker_source(selection, metadata)


def test_public_registration_is_host_only_and_never_serializes_private_material():
    selection, metadata = fixture()
    by_id = {r['instance_id']: r for r in selection['selected']}
    for row in metadata['reports']:
        row['metadata'].update(repo=by_id[row['instance_id']]['repo'], base_commit='a' * 40, log_parser='parse_log_pytest')
    source, proof = bound_worker_source(selection, metadata)
    identity = selection['selected'][0]['instance_id']
    task = {'instance_id': identity, 'base_commit': 'a' * 40, 'image_extras_sha256': {}}
    proof['private_material'] = 'PRIVATE_MATERIAL_MUST_NOT_ENTER_PUBLIC_SERVER'
    settings = public_task_settings(task, operator_registration=proof)
    assert settings['PINNED_TASK_ID'] == identity
    assert settings['PINNED_SOURCE_ROOTS'] == ('src/flask/',)
    for code in (public_bootstrap(task, operator_registration=proof),
        patch_bootstrap(task, operator_registration=proof),
        server_bootstrap('/operator/preset.json', task, operator_registration=proof),
        solver_bootstrap(source, task, operator_registration=proof)):
        ast.parse(code)
        assert proof['private_material'] not in code
    with pytest.raises(ValueError, match='exact pinned'):
        public_task_settings({**task, 'operator_registration': proof}, operator_registration=proof)
    with pytest.raises(ValueError, match='task/base'):
        public_task_settings({**task, 'base_commit': 'b' * 40}, operator_registration=proof)
    changed = dict(proof); changed['source_profiles'] = {**proof['source_profiles'], identity: (('wide/',), ('tests/',))}
    with pytest.raises(ValueError, match='fixed registered'):
        public_task_settings(task, operator_registration=changed)
