"""Discovery safety/plumbing fixtures, not measured task-performance claims."""
from dataclasses import replace
import json

import pytest

from atmem.context_engine.contracts import ContextRequestV3
from atmem.context_engine.discovery import EvidenceDiscoverySession
from atmem.context_engine.discovery_mcp import EvidenceDiscoveryMCP
from atmem.context_engine.formation import FormationManager,SourceEpisode,SourcePart
from atmem.context_engine.navigator import NavigationBudget
from atmem.context_engine.service import GovernanceViolation,stored_manifest
from atmem.contracts.models import AuthorityScope
from atmem.store.sqlite import SQLiteStore


@pytest.fixture
def state():
    store=SQLiteStore(':memory:')
    manager=FormationManager(store)
    scope=AuthorityScope('person','agent','workspace')
    gen=manager.begin_generation(scope,profile_id='context-fast')
    source=manager.retain_source(SourceEpisode(episode_id='source',scope=scope,
        parts=(SourcePart('text',0,'text','text/plain',b'The archive is violet. The old archive was amber.'),)))
    manager.form_source(source,gen,range_granularity='sentence')
    manager.verify_generation(gen);manager.activate_generation(gen)
    revision=store._conn.execute('SELECT canonical_generation FROM context_view_generations WHERE generation_id=?',(gen,)).fetchone()[0]
    request=ContextRequestV3(context_id='ctx',request_id='req',scope=scope,query='Archive color?',
        profile_id='context-fast',generation=revision,turn_id='turn',mode='active')
    ids=[r[0] for r in store._conn.execute('SELECT unit_id FROM context_evidence_units WHERE generation_id=? ORDER BY unit_id',(gen,))]
    audits=[]
    def session(**kwargs):
        return EvidenceDiscoverySession(store,generation_id=gen,request=request,
            authorize=kwargs.pop('authorize',lambda r:stored_manifest(store,r,generation_id=gen)),
            audit=kwargs.pop('audit',lambda receipt:audits.append(receipt) or 'audit-id'),
            budget=kwargs.pop('budget',NavigationBudget(4,20000,10000)),**kwargs)
    yield store,gen,ids,request,audits,session
    store.close()


def test_semantic_only_discovery_does_not_require_lexical_sufficiency(state):
    store,gen,ids,request,audits,session=state
    before=[tuple(r) for r in store._conn.execute('SELECT * FROM context_source_parts')]
    calls=[]
    def nominate(query,manifest,limit):
        calls.append(query)
        return ids[:1]
    value=session(lexical=False,semantic_nominate=nominate).search('unmatched paraphrase')
    assert calls==['unmatched paraphrase']
    assert value['channels']==['semantic']
    assert value['evidence'][0]['unit_id']==ids[0]
    assert value['evidence'][0]['source_range']['source_sha256'].startswith('sha256:')
    assert value['sufficiency']=='not_assessed'
    assert len(audits)==1
    assert before==[tuple(r) for r in store._conn.execute('SELECT * FROM context_source_parts')]


def test_followup_shares_operation_budget_and_rechecks_authorization(state):
    store,gen,ids,request,audits,session=state
    calls=[]
    def authorize(req):
        calls.append(req.request_id)
        return stored_manifest(store,req,generation_id=gen)
    search=session(authorize=authorize,budget=NavigationBudget(2,20000,10000))
    search.inspect(ids[0]);search.inspect(ids[0])
    assert len(calls)==4
    assert len(set(calls))==2
    with pytest.raises(RuntimeError,match='operation budget'):search.inspect(ids[0])


def test_revoked_scope_and_foreign_semantic_nomination_cannot_disclose(state):
    store,gen,ids,request,audits,session=state
    def wrong(req):
        return replace(stored_manifest(store,req,generation_id=gen),scope=AuthorityScope('other','agent','workspace'))
    with pytest.raises(GovernanceViolation):session(authorize=wrong).inspect(ids[0])
    with pytest.raises(GovernanceViolation):session(semantic_nominate=lambda *a:['foreign']).search('archive')
    assert audits==[]


def test_deletion_and_generation_change_block_late_disclosure(state):
    store,gen,ids,request,audits,session=state
    def removed(query,manifest,limit):
        store._conn.execute("UPDATE context_evidence_units SET lifecycle='deleted' WHERE unit_id=?",(ids[0],))
        return ids[:1]
    with pytest.raises(GovernanceViolation):session(lexical=False,semantic_nominate=removed).search('archive')
    store._conn.execute('UPDATE context_view_generations SET canonical_generation=canonical_generation+1 WHERE generation_id=?',(gen,))
    with pytest.raises(GovernanceViolation):session().search('archive')
    assert audits==[]


def test_scope_revocation_during_provider_call_is_rechecked(state):
    store,gen,ids,request,audits,session=state
    revoked=False
    def authorize(req):
        if revoked:raise PermissionError('revoked')
        return stored_manifest(store,req,generation_id=gen)
    def nominate(*args):
        nonlocal revoked
        revoked=True
        return ids[:1]
    with pytest.raises(PermissionError):session(authorize=authorize,lexical=False,semantic_nominate=nominate).search('archive')
    assert audits==[]


def test_response_budget_includes_envelope_and_audit_failure_withholds(state):
    store,gen,ids,request,audits,session=state
    search=session(budget=NavigationBudget(4,1000,10000))
    values=[]
    for _ in range(4):
        try:values.append(search.inspect(ids[0]))
        except RuntimeError:break
    assert sum(len(json.dumps(v,ensure_ascii=False,separators=(',',':')).encode()) for v in values)<=1000
    with pytest.raises(GovernanceViolation,match='audit'):session(audit=lambda r:None).inspect(ids[0])


def test_elapsed_budget_is_checked_after_slow_provider(state):
    store,gen,ids,request,audits,session=state
    now=[0.]
    def nominate(*args):now[0]=2.;return ids[:1]
    search=session(clock=lambda:now[0],budget=NavigationBudget(4,20000,1000),lexical=False,semantic_nominate=nominate)
    with pytest.raises(RuntimeError,match='elapsed-time'):search.search('archive')
    assert audits==[]


def test_mcp_has_no_mutation_or_scope_selection_path(state):
    store,gen,ids,request,audits,session=state
    mcp=EvidenceDiscoveryMCP(session())
    reply=mcp.handle({'jsonrpc':'2.0','id':1,'method':'tools/list'})
    assert {t['name'] for t in reply['result']['tools']}=={'memory_search','memory_inspect'}
    for name,args in [('memory_remember',{'message':'evil'}),('memory_search',{'query':'archive','subject_id':'other'})]:
        value=mcp.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':name,'arguments':args}})
        assert value['error']['code']==-32602
    value=mcp.handle({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'memory_inspect','arguments':{'unit_id':ids[0]}}})
    assert value['result']['isError'] is False
    assert json.loads(value['result']['content'][0]['text'])['sufficiency']=='not_assessed'


def test_wholly_authorized_generation_uses_scoped_index_not_massive_id_filter(state,monkeypatch):
    from atmem.context_engine.retrieval import DeterministicRetriever
    store,gen,ids,request,audits,session=state
    original=DeterministicRetriever.retrieve
    arguments=[]
    def observed(self,**kwargs):
        arguments.append(kwargs['allowed_unit_ids'])
        return original(self,**kwargs)
    monkeypatch.setattr(DeterministicRetriever,'retrieve',observed)
    result=session().search('archive')
    assert result['evidence']
    assert arguments==[None]
    def restricted(req):
        return replace(stored_manifest(store,req,generation_id=gen),
                       authorized_unit_ids=tuple(ids[:1]),all_generation_units_authorized=False)
    result=session(authorize=restricted).search('archive')
    assert arguments[-1]==frozenset(ids[:1])
    assert all(e['unit_id']==ids[0] for e in result['evidence'])


def test_source_bundles_expand_original_part_in_source_order_and_deduplicate(state):
    store,gen,ids,request,audits,session=state
    before=[tuple(row) for row in store._conn.execute('SELECT * FROM context_source_parts')]
    result=session(lexical=False,semantic_nominate=lambda *a:ids[:1],source_bundles=True).search('archive')
    assert result['presentation']=='atomic-source-bundles-v1'
    assert result['whole_source_claim'] is False
    assert [e['text'] for e in result['evidence']]==['The archive is violet.','The old archive was amber.']
    assert len(result['source_groups'])==1
    assert result['source_groups'][0]['unit_ids']==[e['unit_id'] for e in result['evidence']]
    assert before==[tuple(row) for row in store._conn.execute('SELECT * FROM context_source_parts')]


def test_source_bundles_never_expand_beyond_restricted_authorization(state):
    store,gen,ids,request,audits,session=state
    def restricted(req):
        return replace(stored_manifest(store,req,generation_id=gen),
                       authorized_unit_ids=tuple(ids[:1]),all_generation_units_authorized=False)
    result=session(authorize=restricted,source_bundles=True).inspect(ids[0])
    assert [e['unit_id'] for e in result['evidence']]==ids[:1]
    assert result['source_groups'][0]['coverage']=='authorized_active_ranges_only'


def test_source_bundle_omission_is_atomic_under_byte_limit(state):
    store,gen,ids,request,audits,session=state
    full=session(source_bundles=True).inspect(ids[0])
    size=len(json.dumps(full,ensure_ascii=False,separators=(',',':')).encode())
    small=session(source_bundles=True,budget=NavigationBudget(1,size-1,10000)).inspect(ids[0])
    assert small['evidence']==[] and small['source_groups']==[]
    assert small['omitted_groups']==1 and small['omitted_count']==len(full['evidence'])


def test_source_bundles_recheck_every_expanded_member(state):
    store,gen,ids,request,audits,session=state
    calls=0
    def revoked_member(req):
        nonlocal calls
        calls+=1
        result=stored_manifest(store,req,generation_id=gen)
        return result if calls==1 else replace(result,authorized_unit_ids=tuple(ids[:1]))
    with pytest.raises(GovernanceViolation):session(authorize=revoked_member,source_bundles=True).inspect(ids[0])
    assert not audits


def test_bundle_query_seeks_one_source_part_before_generation_units(state):
    from atmem.context_engine.source_bundles import SOURCE_MEMBERS_SQL
    store,gen,ids,request,audits,session=state
    part=store._conn.execute('SELECT source_id,part_id FROM context_source_ranges LIMIT 1').fetchone()
    plan=[tuple(row)[-1] for row in store._conn.execute('EXPLAIN QUERY PLAN '+SOURCE_MEMBERS_SQL,
                         (gen,part['source_id'],part['part_id']))]
    assert 'idx_context_source_ranges_order' in plan[0] and 'source_id=? AND part_id=?' in plan[0]
    assert all(not detail.startswith('SCAN ') for detail in plan)
    previous='''SELECT u.unit_id,r.start_offset,r.end_offset,r.source_sha256
        FROM context_evidence_units u JOIN context_unit_ranges ur
          ON ur.generation_id=u.generation_id AND ur.unit_id=u.unit_id
        JOIN context_source_ranges r USING(range_id)
        WHERE u.generation_id=? AND r.source_id=? AND r.part_id=?
          AND u.lifecycle='active' AND ur.ordinal=0
        ORDER BY r.start_offset,r.end_offset,u.unit_id LIMIT 257'''
    args=(gen,part['source_id'],part['part_id'])
    assert [tuple(row) for row in store._conn.execute(previous,args)]==[
        tuple(row) for row in store._conn.execute(SOURCE_MEMBERS_SQL,args)]
