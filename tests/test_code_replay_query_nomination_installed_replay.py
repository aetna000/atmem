import ast
import inspect

from benchmarks.code_replay import query_nomination_installed_replay as replay


def test_installed_worker_imports_product_before_operator_and_binds_all_cases():
    source = inspect.getsource(replay.worker)
    ast.parse(source, feature_version=(3, 10))
    assert source.index('from atmem.knowledge.code import packing') < source.index('sys.path[:0]')
    assert 'is_relative_to(Path(sys.prefix).resolve())' in source
    assert "len(stages) != 19" in source
    assert "set(lock['staging_manifest']['issues']) != set(expected)" in source
    assert "stage['task_run'] != reference['stage_run']" in source
    assert "case['prepared']['request']['task'] != task" in source
    assert "actual == reference['candidate_pack'] and len(actual.encode()) <= 4096" in source
    assert 'packing.pack_generation(generation, task, budget=4096)' in source
    assert "'model_calls': 0" in source
    assert 'all(r[\'matches\'] for r in results)' in source


def test_replay_profile_is_separate_from_original_evidence():
    assert replay.RUN != replay.LOCK
    assert replay.SUBMIT != replay.RUN
    assert replay.LOCK == 'external-windows-corrective-development-execution-lock-v1-20261018'
    assert replay.PYTHON.endswith('/product-build-cc5aho32/venv/bin/python')
