"""SQL access-path fixtures, not a retrieval-quality or production-speed claim."""
from dataclasses import replace

import pytest

from atmem.context_engine.formation import FormationManager,SourceEpisode,SourcePart
from atmem.context_engine.retrieval import DeterministicRetriever,RetrievedCandidate,SOURCE_RAW_ROWS_SQL
from atmem.contracts.models import AuthorityScope
from atmem.store.sqlite import SQLiteStore


PREVIOUS_SQL='''SELECT u.unit_id,r.part_id,r.start_offset,r.end_offset,p.content_bytes
    FROM context_evidence_units u
    JOIN context_unit_views v ON v.generation_id=u.generation_id AND v.unit_id=u.unit_id
    JOIN context_unit_ranges ur ON ur.generation_id=u.generation_id AND ur.unit_id=u.unit_id
    JOIN context_source_ranges r USING(range_id)
    JOIN context_source_parts p ON p.source_id=r.source_id AND p.part_id=r.part_id
    WHERE u.generation_id=? AND r.source_id=? AND u.lifecycle='active' AND v.kind='raw_state'
    ORDER BY p.ordinal,r.start_offset,r.end_offset,u.unit_id'''


@pytest.fixture
def state():
    store=SQLiteStore(':memory:');manager=FormationManager(store)
    scope=AuthorityScope('owner','agent','workspace')
    gen=manager.begin_generation(scope,profile_id='context-fast')
    source=manager.retain_source(SourceEpisode(episode_id='target',scope=scope,parts=(
        SourcePart('z-first',0,'text','text/plain',b'First item. Second item. Final item.'),
        SourcePart('a-second',1,'text','text/plain','Unicode evidence: café.'.encode()))))
    manager.form_source(source,gen,range_granularity='sentence')
    yield store,manager,scope,gen,source
    store.close()


def rows(store,sql,gen,source):
    return [tuple(r) for r in store._conn.execute(sql,(gen,source))]


def vm_work(store,sql,gen,source):
    steps=0
    def count():
        nonlocal steps
        steps+=1
        return 0
    store._conn.set_progress_handler(count,1)
    try:value=rows(store,sql,gen,source)
    finally:store._conn.set_progress_handler(None,0)
    return value,steps


def test_source_lookup_seeks_one_source_before_generation_members(state):
    store,_,_,gen,source=state
    plan=[tuple(r)[-1] for r in store._conn.execute('EXPLAIN QUERY PLAN '+SOURCE_RAW_ROWS_SQL,(gen,source))]
    assert 'idx_context_source_ranges_order' in plan[0] and 'source_id=?' in plan[0]
    assert 'idx_context_unit_ranges_range' in plan[1] and 'generation_id=? AND range_id=?' in plan[1]
    assert all(not item.startswith('SCAN ') for item in plan)
    assert rows(store,SOURCE_RAW_ROWS_SQL,gen,source)==rows(store,PREVIOUS_SQL,gen,source)


def test_source_lookup_preserves_generation_lifecycle_views_and_byte_ranges(state):
    store,manager,scope,gen,source=state
    other=manager.begin_generation(scope,profile_id='context-fast')
    manager.form_source(source,other,range_granularity='sentence')
    original=rows(store,SOURCE_RAW_ROWS_SQL,gen,source)
    assert [r[1] for r in original]==['z-first','z-first','z-first','a-second']
    store._conn.execute("UPDATE context_evidence_units SET lifecycle='deleted' WHERE generation_id=? AND unit_id=?",(gen,original[0][0]))
    store._conn.execute("DELETE FROM context_unit_views WHERE generation_id=? AND unit_id=? AND kind='raw_state'",(gen,original[1][0]))
    for generation in (gen,other,'unavailable'):
        for selected in (source,'unavailable'):
            assert rows(store,SOURCE_RAW_ROWS_SQL,generation,selected)==rows(store,PREVIOUS_SQL,generation,selected)
    actual=rows(store,SOURCE_RAW_ROWS_SQL,gen,source)
    assert actual==original[2:]
    assert bytes(actual[-1][4])[actual[-1][2]:actual[-1][3]].decode()=='Unicode evidence: café.'


def test_unrelated_generation_ranges_do_not_multiply_source_lookup_vm_work(state):
    store,manager,scope,gen,source=state
    expected,small=vm_work(store,SOURCE_RAW_ROWS_SQL,gen,source)
    noise=manager.retain_source(SourceEpisode(episode_id='unrelated',scope=scope,parts=(
        SourcePart('text',0,'text','text/plain',
            ' '.join(f'Unrelated item number {i}.' for i in range(600)).encode()),)))
    manager.form_source(noise,gen,range_granularity='sentence')
    actual,large=vm_work(store,SOURCE_RAW_ROWS_SQL,gen,source)
    previous,old=vm_work(store,PREVIOUS_SQL,gen,source)
    assert actual==previous==expected
    assert large<=small+50
    assert old>5*large


def test_neighbor_and_query_head_selection_keep_existing_order_and_scores(state):
    store,_,_,gen,source=state
    values=rows(store,SOURCE_RAW_ROWS_SQL,gen,source)
    first=values[1]
    seed=RetrievedCandidate(unit_id=first[0],kind='raw_state',source_id=source,
        part_id=first[1],start=first[2],end=first[3],
        text=bytes(first[4])[first[2]:first[3]].decode(),score=1.25,matched_obligation_ids=())
    retriever=DeterministicRetriever(store)
    neighbors=retriever._neighbors(gen,seed,radius=1)
    assert [r.unit_id for r in neighbors]==[values[0][0],values[2][0]]
    assert all(r.score==seed.score for r in neighbors)
    head=retriever._source_query_head(gen,seed,'Unicode café')
    assert head.part_id=='a-second' and head.score==seed.score
    unavailable=replace(seed,unit_id='missing')
    assert retriever._neighbors(gen,unavailable)==()
