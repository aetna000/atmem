"""Read-only, host-bound investigative evidence discovery.

Unlike context injection, this API makes no sufficiency/truth claim. Lexical
and semantic nominations run independently, before canonical authorization and
reload. Hosts own authenticated session construction and durable audit storage.
This primitive does not enable itself in any existing adapter or profile.
"""
from __future__ import annotations

from dataclasses import replace
import json
from threading import Lock
import time

from .navigator import NavigationBudget
from .pools import PoolBudget
from .retrieval import DeterministicRetriever
from .planner import DeterministicPlanner
from .service import GovernanceViolation, load_stored_canonical


class EvidenceDiscoverySession:
    def __init__(self, store, *, generation_id, request, authorize, audit,
                 budget: NavigationBudget, semantic_nominate=None, lexical=True,
                 clock=time.monotonic, source_bundles=False):
        if not callable(authorize) or not callable(audit):
            raise ValueError('discovery requires live authorization and durable audit')
        if semantic_nominate is not None and not callable(semantic_nominate):
            raise ValueError('semantic nomination must be a trusted callable')
        if type(lexical) is not bool or (not lexical and semantic_nominate is None):
            raise ValueError('at least one discovery channel is required')
        self.store, self.generation_id, self.request = store, generation_id, request
        self.authorize, self.audit = authorize, audit
        self.budget, self.semantic_nominate, self.lexical = budget, semantic_nominate, lexical
        if type(source_bundles) is not bool:
            raise TypeError('explicit source bundle selection required')
        self.source_bundles = source_bundles
        self.clock, self.started = clock, clock()
        self.operations = self.bytes_used = 0
        self._lock = Lock()

    def _manifest(self, request):
        manifest = self.authorize(request)
        if (manifest.request_id != request.request_id or manifest.scope != self.request.scope
                or manifest.generation != self.request.generation):
            raise GovernanceViolation('discovery authorization is stale or mismatched')
        row = self.store._conn.execute(
            'SELECT * FROM context_view_generations WHERE generation_id=?',
            (self.generation_id,)).fetchone()
        if (row is None or row['state'] not in {'verified','active'}
                or int(row['canonical_generation']) != request.generation
                or (row['subject_id'],row['agent_id'],row['workspace_id']) != (
                    request.scope.subject_id,request.scope.agent_id,request.scope.workspace_id)):
            raise GovernanceViolation('discovery source generation is stale or unavailable')
        return manifest

    def _begin(self, query):
        if self.clock()-self.started >= self.budget.max_elapsed_ms/1000:
            raise RuntimeError('discovery elapsed-time budget exhausted')
        if self.operations >= self.budget.max_operations:
            raise RuntimeError('discovery operation budget exhausted')
        if self.bytes_used >= self.budget.max_bytes:
            raise RuntimeError('discovery byte budget exhausted')
        self.operations += 1
        request = replace(self.request, query=query,
                          request_id=f'{self.request.request_id}:discovery:{self.operations}')
        return request, self._manifest(request)

    def _publish(self, request, manifest, identities, *, channels):
        allowed = set(manifest.authorized_unit_ids)
        if set(identities)-allowed:
            raise GovernanceViolation('discovery nomination is outside authorized scope')
        omitted_groups = 0
        if self.source_bundles:
            from .source_bundles import expand_source_bundles
            identities, omitted_groups = expand_source_bundles(self.store,
                generation_id=self.generation_id, request=request,
                manifest=manifest, nominated=identities)
        canonical = load_stored_canonical(self.store, request.scope, self.generation_id,
                                          tuple(identities), request.generation)
        if tuple(e.unit_id for e in canonical) != tuple(identities):
            raise GovernanceViolation('discovery evidence is unavailable')
        if any(e.scope != request.scope or e.generation != request.generation
               or e.lifecycle != 'active' for e in canonical):
            raise GovernanceViolation('discovery evidence changed scope or lifecycle')
        response = {'format':'atmem-evidence-discovery-v1', 'request_id':request.request_id,
                    'generation':request.generation, 'status':'investigative_evidence',
                    'sufficiency':'not_assessed', 'channels':list(channels),
                    'evidence':[], 'omitted_count':0, 'operations_used':self.operations}
        if self.source_bundles:
            response.update(presentation='atomic-source-bundles-v1', source_groups=[],
                            omitted_groups=omitted_groups, whole_source_claim=False)
        def size():
            return len(json.dumps(response,ensure_ascii=False,separators=(',',':')).encode())
        remaining = self.budget.max_bytes-self.bytes_used
        groups = []
        for item in canonical:
            key = (item.source_range.source_id, item.source_range.part_id)
            if not self.source_bundles or not groups or groups[-1][0] != key:
                groups.append((key, []))
            groups[-1][1].append(item)
        for key, items in groups:
            values = [{'unit_id':item.unit_id, 'text':item.text,
                       'source_range':item.source_range.to_dict()} for item in items]
            response['evidence'].extend(values)
            if self.source_bundles:
                response['source_groups'].append({'source_id':key[0], 'part_id':key[1],
                    'unit_ids':[item.unit_id for item in items],
                    'coverage':'authorized_active_ranges_only'})
            # Reserve the maximum omission-count digit width before packing.
            response['omitted_count'] = len(canonical)
            if size() > remaining:
                del response['evidence'][-len(values):]
                if self.source_bundles:
                    response['source_groups'].pop()
                    response['omitted_groups'] += 1
        response['omitted_count'] = len(canonical)-len(response['evidence'])
        encoded_size = size()
        if encoded_size > remaining:
            raise RuntimeError('discovery byte budget exhausted')
        fresh = self._manifest(request)
        if set(identities)-set(fresh.authorized_unit_ids):
            raise GovernanceViolation('discovery authorization changed before delivery')
        if self.clock()-self.started >= self.budget.max_elapsed_ms/1000:
            raise RuntimeError('discovery elapsed-time budget exhausted')
        # An application must persist this receipt before returning evidence.
        if not self.audit(response):
            raise GovernanceViolation('discovery audit was not persisted')
        self.bytes_used += encoded_size
        return response

    def search(self, query, *, limit=12):
        if not isinstance(query,str) or not query.strip() or len(query.encode())>8192:
            raise ValueError('discovery query requires 1..8192 UTF-8 bytes')
        if type(limit) is not int or not 1<=limit<=32:
            raise ValueError('discovery limit must be 1..32')
        with self._lock:
            request,manifest = self._begin(query)
            limit = min(limit,request.budget.total_candidates)
            if limit < 1:
                raise RuntimeError('discovery candidate budget exhausted')
            channels = []
            lists = []
            # Semantic discovery MUST NOT depend on lexical sufficiency.
            if self.semantic_nominate is not None:
                ids = tuple(self.semantic_nominate(query,manifest,limit))
                if len(ids)>limit or len(set(ids))!=len(ids):
                    raise GovernanceViolation('semantic nomination violated its bound')
                lists.append(ids)
                channels.append('semantic')
            if self.lexical:
                plan = DeterministicPlanner().plan(query)
                result = DeterministicRetriever(self.store,
                    budget=PoolBudget(total_units=min(200,request.budget.total_candidates)),
                    balanced_pools=True).retrieve(generation_id=self.generation_id,
                        query=query,plan=plan,max_sources=limit,
                        allowed_unit_ids=(None if manifest.all_generation_units_authorized
                                          else frozenset(manifest.authorized_unit_ids)))
                # Internal lexical neighbourhood expansion can include a
                # same-source sibling outside a restricted read manifest.
                # Never pass that sibling to intelligence or delivery.
                authorized=frozenset(manifest.authorized_unit_ids)
                lists.append(tuple(c.unit_id for c in result.candidates if c.unit_id in authorized))
                channels.append('lexical')
            scores = {}
            for sequence in lists:
                for rank,identity in enumerate(sequence,1):
                    scores[identity] = scores.get(identity,0.)+1/(60+rank)
            # Reject invalid nominations even if they would fall below top-k.
            if set(scores)-set(manifest.authorized_unit_ids):
                raise GovernanceViolation('discovery nomination is outside authorized scope')
            identities = sorted(scores,key=lambda i:(-scores[i],i))[:limit]
            return self._publish(request,manifest,identities,channels=channels)

    def inspect(self, unit_id):
        if not isinstance(unit_id,str) or not unit_id or len(unit_id)>512:
            raise ValueError('discovery requires one bounded evidence identifier')
        with self._lock:
            request,manifest = self._begin(self.request.query)
            return self._publish(request,manifest,(unit_id,),channels=('inspect',))
