"""Index-first authorized Code evidence. No model, side store or native-tool rewrite."""
import base64
from copy import deepcopy
import re
from collections import Counter, OrderedDict
from hashlib import sha256
from uuid import uuid4

from atmem.code.application import digest
from atmem.code.contracts import _id, CodeContextRequest
from atmem.code.context import source_current
from atmem.code.formation import memory_subject_id
from atmem.code.evidence_ledger import EvidenceLedger
from atmem.core.canonical import canonical_json
from atmem.extract.validation import screen_content
from atmem.knowledge.projections import CodeKnowledge
from atmem.knowledge.source_text import source_text
from atmem.memory import _screenable_metadata

FORMAT = 'atmem-code-curation-v1'
ESTIMATOR = 'utf8-byte-upper-bound-v1'
FIELDS = {
    'discover': {'query', 'kind', 'limit', 'budget'},
    'fetch': {'ids', 'goal', 'budget', 'session', 'epoch', 'known', 'references'},
    'changes': {'ids', 'goal', 'budget', 'session', 'epoch', 'known', 'references'},
    'capabilities': set(),
}


def encoded(value):
    return canonical_json(value).encode('utf-8')


def safe(value):
    return all(screen_content(text, trusted=True).admissible for text in _screenable_metadata(value))


def terms(text):
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    return set(re.findall(r'[^\W_]+', text.casefold(), re.UNICODE)) - {'the', 'a', 'an', 'is', 'of', 'to', 'and', 'in'}


def title(text, limit=96):
    # Exact bounded projection, not a generated factual summary.
    return ' '.join(text.split())[:limit]


def fit(items, budget, **metadata):
    answer = {'format': FORMAT, 'status': 'ready', 'items': [],
              'estimator': ESTIMATOR, 'truncated': False, **metadata}
    for item in items:
        candidate = {**answer, 'items': [*answer['items'], item]}
        if len(encoded(candidate)) > budget:
            answer['truncated'] = True
            continue
        answer = candidate
    if len(encoded(answer)) > budget:
        return {'format': FORMAT, 'status': 'withheld', 'items': [], 'reason': 'response_budget'}
    return answer


class Curation:
    def __init__(self, application, scope, root, *, experience=True):
        self.app, self.scope = application, scope
        self.knowledge = CodeKnowledge(application, scope)
        self.root = str(self.knowledge.graph._root(root))
        self.experience = experience
        self.ledger = EvidenceLedger()
        self.pending = OrderedDict()

    def validate_args(self, operation, args):
        if not isinstance(operation, str) or operation not in FIELDS or not isinstance(args, dict) or set(args) - FIELDS[operation]:
            raise ValueError('unknown curation operation or argument')
        for key, maximum in [('query', 4000), ('goal', 1000)]:
            value = args.get(key, '')
            if not isinstance(value, str) or len(value.encode()) > maximum:
                raise ValueError('invalid curation text')
        for key, default, minimum, maximum in [('budget', 4096, 256, 8192), ('limit', 5, 1, 8)]:
            value = args.get(key, default)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError('invalid curation budget or limit')
        if args.get('kind', 'both') not in {'code', 'experience', 'both'}:
            raise ValueError('invalid curation kind')
        if 'references' in args and type(args['references']) is not bool:
            raise ValueError('references must be boolean')
        for key in ('session', 'epoch'):
            if key in args:
                _id(key, args[key])
        if operation in {'fetch', 'changes'}:
            ids = args.get('ids')
            if not isinstance(ids, list) or not 1 <= len(ids) <= 8 or any(not isinstance(v, str) for v in ids) or len(set(ids)) != len(ids):
                raise ValueError('fetch requires 1 to 8 unique IDs')
            for identity in ids:
                _id('evidence ID', identity)
            known = args.get('known', [])
            if not isinstance(known, list) or len(known) > 64:
                raise ValueError('invalid known evidence')
            for row in known:
                if not isinstance(row, dict) or set(row) != {'id', 'version'} or not isinstance(row['version'], str) or not re.fullmatch('[0-9a-f]{64}', row['version']):
                    raise ValueError('invalid evidence reference')
                _id('evidence ID', row['id'])
            if args.get('references') and not {'session', 'epoch'} <= args.keys():
                raise ValueError('references require session and epoch')
        if not safe(args):
            raise PermissionError('curation request failed secret screening')

    def _experiences(self):
        if not self.experience:
            return []
        records = self.app.records(self.scope.project_id, profile=self.scope.profile_id,
            agent=None if self.scope.profile_id == 'shared' else self.scope.agent_id,
            memory_class='coding_experience', limit=1000)
        result, seen = [], set()
        for row in records:
            if row['id'] in seen:
                continue
            seen.add(row['id'])
            current = self.app.store.get_record(memory_subject_id(self.scope), row['id'])
            origin = row['code_source']
            proposal_id = origin.get('experience_proposal_id')
            value = self.app.store.code_document(self.scope.subject_id, self.scope.project_id, 'code-experience', proposal_id) if proposal_id else None
            if not current or current['status'] != 'active' or not value or row['id'] not in value['formation']['record_ids'] or not safe(value):
                continue
            from atmem.code.contracts import CodeScope
            if memory_subject_id(CodeScope.from_dict(value['proposal']['scope'])) != memory_subject_id(self.scope):
                continue
            result.append((current, value))
        return result

    def _experience_item(self, record, value, *, detail=False):
        proposal = value['proposal']
        item = {'id': 'exp:' + record['id'], 'kind': 'experience',
                'title': title(proposal['intent']), 'outcome': proposal['outcome'],
                'revision': value['snapshot']['revision'], 'applicability': 'unchecked',
                'version': digest([record, proposal, value['snapshot']]),
                'estimated_detail_tokens': len(encoded(proposal)) + 1024, 'fetch_ref': 'exp:' + record['id']}
        if detail:
            check = CodeContextRequest('curation', 'curation', 'fetch', 'Inspect experience', 8192, self.scope)
            if not source_current(self.app.store, check, record, self.root):
                return {'id': item['id'], 'status': 'withheld', 'reason': 'experience_not_applicable'}
            item.update(status='current', applicability='applicable', observation=proposal['observation'],
                        anchors=proposal['anchors'], assurance='observed_attempt_not_verified_fix')
        return item

    def _authorized_object(self, generation, obj):
        from atmem.knowledge.contracts import StructuralObject
        try:
            parsed = StructuralObject.from_dict(obj)
            files = dict(generation['snapshot']['files'])
            return (memory_subject_id(parsed.scope) == memory_subject_id(self.scope)
                    and parsed.snapshot_id == generation['snapshot_id'] and bool(parsed.anchors)
                    and all(files.get(anchor.path) == anchor.content_sha256
                            and anchor.path in generation['source_bytes'] for anchor in parsed.anchors))
        except (ValueError, KeyError, TypeError):
            return False

    def _code_items(self, generation, query):
        if not generation:
            return []
        words = terms(query)
        rows, scores = {}, {}
        for obj in generation['objects']:
            if not self._authorized_object(generation, obj) or not safe(obj):
                continue
            anchor = obj['anchors'][0]
            name_words = terms(obj['name'])
            path_words = terms(anchor['path'])
            score = 4 * len(words & name_words) + len(words & path_words)
            identity = obj['object_id']
            rows[identity] = obj
            scores[identity] = score
        # Bounded personalized propagation: relevant neighbors, not global hubs.
        influence = Counter()
        for edge in generation['relations']:
            source, target = edge['source_id'], edge['target_id']
            if source in rows and target in rows:
                influence[target] += min(scores[source], 4) * .15
                influence[source] += min(scores[target], 4) * .15
        ranked = sorted(rows, key=lambda key: (-(scores[key] + min(influence[key], 1)), rows[key]['name'], key))
        items = []
        per_file = Counter()
        for identity in ranked:
            obj = rows[identity]
            if words and scores[identity] + influence[identity] <= 0:
                continue
            anchor = obj['anchors'][0]
            if per_file[anchor['path']] >= 3:
                continue
            per_file[anchor['path']] += 1
            detail = self._code_fetch(generation, 'code:' + identity, '')
            if detail.get('status') != 'current':
                continue
            detail_size = len(encoded(detail)) + 384
            items.append({'id': 'code:' + identity, 'kind': 'code', 'title': title(obj['name']),
                'location': anchor, 'version': digest([generation['snapshot_id'], obj]),
                'estimated_detail_tokens': detail_size,
                'fetch_ref': 'code:' + identity,
                'match': 'identifier_or_path' if scores[identity] else 'structural_neighbor'})
            if len(items) >= 8:
                break
        return items

    def _code_fetch(self, generation, identity, goal):
        obj = next((row for row in generation['objects'] if 'code:' + row['object_id'] == identity), None) if generation else None
        if not obj or not self._authorized_object(generation, obj) or not safe(obj):
            return {'id': identity, 'status': 'withheld', 'reason': 'source_not_current_or_missing'}
        anchor = obj['anchors'][0]
        path = anchor['path']
        raw = base64.b64decode(generation['source_bytes'][path], validate=True)
        if sha256(raw).hexdigest() != anchor['content_sha256']:
            return {'id': identity, 'status': 'withheld', 'reason': 'source_integrity'}
        lines = source_text(path, raw).splitlines()
        start = anchor['start_line']
        # Some extractors give only the declaration line. Supply a bounded
        # neighboring source window, not a claim to know the whole symbol body.
        end = min(len(lines), anchor['end_line'] if anchor['end_line'] > start else start + 29)
        if path.endswith(('.py', '.pyi')) and anchor['end_line'] == start:
            from atmem.knowledge.code.packing import _definitions
            definition = _definitions('\n'.join(lines)).get(start)
            if definition is not None:
                end = min(len(lines), definition.end_lineno)
        if goal and end - start > 30:
            words = terms(goal)
            best = max(range(start - 1, end), key=lambda i: (len(words & terms(lines[i])), -i))
            low = max(start, best + 1 - 5)
        else:
            low = start
        high = min(end, low + 29)
        content = '\n'.join(lines[low - 1:high])
        result = {'id': identity, 'kind': 'code', 'status': 'current', 'path': path,
                  'start_line': low, 'end_line': high, 'content': content,
                  'snapshot_id': generation['snapshot_id'], 'source_sha256': anchor['content_sha256'],
                  'omitted': low > start or high < end,
                  'original_range': [start, end], 'assurance': 'exact_source_not_runtime_proof'}
        result['version'] = digest(result)
        return result if safe(result) else {'id': identity, 'status': 'withheld', 'reason': 'secret_screen'}

    def _build(self, operation, args):
        self.app.authorize(self.scope.project_id)
        self.knowledge.graph._root(self.root)
        if operation == 'capabilities':
            return {'format': FORMAT, 'status': 'ready', 'items': [], 'index_first': True,
                    'experience': self.experience, 'native_history_masking': False,
                    'prompt_owner_masking_helper': True, 'learned_pruning': False,
                    'ledger': 'process_local_stream_delivery_not_model_acknowledgement'}
        budget = args.get('budget', 4096)
        if operation == 'discover':
            kind, query = args.get('kind', 'both'), args.get('query', '')
            items = []
            if kind != 'code':
                words = terms(query)
                candidates = self._experiences()
                ranked = sorted(candidates, key=lambda pair: (-len(words & terms(pair[1]['proposal']['intent'] + ' ' + pair[1]['proposal']['observation'])), pair[0]['id']))
                for record, value in ranked:
                    if words and not words & terms(value['proposal']['intent'] + ' ' + value['proposal']['observation']):
                        continue
                    items.append(self._experience_item(record, value))
            generation = self.knowledge.current(self.root) if kind != 'experience' else None
            code = self._code_items(generation, query)
            # Interleave kinds so experience cannot crowd out source navigation.
            combined = []
            for index in range(max(len(items), len(code))):
                if index < len(code):
                    combined.append(code[index])
                if index < len(items):
                    combined.append(items[index])
            return fit(combined[:args.get('limit', 5)], budget,
                coverage='current code; at most 1000 active experience candidates; index applicability unchecked')
        generation = self.knowledge.current(self.root) if any(v.startswith('code:') for v in args['ids']) else None
        experiences = {('exp:' + record['id']): (record, value) for record, value in self._experiences()} if any(v.startswith('exp:') for v in args['ids']) else {}
        known = {row['id']: row['version'] for row in args.get('known', [])}
        items = []
        for identity in args['ids']:
            if identity.startswith('code:'):
                item = self._code_fetch(generation, identity, args.get('goal', ''))
            elif identity in experiences:
                item = self._experience_item(*experiences[identity], detail=True)
            else:
                item = {'id': identity, 'status': 'missing'}
            if (args.get('references') and item.get('version') == known.get(identity)
                    and self.ledger.has(args['session'], args['epoch'], identity, item['version'])):
                item = {'id': identity, 'version': item['version'], 'status': 'reference',
                        'reason': 'unchanged_previously_delivered_caller_opted_in'}
            items.append(item)
        return fit(items, budget, coverage='selected authorized evidence; omissions explicit')

    def prepare(self, operation, args):
        self.validate_args(operation, args)
        args = deepcopy(args)
        bounded = deepcopy(args)
        if operation != 'capabilities':
            bounded['budget'] = args.get('budget', 4096) - 64
        response = self._build(operation, bounded)
        if self._build(operation, bounded) != response:
            response = {'format': FORMAT, 'status': 'withheld', 'items': [], 'reason': 'evidence_changed_during_preparation'}
        receipt_id = uuid4().hex
        response['receipt_id'] = receipt_id
        key = digest(response)
        row = {'scope': self.scope.to_dict(), 'operation': operation, 'arguments': args,
               'response': response, 'assurance': 'prepared_only'}
        self.app.store.put_code_document(self.scope.subject_id, self.scope.project_id, 'curation-exposure', receipt_id, row)
        self.app.store.append_audit_event(subject_id=self.scope.subject_id, actor='code-curation',
            event_type='code.curation_prepared', payload={'project_id': self.scope.project_id, 'receipt_id': receipt_id})
        self.pending[key] = (operation, bounded, receipt_id)
        while len(self.pending) > 32:
            self.pending.popitem(last=False)
        return response

    def revalidate(self, response):
        pending = self.pending.get(digest(response))
        if pending is None:
            return False
        operation, args, _ = pending
        # Recompute before emitting: no cached authority or stale reference reuse.
        if response.get('reason') == 'evidence_changed_during_preparation':
            return True
        content = {key: value for key, value in response.items() if key != 'receipt_id'}
        return self._build(operation, args) == content

    def written(self, original, final, *, wire=None):
        pending = self.pending.pop(digest(original), None)
        if pending is None:
            return
        operation, args, receipt_id = pending
        row = self.app.store.code_document(self.scope.subject_id, self.scope.project_id, 'curation-exposure', receipt_id)
        if row is None:
            # A governed forget may have deleted this prepared projection.
            return
        row.update(delivered_response=final, assurance='written_to_server_stream_not_model_acknowledged')
        if wire is not None:
            row['delivered_wire'] = wire
        self.app.store.put_code_document(self.scope.subject_id, self.scope.project_id, 'curation-exposure', receipt_id, row)
        self.app.store.append_audit_event(subject_id=self.scope.subject_id, actor='code-curation',
            event_type='code.curation_written', payload={'project_id': self.scope.project_id, 'receipt_id': receipt_id})
        if operation in {'fetch', 'changes'} and 'session' in args and 'epoch' in args:
            self.ledger.delivered(args['session'], args['epoch'], final.get('items', []))
