import inspect

import pytest

from benchmarks.code_replay import public_selector_profile as profile
from benchmarks.code_replay.public_selector_audit import audit_programs


def plans():
    old, _ = profile.validators()
    def program(role):
        return 'for name,source in '+repr([(profile.ROLES[role], old+'\n')])+':\n pass\n'
    return [{'block': {'instance_id': 'repo-'+str(i), 'slot': i},
             'server_template': program('server'), 'public_worker_source': program('worker')}
            for i in range(19)]


def test_every_template_is_parsed_and_delta_is_retained_without_execution():
    value = audit_programs(plans(), profile.validators(), inspect.getsource(profile))
    assert value['summary']['programs'] == 38
    assert value['summary']['runtime_qualified'] is False
    assert value['summary']['template_programs_executed'] == 0
    for case in value['cases']:
        assert set(case['programs']) == {'server', 'worker'}
        for row in case['programs'].values():
            assert row['original_sha256'] != row['corrected_sha256']
            assert row['original'] != row['corrected']


def test_partial_duplicate_or_mutated_cohort_cannot_pass():
    source = inspect.getsource(profile); pair = profile.validators()
    with pytest.raises(ValueError):
        audit_programs(plans()[:-1], pair, source)
    duplicate = plans(); duplicate[-1]['block'] = duplicate[0]['block']
    with pytest.raises(ValueError):
        audit_programs(duplicate, pair, source)
    changed = plans(); changed[-1]['public_worker_source'] = 'raise RuntimeError("must not execute")'
    with pytest.raises(ValueError):
        audit_programs(changed, pair, source)
