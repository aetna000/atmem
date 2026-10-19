"""Authorized historical experience with explicit, current applicability."""
from atmem.code.formation import memory_subject_id
from atmem.knowledge.contracts import ExperienceProposal, SourceSnapshot
from atmem.knowledge.code.applicability import assess
from atmem.knowledge.code.environment import environment_digest
from atmem.knowledge.projections import CodeKnowledge


def experiences(application, scope, root, *, query='', limit=20, offset=0):
    application.authorize(scope.project_id)
    if scope.subject_id != application.subject_id:
        raise PermissionError('experience subject mismatch')
    if not isinstance(query, str) or len(query.encode()) > 1000 or type(limit) is not int or not 1 <= limit <= 50 or type(offset) is not int or not 0 <= offset <= 950:
        raise ValueError('invalid experience query or page')
    records = application.records(scope.project_id, profile=scope.profile_id, query=query,
        agent=None if scope.profile_id == 'shared' else scope.agent_id,
        memory_class='coding_experience', limit=1000)
    items = []
    current = None
    unavailable = None
    # Check the owned root even if there are no matching records.
    knowledge = CodeKnowledge(application, scope)
    knowledge.graph._root(root)
    environment = application.store.code_document(scope.subject_id, scope.project_id, 'experience-environment', memory_subject_id(scope))
    identity = (environment['environment_sha256'] if environment and environment.get('assurance') == 'producer_declared_tool_environment'
                else environment_digest())
    try:
        current, _, _ = knowledge.capture(root, identity, max_file_bytes=2_000_000, max_source_bytes=64_000_000)
    except (OSError, ValueError):
        unavailable = 'CURRENT_SOURCE_UNAVAILABLE'
    for record in records:
        origin = record['code_source']
        value = application.store.code_document(scope.subject_id, scope.project_id, 'code-experience', origin.get('experience_proposal_id', ''))
        if not value or record['id'] not in value['formation']['record_ids']:
            continue
        proposal = ExperienceProposal.from_dict(value['proposal'])
        if memory_subject_id(proposal.scope) != memory_subject_id(scope):
            continue
        if query and query.casefold() not in (proposal.intent + ' ' + proposal.observation).casefold():
            continue
        applicability = (assess(proposal, SourceSnapshot.from_dict(value['snapshot']), current).to_dict()
            if current else {'status': 'withheld', 'reason_codes': [unavailable]})
        evidence = []
        for receipt_id in value['receipt_ids']:
            receipt = application.store.code_document(scope.subject_id, scope.project_id, 'execution-receipt', receipt_id)
            if receipt:
                evidence.append({'receipt_id': receipt_id, 'command': receipt['receipt']['command'],
                    'exit_code': receipt['receipt']['exit_code'], 'result_sha256': receipt['receipt']['result_sha256'],
                    'assurance': receipt['producer_assurance']})
        items.append({'record_id': record['id'], 'experience_id': proposal.proposal_id,
            'intent': proposal.intent, 'observation': proposal.observation, 'outcome': proposal.outcome,
            'anchors': [a.to_dict() for a in proposal.anchors], 'applicability': applicability,
            'execution_evidence': evidence, 'assurance': value['formation']['assurance'],
            'source_revision': value['snapshot']['revision'], 'agent': proposal.scope.agent_id})
    page = items[offset:offset + limit]
    application.store.append_audit_event(subject_id=scope.subject_id, actor='user', event_type='code.experiences_inspected',
        payload={'project_id': scope.project_id, 'profile_id': scope.profile_id, 'count': len(page)})
    result = {'format': 'atmem-code-experiences-v1', 'status': 'inspected', 'items': page,
        'offset': offset, 'limit': limit, 'has_more': offset + limit < len(items),
        'candidate_scan_limit': 1000, 'candidate_window_full': len(records) == 1000,
        'coverage': 'bounded active experiences; applicability is source evidence, not semantic proof'}
    from atmem.core.canonical import canonical_json
    if len(canonical_json(result).encode()) > 32768:
        return {'format': 'atmem-code-experiences-v1', 'status': 'withheld', 'items': [],
                'reason': 'response_budget', 'next_action': 'Use a narrower query or smaller limit'}
    return result


def execution_evidence(application, project, record_id, receipt_id):
    """Explicit, audited owner inspection, not automatically supplied context."""
    import base64
    import json
    from hashlib import sha256
    from atmem.extract.validation import screen_content
    from atmem.code.contracts import _id
    _id('receipt_id', receipt_id)
    _, record = application.exact(project, record_id)
    origin = application.store.code_document(application.subject_id, project, 'origin', record['id']) or {}
    experience = application.store.code_document(application.subject_id, project, 'code-experience', origin.get('experience_proposal_id', ''))
    if not experience or receipt_id not in experience['receipt_ids'] or record_id not in experience['formation']['record_ids']:
        raise PermissionError('receipt is not linked to the authorized record')
    value = application.store.code_document(application.subject_id, project, 'execution-receipt', receipt_id)
    if not value:
        raise ValueError('captured execution is unavailable')
    raw = base64.b64decode(value['result'], validate=True)
    if len(raw) > 2_000_000 or sha256(raw).hexdigest() != value['receipt']['result_sha256']:
        raise ValueError('execution result failed integrity validation')
    result = json.loads(raw)
    if result.get('format') != 'atmem-code-command-result-v1':
        raise ValueError('use the producer-specific inspector for this legacy receipt')
    output = {key: base64.b64decode(result[key + '_base64'], validate=True).decode('utf-8', errors='replace')
              for key in ('stdout', 'stderr')}
    if any(not screen_content(text, trusted=True).admissible for text in output.values() if text):
        raise PermissionError('execution output is withheld by secret screening')
    application.store.append_audit_event(subject_id=application.subject_id, actor='user', event_type='code.execution_inspected',
        payload={'project_id': project, 'record_id': record_id, 'receipt_id': receipt_id})
    return {'format': 'atmem-code-execution-inspection-v1', 'receipt': value['receipt'], 'result': result,
            **output, 'assurance': 'locally_observed_command_not_verified_fix'}
