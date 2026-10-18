import pytest

from benchmarks.code_replay import query_nomination_screen as screen


def namespace(source):
    result = {'__name__': 'cd2_profile_test'}
    exec(compile(source, '<cd2-profile-test>', 'exec'), result)
    return result


def test_cd2_has_fresh_deterministic_all_issue_schedule_and_candidate_gates():
    sources = screen.sources()
    stage = namespace(sources['staging'])
    blocks = [{'instance_id': str(i), 'repeat': r, 'slot': 2*i+r-1}
              for i in range(19) for r in (1, 2)]
    schedule = stage['development_blocks'](blocks)
    assert schedule == stage['development_blocks'](list(reversed(blocks)))
    assert len(schedule) == 19
    assert {r['instance_id'] for r in schedule} == {str(i) for i in range(19)}
    assert sum(r['order'][0] == 'native' for r in schedule) == 10
    assert stage['SEED'] == screen.SEED
    assert screen.BUILD in sources['staging']
    assert screen.QUALIFICATION in sources['staging']
    assert screen.REPLAY in sources['staging']
    assert 'all installed pack replays required' in sources['staging']
    with pytest.raises(ValueError):
        stage['development_blocks'](blocks[:-1])


def test_cd2_profiles_preserve_budgets_no_retry_and_development_reporting():
    sources = screen.sources()
    for source in sources.values():
        namespace(source)
        assert 'external-windows-corrective-development-' not in source
        assert '/corrective-development-stage-v1' not in source
    assert "'model_attempts':38" in sources['prepare']
    assert "'max_seconds':600,'max_tool_calls':100" in sources['prepare']
    assert "'max_context_bytes':4096" in sources['prepare']
    assert "'no_model_retries':True" in sources['models']
    assert "'model':'gpt-6-luna','effort':'low'" in sources['models']
    assert 'reused-issue CD2 development screen; not independent confirmation' in sources['report']
    assert screen.CLUSTER_SEED in sources['report']
    assert len(screen.supporting_sources()) == 3
