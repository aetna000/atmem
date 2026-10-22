"""Opt-in semantic supplements through the existing canonical V3 authority.

Prototype engine: not selected by any existing profile/default. Semantic scores
never satisfy missing obligations or override conflicts/denials. The caller's
query-vector provider must have been approved before this engine is invoked.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
from typing import Sequence

from .semantic import SemanticIndex
from .service import StoredContextEngine, load_stored_canonical


class HybridStoredContextEngine:
    def __init__(self, store, *, generation_id: str, semantic_index: SemanticIndex,
                 query: str, query_vector: Sequence[float], semantic_candidates: int = 32):
        if semantic_index.store is not store or semantic_index.generation_id != generation_id:
            raise ValueError('semantic index must share the canonical generation and store')
        if type(semantic_candidates) is not int or not 1 <= semantic_candidates <= 128:
            raise ValueError('semantic candidate allocation must be 1..128')
        self.store, self.generation_id, self.semantic_index = store, generation_id, semantic_index
        self.query_digest = hashlib.sha256(query.encode()).hexdigest()
        self.query_vector = tuple(query_vector)
        self.semantic_candidates = semantic_candidates

    @property
    def identity(self):
        return {'engine': 'context-semantic-supplement-v1',
                'semantic_index_id': self.semantic_index.index_id,
                'semantic_candidates': self.semantic_candidates,
                'semantic_backend': getattr(self.semantic_index, 'backend', 'lsh-v1'),
                'replacement_ranking_qualified': False}

    def select(self, request, manifest):
        if hashlib.sha256(request.query.encode()).hexdigest() != self.query_digest:
            raise ValueError('query vector is bound to a different request text')
        allocation = min(self.semantic_candidates, max(0, request.budget.total_candidates-1))
        lexical = StoredContextEngine(self.store, generation_id=self.generation_id,
                                      candidate_budget=max(1, request.budget.total_candidates-allocation))
        selection = lexical.select(request, manifest)
        if selection.status != 'sufficient' or allocation == 0:
            return selection
        hits = self.semantic_index.nominate(self.query_vector,
            allowed_unit_ids=frozenset(manifest.authorized_unit_ids),
            limit=allocation, candidate_limit=allocation)
        # Keep every evidence unit the deterministic gate actually relies on.
        # Additional nominations cannot authorize a previously insufficient case.
        # Preserve the original constraint-supporting context too. Replacement
        # ranking needs separately verified support accounting; this first
        # prototype only adds bounded semantic evidence to unused byte capacity.
        required = tuple(selection.selected_unit_ids)
        ranked = list(dict.fromkeys(required))
        scores = {}
        for sequence in (selection.selected_unit_ids, tuple(hit.unit_id for hit in hits)):
            for rank, identity in enumerate(sequence, 1):
                scores[identity] = scores.get(identity, 0.) + 1/(60+rank)
        ranked += [identity for identity in sorted(scores, key=lambda i: (-scores[i], i))
                   if identity not in set(required)]
        chosen, excluded, bytes_used = [], [], 0
        for identity in ranked[:request.budget.total_candidates]:
            evidence = load_stored_canonical(self.store, request.scope, self.generation_id,
                                             (identity,), request.generation)
            if not evidence:
                raise ValueError('semantic nomination cannot be loaded canonically')
            addition = sum(len(item.text.encode()) for item in evidence)
            addition += 2 * (len(evidence)-1 + bool(chosen))
            if bytes_used + addition > request.budget.context_bytes:
                if identity in required:
                    # Fail closed if the protected obligation evidence itself
                    # cannot fit; never silently drop it to make semantic room.
                    return replace(selection, reason_codes=(*selection.reason_codes, 'semantic_supplement_budget_refused'))
                excluded.append({'evidence_id': identity, 'reason': 'context_budget'})
                continue
            chosen.append(identity)
            bytes_used += addition
        return replace(selection, selected_unit_ids=tuple(chosen),
                       excluded_evidence=tuple(item for item in (*selection.excluded_evidence, *excluded)
                                               if item['evidence_id'] not in set(chosen)),
                       reason_codes=(*selection.reason_codes, 'semantic_supplement_v1'))
