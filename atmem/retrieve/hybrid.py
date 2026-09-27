"""Scoped core candidate generation. No agent/model owns authorization."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from atmem.core.canonical import canonical_json
from atmem.retrieve.fusion import FUSION_VERSION, fuse_rankings
from atmem.retrieve.rank import rank_records
from atmem.retrieve import query_tokens
from atmem.retrieve.intent import route_information_need
from atmem.retrieve.profiles import profile_for_need

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


def collect(memory, request):
    from atmem.memory import _embedder_for_epoch
    from atmem.semantic import SemanticIndex, default_index_path
    from atmem.semantic.index import SemanticIndexIntegrityError

    generation = memory.store.record_generation(request.scope.subject_id)
    need = route_information_need(request.query)
    profile = profile_for_need(need.type)
    records, indexed_lexical, indexed_fact, withheld_count, input_metadata = (
        memory.store.scoped_search_candidates(
            request.scope.subject_id,
            request.scope.workspace_id,
            query_tokens(request.query),
            limit=request.candidate_limit,
            remote=request.egress_class == 'remote',
        )
    )
    excluded = memory.store.excluded_record_ids(request.scope.subject_id)
    authorized_records = [
        record for record in records if authorized(record, request, excluded)
    ]
    withheld_count += len(records) - len(authorized_records)
    records = authorized_records
    by_id = {r['id']: r for r in records}
    typed_kinds = _TYPED_KINDS_BY_NEED[need.type]
    typed_records = memory.store.scoped_typed_candidates(
        request.scope.subject_id,
        request.scope.workspace_id,
        typed_kinds,
        limit=min(request.candidate_limit, profile.graph_quota),
        remote=request.egress_class == 'remote',
    )
    typed_records = [
        record for record in typed_records
        if _typed_relevant(record, request.query, need)
    ]
    for record in typed_records:
        if record['id'] not in by_id and authorized(record, request, excluded):
            records.append(record)
            by_id[record['id']] = record
    indexed_lexical = {
        record_id: score for record_id, score in indexed_lexical.items()
        if record_id in by_id
    }
    indexed_fact = {
        record_id: score for record_id, score in indexed_fact.items()
        if record_id in by_id
    }
    channels = {}
    raw_scores = {}
    statuses = {'lexical': 'disabled', 'fact': 'disabled', 'semantic': 'disabled',
                'graph': 'disabled', 'typed': 'disabled'}
    if 'lexical' in request.signals:
        statuses['lexical'] = 'persistent_postings'
        priors = rank_records(request.query, records, fts_scores=indexed_lexical)
        eligible = {r.record['id'] for r in priors if r.score >= request.min_score}
        channels['lexical'] = sorted((i for i in indexed_lexical if i in eligible), key=lambda i: (-indexed_lexical[i], i))[:min(request.candidate_limit, profile.lexical_quota)]
        raw_scores['lexical'] = indexed_lexical
        fact_priors = rank_records(request.query, records, fts_scores=indexed_fact)
        eligible_fact = {r.record['id'] for r in fact_priors if r.score >= request.min_score}
        channels['fact'] = sorted((i for i in indexed_fact if i in eligible_fact), key=lambda i: (-indexed_fact[i], i))[:min(request.candidate_limit, profile.exact_quota)]
        raw_scores['fact'] = indexed_fact
        statuses['fact'] = 'persistent_postings'
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
                                                   statuses=('active',), limit=min(request.candidate_limit, profile.semantic_quota),
                                                   min_similarity=SEMANTIC_NOMINATION_FLOOR,
                                                   authorize_ids=lambda ids: memory.store.authorized_record_ids(
                                                       request.scope.subject_id,
                                                       request.scope.workspace_id,
                                                       ids,
                                                       remote=request.egress_class == 'remote',
                                                   ))
                            semantic = {r['record_id']: {**r, 'provider': provider} for r in matches}
                            semantic_records = memory.store.get_records(
                                request.scope.subject_id, list(semantic)
                            )
                            for record_id in list(semantic):
                                record = semantic_records.get(record_id)
                                if record is None or not authorized(record, request, excluded):
                                    semantic.pop(record_id, None)
                                    continue
                                if record_id not in by_id:
                                    records.append(record)
                                    by_id[record_id] = record
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
            records, request.query, min(request.candidate_limit, profile.graph_quota))
        graph_metadata.update(input_metadata)
        statuses['graph'] = graph_metadata['graph_status']
    typed = {record['id']: 1.0 for record in typed_records}
    if typed:
        statuses['typed'] = 'canonical_typed_units'
        channels['typed'] = sorted(typed)[:min(request.candidate_limit, profile.graph_quota)]
        raw_scores['typed'] = typed
    fused = fuse_rankings(channels)
    preserved_record_id = None
    if need.type in {'exact_fact', 'current_state'} and len(channels.get('typed', ())) == 1:
        preserved_record_id = channels['typed'][0]
        fused.sort(key=lambda item: (item['record_id'] != preserved_record_id, -item['score'], item['record_id']))
    signal_metadata = {'version': FUSION_VERSION, 'channel_status': statuses,
                'lexical_fact_min_score': request.min_score, 'semantic_nomination_floor': SEMANTIC_NOMINATION_FLOOR,
                'candidate_limit_per_channel': request.candidate_limit,
                'information_need': need.type, 'profile_id': profile.profile_id,
                'channel_quotas': {
                    'fact': profile.exact_quota, 'lexical': profile.lexical_quota,
                    'semantic': profile.semantic_quota, 'graph': profile.graph_quota,
                    'typed': profile.graph_quota,
                }, **graph_metadata}
    if preserved_record_id is not None:
        signal_metadata['exact_preserved_record_id'] = preserved_record_id
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


_TYPED_KINDS_BY_NEED = {
    'exact_fact': {'atomic_fact'},
    'current_state': {'environment_state', 'atomic_fact'},
    'state_change': {'state_transition', 'environment_state'},
    'ordered_task': {'procedure'},
    'exception_risk': {'failure_gotcha', 'durable_rule'},
    'rule_application': {'durable_rule', 'failure_gotcha'},
    'assumption_check': {'premise_constraint', 'atomic_fact'},
    'relational_synthesis': {
        'atomic_fact', 'durable_rule', 'environment_state', 'state_transition',
        'procedure', 'failure_gotcha', 'premise_constraint',
    },
}


_RELATION_ALIASES = {
    'old': {'age'},
    'aged': {'age'},
    'where': {'location', 'channel', 'path'},
    'when': {'time', 'date', 'schedule'},
    'food': {'meal', 'dish', 'cuisine'},
    'car': {'vehicle'},
}


def _typed_relevant(record: dict, query: str, need) -> bool:
    """Require a topical bridge before a typed unit can nominate itself."""
    unit = ((record.get('raw') or {}).get('typed_unit') or {})
    payload = unit.get('payload') or {}
    query_terms = set(query_tokens(query))
    for term in tuple(query_terms):
        query_terms.update(_RELATION_ALIASES.get(term, ()))
    payload_terms = set(query_tokens(canonical_json(payload)))
    if re.search(r"\b(?:i|me|my|mine)\b", query, re.I):
        # An implicit user subject narrows authority, not topic. Counting it as
        # topical evidence would let every personal fact answer every question.
        payload_terms.discard('user')
    entity_terms = {str(value).casefold() for value in need.entities}
    return bool((query_terms | entity_terms) & payload_terms)
