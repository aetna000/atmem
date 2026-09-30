"""Scoped core candidate generation. No agent/model owns authorization."""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.retrieve.fusion import FUSION_VERSION, fuse_rankings
from atmem.retrieve.rank import rank_records
from atmem.retrieve import query_tokens
from atmem.retrieve.intent import (
    comparison_retrieval_queries,
    contextual_retrieval_query,
    evidence_anchor_queries,
    plan_retrieval_queries,
    route_information_need,
    salient_retrieval_query,
)
from atmem.retrieve.profiles import profile_for_need

SEMANTIC_NOMINATION_FLOOR = 0.0


def authorized(record, request, excluded, *, include_superseded=False):
    scope = request.scope
    allowed_statuses = {'active', 'superseded'} if include_superseded else {'active'}
    if record['subject_id'] != scope.subject_id or record['status'] not in allowed_statuses or record['id'] in excluded:
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
    include_superseded = bool(
        need.temporal_target and need.temporal_target != 'current'
    )
    profile = profile_for_need(need.type)
    query_plan = plan_retrieval_queries(request.query, need=need)
    salient_query = salient_retrieval_query(request.query)
    contextual_query = contextual_retrieval_query(
        request.query, excluding=salient_query
    )
    comparison_queries = comparison_retrieval_queries(request.query)
    salient_tokens = query_tokens(salient_query)
    anchor_phrases = evidence_anchor_queries(request.query)
    # Persistent FTS is the expensive operation on encrypted households.  The
    # full plan remains audit evidence, while nomination uses at most two
    # high-information probes: caller-stated exact anchors and the stripped
    # semantic intent.  Remaining channel variation is ranked in memory over
    # that bounded authorized union.
    anchor_query = " ".join(anchor_phrases)
    anchored_context_query = " ".join(
        value for value in (anchor_query, salient_query) if value
    )
    # A lone literal already present in the salient query is not a distinct
    # retrieval probe.  Running it separately adds a second recency/graph tail
    # when the premise is absent (for example, a requested state the UI does
    # not support), which can swamp the actual entity and workflow evidence.
    # Multiple UI anchors remain a useful phrase-specific probe.
    salient_token_set = frozenset(query_tokens(salient_query))
    anchor_token_set = frozenset(query_tokens(anchor_query))
    use_anchor_probe = bool(anchor_query) and (
        len(anchor_phrases) > 1
        or len(anchor_token_set) > 1
        or not anchor_token_set.issubset(salient_token_set)
    )
    supplemental_queries = tuple(
        value for value in query_plan[1:]
        if value not in {anchor_query, salient_query, contextual_query}
    )
    nomination_queries = tuple(dict.fromkeys(
        value for value in (
            *comparison_queries,
            anchored_context_query if use_anchor_probe else "",
            salient_query,
            contextual_query,
            *supplemental_queries,
        ) if value
    ))[:2] or (request.query,)
    search_results = []
    nomination_limit = min(
        request.candidate_limit,
        max(
            profile.lexical_quota,
            profile.exact_quota,
            profile.graph_quota,
            profile.semantic_quota,
        ) * 2,
    )
    for planned_query in nomination_queries:
        search_results.append(memory.store.scoped_search_candidates(
            request.scope.subject_id,
            request.scope.workspace_id,
            query_tokens(planned_query),
            limit=nomination_limit,
            remote=request.egress_class == 'remote',
            include_superseded=include_superseded,
            # Until the extracted entity graph is materialized separately,
            # graph traversal needs a small authorized tail to discover a
            # bridge whose wording differs from the question.  Keep it
            # profile-bounded rather than scanning the historical corpus.
            graph_floor=max(profile.graph_quota, request.limit),
            include_recency='graph' in request.signals,
            include_fact=need.type not in {
                'ordered_task', 'exception_risk', 'rule_application'
            },
        ))
        if memory.store.record_generation(request.scope.subject_id) != generation:
            raise ValueError('memory changed during core hybrid candidate nomination')
    records = []
    indexed_lexical_by_query: list[dict[str, float]] = []
    indexed_fact_by_query: list[dict[str, float]] = []
    withheld_count = 0
    input_metadata = {
        'graph_input_source': 'persistent_fts',
        'graph_input_records': 0,
        'graph_input_limit': 0,
        'graph_input_truncated': False,
        'query_plan_count': len(query_plan),
        'nomination_query_count': len(nomination_queries),
        'query_plan_digest': 'sha256:' + sha256_hex(canonical_json(query_plan)),
        'query_plan_version': 'deterministic-evidence-queries-v2',
    }
    seen_records: set[str] = set()
    for result_records, lexical, facts, withheld, metadata in search_results:
        input_metadata['graph_input_source'] = str(
            metadata.get('graph_input_source') or input_metadata['graph_input_source']
        )
        indexed_lexical_by_query.append(lexical)
        indexed_fact_by_query.append(facts)
        withheld_count = max(withheld_count, withheld)
        input_metadata['graph_input_records'] = max(
            int(input_metadata['graph_input_records']),
            int(metadata.get('graph_input_records') or 0),
        )
        input_metadata['graph_input_limit'] = max(
            int(input_metadata['graph_input_limit']),
            int(metadata.get('graph_input_limit') or 0),
        )
        input_metadata['graph_input_truncated'] = bool(
            input_metadata['graph_input_truncated']
            or metadata.get('graph_input_truncated')
        )
        for record in result_records:
            record_id = str(record['id'])
            if record_id not in seen_records:
                records.append(record)
                seen_records.add(record_id)
    excluded = memory.store.excluded_record_ids(request.scope.subject_id)
    authorized_records = [
        record for record in records
        if authorized(record, request, excluded, include_superseded=include_superseded)
    ]
    withheld_count += len(records) - len(authorized_records)
    records = authorized_records
    by_id = {r['id']: r for r in records}
    typed_kinds = _TYPED_KINDS_BY_NEED[need.type]
    # Typing refines candidates nominated by lexical/fact/semantic channels;
    # it must not introduce a blind "latest N of this kind" corpus scan.  The
    # latter was both expensive on encrypted stores and prone to unrelated
    # recent-state distraction.
    typed_records = [
        record for record in records
        if str(
            (((record.get('raw') or {}).get('typed_unit') or {}).get('kind') or '')
        ) in typed_kinds
    ]
    typed_records = [
        record for record in typed_records
        if _typed_relevant(record, request.query, need)
    ]
    for record in typed_records:
        if record['id'] not in by_id and authorized(
            record, request, excluded, include_superseded=include_superseded
        ):
            records.append(record)
            by_id[record['id']] = record
    historical_records = []
    if include_superseded:
        obligation = need.obligations[0] if need.obligations else {}
        historical_records = memory.store.scoped_historical_typed_candidates(
            request.scope.subject_id,
            request.scope.workspace_id,
            subject=str(obligation.get('entity') or '') or None,
            relation=str(obligation.get('relation') or need.relation_or_action or '') or None,
            temporal_target=str(need.temporal_target or '') or None,
            limit=max(request.candidate_limit, profile.graph_quota),
            remote=request.egress_class == 'remote',
        )
        temporal_target = str(need.temporal_target or '')
        historical_records.sort(key=lambda record: (
            not str(
                ((record.get('raw') or {}).get('typed_unit') or {}).get('event_at')
                or ((record.get('raw') or {}).get('typed_unit') or {}).get('observed_at')
                or ''
            ).startswith(temporal_target),
            str(record.get('id') or ''),
        ))
        for record in historical_records:
            if record['id'] not in by_id:
                records.append(record)
                by_id[record['id']] = record
    indexed_lexical_by_query = [
        {record_id: score for record_id, score in scores.items() if record_id in by_id}
        for scores in indexed_lexical_by_query
    ]
    indexed_fact_by_query = [
        {record_id: score for record_id, score in scores.items() if record_id in by_id}
        for scores in indexed_fact_by_query
    ]
    channels = {}
    raw_scores = {}
    statuses = {'lexical': 'disabled', 'fact': 'disabled', 'semantic': 'disabled',
                'graph': 'disabled', 'typed': 'disabled'}
    if 'lexical' in request.signals:
        statuses['lexical'] = 'persistent_fts'
        for index, planned_query in enumerate(nomination_queries):
            indexed_lexical = indexed_lexical_by_query[index]
            priors = rank_records(planned_query, records, fts_scores=indexed_lexical)
            eligible = {r.record['id'] for r in priors if r.score >= request.min_score}
            channel = (
                'lexical' if len(nomination_queries) == 1 else f'lexical:q{index}'
            )
            channels[channel] = sorted(
                (record_id for record_id in indexed_lexical if record_id in eligible),
                key=lambda record_id: (-indexed_lexical[record_id], record_id),
            )[:min(request.candidate_limit, profile.lexical_quota)]
            raw_scores[channel] = indexed_lexical

            indexed_fact = indexed_fact_by_query[index]
            fact_priors = rank_records(planned_query, records, fts_scores=indexed_fact)
            eligible_fact = {
                row.record['id'] for row in fact_priors if row.score >= request.min_score
            }
            fact_channel = (
                'fact' if len(nomination_queries) == 1 else f'fact:q{index}'
            )
            channels[fact_channel] = sorted(
                (record_id for record_id in indexed_fact if record_id in eligible_fact),
                key=lambda record_id: (-indexed_fact[record_id], record_id),
            )[:min(request.candidate_limit, profile.exact_quota)]
            raw_scores[fact_channel] = indexed_fact
        statuses['fact'] = 'persistent_postings'
        # Query rewrites are alternate probes within one retrieval channel,
        # not independent votes that may each consume the full channel quota.
        # Consolidate them before cross-channel fusion so ``candidate_limit``
        # remains a per-signal cap and a common-word rewrite cannot add filler.
        for family in ("lexical", "fact"):
            names = [name for name in channels if name.startswith(family + ":q")]
            if len(names) <= 1:
                continue
            consolidated = fuse_rankings({name: channels[name] for name in names})
            channels[family] = [
                item["record_id"] for item in consolidated[: request.candidate_limit]
            ]
            raw_scores[family] = {
                item["record_id"]: item["score"] for item in consolidated
            }
            for name in names:
                channels.pop(name, None)
                raw_scores.pop(name, None)
    semantic = {}
    if 'semantic' in request.signals:
        statuses['semantic'] = 'unavailable'
        if memory.store.path != ':memory:':
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
                                if record is None or not authorized(
                                    record, request, excluded,
                                    include_superseded=include_superseded,
                                ):
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
    temporal = {record['id']: 1.0 for record in historical_records}
    if temporal:
        channels['temporal'] = list(temporal)[:max(
            request.candidate_limit, profile.graph_quota
        )]
        raw_scores['temporal'] = temporal
    content_token_sequences = {
        str(record_id): tuple(query_tokens(str(record.get('content') or '')))
        for record_id, record in by_id.items()
    }
    candidate_tokens = {
        str(record_id): frozenset((
            *content_token_sequences[str(record_id)],
            *query_tokens(str(record.get('fact_key') or '')),
        ))
        for record_id, record in by_id.items()
    }
    # IDF is deliberately computed over the bounded, already-authorized
    # candidate union.  This avoids both cross-workspace corpus statistics and
    # one encrypted COUNT query per token on large households.
    ranking_tokens = tuple(dict.fromkeys(
        token
        for planned_query in nomination_queries
        for token in query_tokens(planned_query)
    ))
    term_frequencies = {
        term: sum(term in tokens for tokens in candidate_tokens.values())
        for term in ranking_tokens
    }
    token_order = {
        token: index for index, token in enumerate(ranking_tokens)
    }
    rare_terms = tuple(
        term for term, frequency in sorted(
            ((term, frequency) for term, frequency in term_frequencies.items()
             if frequency > 0),
            key=lambda item: (item[1], token_order.get(item[0], len(token_order))),
        )[:2]
    )
    fused = fuse_rankings(channels)
    anchor_token_sequences = tuple(
        tuple(query_tokens(value)) for value in anchor_phrases
        if query_tokens(value)
    )
    exact_anchor_coverage: dict[str, int] = {}
    if anchor_token_sequences:
        for record_id, record in by_id.items():
            content_tokens = content_token_sequences[record_id]
            covered = sum(
                _contains_token_phrase(content_tokens, phrase)
                for phrase in anchor_token_sequences
            )
            if covered == len(anchor_token_sequences):
                exact_anchor_coverage[record_id] = covered
        if exact_anchor_coverage:
            # Exact caller-stated anchors are evidence, not an answer guess.
            # Preserve them ahead of broad records that receive small RRF
            # contributions from several partial query rewrites.
            fused.sort(key=lambda item: (
                item['record_id'] not in exact_anchor_coverage,
                -item['score'], item['record_id'],
            ))
    salient_terms = frozenset(salient_tokens)
    salient_coverage: dict[str, int] = {}
    if len(salient_terms) >= 3:
        threshold = max(3, (len(salient_terms) * 2 + 2) // 3)
        for record_id, record in by_id.items():
            content_tokens = candidate_tokens[record_id]
            covered = len(salient_terms & content_tokens)
            if covered >= threshold:
                salient_coverage[record_id] = covered
        if salient_coverage:
            # A corpus-independent intent projection is stronger than several
            # weak RRF votes from generic framing/action-schema words.  Permit
            # one missing term so a caller typo cannot discard an otherwise
            # exact goal match.  A two-thirds floor also tolerates generic
            # actors ("user") that a source goal replaces with a proper name.
            fused.sort(key=lambda item: (
                item['record_id'] not in salient_coverage,
                -salient_coverage.get(item['record_id'], 0),
                -item['score'], item['record_id'],
            ))
    rare_term_set = frozenset(rare_terms)
    rare_term_matches: set[str] = set()
    if rare_term_set:
        rare_term_matches = {
            record_id for record_id in by_id
            if rare_term_set <= candidate_tokens[record_id]
        }
        if rare_term_matches:
            fused.sort(key=lambda item: (
                item['record_id'] not in rare_term_matches,
                -item['score'], item['record_id'],
            ))
    idf_salience_scores: dict[str, float] = {}
    for record_id in by_id:
        content_tokens = candidate_tokens[record_id]
        matched = [
            term for term, frequency in term_frequencies.items()
            if frequency > 0 and term in content_tokens
        ]
        if len(matched) >= 2:
            idf_salience_scores[record_id] = sum(
                1.0 / term_frequencies[term] for term in matched
            )
    structured_goal_coverage: dict[str, int] = {}
    if need.type in {
        'ordered_task', 'exception_risk', 'rule_application', 'assumption_check'
    }:
        for record_id, record in by_id.items():
            unit = ((record.get('raw') or {}).get('typed_unit') or {})
            payload = unit.get('payload') or {}
            value = payload.get('value')
            try:
                structured = json.loads(value) if isinstance(value, str) else value
            except json.JSONDecodeError:
                structured = None
            goal = structured.get('goal') if isinstance(structured, dict) else None
            if not isinstance(goal, str) or not goal.strip():
                continue
            covered = len(
                frozenset(salient_tokens)
                & frozenset(query_tokens(goal))
            )
            if covered >= 2:
                structured_goal_coverage[record_id] = covered
    if idf_salience_scores:
        # Score only inside the already authorized bounded candidate union.
        # This makes a source matching two rare intent terms beat records that
        # match many high-frequency framing words, without any global-tenant
        # document statistics or model call.
        fused.sort(key=lambda item: (
            item['record_id'] not in idf_salience_scores,
            -idf_salience_scores.get(item['record_id'], 0.0),
            -item['score'], item['record_id'],
        ))
    # Apply one final, explicit evidence hierarchy. Exact anchors and broad
    # salient coverage are strong query-conditioned evidence. A record that
    # merely contains two locally rare terms is not: on UI histories, phrases
    # such as "two items" can otherwise outrank the correct workflow despite
    # weak overall retrieval support. Keep IDF as a final tie-breaker behind
    # the multi-channel fusion score.
    fused.sort(key=lambda item: (
        item['record_id'] not in exact_anchor_coverage,
        -exact_anchor_coverage.get(item['record_id'], 0),
        item['record_id'] not in structured_goal_coverage,
        -structured_goal_coverage.get(item['record_id'], 0),
        item['record_id'] not in salient_coverage,
        -salient_coverage.get(item['record_id'], 0),
        item['record_id'] not in rare_term_matches,
        -item['score'],
        -idf_salience_scores.get(item['record_id'], 0.0),
        item['record_id'],
    ))
    comparison_head_ids: list[str] = []
    if comparison_queries:
        fused_ids = {item['record_id'] for item in fused}
        used: set[str] = set()
        for index in range(min(len(comparison_queries), len(indexed_lexical_by_query))):
            lexical_scores = indexed_lexical_by_query[index]
            fact_scores = indexed_fact_by_query[index]
            side_terms = frozenset(query_tokens(comparison_queries[index]))
            ranked_ids = sorted(
                fused_ids,
                key=lambda record_id: (
                    -len(side_terms & candidate_tokens.get(record_id, frozenset())),
                    -max(
                        lexical_scores.get(record_id, 0.0),
                        fact_scores.get(record_id, 0.0),
                    ),
                    record_id,
                ),
            )
            head = next(
                (
                    record_id for record_id in ranked_ids
                    if record_id not in used
                    and (
                        record_id in lexical_scores or record_id in fact_scores
                    )
                ),
                None,
            )
            if head is not None:
                comparison_head_ids.append(head)
                used.add(head)
        if comparison_head_ids:
            head_order = {
                record_id: index
                for index, record_id in enumerate(comparison_head_ids)
            }
            fused.sort(key=lambda item: (
                item['record_id'] not in head_order,
                head_order.get(item['record_id'], len(head_order)),
            ))
    if include_superseded:
        target = str(need.temporal_target or "")

        def temporal_match(record_id: str) -> bool:
            unit = ((by_id.get(record_id, {}).get('raw') or {}).get('typed_unit') or {})
            observed = str(unit.get('event_at') or unit.get('observed_at') or '')
            return bool(target and observed.startswith(target))

        if any(temporal_match(item['record_id']) for item in fused):
            fused.sort(key=lambda item: (
                not temporal_match(item['record_id']), -item['score'], item['record_id']
            ))
    preserved_record_id = None
    if (
        not include_superseded
        and need.type in {'exact_fact', 'current_state'}
        and len(channels.get('typed', ())) == 1
    ):
        preserved_record_id = channels['typed'][0]
        fused.sort(key=lambda item: (item['record_id'] != preserved_record_id, -item['score'], item['record_id']))
    signal_metadata = {'version': FUSION_VERSION, 'channel_status': statuses,
                'lexical_fact_min_score': request.min_score, 'semantic_nomination_floor': SEMANTIC_NOMINATION_FLOOR,
                'candidate_limit_per_channel': request.candidate_limit,
                'information_need': need.type, 'profile_id': profile.profile_id,
                'query_plan_count': len(query_plan),
                'nomination_query_count': len(nomination_queries),
                'query_plan_digest': 'sha256:' + sha256_hex(canonical_json(query_plan)),
                'query_plan_version': 'deterministic-evidence-queries-v2',
                'exact_anchor_count': len(anchor_phrases),
                'exact_anchor_match_count': len(exact_anchor_coverage),
                'salient_match_count': len(salient_coverage),
                'rare_term_count': len(rare_terms),
                'rare_term_match_count': len(rare_term_matches),
                'idf_salience_match_count': len(idf_salience_scores),
                'structured_goal_match_count': len(structured_goal_coverage),
                'comparison_head_count': len(comparison_head_ids),
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
                or not authorized(
                    record, request, current_excluded,
                    include_superseded=include_superseded,
                )
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
    metadata['include_superseded'] = include_superseded
    return result, metadata


_TYPED_KINDS_BY_NEED = {
    'exact_fact': {'atomic_fact'},
    'current_state': {'environment_state', 'atomic_fact'},
    'state_change': {'state_transition', 'environment_state'},
    # Exact structured observations may contain explicit goal/actions/outcome
    # fields without being promoted into executable procedure/rule memory.
    'ordered_task': {'procedure', 'environment_state'},
    'exception_risk': {'failure_gotcha', 'durable_rule', 'environment_state'},
    'rule_application': {'durable_rule', 'failure_gotcha', 'environment_state'},
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


def _contains_token_phrase(
    content: tuple[str, ...], phrase: tuple[str, ...]
) -> bool:
    """Match a caller-stated literal as a phrase, not scattered bag-of-words."""
    if not phrase or len(phrase) > len(content):
        return False
    width = len(phrase)
    return any(content[index:index + width] == phrase for index in range(len(content) - width + 1))
