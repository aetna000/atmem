import inspect

import pytest

from benchmarks.code_replay import confirmation_v3_staging
from benchmarks.code_replay.corrective_staging import development_blocks, staging_source


def test_fresh_schedule_preserves_every_issue_and_balances_order():
    old = [{'instance_id': str(i), 'repeat': r, 'slot': i*2+r-1}
           for i in range(19) for r in (1, 2)]
    result = development_blocks(old)
    assert result == development_blocks(list(reversed(old)))
    assert len(result) == 19
    assert sum(b['order'][0] == 'native' for b in result) == 10
    assert {b['instance_id'] for b in result} == {b['instance_id'] for b in old}
    assert [b['slot'] for b in result] == list(range(19))
    with pytest.raises(ValueError):
        development_blocks(old[:-1])


def test_staging_reuses_full_original_sources_and_does_not_infer():
    source = staging_source(inspect.getsource(confirmation_v3_staging))
    namespace = {'__name__': 'corrective_staging_test'}
    exec(compile(source, '<corrective-staging>', 'exec'), namespace)
    assert namespace['RUN'].startswith('external-windows-corrective-development-')
    assert "'all_38_cases_staged':len(results)==19" in source
    assert "str(prior_slots[identity])" in source
    assert "'model_calls':0" in source
    assert "'inference_authorized_by_staging':False" in source
    assert "max_workers=2" in source
    with pytest.raises(ValueError):
        staging_source('unknown source')
