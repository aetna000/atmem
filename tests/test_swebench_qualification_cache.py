from pathlib import Path
from benchmarks.code_replay.swebench_qualification_cache import grader_binding


def test_eligibility_reuse_binds_all_grading_helpers_and_authority_constants():
    source = Path('benchmarks/code_replay/swebench_worker.py').read_text()
    original = grader_binding(source)
    assert grader_binding(source + '\n# annotation\n') == original
    assert grader_binding(source.replace('48 * 1024 ** 3', '47 * 1024 ** 3')) != original
    assert grader_binding(source.replace("LABEL = 'atmem.benchmark=swebench-lite-20261019'",
        "LABEL = 'unrelated'")) != original
    assert grader_binding(source.replace("'/bin/sleep'", "'/bin/other'")) != original
    assert grader_binding(source.replace("return grade(payload['task'], payload['image_id'], payload['patch'])",
        "return grade(payload['task'], payload['image_id'], '')")) != original
