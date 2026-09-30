from dataclasses import replace

import pytest

from atmem import Memory
from atmem.contracts import AuthorityScope, EpisodeIngestRequest, EpisodePart, RecallRequest
from atmem.core.canonical import sha256_hex
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
        assert any(
            any(channel.startswith('lexical') for channel in r.signals['fusion']['channel_ranks'])
            for r in result.candidates
        )
        assert all('always choose' not in r.content for r in result.candidates)
    finally:
        memory.close()


def test_persistent_fts_does_not_scan_the_active_corpus(tmp_path, monkeypatch):
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        memory.remember('u', 'My booking reference is ZX93.')
        for index in range(300):
            seed(memory, f'Unrelated retained note {index}.')
        monkeypatch.setattr(
            memory.store,
            'iter_records',
            lambda *_args, **_kwargs: pytest.fail('whole-corpus iterator used'),
        )
        result = memory.eligible_candidates(request(signals=('lexical',)))
        assert 'booking reference is ZX93' in result.candidates[0].content
    finally:
        memory.close()


def test_exact_anchor_ranking_requires_phrase_not_scattered_tokens(tmp_path):
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        scattered = seed(
            memory,
            'Customer profile. Delete this address. Return Back to the account.',
        )
        exact = seed(
            memory,
            'Back | Login as Customer | Delete Customer | Reset',
        )
        result = memory.eligible_candidates(replace(
            request(signals=('lexical',), limit=2, candidate_limit=20),
            query=(
                'On the admin customer page, what is between '
                '"Delete Customer" and "Back"?'
            ),
        ))
        assert [row.record_id for row in result.candidates][:2] == [exact, scattered]
    finally:
        memory.close()


def test_comparison_nomination_preserves_one_head_per_side(tmp_path):
    memory = Memory(tmp_path / 'comparison.db', auto_vectors=False)
    try:
        incident = seed(
            memory,
            'Incident new record form. Priority value is 5 Planning.',
        )
        problem = seed(
            memory,
            'Problem new record form. Priority value is 5 Planning.',
        )
        for index in range(20):
            seed(memory, f'Problem list mentions related incidents and priority {index}.')

        result = memory.eligible_candidates(replace(
            request(signals=('lexical',), limit=8, candidate_limit=40),
            query=(
                'Create Incident vs Problem. In both forms, is the default '
                'value for "Priority" 5?'
            ),
        ))

        assert {row.record_id for row in result.candidates[:2]} == {
            incident,
            problem,
        }
        assert result.candidates[0].signals['fusion']['comparison_head_count'] == 2
    finally:
        memory.close()


def test_persistent_posting_and_diagnostic_status(tmp_path, monkeypatch):
    memory = Memory(tmp_path / 'm.db')
    try:
        memory.remember('u', 'My booking reference is ZX93.')
        from atmem.semantic import SemanticIndex, HashingEmbedder
        index = SemanticIndex(f'{memory.store.path}.vectors.db', policy=memory.policy)
        index.build(memory, 'u', HashingEmbedder())
        index.close()
        result = memory.eligible_candidates(request())
        assert result.candidates
        statuses = result.candidates[0].signals['fusion']['channel_status']
        assert statuses['lexical'] == 'persistent_fts'
        assert statuses['fact'] == 'persistent_postings'
        assert statuses['semantic'] == 'diagnostic'
    finally:
        memory.close()


def test_typed_nomination_uses_information_need_profile(tmp_path):
    memory = Memory(
        tmp_path / 'm.db', auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        text = 'I am 45 years old.'
        memory.form_episode(EpisodeIngestRequest(
            episode_id='age-episode', idempotency_key='age-episode-key',
            scope=AuthorityScope('u', 'agent', 'workspace'),
            parts=(EpisodePart(
                part_id='age-part', ordinal=0, kind='text', source_type='user_message',
                content=text, content_sha256=f'sha256:{sha256_hex(text)}',
            ),),
        ))
        seed(memory, 'How old am I is a common example question.')
        result = memory.eligible_candidates(replace(
            request(signals=('lexical',)), query='How old am I?', limit=1
        ))
        fusion = result.candidates[0].signals['fusion']
        assert fusion['information_need'] == 'exact_fact'
        assert fusion['profile_id'] == 'fact-and-state-v1'
        assert 'typed' in fusion['channel_ranks']
        assert fusion['channel_status']['typed'] == 'canonical_typed_units'
        assert fusion['exact_preserved_record_id'] == result.candidates[0].record_id
        assert '45' in result.candidates[0].content
    finally:
        memory.close()


def test_unrelated_typed_fact_cannot_self_nominate_by_type_alone(tmp_path):
    memory = Memory(
        tmp_path / 'm.db', auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        text = 'My favorite color is blue.'
        memory.form_episode(EpisodeIngestRequest(
            episode_id='color-episode', idempotency_key='color-episode-key',
            scope=AuthorityScope('u', 'agent', 'workspace'),
            parts=(EpisodePart(
                part_id='color-part', ordinal=0, kind='text', source_type='user_message',
                content=text, content_sha256=f'sha256:{sha256_hex(text)}',
            ),),
        ))
        result = memory.eligible_candidates(replace(
            request(signals=('lexical',)), query='How old am I?', limit=1
        ))
        assert result.candidates == ()
    finally:
        memory.close()


def test_postings_backfill_marker_prevents_reopen_rebuild_for_symbol_only_record(tmp_path):
    path = tmp_path / 'm.db'
    memory = Memory(path, auto_vectors=False)
    try:
        seed(memory, '!!! 🧠 !!!')
        generation = memory.store.record_generation('u')
        state = memory.store._conn.execute(
            "SELECT value FROM retrieval_index_state WHERE key='postings_version'"
        ).fetchone()
        assert state['value'] == 'scoped-postings-v3-fact-only'
    finally:
        memory.close()
    reopened = Memory(path, auto_vectors=False)
    try:
        assert reopened.store.record_generation('u') == generation
    finally:
        reopened.close()


def test_semantic_only_can_nominate_a_meaning_match_older_than_graph_tail(tmp_path, monkeypatch):
    from atmem.semantic import SemanticIndex

    class Embedder:
        identity = {'provider': 'test', 'model': 'old-meaning', 'version': '1', 'normalization': 'l2'}

        def embed_documents(self, texts):
            return [[1., 0.] if 'aisle' in text else [0., 1.] for text in texts]

        def embed_query(self, query):
            return [1., 0.]

    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    embedder = Embedder()
    try:
        old = seed(memory, 'Ancient preference: always choose an aisle seat.')
        for index in range(300):
            seed(memory, f'Recent unrelated retained note {index}.')
        index = SemanticIndex(f'{memory.store.path}.vectors.db', policy=memory.policy)
        index.build(memory, 'u', embedder)
        index.close()
        monkeypatch.setattr('atmem.memory._embedder_for_epoch', lambda epoch: embedder)
        result = memory.eligible_candidates(request(signals=('semantic',), candidate_limit=1))
        assert [candidate.record_id for candidate in result.candidates] == [old]
    finally:
        memory.close()


def test_authorized_rare_term_beats_many_common_term_ties(tmp_path):
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        rare = seed(memory, 'Seattle weather details.')
        for index in range(300):
            seed(memory, f'Common note {index}.')
        req = replace(
            request(signals=('lexical',), candidate_limit=1),
            query='note seattle',
        )
        result = memory.eligible_candidates(req)
        assert [candidate.record_id for candidate in result.candidates] == [rare]
    finally:
        memory.close()


def test_raw_authority_divergence_is_withheld_without_retrieval_outage(tmp_path):
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        record_id = seed(memory, 'My booking reference is ZX93.')
        memory.store._conn.execute(
            "UPDATE records SET raw=? WHERE id=?",
            ('{"authority_scope":{"subject_id":"u","workspace_id":"hidden"}}', record_id),
        )
        result = memory.eligible_candidates(request(signals=('lexical',)))
        assert not result.candidates
        event = next(
            row for row in memory.store.list_audit_events('u')
            if row['event_id'] == result.audit_event_id
        )
        assert event['payload']['retrieval_fusion']['authorization_withheld_active_count'] >= 1
    finally:
        memory.close()


def test_unmaterialized_mixed_version_row_fails_closed_before_nomination(tmp_path):
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        record_id = seed(memory, 'My booking reference is ZX93.')
        memory.store._conn.execute(
            "UPDATE records SET authority_materialized=0 WHERE id=?", (record_id,)
        )
        result = memory.eligible_candidates(request(signals=('lexical',)))
        assert not result.candidates
        event = next(
            row for row in memory.store.list_audit_events('u')
            if row['event_id'] == result.audit_event_id
        )
        assert event['payload']['retrieval_fusion']['authorization_withheld_active_count'] == 1
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
    memory = Memory(tmp_path / 'm.db', auto_vectors=False)
    try:
        record_id = seed(memory, 'My booking reference is ZX93.')
        original = memory.store.scoped_search_candidates
        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            memory.forget_record('u', record_id)
            return result
        monkeypatch.setattr(memory.store, 'scoped_search_candidates', mutate)
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
