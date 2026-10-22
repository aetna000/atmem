"""Fabricated arithmetic fixtures only; never retrieval efficacy evidence."""
from copy import deepcopy

import pytest

from research.retrieval_2310.evaluate import PILLARS,working_set_readiness


def report(count,baseline,candidate):
    def arm(passed):
        return {'requested':count,'graded':count,'passed':passed,'complete':True,
            'ungraded_or_not_executed':0,'reader_input_tokens':{'unknown_tasks':0},
            'reader_output_tokens':{'unknown_tasks':0}}
    return {'baseline':arm(baseline),'candidate':arm(candidate),'paired_tasks':count,
        'complete_paired_comparison':True,'paired_wins':candidate-baseline,'paired_losses':0}


def gate(working=None,recurring=None,**overrides):
    options=dict(pillar_decisions={p:'accepted' for p in PILLARS},review_passed=True,
        guardrails_passed=True,artifact_qualified=True,recording_qualified=True,
        budget_qualified=True,archive_qualified=True)
    options.update(overrides)
    return working_set_readiness(working or report(60,30,54),recurring or report(18,9,18),**options)


def test_owner_fixed_set_gate_does_not_invent_comparator_or_transfer_evidence():
    value=gate()
    assert value['ready_for_600']
    assert not value['generalization_established']
    assert not value['mem0_superiority_established']
    assert not value['external_transfer_corpus_required']


@pytest.mark.parametrize('flag',['review_passed','guardrails_passed','artifact_qualified',
    'recording_qualified','budget_qualified','archive_qualified'])
def test_every_operational_gate_is_mandatory(flag):
    assert not gate(**{flag:False})['ready_for_600']
    assert not gate(**{flag:1})['ready_for_600']


@pytest.mark.parametrize('change',['missing','unknown_usage','low_score','boolean_count','bad_pair_counts'])
def test_missing_failed_unknown_and_inconsistent_outcomes_never_pass(change):
    working=report(60,30,54)
    if change=='missing':working['candidate']['graded']=59
    if change=='unknown_usage':working['candidate']['reader_input_tokens']['unknown_tasks']=1
    if change=='low_score':working=report(60,30,53)
    if change=='boolean_count':working['candidate']['passed']=True
    if change=='bad_pair_counts':working['paired_wins']=1
    assert not gate(working=working)['ready_for_600']


def test_full_recurring_check_and_real_component_acceptance_are_required():
    assert not gate(recurring=report(18,9,17))['ready_for_600']
    pending={p:'accepted' for p in PILLARS};pending['complete-evidence']='pending'
    assert not gate(pillar_decisions=pending)['ready_for_600']
    assert not gate(pillar_decisions={})['ready_for_600']
    assert not gate(working=report(60,54,54))['ready_for_600']
