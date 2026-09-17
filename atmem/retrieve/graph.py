"""Bounded associative nominations over an already-authorized canonical corpus.

No persisted graph statistics, aliases or identity mutations are consulted.
Paths explain nominations; they are not entailment or causal evidence.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from atmem.graph import GRAPH_EXTRACTOR_VERSION, _normalize, extract_graph_fact
from atmem.retrieve import query_tokens

GRAPH_VERSION = 'scoped-graph-v1'
MAX_SEEDS = 16
MAX_HOPS = 2
MAX_EDGE_VISITS = 256
MAX_CANDIDATES = 256
ROOT = 'you'


def nominate(records: list[dict[str, Any]], query: str, limit: int):
    """Return ranked IDs, raw activation scores, paths and content-free metadata."""
    edges = {}
    adjacency = defaultdict(list)
    for record in sorted(records, key=lambda r: r['id']):
        fact = extract_graph_fact(record)
        if fact is None:
            continue
        source, target = _normalize(fact.source), _normalize(fact.destination)
        # The extractor maps possessive "User's" to you, but named-relation
        # forms ("User likes ...") retain User. Both are the same supernode.
        source = ROOT if source == 'user' else source
        target = ROOT if target == 'user' else target
        edge = {'record_id': record['id'], 'source': source,
                'target': target, 'relation': fact.relation}
        edges[record['id']] = (edge, fact.relation_label)
        adjacency[source].append(record['id'])
        if target != source:
            adjacency[target].append(record['id'])

    terms = set(query_tokens(query))

    def match(surface):
        tokens = set(query_tokens(surface))
        return len(terms & tokens) / len(tokens) if tokens else 0.0

    def step(edge, origin, destination):
        return {**edge, 'traversal_from': origin, 'traversal_to': destination}

    # A named entity can seed independently of lexical/semantic candidate quotas.
    # Relation seeds include their evidence edge in the two-edge path budget.
    seeds = []
    for entity in sorted(adjacency):
        score = match(entity)
        if entity != ROOT and score:
            seeds.append((score, entity, (), (entity,)))
    for edge, label in edges.values():
        score = match(label)
        if not score or edge['source'] == edge['target']:
            continue
        for origin, destination in ((edge['source'], edge['target']),
                                    (edge['target'], edge['source'])):
            if destination != ROOT:
                seeds.append((score, destination, (step(edge, origin, destination),),
                              (origin, destination)))

    def seed_key(seed):
        score, node, path, _ = seed
        return (-score, len(path), node, tuple(s['record_id'] for s in path))

    seeds.sort(key=seed_key)
    truncated = len(seeds) > MAX_SEEDS
    seeds = seeds[:MAX_SEEDS]
    best = {}
    visited = set()
    examinations = 0

    def consider(path, score):
        record_id = path[-1]['record_id']
        activation = score * .75 ** (len(path) - 1)
        key = (-activation, len(path), tuple(s['record_id'] for s in path),
               tuple(s['traversal_from'] for s in path))
        if record_id not in best or key < best[record_id][0]:
            best[record_id] = (key, activation, path)
        visited.add(record_id)

    frontier = deque()
    for score, node, path, nodes in seeds:
        if path:
            examinations += 1
            consider(path, score)
        frontier.append((score, node, path, nodes))

    while frontier:
        score, node, path, nodes = frontier.popleft()
        if len(path) >= MAX_HOPS or node == ROOT:
            continue
        for record_id in adjacency[node]:
            if examinations >= MAX_EDGE_VISITS:
                truncated = True
                frontier.clear()
                break
            examinations += 1
            edge = edges[record_id][0]
            other = edge['target'] if edge['source'] == node else edge['source']
            if other in nodes or any(s['record_id'] == record_id for s in path):
                continue
            extended = (*path, step(edge, node, other))
            consider(extended, score)
            if other != ROOT and len(extended) < MAX_HOPS:
                frontier.append((score, other, extended, (*nodes, other)))

    ordered = sorted(best, key=lambda i: (-best[i][1], i))
    quota = min(limit, MAX_CANDIDATES)
    truncated |= len(ordered) > quota
    ordered = ordered[:quota]
    metadata = {
        'graph_version': GRAPH_VERSION,
        'graph_extractor_version': GRAPH_EXTRACTOR_VERSION,
        'graph_status': 'active' if ordered else 'empty',
        'graph_truncated': truncated,
        'graph_extracted_edges': len(edges),
        'graph_seeds_used': len(seeds),
        'graph_visited_edges': len(visited),
        'graph_edge_examinations': examinations,
        'graph_nominated_count': len(ordered),
        'graph_min_score_applied': False,
        'graph_max_hops': MAX_HOPS,
        'graph_seed_limit': MAX_SEEDS,
        'graph_work_limit': MAX_EDGE_VISITS,
        'graph_candidate_limit': quota,
    }
    return (ordered, {i: best[i][1] for i in ordered},
            {i: list(best[i][2]) for i in ordered}, metadata)
