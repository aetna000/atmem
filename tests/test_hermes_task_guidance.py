from atmem.adapters.hermes.task_guidance import task_guidance,RECOVERABLE_CONTEXT_STATUSES


def test_workflow_is_explicit_and_never_treats_policy_denial_as_recoverable():
    assert task_guidance()==''
    assert not RECOVERABLE_CONTEXT_STATUSES & {'stale','withheld','withheld_by_policy','inactive','unavailable_or_denied'}
    assert 'not a substitute' in task_guidance(application_workflow=True)
    assert 'not a policy authorization denial' in task_guidance(discovery=True,initial_status='contradicted')
    assert 'not a policy authorization denial' not in task_guidance(discovery=True,initial_status='withheld')
