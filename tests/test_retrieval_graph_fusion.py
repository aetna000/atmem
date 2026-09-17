from dataclasses import replace

import pytest

from atmem import Memory
from atmem.contracts import AuthorityScope, ContextRequest, RecallRequest
from atmem.retrieve.graph import nominate


def request(**kwargs):
    return RecallRequest(request_id='graph-test', scope=AuthorityScope('u', 'a', 'w'),
                         query='What does my boss use for flights?',
                         retrieval_strategy='core-rrf-v1', **kwargs)


def seed(memory, content, subject='u', **kwargs):
    return memory.store.insert_record(subject_id=subject, content=content,
        source_type='user_message', trust_tier='user', source_session_id=None,
        source_turn_id=None, episode_id=None, confidence=1., scope='test', **kwargs)


@pytest.fixture
def memory(tmp_path):
    value = Memory(tmp_path / 'graph.db', auto_vectors=False)
    yield value
    value.close()


def test_graph_recovers_named_bridge_independently_of_lexical(memory):
    bridge = seed(memory, "User's boss is Sarah.")
    target = seed(memory, "Sarah's preferred airport is SEA.", raw={'modality': 'image'})
    seed(memory, 'Flights are frequent for the boss.')
    seed(memory, 'Flights for the boss are booked every week.')
    req = request(signals=('lexical',), candidate_limit=2, limit=10)
    lexical = memory.eligible_candidates(req)
    assert target not in {r.record_id for r in lexical.candidates}
    mixed = memory.eligible_candidates(replace(req, signals=('lexical', 'graph')))
    candidate = next(r for r in mixed.candidates if r.record_id == target)
    fusion = candidate.signals['fusion']
    assert fusion['channel_ranks'] == {'graph': 2}
    assert [s['record_id'] for s in fusion['graph_path']] == [bridge, target]
    assert fusion['graph_path'][0]['traversal_to'] == 'sarah'
    assert fusion['graph_path'][1]['traversal_from'] == 'sarah'
    assert fusion['graph_max_hops'] == 2
    assert fusion['graph_min_score_applied'] is False
    assert fusion['raw_scores']['graph'] == .75
    graph = memory.eligible_candidates(replace(req, signals=('graph',), min_score=1))
    assert {r.record_id for r in graph.candidates} == {bridge, target}
    event = next(e for e in memory.store.list_audit_events('u') if e['event_id'] == mixed.audit_event_id)
    metadata = event['payload']['retrieval_fusion']
    assert metadata['graph_support_record_ids'][target] == [bridge, target]
    assert 'Sarah' not in str(metadata) and req.query not in str(metadata)
    context = memory.prepare_context_v1(ContextRequest(context_id='gctx', scope=req.scope,
        candidate_set_id=mixed.candidate_set_id, record_ids=(target,)))
    assert 'SEA' in context.context


@pytest.mark.parametrize('denial', ['workspace', 'subject', 'remote', 'excluded',
                                  'quarantined', 'superseded', 'tombstoned'])
def test_denied_bridge_cannot_nominate_or_change_visible_scores(memory, denial):
    seed(memory, "User's boss is Alice.")
    seed(memory, 'Alice lives in Paris.')
    secret_target = seed(memory, "Sarah's preferred airport is SEA.")
    req = request(signals=('graph',), egress_class='remote')
    before = memory.eligible_candidates(req)
    args = {}
    if denial == 'workspace':
        args['raw'] = {'authority_scope': {'subject_id': 'u', 'workspace_id': 'hidden'}}
    elif denial == 'subject':
        args['subject'] = 'other'
    elif denial == 'remote':
        args['raw'] = {'sensitivity': 'restricted'}
    elif denial != 'excluded':
        args['status'] = denial
    bridge = seed(memory, "User's boss is Sarah.", **args)
    if denial == 'excluded':
        memory.store.set_retrieval_excluded('u', bridge, True, actor='test')
    after = memory.eligible_candidates(req)
    assert [r.to_dict() for r in after.candidates] == [r.to_dict() for r in before.candidates]
    assert secret_target not in {r.record_id for r in after.candidates}


def test_persisted_graph_aliases_and_edges_are_not_inputs(memory, monkeypatch):
    from atmem.graph import GraphIndex
    memory.remember('u', 'My boss is Sarah.')
    memory.remember('u', "Sarah's preferred airport is SEA.")
    req = request(signals=('graph',))
    before = memory.eligible_candidates(req)
    def forbidden(*args, **kwargs):
        raise AssertionError('global graph must not be consulted')
    monkeypatch.setattr(GraphIndex, 'recall', forbidden)
    memory.store._conn.execute("UPDATE entity_aliases SET surface = 'bogus secret alias'")
    memory.store._conn.execute("UPDATE edges SET status = 'tombstoned'")
    after = memory.eligible_candidates(req)
    assert [r.to_dict() for r in after.candidates] == [r.to_dict() for r in before.candidates]


def test_normalized_surface_join_and_root_fanout(memory):
    seed(memory, 'Sarah lives in Austin.')
    city = seed(memory, 'Austin uses Rail.')
    seed(memory, "User's boss is Sarah.")
    unrelated = seed(memory, "User's favorite color is blue.")
    req = replace(request(signals=('graph',)), query='Sarah')
    result = memory.eligible_candidates(req)
    assert city in {r.record_id for r in result.candidates}
    assert unrelated not in {r.record_id for r in result.candidates}
    assert not memory.eligible_candidates(replace(req, query='you')).candidates


def test_cycles_self_loops_and_two_edge_bound():
    records = [dict(id=str(i), content=t) for i, t in enumerate([
        'Alice works with Bob.', 'Bob works with Carol.',
        'Carol works with Alice.', 'Alice works with Alice.',
        'Carol uses Delta.', 'Delta uses Echo.',
    ])]
    ids, scores, paths, metadata = nominate(records, 'Alice', 100)
    assert '5' not in ids
    assert '3' not in ids
    for path in paths.values():
        assert 1 <= len(path) <= 2
        assert len({s['record_id'] for s in path}) == len(path)
        nodes = [path[0]['traversal_from']] + [s['traversal_to'] for s in path]
        assert len(set(nodes)) == len(nodes)
    assert metadata['graph_edge_examinations'] <= 256
    assert nominate(list(reversed(records)), 'Alice', 100) == (ids, scores, paths, metadata)


def test_named_user_form_cannot_bypass_root_fanout():
    records = [dict(id='a', content='User likes Sarah.'),
               dict(id='b', content='User likes Secrets.')]
    ids, _, _, _ = nominate(records, 'Sarah', 100)
    assert ids == ['a']
    assert nominate(records, 'User', 100)[0] == []


def test_correction_and_forgetting_remove_old_graph_paths(memory):
    memory.remember('u', 'My boss is Sarah.')
    old = memory.remember('u', "Sarah's preferred airport is SEA.")['records'][0]['id']
    new = memory.remember('u', "Sarah's preferred airport is LAX.")['records'][0]['id']
    req = request(signals=('graph',))
    found = {r.record_id for r in memory.eligible_candidates(req).candidates}
    assert new in found and old not in found
    memory.forget_record('u', new)
    assert new not in {r.record_id for r in memory.eligible_candidates(req).candidates}


def test_truncation_seed_work_and_output_budgets():
    many_seeds = [dict(id=f'r{i:04}', content=f'Person{i} uses Tool{i}.') for i in range(30)]
    _, _, _, metadata = nominate(many_seeds, 'uses', 100)
    assert metadata['graph_seeds_used'] == 16 and metadata['graph_truncated']
    fanout = [dict(id=f'r{i:04}', content=f'Alice uses Tool{i}.') for i in range(400)]
    ids, _, _, metadata = nominate(fanout, 'Alice', 2000)
    assert len(ids) == 256
    assert metadata['graph_edge_examinations'] == 256
    assert metadata['graph_truncated']
    ids, _, _, metadata = nominate(fanout[:10], 'Alice', 1)
    assert len(ids) == 1 and metadata['graph_truncated']
    assert metadata['graph_candidate_limit'] == 1


@pytest.mark.parametrize('mutation', ['content', 'exclude', 'scope'])
def test_support_record_outside_nomination_quota_revalidated(memory, monkeypatch, mutation):
    import atmem.retrieve.graph as graph
    bridge = seed(memory, "User's boss is Sarah.")
    target = seed(memory, "Sarah's preferred airport is SEA.")
    original = graph.nominate
    def mutate(records, query, limit):
        ids, scores, paths, metadata = original(records, query, limit)
        assert [s['record_id'] for s in paths[target]] == [bridge, target]
        # Retain only the target to exercise supporting IDs outside fused IDs.
        if mutation == 'content':
            memory.store._conn.execute('UPDATE records SET content = ? WHERE id = ?', ('changed', bridge))
        elif mutation == 'scope':
            memory.store._conn.execute('UPDATE records SET raw = ? WHERE id = ?',
                ('{"authority_scope":{"subject_id":"u","workspace_id":"hidden"}}', bridge))
        else:
            memory.store.set_retrieval_excluded('u', bridge, True, actor='test')
        return [target], {target: scores[target]}, {target: paths[target]}, metadata
    monkeypatch.setattr(graph, 'nominate', mutate)
    with pytest.raises(ValueError, match='changed during core hybrid'):
        memory.eligible_candidates(request(signals=('graph',)))


def test_empty_graph_audits_coverage_and_disabled_graph_does_no_work(memory, monkeypatch):
    import atmem.retrieve.graph as graph
    seed(memory, 'booking ZX93')
    empty = memory.eligible_candidates(request(signals=('graph',)))
    assert not empty.candidates
    event = next(e for e in memory.store.list_audit_events('u') if e['event_id'] == empty.audit_event_id)
    assert event['payload']['retrieval_fusion']['graph_extracted_edges'] == 0
    assert event['payload']['retrieval_fusion']['channel_status']['graph'] == 'empty'
    monkeypatch.setattr(graph, 'nominate', lambda *args: pytest.fail('graph disabled'))
    memory.eligible_candidates(request(signals=('lexical',)))
    memory.eligible_candidates(replace(request(), retrieval_strategy='legacy'))


def test_forgetting_bridge_invalidates_candidate_set_before_context(memory):
    bridge = seed(memory, "User's boss is Sarah.")
    target = seed(memory, "Sarah's preferred airport is SEA.")
    req = request(signals=('graph',))
    candidates = memory.eligible_candidates(req)
    assert target in {r.record_id for r in candidates.candidates}
    memory.forget_record('u', bridge)
    with pytest.raises(ValueError):
        memory.prepare_context_v1(ContextRequest(context_id='stale-path', scope=req.scope,
            candidate_set_id=candidates.candidate_set_id, record_ids=(target,)))
