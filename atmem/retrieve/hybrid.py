"""Scoped core candidate generation. No agent/model owns authorization."""
from __future__ import annotations

import sqlite3
from urllib.parse import urlparse

from atmem.retrieve.fusion import FUSION_VERSION, fuse_rankings
from atmem.retrieve.rank import rank_records
from atmem.retrieve import query_tokens, token_overlap_components

MAX_CORPUS_RECORDS = 10_000
MAX_CORPUS_BYTES = 8 * 1024 * 1024
SEMANTIC_NOMINATION_FLOOR = 0.0


def authorized(record, request, excluded):
    scope = request.scope
    if record['subject_id'] != scope.subject_id or record['status'] != 'active' or record['id'] in excluded:
        return False
    raw = record.get('raw') or {}
    authority = raw.get('authority_scope') or {}
    if authority and (authority.get('subject_id') != scope.subject_id or authority.get('workspace_id') != scope.workspace_id):
        return False
    return not (request.egress_class == 'remote' and raw.get('sensitivity', 'personal') in {'sensitive', 'restricted'})


def lexical_scores(records, query):
    connection = sqlite3.connect(':memory:')
    try:
        connection.execute('PRAGMA temp_store=MEMORY')
        connection.execute("CREATE VIRTUAL TABLE corpus USING fts5(id UNINDEXED, content, tokenize='porter unicode61')")
        connection.executemany('INSERT INTO corpus VALUES (?, ?)', [(r['id'], r['content']) for r in records])
        terms = query_tokens(query)
        if not terms:
            return {}, 'active'
        expression = ' OR '.join('"' + t.replace('"', '') + '"' for t in terms)
        rows = connection.execute('SELECT id, -bm25(corpus) FROM corpus WHERE corpus MATCH ? ORDER BY rank, id', (expression,))
        return dict(rows), 'active'
    except sqlite3.OperationalError:
        scores = {}
        for record in records:
            matched, total = token_overlap_components(query, record['content'])
            if matched:
                scores[record['id']] = matched / max(total, 1)
        return scores, 'overlap_fallback'
    finally:
        connection.close()


def collect(memory, request):
    from atmem.memory import _embedder_for_epoch
    from atmem.semantic import SemanticIndex, default_index_path
    from atmem.semantic.index import SemanticIndexIntegrityError

    generation = memory.store.record_generation(request.scope.subject_id)
    excluded = memory.store.excluded_record_ids(request.scope.subject_id)
    records = []
    size = 0
    withheld_count = 0
    for record in memory.store.iter_records(request.scope.subject_id):
        if not authorized(record, request, excluded):
            withheld_count += 1
            continue
        size += len(str(record['content']).encode('utf-8')) + len(str(record.get('fact_key') or '').encode('utf-8'))
        if len(records) >= MAX_CORPUS_RECORDS or size > MAX_CORPUS_BYTES:
            raise ValueError('core hybrid corpus limit exceeded; narrow scope or use legacy retrieval')
        records.append(record)
    by_id = {r['id']: r for r in records}
    channels = {}
    raw_scores = {}
    statuses = {'lexical': 'disabled', 'fact': 'disabled', 'semantic': 'disabled',
                'graph': 'disabled'}
    if 'lexical' in request.signals:
        bm25, statuses['lexical'] = lexical_scores(records, request.query)
        priors = rank_records(request.query, records, fts_scores=bm25)
        eligible = {r.record['id'] for r in priors if r.score >= request.min_score}
        channels['lexical'] = sorted((i for i in bm25 if i in eligible), key=lambda i: (-bm25[i], i))[:request.candidate_limit]
        raw_scores['lexical'] = bm25
        fact_scores = {}
        for record in records:
            key = str(record.get('fact_key') or '').replace('_', ' ')
            matched, total = token_overlap_components(request.query, key)
            if matched:
                fact_scores[record['id']] = matched / max(total, 1)
        fact_priors = rank_records(request.query, records, fts_scores=fact_scores)
        eligible_fact = {r.record['id'] for r in fact_priors if r.score >= request.min_score}
        channels['fact'] = sorted((i for i in fact_scores if i in eligible_fact), key=lambda i: (-fact_scores[i], i))[:request.candidate_limit]
        raw_scores['fact'] = fact_scores
        statuses['fact'] = 'active'
    semantic = {}
    if 'semantic' in request.signals:
        statuses['semantic'] = 'unavailable'
        if memory.store.path != ':memory:' and records:
            index = SemanticIndex(default_index_path(memory.store.path), policy=memory.policy)
            try:
                epoch = index.active_epoch(request.scope.subject_id)
                statuses['semantic'] = 'no_epoch'
                if epoch:
                    provider = str(epoch['identity'].get('provider') or '')
                    endpoint = str(epoch['identity'].get('endpoint') or '')
                    remote = ((bool(endpoint) and urlparse(endpoint).hostname not in {'127.0.0.1', 'localhost', '::1'})
                              or (provider == 'openai-compatible' and not endpoint))
                    if provider in {'hashing', 'hashing-diagnostic', 'hash', 'deterministic-hashing'}:
                        statuses['semantic'] = 'diagnostic'
                    elif remote:
                        statuses['semantic'] = 'egress_denied'
                    else:
                        try:
                            embedder = _embedder_for_epoch(epoch)
                            matches = index.search(memory, request.scope.subject_id, request.query, embedder,
                                                   statuses=('active',), limit=request.candidate_limit,
                                                   min_similarity=SEMANTIC_NOMINATION_FLOOR, allowed_ids=set(by_id))
                            semantic = {r['record_id']: {**r, 'provider': provider} for r in matches}
                            statuses['semantic'] = 'active'
                        except SemanticIndexIntegrityError:
                            statuses['semantic'] = 'integrity_failure'
                        except ValueError:
                            statuses['semantic'] = 'incompatible'
                        except OSError:
                            statuses['semantic'] = 'unavailable'
            finally:
                index.close()
        channels['semantic'] = list(semantic)
        raw_scores['semantic'] = {i: r['similarity'] for i, r in semantic.items()}
    graph_paths, graph_metadata = {}, {}
    if 'graph' in request.signals:
        from atmem.retrieve.graph import nominate
        channels['graph'], raw_scores['graph'], graph_paths, graph_metadata = nominate(
            records, request.query, request.candidate_limit)
        statuses['graph'] = graph_metadata['graph_status']
    fused = fuse_rankings(channels)
    signal_metadata = {'version': FUSION_VERSION, 'channel_status': statuses,
                'lexical_fact_min_score': request.min_score, 'semantic_nomination_floor': SEMANTIC_NOMINATION_FLOOR,
                'candidate_limit_per_channel': request.candidate_limit, **graph_metadata}
    # Authorization counts belong to the audit, not candidate/reranker signals.
    metadata = {**signal_metadata, 'authorization_withheld_active_count': withheld_count}
    validation_ids = {r['record_id'] for r in fused}
    validation_ids.update(s['record_id'] for path in graph_paths.values() for s in path)
    current = memory.store.get_records(request.scope.subject_id, sorted(validation_ids))
    current_excluded = memory.store.excluded_record_ids(request.scope.subject_id)
    if generation != memory.store.record_generation(request.scope.subject_id):
        raise ValueError('memory changed during core hybrid retrieval; retry')
    for record_id in validation_ids:
        record = current.get(record_id)
        if (record_id not in by_id or record is None
                or not authorized(record, request, current_excluded)
                or record['content'] != by_id[record_id]['content']):
            raise ValueError('candidate changed during core hybrid retrieval; retry')
    result = []
    for item in fused:
        record_id = item['record_id']
        record = current[record_id]
        result.append({**record, 'record_id': record_id, 'score': item['score'],
                       'signals': {'fact_key': record.get('fact_key') or '',
                                   'semantic_evidence': semantic.get(record_id),
                                   'fusion': {**signal_metadata, 'channel_ranks': item['channel_ranks'],
                                              'raw_scores': {c: raw_scores[c][record_id] for c in item['channel_ranks']},
                                              **({'graph_path': graph_paths[record_id]} if record_id in graph_paths else {})}}})
    return result, metadata
