from dataclasses import replace

import pytest

from atmem import Memory
from atmem.contracts import AuthorityScope, RecallRequest
from atmem.retrieve.fusion import fuse_rankings


def request(**kwargs):
    return RecallRequest(request_id='q', scope=AuthorityScope('u', 'agent', 'workspace'),
                         query='booking ZX93', retrieval_strategy='core-rrf-v1', **kwargs)


def seed(memory, content, **kwargs):
    return memory.store.insert_record(subject_id='u', content=content,
        source_type='user_message', trust_tier='user', source_session_id=None,
        source_turn_id=None, episode_id=None, confidence=1., scope='test', **kwargs)


def test_rrf_union_dedup_and_determinism():
    result = fuse_rankings({'lexical': ['a', 'a', 'both'], 'semantic': ['b', 'both']})
    assert [r['record_id'] for r in result] == ['both', 'a', 'b']
    assert result[0]['channel_ranks'] == {'lexical': 2, 'semantic': 2}
    assert all(0 < r['score'] <= 1 for r in result)


def test_contract_legacy_wire_unchanged():
    req = request()
    assert req.to_dict()['retrieval_strategy'] == 'core-rrf-v1'
    assert 'retrieval_strategy' not in replace(req, retrieval_strategy='legacy').to_dict()
    with pytest.raises(ValueError):
        replace(req, retrieval_strategy='unknown')
    assert replace(req, signals=('graph',)).signals == ('graph',)
    with pytest.raises(ValueError, match='requires lexical'):
        replace(req, signals=('trust',))


def test_lexical_no_filler_scope_noninterference(tmp_path):
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        memory.remember('u', 'My booking reference is ZX93.')
        memory.remember('u', 'My favorite food is pasta.')
        req = request(signals=('lexical', 'graph'), min_score=.3)
        before = memory.eligible_candidates(req)
        assert len(before.candidates) == 1
        for i in range(5):
            seed(memory, f'My booking ZX93 secret reference is {i}.',
                            raw={'authority_scope': {'subject_id': 'u', 'workspace_id': 'denied'}})
        after = memory.eligible_candidates(req)
        assert [(r.record_id, r.score) for r in before.candidates] == [(r.record_id, r.score) for r in after.candidates]
        assert after.candidates[0].signals['fusion']['channel_status']['graph'] in {'empty', 'active'}
        assert 'authorization_withheld_active_count' not in after.candidates[0].signals['fusion']
        event = next(e for e in memory.store.list_audit_events('u') if e['event_id'] == after.audit_event_id)
        assert event['payload']['retrieval_fusion']['authorization_withheld_active_count'] == 5
        assert event['payload']['retrieval_fusion']['lexical_fact_min_score'] == .3
    finally:
        memory.close()


def test_semantic_only_nomination_and_quota(tmp_path, monkeypatch):
    from atmem.semantic import SemanticIndex
    class Embedder:
        identity = {'provider': 'test', 'model': 'concept', 'version': '1', 'normalization': 'l2'}
        def embed_documents(self, texts):
            return [[1., 0.] if 'aisle' in t else [0., 1.] for t in texts]
        def embed_query(self, query):
            return [1., 0.]
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    embedder = Embedder()
    try:
        memory.remember('u', 'I prefer aisle seats.')
        memory.remember('u', 'My booking reference is ZX93.')
        seed(memory, 'I always choose an aisle seat.', raw={'sensitivity': 'restricted'})
        index = SemanticIndex(f'{memory.store.path}.vectors.db', policy=memory.policy)
        index.build(memory, 'u', embedder)
        index.close()
        monkeypatch.setattr('atmem.memory._embedder_for_epoch', lambda epoch: embedder)
        result = memory.eligible_candidates(request(egress_class='remote', candidate_limit=1))
        assert len(result.candidates) == 2
        assert any(set(r.signals['fusion']['channel_ranks']) == {'semantic'} for r in result.candidates)
        assert any('lexical' in r.signals['fusion']['channel_ranks'] for r in result.candidates)
        assert all('always choose' not in r.content for r in result.candidates)
    finally:
        memory.close()


def test_corpus_overflow_explicit(tmp_path, monkeypatch):
    import atmem.retrieve.hybrid as hybrid
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        memory.remember('u', 'My booking reference is ZX93.')
        monkeypatch.setattr(hybrid, 'MAX_CORPUS_BYTES', 1)
        with pytest.raises(ValueError, match='corpus limit'):
            memory.eligible_candidates(request())
    finally:
        memory.close()


def test_fallback_and_diagnostic_status(tmp_path, monkeypatch):
    import atmem.retrieve.hybrid as hybrid
    memory = Memory(tmp_path / 'm.db')
    try:
        memory.remember('u', 'My booking reference is ZX93.')
        from atmem.semantic import SemanticIndex, HashingEmbedder
        index = SemanticIndex(f'{memory.store.path}.vectors.db', policy=memory.policy)
        index.build(memory, 'u', HashingEmbedder())
        index.close()
        original = hybrid.sqlite3.connect
        class NoFTS:
            def __init__(self):
                self.connection = original(':memory:')
            def execute(self, statement, *args):
                if statement.startswith('CREATE VIRTUAL'):
                    raise hybrid.sqlite3.OperationalError('no fts5')
                return self.connection.execute(statement, *args)
            def close(self):
                self.connection.close()
        monkeypatch.setattr(hybrid.sqlite3, 'connect', lambda *a, **k: NoFTS() if a[0] == ':memory:' else original(*a, **k))
        result = memory.eligible_candidates(request())
        assert result.candidates
        statuses = result.candidates[0].signals['fusion']['channel_status']
        assert statuses['lexical'] == 'overlap_fallback'
        assert statuses['semantic'] == 'diagnostic'
    finally:
        memory.close()


def test_empty_result_audits_regime(tmp_path):
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        result = memory.eligible_candidates(request())
        assert not result.candidates
        events = memory.store.list_audit_events('u')
        event = next(e for e in events if e['event_id'] == result.audit_event_id)
        assert event['payload']['retrieval_fusion']['version'] == 'core-rrf-v1'
    finally:
        memory.close()


def test_inactive_and_media_derived_text(tmp_path):
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        for status in ('quarantined', 'superseded', 'tombstoned'):
            seed(memory, f'booking ZX93 {status}', status=status)
        good = seed(memory, 'Image caption: booking ZX93 on receipt.', raw={'modality': 'image'})
        result = memory.eligible_candidates(request(signals=('lexical',)))
        assert [r.record_id for r in result.candidates] == [good]
    finally:
        memory.close()


def test_stale_mutation_fails_before_publication(tmp_path, monkeypatch):
    import atmem.retrieve.hybrid as hybrid
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        record_id = seed(memory, 'My booking reference is ZX93.')
        original = hybrid.lexical_scores
        def mutate(records, query):
            result = original(records, query)
            memory.forget_record('u', record_id)
            return result
        monkeypatch.setattr(hybrid, 'lexical_scores', mutate)
        with pytest.raises(ValueError, match='changed during core hybrid'):
            memory.eligible_candidates(request(signals=('lexical',)))
    finally:
        memory.close()


def test_fact_only_and_published_rrf_score(tmp_path):
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        fact = seed(memory, 'ZX93', fact_key='booking reference')
        req = replace(request(signals=('lexical',)), query='booking')
        result = memory.eligible_candidates(req)
        assert [r.record_id for r in result.candidates] == [fact]
        candidate = result.candidates[0]
        assert candidate.score == 1.0
        assert candidate.signals['fusion']['channel_ranks'] == {'fact': 1}
        event = next(e for e in memory.store.list_audit_events('u') if e['event_id'] == result.audit_event_id)
        assert event['payload']['support_aggregation_version'] is None
        assert event['payload']['retrieval_fusion']['candidate_ranks'] == {fact: {'fact': 1}}
        from atmem.contracts import ContextRequest
        context = memory.prepare_context_v1(ContextRequest(
            context_id='context', candidate_set_id=result.candidate_set_id,
            scope=req.scope, record_ids=(fact,),
        ))
        assert 'ZX93' in context.context
    finally:
        memory.close()


@pytest.mark.parametrize('mode,expected', [('corrupt', 'integrity_failure'), ('remote', 'egress_denied')])
def test_semantic_failure_disclosure(tmp_path, monkeypatch, mode, expected):
    from atmem.semantic import SemanticIndex
    from atmem.semantic.index import SemanticIndexIntegrityError
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        seed(memory, 'booking ZX93')
        identity = {'provider': 'test', 'endpoint': 'https://example.invalid' if mode == 'remote' else ''}
        monkeypatch.setattr(SemanticIndex, 'active_epoch', lambda *a: {'identity': identity})
        monkeypatch.setattr('atmem.memory._embedder_for_epoch', lambda epoch: object())
        def fail(*args, **kwargs):
            assert mode != 'remote', 'must not access a denied endpoint'
            raise SemanticIndexIntegrityError('synthetic invalid vector')
        monkeypatch.setattr(SemanticIndex, 'search', fail)
        result = memory.eligible_candidates(request())
        assert result.candidates[0].signals['fusion']['channel_status']['semantic'] == expected
    finally:
        memory.close()


def test_high_fusion_prior_does_not_authorize_wrong_relation(tmp_path):
    from atmem.retrieve import decide_retrieval, SupportClass
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        seed(memory, 'My daughter is 9 years old.', fact_key='daughter_age')
        req = replace(request(signals=('lexical',)), query='what is my age?')
        candidates = memory.eligible_candidates(req)
        decision = decide_retrieval(req.query, [r.to_dict() for r in candidates.candidates])
        assert decision.support_class is not SupportClass.DIRECT
        own = {'record_id': 'self', 'content': 'I am 42 and my daughter is 9.',
               'score': 1., 'signals': {'fact_key': 'user_age'}}
        assert decide_retrieval(req.query, [own]).support_class is SupportClass.DIRECT
    finally:
        memory.close()
