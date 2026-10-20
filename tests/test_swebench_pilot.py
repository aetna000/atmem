from benchmarks.code_replay.swebench_pilot import REPOSITORIES, select, usage, patch_allowed, public_environment
import pytest
from benchmarks.code_replay.swebench_worker import resolution_value
from enum import Enum
from benchmarks.code_replay.swebench_report import summarize, percentile95
from benchmarks.code_replay import swebench_worker
from benchmarks.code_replay.swebench_pilot import validate_product_runtime, REMOTE
from benchmarks.code_replay.swebench_pilot import validate_frozen_manifest
from benchmarks.code_replay.swebench_pilot import comparison_cohort, validate_cognee_runtime, THREE_ARMS
from benchmarks.code_replay.swebench_pilot import automatic_context_for
from types import SimpleNamespace
import io
import tarfile


def rows():
    return [{'instance_id': repo.replace('/', '__') + '-' + str(i), 'repo': repo,
             'base_commit': 'a' * 40} for repo in REPOSITORIES for i in range(10)]


def test_automatic_source_pack_is_not_sent_to_other_providers():
    assert automatic_context_for('atmem_structure', 'automatic')
    for arm in THREE_ARMS:
        assert not automatic_context_for(arm, 'optional')
    assert not automatic_context_for('cognee_structure', 'automatic')
    assert not automatic_context_for('no_memory', 'automatic')
    with pytest.raises(ValueError):
        automatic_context_for('atmem_structure', 'invented')


def test_fixed_balanced_selection_is_order_invariant():
    chosen = select(rows())
    assert chosen == select(list(reversed(rows())))
    assert len(chosen) == 30
    assert all(sum(r['repo'] == repo for r in chosen) == 6 for repo in REPOSITORIES)
    assert chosen[0]['arm_order'] == list(reversed(chosen[1]['arm_order']))


def test_three_way_sets_are_task_disjoint_and_keep_all_repository_families():
    selected = [{'instance_id': str(i), 'repo': REPOSITORIES[i % 5]} for i in range(30)]
    validation = comparison_cohort(selected, 'validation')
    confirmation = comparison_cohort(selected, 'confirmation')
    assert len(validation) == len(confirmation) == 5
    assert {r['instance_id'] for r in validation}.isdisjoint(r['instance_id'] for r in confirmation)
    assert {r['repo'] for r in validation} == {r['repo'] for r in confirmation} == set(REPOSITORIES)
    assert all(set(row['arm_order']) == set(THREE_ARMS) for row in validation + confirmation)
    with pytest.raises(ValueError):
        comparison_cohort(selected, 'chosen_by_scores')


def test_cognee_provider_must_be_explicitly_pinned():
    runtime = {'python': REMOTE + '/cognee-runtime-test/venv/bin/python',
        'wheel_path': REMOTE + '/cognee-runtime-test/cognee.whl',
        'server_path': REMOTE + '/cognee-runtime-test/server.py',
        'wheel_sha256': 'a' * 64, 'server_sha256': 'b' * 64, 'dependencies_sha256': 'c' * 64,
        'upstream_commit': 'f154b32a9e544dac73e7ddf2010327cf9988edcd'}
    assert validate_cognee_runtime(runtime) == runtime
    for changes in ({'python': '/usr/bin/python'}, {'server_path': REMOTE + '/cognee-runtime-test/../owner'},
                    {'wheel_sha256': 'latest'}, {'upstream_commit': 'main'}):
        with pytest.raises(ValueError):
            validate_cognee_runtime({**runtime, **changes})


def test_new_product_runtime_is_explicitly_pinned_and_benchmark_scoped():
    runtime = {'python': REMOTE + '/candidate/venv/bin/python',
               'wheel_path': REMOTE + '/candidate/atmem-2.3.8-py3-none-any.whl',
               'wheel_sha256': 'a' * 64, 'worker_image_id': 'sha256:' + 'b' * 64}
    assert validate_product_runtime(runtime) == runtime
    for changes in ({'python': '/usr/bin/python'}, {'python': REMOTE + '/../../owner/bin/python'},
                    {'python': REMOTE + '/candidate/bin/python;echo'}, {'wheel_sha256': None},
                    {'worker_image_id': 'image:latest'}, {'unexpected': 'field'}):
        with pytest.raises(ValueError):
            validate_product_runtime({**runtime, **changes})


def test_duplicate_and_incomplete_cohorts_fail_closed():
    with pytest.raises(ValueError, match='duplicate'):
        select(rows() + rows()[:1])
    with pytest.raises(ValueError, match='insufficient'):
        select([r for r in rows() if r['repo'] != REPOSITORIES[0]])


def test_campaign_cannot_silently_change_delivery_or_product_after_freeze():
    manifest = {'selected': ['task'], 'context_delivery': 'optional'}
    event = {'envelope': {'event_type': 'selection.frozen', 'payload': manifest}}
    validate_frozen_manifest([event], manifest)
    for changed in ({**manifest, 'context_delivery': 'automatic'}, {**manifest, 'product_runtime': {}},
                    {'selected': ['replacement']}):
        with pytest.raises(ValueError, match='new campaign'):
            validate_frozen_manifest([event], changed)
    with pytest.raises(ValueError):
        validate_frozen_manifest([event, event], manifest)


def test_upstream_resolution_accepts_string_and_enum_without_inventing_status():
    class Status(str, Enum):
        FULL = 'RESOLVED_FULL'
    assert resolution_value('RESOLVED_FULL') == 'RESOLVED_FULL'
    assert resolution_value(Status.FULL) == 'RESOLVED_FULL'
    with pytest.raises(ValueError, match='unknown'):
        resolution_value('success')


def test_usage_includes_all_cache_tokens_and_preserves_missing_receipts():
    event = {'type': 'result', 'subtype': 'success', 'is_error': False, 'usage': {
        'input_tokens': 10, 'cache_read_input_tokens': 20, 'cache_creation_input_tokens': 30,
        'output_tokens': 4}, 'total_cost_usd': 0.1}
    measured = usage([event])
    assert measured['complete'] and measured['total_input_tokens'] == 60
    assert measured['output_tokens'] == 4 and measured['estimated_usd'] == 0.1
    assert usage([]) == {'complete': False}
    assert usage([event, event]) == {'complete': False}
    event['usage']['cache_read_input_tokens'] = -1
    assert usage([event]) == {'complete': False}


def test_patch_policy_rejects_test_changes_git_rewrites_and_omitted_new_source():
    patch = {'head': 'a', 'exit_code': 0, 'changed_paths': ['sympy/core/add.py'], 'untracked': []}
    assert patch_allowed(patch, {'baseline_head': 'a'})
    for paths in [['sympy/core/tests/test_add.py'], ['conftest.py'], ['../escape.py']]:
        assert not patch_allowed({**patch, 'changed_paths': paths}, {'baseline_head': 'a'})
    assert not patch_allowed({**patch, 'head': 'b'}, {'baseline_head': 'a'})
    assert not patch_allowed({**patch, 'untracked': ['new_module.py']}, {'baseline_head': 'a'})


def test_report_does_not_call_preparation_failure_zero_token_inference():
    manifest = {'selected': [{'instance_id': 'task'}]}
    result = {'status': 'running', 'rows': [
        {'instance_id': 'task', 'arm': 'no_memory', 'task_pass': True, 'grade_valid': True,
         'solver_s': 20, 'usage': {'complete': True, 'total_input_tokens': 100, 'output_tokens': 10}},
        {'instance_id': 'task', 'arm': 'atmem_structure', 'task_pass': False, 'grade_valid': False,
         'status': 'product_preparation_failed', 'usage': None}]}
    report = summarize(manifest, result)
    assert report['paired_terminal_tasks'] == 1 and report['paired_runnable_tasks'] == 0
    assert report['arms']['atmem_structure']['product_preparation_failures'] == 1
    assert report['arms']['atmem_structure']['paired_complete_input_tokens'] is None
    assert report['arms']['no_memory']['paired_complete_input_tokens'] is None
    with pytest.raises(ValueError, match='duplicate'):
        summarize(manifest, {**result, 'rows': result['rows'] * 2})


def test_small_sample_latency_uses_observed_nearest_rank_and_no_missing_imputation():
    assert percentile95([]) is None
    assert percentile95([1, 2, 3]) == 3
    manifest = {'selected': [{'instance_id': 'task'}]}
    rows = [{'instance_id': 'task', 'arm': arm, 'task_pass': True, 'grade_valid': True,
             'solver_s': 10, 'usage': {'complete': True, 'total_input_tokens': 100, 'output_tokens': 3}}
            for arm in ['no_memory', 'atmem_structure']]
    report = summarize(manifest, {'rows': rows})
    assert report['arms']['atmem_structure']['paired_p95_solver_seconds'] == 10
    assert report['arms']['atmem_structure']['paired_median_cold_seconds'] is None
    report = summarize(manifest, {'rows': [{**r, 'setup_s': 5} for r in rows]})
    assert report['arms']['atmem_structure']['paired_p95_cold_seconds'] == 15


def test_prepared_image_verification_does_not_destroy_upstream_runtime_changes(monkeypatch):
    calls = []
    base = 'a' * 40
    def execute(container, argv):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=(b'' if 'diff' in argv else (base + '\n').encode()))
    monkeypatch.setattr(swebench_worker, 'execute', execute)
    swebench_worker.reset('owned-container', base)
    assert len(calls) == 2 and calls[0][-2:] == ['rev-parse', 'HEAD']
    assert not any('reset' in c or 'clean' in c for c in calls)
    with pytest.raises(RuntimeError, match='base does not match'):
        swebench_worker.reset('owned-container', 'b' * 40)


def test_public_environment_projection_excludes_private_grader_and_setup_bytes():
    projected = public_environment({'instance_id': 'task', 'qualified': True, 'reference': {
        'valid': True, 'resolution': 'RESOLVED_FULL', 'report': {'FAIL_TO_PASS': {'success': ['hidden-test']}},
        'prepared_runtime': {'setup_delta_base64': 'raw-source'}, 'log_base64': 'raw-output'}})
    assert projected['reference'] == {'valid': True, 'resolution': 'RESOLVED_FULL'}


def test_three_provider_report_uses_same_complete_cohort():
    arms = ['no_memory', 'atmem_structure', 'cognee_structure']
    manifest = {'arms': arms, 'selected': [{'instance_id': 'task'}]}
    rows = [{'instance_id': 'task', 'arm': arm, 'task_pass': True, 'grade_valid': True,
             'solver_s': i + 1, 'usage': {'complete': True, 'total_input_tokens': 100 + i, 'output_tokens': 10}}
            for i, arm in enumerate(arms)]
    report = summarize(manifest, {'status': 'completed', 'rows': rows})
    assert report['paired_runnable_tasks'] == 1 and set(report['arms']) == set(arms)
    assert report['arms']['cognee_structure']['paired_complete_input_tokens'] == 102
    report = summarize(manifest, {'status': 'running', 'rows': rows[:-1]})
    assert report['paired_runnable_tasks'] == 0
    assert report['arms']['no_memory']['paired_complete_input_tokens'] is None


def source_tar(link):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w') as tar:
        member = tarfile.TarInfo('pkg/a.py'); member.size = 4
        tar.addfile(member, io.BytesIO(b'x=1\n'))
        member = tarfile.TarInfo('pkg/alias.py'); member.type = tarfile.SYMTYPE; member.linkname = link
        tar.addfile(member)
    return raw.getvalue()


def test_source_snapshot_preserves_internal_links_but_denies_escapes(tmp_path):
    swebench_worker.materialize_source(source_tar('a.py'), tmp_path)
    assert (tmp_path / 'pkg/alias.py').is_symlink()
    assert (tmp_path / 'pkg/alias.py').read_bytes() == b'x=1\n'
    for i, link in enumerate(('../../owner', '/etc/passwd')):
        target = tmp_path / str(i); target.mkdir()
        with pytest.raises(ValueError, match='escapes'):
            swebench_worker.materialize_source(source_tar(link), target)
