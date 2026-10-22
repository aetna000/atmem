from types import SimpleNamespace

import pytest

from benchmarks.dolphinbench import adapter


def fixture(monkeypatch,totals,engine='context-v3'):
    value=object.__new__(adapter.AtMemAdapter)
    value.ledger='fixture';value.cap_usd=1;value.campaign_identity={};value.memory_engine=engine
    monkeypatch.setattr(adapter,'BudgetLedger',lambda *a,**k:
        SimpleNamespace(totals=lambda:totals,close=lambda:None))
    return value


def test_upstream_test_cost_includes_memory_intelligence_but_excludes_grading(monkeypatch):
    value=fixture(monkeypatch,{
        'tests':{'actual_usd':0,'reserved_usd':0},
        'state-assessment':{'actual_usd':.2,'reserved_usd':0},
        'initial-state-assessment':{'actual_usd':.3,'reserved_usd':0},
        'judge':{'actual_usd':5,'reserved_usd':0},
        'ingestion':{'actual_usd':.4,'reserved_usd':0}})
    assert value.total_cost_usd('tests')==.5
    assert value.total_cost_usd('ingestion')==.4


def test_uncertain_memory_processing_cannot_be_reported_as_zero_cost(monkeypatch):
    value=fixture(monkeypatch,{'state-assessment':{'actual_usd':0,'reserved_usd':.2}})
    with pytest.raises(ValueError,match='Unreconciled'):value.total_cost_usd('tests')


def test_unknown_upstream_phase_fails_instead_of_inventing_zero(monkeypatch):
    value=fixture(monkeypatch,{})
    with pytest.raises(ValueError,match='phases'):value.total_cost_usd('judge')
