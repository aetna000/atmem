import ast
import base64
from hashlib import sha256
import json

import pytest

from benchmarks.code_replay.external_catalog import CONFIRMATION_REPOSITORIES, CONFIRMATION_SEED, catalog, digest, TASK_TREE
from benchmarks.code_replay.external_qualify_worker import CONFIRMATION_BINDINGS, TASK_BINDINGS, task_binding, task_source_roots
from benchmarks.code_replay.windows_confirmation_images import bound_descriptor, runtime_program, validate_preflight, runtime_evidence_qualifies
from benchmarks.code_replay.public_test_control import public_task_settings


def test_fixed_confirmation_bindings_keep_original_manifest_separate():
    assert len(TASK_BINDINGS) == 6 and len(CONFIRMATION_BINDINGS) == 20
    assert not set(TASK_BINDINGS) & set(CONFIRMATION_BINDINGS)
    for identity, (base, parser) in CONFIRMATION_BINDINGS.items():
        assert task_binding(identity, base) == (base, parser)
        roots, tests = task_source_roots(identity, base)
        assert roots and tests and all(r.endswith('/') for r in roots + tests)
        with pytest.raises(ValueError, match='preselected'):
            task_binding(identity, '0' * 40)


def test_registry_manifest_and_config_identity_are_different_and_verified():
    decoded = {'schemaVersion': 2, 'config': {'digest': 'sha256:' + 'a' * 64}, 'layers': [{'size': 42}]}
    raw = json.dumps(decoded).encode()
    value = {'Descriptor': {'digest': 'sha256:' + sha256(raw).hexdigest(), 'size': len(raw),
        'platform': {'architecture': 'amd64', 'os': 'linux'}},
        'Raw': base64.b64encode(raw).decode(), 'SchemaV2Manifest': decoded}
    result = bound_descriptor(json.dumps(value))
    assert result['configuration_digest'] != result['digest']
    assert result['compressed_layer_bytes'] == 42
    value['Descriptor']['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(ValueError, match='digest'):
        bound_descriptor(json.dumps(value))


def test_confirmation_preflight_binds_all_twenty_exact_metadata_rows():
    tree = {'sha': TASK_TREE, 'truncated': False, 'tree': [
        {'path': identity, 'type': 'tree', 'sha': 'a' * 40} for identity in CONFIRMATION_BINDINGS]}
    selection = catalog(tree, seed=CONFIRMATION_SEED, per_repo=4, repositories=CONFIRMATION_REPOSITORIES)
    metadata = {'selection_sha256': digest(selection), 'reports': [
        {'instance_id': identity, 'status': 'metadata_verified_environment_not_executed',
         'metadata': {'instance_id': identity, 'base_commit': base, 'log_parser': parser}}
        for identity, (base, parser) in CONFIRMATION_BINDINGS.items()]}
    validate_preflight(selection, metadata)
    metadata['reports'][0]['metadata']['log_parser'] = 'wrong_parser'
    with pytest.raises(ValueError, match='parser'):
        validate_preflight(selection, metadata)


def test_windows_pull_keeps_original_bounds_and_checks_physical_disk():
    source = runtime_program()
    ast.parse(source)
    assert '8 * 1024 ** 3' in source and '> 180' in source
    assert '/mnt/c' in source and '/dev/shm' in source
    assert '/private/tmp' not in source


def test_confirmation_public_layouts_are_bound_before_model_requests():
    for identity, (base, _) in CONFIRMATION_BINDINGS.items():
        settings = public_task_settings({'instance_id': identity, 'base_commit': base, 'image_extras_sha256': {}})
        assert set(settings['PINNED_DEFAULT_TEST_PATHS']) <= set(settings['PINNED_TEST_PATHS'])
        assert settings['PINNED_SOURCE_SUBDIR'] == ('src' if identity.startswith(('pytest-dev__', 'sqlfluff__')) else '.')
    with pytest.raises(ValueError, match='exact pinned'):
        public_task_settings({'instance_id': identity, 'base_commit': base, 'image_extras_sha256': {}, 'paths': ['elsewhere']})


def test_runtime_identity_supports_both_docker_stores_but_not_unknown_ids():
    descriptor = {'digest': 'sha256:' + 'a' * 64, 'configuration_digest': 'sha256:' + 'b' * 64}
    for identity in (descriptor['digest'], descriptor['configuration_digest'], 'sha256:' + 'c' * 64):
        result = {'pull': {'passed': True, 'reason': None}, 'runtime': {'exit_code': 0,
            'stdout_base64': base64.b64encode(b'x86_64\nPYTHON 3.8.20 linux\n').decode(),
            'image': {'Id': identity, 'Architecture': 'amd64', 'Os': 'linux'}}}
        record = {'transport_exit': 0, 'result': result,
            'transport_stdout_base64': base64.b64encode(json.dumps(result).encode()).decode()}
        assert runtime_evidence_qualifies(record, descriptor) == (identity != 'sha256:' + 'c' * 64)
        record['result'] = {}
        with pytest.raises(ValueError, match='retained raw'):
            runtime_evidence_qualifies(record, descriptor)
