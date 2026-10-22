"""Semantic nomination contract tests; vectors here are plumbing fixtures only."""
import math

import pytest

from atmem.context_engine.contracts import ContextRequestV3
from atmem.context_engine.hybrid import HybridStoredContextEngine
from atmem.context_engine.formation import FormationManager, SourceEpisode, SourcePart
from atmem.context_engine.semantic import SemanticIndex, SQLiteExactSemanticIndex
from atmem.context_engine.service import StoredContextEngine, stored_manifest, load_stored_canonical
from atmem.contracts.models import AuthorityScope
from atmem.store.sqlite import SQLiteStore


@pytest.fixture
def generation():
    store = SQLiteStore(':memory:')
    manager = FormationManager(store)
    scope = AuthorityScope(subject_id='fixture-person', agent_id='fixture-agent', workspace_id='fixture-workspace')
    gen = manager.begin_generation(scope, profile_id='context-fast')
    identities = []
    for i, text in enumerate(['First exact source.', 'Second exact source.']):
        source = manager.retain_source(SourceEpisode(episode_id=str(i), scope=scope,
            parts=(SourcePart('p', 0, 'text', 'text/plain', text.encode()),)))
        receipt = manager.form_source(source, gen, range_granularity='sentence')
        unit = store._conn.execute('SELECT unit_id FROM context_unit_ranges ur JOIN context_source_ranges r USING(range_id) WHERE ur.generation_id=? AND r.source_id=? LIMIT 1', (gen, source)).fetchone()[0]
        identities.append(unit)
    try:
        yield store, manager, gen, identities
    finally:
        store.close()


def index(store, gen, revision='fixed'):
    return SemanticIndex(store, generation_id=gen,
        model_identity={'model': 'fixture-embedding', 'revision': revision},
        dimensions=3, tables=4, bits=3)


def test_semantic_lookup_authorization_and_no_source_mutation(generation):
    store, manager, gen, ids = generation
    before = [tuple(r) for r in store._conn.execute('SELECT * FROM context_source_parts')]
    semantic = index(store, gen)
    assert semantic.build([(ids[0], [1, 0, 0]), (ids[1], [0, 1, 0])],
                          allowed_unit_ids=frozenset(ids)) == 2
    hits = semantic.nominate([1, 0, 0], allowed_unit_ids=frozenset(ids))
    assert hits[0].unit_id == ids[0]
    assert hits[0].score == pytest.approx(1.)
    assert semantic.nominate([1, 0, 0], allowed_unit_ids=frozenset()) == ()
    hidden = semantic.nominate([1, 0, 0], allowed_unit_ids=frozenset([ids[1]]))
    assert all(h.unit_id != ids[0] for h in hidden)
    assert before == [tuple(r) for r in store._conn.execute('SELECT * FROM context_source_parts')]


def test_failed_build_rolls_back_and_unknown_ids_cannot_be_indexed(generation):
    store, manager, gen, ids = generation
    semantic = index(store, gen)
    with pytest.raises(ValueError, match='unauthorized'):
        semantic.build([(ids[0], [1, 0, 0]), ('foreign', [0, 1, 0])], allowed_unit_ids=frozenset(ids))
    assert store._conn.execute('SELECT COUNT(*) FROM context_vectors').fetchone()[0] == 0
    assert semantic.build([(ids[0], [1, 0, 0])], allowed_unit_ids=frozenset(ids)) == 1


def test_unauthorized_bucket_entries_cannot_consume_authorized_candidate_quota(generation):
    store, manager, gen, ids = generation
    semantic = index(store, gen)
    semantic.build([(identity, [1, 0, 0]) for identity in ids], allowed_unit_ids=frozenset(ids))
    visible = max(ids)  # Hidden lower-sorting ID must not crowd this one out.
    hits = semantic.nominate([1, 0, 0], allowed_unit_ids=frozenset([visible]),
                             limit=1, candidate_limit=1)
    assert [h.unit_id for h in hits] == [visible]


@pytest.mark.parametrize('vector', [[0, 0, 0], [1, 0], [math.nan, 1, 0], [True, 0, 0]])
def test_invalid_vectors_cannot_become_index(generation, vector):
    store, manager, gen, ids = generation
    with pytest.raises(ValueError):
        index(store, gen).build([(ids[0], vector)], allowed_unit_ids=frozenset(ids))


def test_semantic_model_identity_mismatch_and_duplicate_build_fail(generation):
    store, manager, gen, ids = generation
    semantic = index(store, gen)
    semantic.build([(ids[0], [1, 0, 0])], allowed_unit_ids=frozenset(ids))
    with pytest.raises(ValueError, match='already built'):
        semantic.build([(ids[0], [1, 0, 0])], allowed_unit_ids=frozenset(ids))
    with pytest.raises(ValueError, match='mismatched'):
        index(store, gen, revision='changed').nominate([1, 0, 0], allowed_unit_ids=frozenset(ids))


def test_stale_revision_and_inactive_units_fail_closed(generation):
    store, manager, gen, ids = generation
    semantic = index(store, gen)
    semantic.build([(ids[0], [1, 0, 0])], allowed_unit_ids=frozenset(ids))
    store._conn.execute('UPDATE context_evidence_units SET lifecycle=? WHERE unit_id=?', ('deleted', ids[0]))
    assert semantic.nominate([1, 0, 0], allowed_unit_ids=frozenset(ids)) == ()
    store._conn.execute('UPDATE context_view_generations SET revision=revision+1 WHERE generation_id=?', (gen,))
    with pytest.raises(ValueError, match='stale'):
        semantic.nominate([1, 0, 0], allowed_unit_ids=frozenset(ids))


def test_active_generation_cannot_be_rebuilt_in_place(generation):
    store, manager, gen, ids = generation
    manager.verify_generation(gen)
    manager.activate_generation(gen)
    with pytest.raises(ValueError, match='before generation freeze'):
        index(store, gen).build([(ids[0], [1, 0, 0])], allowed_unit_ids=frozenset(ids))


def test_hybrid_preserves_baseline_evidence_and_byte_budget(generation):
    store, manager, gen, ids = generation
    semantic = index(store, gen)
    semantic.build([(ids[0], [1, 0, 0]), (ids[1], [0, 1, 0])], allowed_unit_ids=frozenset(ids))
    manager.verify_generation(gen)
    manager.activate_generation(gen)
    scope = AuthorityScope(subject_id='fixture-person', agent_id='fixture-agent', workspace_id='fixture-workspace')
    revision = store._conn.execute('SELECT canonical_generation FROM context_view_generations WHERE generation_id=?', (gen,)).fetchone()[0]
    query = 'What is the first exact source?'
    request = ContextRequestV3(context_id='context', request_id='request', scope=scope,
        query=query, profile_id='context-fast', generation=revision, turn_id='turn', mode='active')
    manifest = stored_manifest(store, request, generation_id=gen)
    base = StoredContextEngine(store, generation_id=gen, candidate_budget=168).select(request, manifest)
    hybrid = HybridStoredContextEngine(store, generation_id=gen, semantic_index=semantic,
        query=query, query_vector=[0, 1, 0]).select(request, manifest)
    assert hybrid.status == base.status
    assert set(base.selected_unit_ids).issubset(hybrid.selected_unit_ids)
    assert set(hybrid.selected_unit_ids).issubset(manifest.authorized_unit_ids)
    assert hybrid.action_constraints == base.action_constraints
    canonical = load_stored_canonical(store, scope, gen, hybrid.selected_unit_ids, revision)
    assert len('\n\n'.join(item.text for item in canonical).encode()) <= request.budget.context_bytes
    with pytest.raises(ValueError, match='different request text'):
        HybridStoredContextEngine(store, generation_id=gen, semantic_index=semantic,
            query='a different query', query_vector=[0, 1, 0]).select(request, manifest)


def test_optional_native_exact_backend_reuses_vectors_without_approximation(generation):
    pytest.importorskip('sqlite_vec')
    store, manager, gen, ids = generation
    semantic = index(store, gen)
    semantic.build([(ids[0], [1, 0, 0]), (ids[1], [0, 1, 0])], allowed_unit_ids=frozenset(ids))
    exact = SQLiteExactSemanticIndex(store, generation_id=gen,
        model_identity={'model': 'fixture-embedding', 'revision': 'fixed'},
        dimensions=3, tables=4, bits=3)
    if not callable(getattr(store._conn, 'enable_load_extension', None)):
        with pytest.raises(ValueError, match='SQLite runtime cannot load extensions'):
            exact.nominate([1, 0, 0], allowed_unit_ids=frozenset(ids))
        return
    hits = exact.nominate([1, 0, 0], allowed_unit_ids=frozenset(ids))
    assert hits[0].unit_id == ids[0]
    assert hits[0].score == pytest.approx(1.)
    assert [h.unit_id for h in exact.nominate([1, 0, 0], allowed_unit_ids=frozenset([ids[1]]))] == [ids[1]]
    with pytest.raises(ValueError, match='capacity exceeded'):
        exact.nominate([1, 0, 0], allowed_unit_ids=frozenset(ids), max_index_vectors=1)


def test_native_exact_backend_on_encrypted_sqlcipher(tmp_path):
    pytest.importorskip('sqlcipher3')
    pytest.importorskip('sqlite_vec')
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    database = tmp_path / 'native.db'
    HouseholdApplication.initialize(database, encrypted=True, backend='file')
    memory = Memory(database, auto_vectors=False)
    try:
        manager = FormationManager(memory.store)
        scope = AuthorityScope(subject_id='owner', agent_id='agent', workspace_id='workspace')
        gen = manager.begin_generation(scope, profile_id='context-fast')
        source = manager.retain_source(SourceEpisode(episode_id='source', scope=scope,
            parts=(SourcePart('p', 0, 'text', 'text/plain', b'Encrypted native evidence.'),)))
        manager.form_source(source, gen, range_granularity='sentence')
        unit = memory.store._conn.execute('SELECT unit_id FROM context_evidence_units WHERE generation_id=? LIMIT 1', (gen,)).fetchone()[0]
        semantic = index(memory.store, gen)
        semantic.build([(unit, [1, 0, 0])], allowed_unit_ids=frozenset([unit]))
        exact = SQLiteExactSemanticIndex(memory.store, generation_id=gen,
            model_identity={'model': 'fixture-embedding', 'revision': 'fixed'},
            dimensions=3, tables=4, bits=3)
        hits = exact.nominate([1, 0, 0], allowed_unit_ids=frozenset([unit]))
        assert hits[0].unit_id == unit and hits[0].score == pytest.approx(1.)
    finally:
        memory.close()


def test_balanced_pool_nomination_visits_views_before_second_query(generation,monkeypatch):
    from atmem.context_engine.planner import DeterministicPlanner
    from atmem.context_engine.retrieval import DeterministicRetriever
    from atmem.context_engine.pools import POOL_KINDS,PoolBudget
    store,manager,gen,ids=generation
    plan=DeterministicPlanner().plan('What is the deployment rule and who approved it?')
    calls=[]
    def empty_pool(generation_id,kind,query,allowed_unit_ids=None,result_limit=None):
        calls.append((kind,query,result_limit))
        return []
    retriever=DeterministicRetriever(store,budget=PoolBudget(total_units=40),balanced_pools=True)
    monkeypatch.setattr(retriever,'_pool',empty_pool)
    result=retriever.retrieve(generation_id=gen,query='What is the deployment rule and who approved it?',
                             plan=plan,max_sources=8,allowed_unit_ids=frozenset(ids))
    active=[kind for kind in POOL_KINDS if plan.pool_queries.get(kind)]
    assert [kind for kind,_,_ in calls[:len(active)]]==active
    assert all(1 <= limit <= 32 for _,_,limit in calls)
    assert result.scanned_units==0
