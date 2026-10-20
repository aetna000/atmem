"""Explicit source navigation, not source injection or a native shell rewrite.

The operator binds authority using Curation. Preparation and actual stream
delivery are separate and share its existing encrypted exposure document.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass

from atmem.code.application import digest
from atmem.code.contracts import _closed, _id, _text
from atmem.code.curation import Curation, encoded, safe
from atmem.knowledge.contracts import SourceAnchor

REQUEST = 'atmem-repository-discovery-request-v1'
RESPONSE = 'atmem-repository-discovery-response-v1'
REQUEST_FIELDS = {'request_id', 'turn_id', 'query', 'limit', 'budget'}
ITEM_FIELDS = ('id', 'title', 'location', 'version', 'match')


@dataclass(frozen=True)
class DiscoveryRequest:
    request_id: str
    turn_id: str
    query: str
    limit: int
    budget: int

    @classmethod
    def from_dict(cls, value):
        value = _closed(value, REQUEST_FIELDS, REQUEST)
        _id('request_id', value['request_id'])
        _id('turn_id', value['turn_id'])
        _text('query', value['query'], 4000)
        for key, low, high in (('limit', 1, 8), ('budget', 512, 8192)):
            if type(value[key]) is not int or not low <= value[key] <= high:
                raise ValueError('invalid discovery ' + key)
        if not safe(value):
            raise PermissionError('discovery request failed secret screening')
        return cls(**{key: value[key] for key in REQUEST_FIELDS})

    def to_dict(self):
        return {'format': REQUEST, **self.__dict__}


class Discovery:
    """One operator-bound AtMem backend. Host routing is qualified separately."""

    def __init__(self, application, scope, root, *, native_fallback=False):
        if type(native_fallback) is not bool:
            raise ValueError('native fallback must be an operator-selected boolean')
        self.curation = Curation(application, scope, root, experience=False)
        self.native_fallback = native_fallback
        self.pending = OrderedDict()
        self.delivery_ready = {}

    def _withheld(self, request, reason):
        # This smaller envelope also fits the minimum budget with max-size IDs.
        return {'format': RESPONSE, 'request_id': request.request_id,
                'turn_id': request.turn_id, 'backend': 'atmem', 'status': 'withheld',
                'items': [], 'reason': reason}

    def _project(self, request, original):
        if original.get('status') != 'ready':
            return self._withheld(request, 'evidence_unavailable')
        answer = {'format': RESPONSE, 'request_id': request.request_id,
                  'turn_id': request.turn_id, 'backend': 'atmem', 'status': 'ready',
                  'items': [], 'non_exhaustive': True,
                  'truncated': original.get('truncated', False),
                  'freshness': 'not_established',
                  'native_fallback': 'available_to_host' if self.native_fallback else 'unknown',
                  'assurance': 'prepared_only'}
        for item in original.get('items', []):
            if item.get('kind') != 'code' or not str(item.get('id', '')).startswith('code:'):
                raise ValueError('non-code result at repository discovery boundary')
            projected = {key: deepcopy(item[key]) for key in ITEM_FIELDS}
            # Validate the nested location too; a top-level allowlist alone
            # cannot prevent an unexpected source-body field inside an anchor.
            projected['location'] = SourceAnchor.from_dict(projected['location']).to_dict()
            candidate = {**answer, 'items': [*answer['items'], projected],
                         'freshness': 'current_at_preparation'}
            if len(encoded(candidate)) <= request.budget:
                answer = candidate
            else:
                answer['truncated'] = True
        return answer if len(encoded(answer)) <= request.budget else self._withheld(request, 'response_budget')

    def _retain(self, original, **extra):
        service = self.curation
        service.app.authorize(service.scope.project_id)
        receipt = original['receipt_id']
        row = service.app.store.code_document(service.scope.subject_id,
            service.scope.project_id, 'curation-exposure', receipt)
        if row is None:
            raise PermissionError('discovery exposure no longer available')
        row.update(extra)
        service.app.store.put_code_document(service.scope.subject_id,
            service.scope.project_id, 'curation-exposure', receipt, row)

    def prepare(self, value):
        request = DiscoveryRequest.from_dict(value)
        if any((r.request_id, r.turn_id) == (request.request_id, request.turn_id)
               for r, _ in self.pending.values()):
            raise ValueError('discovery request already pending')
        # Exactly one selected backend entry, no competing/provider fallback call.
        original = self.curation.prepare('discover', {'query': request.query,
            # Candidate metadata is larger than the navigation projection. Do
            # not discard an authorized location before projecting it into the
            # caller's byte budget. Delivery still revalidates the same receipt.
            'kind': 'code', 'limit': request.limit, 'budget': 8192})
        try:
            response = self._project(request, original)
            self._retain(original, navigation_request=request.to_dict(), navigation_prepared=response)
        except Exception:
            self.curation.pending.pop(digest(original), None)
            raise
        key = digest(response)
        self.pending[key] = (request, original)
        while len(self.pending) > 32:
            expired_key, (_, expired) = self.pending.popitem(last=False)
            self.delivery_ready.pop(expired_key, None)
            self.curation.pending.pop(digest(expired), None)
        return response

    def for_delivery(self, prepared):
        binding = self.pending.get(digest(prepared))
        if binding is None:
            raise ValueError('unknown or expired discovery preparation')
        request, original = binding
        self.curation.app.authorize(self.curation.scope.project_id)
        try:
            current = self.curation.revalidate(original)
        except (OSError, ValueError, PermissionError):
            current = False
        response = self._project(request, original) if current else self._withheld(request, 'evidence_changed_before_delivery')
        self._retain(original, navigation_delivery_prepared=response)
        self.delivery_ready[digest(prepared)] = digest(response)
        return response

    def written(self, prepared, final, *, wire):
        key = digest(prepared)
        binding = self.pending.get(key)
        if binding is None:
            raise ValueError('unknown or expired discovery preparation')
        if self.delivery_ready.get(key) != digest(final) or not isinstance(wire, str):
            raise ValueError('discovery output was not revalidated for delivery')
        self.pending.pop(key)
        self.delivery_ready.pop(key)
        _, original = binding
        self._retain(original, navigation_delivered=deepcopy(final),
                     navigation_assurance='written_to_server_stream_not_model_acknowledged')
        self.curation.written(original, final, wire=wire)
