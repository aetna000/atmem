"""Matched confirmation accounting; no successful-case filtering or imputation."""
from collections import Counter
from hashlib import sha256
import base64
import json

from benchmarks.code_replay.windows_metrics import acceptance, quality, usage, trace_summary, recover_stream
from benchmarks.code_replay.windows_uncertainty import paired_uncertainty, percentile

RUN = 'external-windows-confirmation-v3-comparison-v1-20261018'
SEED = 'atmem-windows-confirmation-cluster-audit-20261018-v2'


def comparison(rows, blocks):
    expected = {(b['slot'], arm): (b['instance_id'], b['repeat'])
                for b in blocks for arm in b['order']}
    if (len(expected) != 76 or len(rows) != 76
            or len({(r['slot'], r['arm']) for r in rows}) != 76
            or any(expected.get((r['slot'], r['arm'])) != (r['instance_id'], r['repeat']) for r in rows)):
        raise ValueError('exact frozen seventy-six cells required; no subset comparison')
    result = {'rows': rows, 'acceptance': acceptance(rows, 'tools', required_pairs=38),
              'arms': {}, 'uncertainty': None, 'archive_verified': False,
              'goal_complete': False, 'scope': 'repository-disjoint qualification-informed confirmation'}
    for arm in ('native', 'tools'):
        group = [r for r in rows if r['arm'] == arm]
        complete = all(r['usage'] is not None for r in group)
        elapsed = [r['elapsed_ms'] for r in group]
        result['arms'][arm] = {
            'attempts': len(group), 'normal_usage_receipts': sum(r['usage'] is not None for r in group),
            'token_totals': {k: sum(r['usage'][k] for r in group) if complete else None
                             for k in ('input_tokens', 'cached_input_tokens', 'uncached_input_tokens', 'output_tokens')},
            'full_task_passes': sum(r['quality']['task_pass'] for r in group),
            'grades_available': sum(r['quality']['grade_available'] for r in group),
            'partial_checks': {k: sum(r['grading'].get(k, 0) for r in group)
                               for k in ('f2p_success', 'f2p_failure', 'p2p_success', 'p2p_failure', 'p2p_skipped')},
            'stop_reasons': dict(Counter(str(r['stop_reason']) for r in group)),
            'source_policy_violations': sum(not r['source_policy_compliant'] for r in group),
            'code_mcp_calls': sum(r['trace']['code_mcp_calls'] for r in group),
            'public_test_calls': sum(r['trace']['public_test_calls'] for r in group),
            'solver_elapsed_ms': {'p50': percentile(elapsed, .5), 'p95': percentile(elapsed, .95)},
            'latency_scope': 'solver only; preparation and supervisor are separate components',
        }
    if result['acceptance']['complete_paired_usage'] and result['acceptance']['complete_grading']:
        result['uncertainty'] = paired_uncertainty(rows, candidate_arm='tools', required_pairs=38,
                                                  resamples=10000, seed=SEED)
    return result


def private_controller(events, row):
    """Reconstruct the retained controller bytes rather than trusting its projection."""
    from atmem.core.canonical import canonical_json
    from benchmarks.code_replay.result_transport import decode_result
    by_id = {e['object_id']: e for e in events}
    streams = {}
    for name, expected in row['streams'].items():
        parts = []
        for receipt in expected['receipts']:
            event = by_id[receipt['object_id']]
            payload = event['envelope']['payload']
            if (event['envelope']['event_type'] != 'external.runtime_projection_chunk'
                    or sha256(canonical_json(payload).encode()).hexdigest() != receipt['payload_sha256']
                    or payload['offset'] != sum(map(len, parts))):
                raise ValueError('private transport receipt or ordering differs')
            parts.append(base64.b64decode(payload['bytes_base64'], validate=True))
        raw = b''.join(parts)
        if len(raw) != expected['bytes'] or sha256(raw).hexdigest() != expected['sha256']:
            raise ValueError('private transport bytes differ')
        streams[name] = raw
    if row['transport_exit'] != 0:
        return {}
    controller = json.loads(streams['stdout'])
    if controller.get('exit_code') == 0 and not controller.get('reason') and controller.get('raw_output_truncated') is False:
        raw = base64.b64decode(controller['raw_output_base64'], validate=True)
        if len(raw) != controller['output_bytes']:
            raise ValueError('private worker length differs')
        controller['worker'] = decode_result(raw)
    return controller


def main():
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.confirmation_v3_grade import LOCK, MODELS, RUN as GRADING, complete_cases
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=RUN)
    def events(run): return vault.inspect(principal, run)
    def of(es, kind): return [e['envelope']['payload'] for e in es if e['envelope']['event_type'] == kind]
    if events(RUN): raise ValueError('comparison already attempted; inspect retained result')
    lock, = of(events(LOCK), 'external.v3_execution_manifest_frozen')
    model_events = events(MODELS)
    cases = of(model_events, 'external.v3_case_completed')
    complete_cases(lock, cases, of(model_events, 'external.v3_models_completed'))
    grades = events(GRADING)
    terminal, = of(grades, 'external.v3_grading_completed')
    grade_rows = of(grades, 'external.v3_grade_summary')
    if terminal['cases'] != 76 or len(grade_rows) != 76:
        raise ValueError('all private grading attempts required')
    by_cell = {(r['slot'], r['arm']): r for r in grade_rows}
    if len(by_cell) != 76: raise ValueError('duplicate grade cell')
    vault.capture(run_id=RUN, kind='external.v3_comparison_planned', principal=principal,
                  payload={'driver_source': job['driver_source'], 'required_pairs': 38,
                           'uncertainty_seed': SEED, 'resamples': 10000, 'no_exclusions': True})
    rows = []
    stages = {r['block']['slot']: r for r in lock['staged_blocks']}
    for case in cases:
        es = events(case['task_run'])
        model, = of(es, 'external.v3_model_result')
        by_id = {e['object_id']: e for e in es}
        streams = {k: recover_stream(by_id, v) for k, v in model['raw_response_transport'].items()}
        original = json.loads(streams['stdout'])
        model_usage = [e for e in original['events'] if e.get('type') == 'turn.completed']
        if (model_usage != model['usage_receipts'] or model_usage != case['usage_receipts']
                or any(original[k] != model[k] for k in ('exit_code', 'stop_reason', 'elapsed_ms'))):
            raise ValueError('model metadata differs from complete original transport')
        grade = by_cell[(case['slot'], case['arm'])]
        if (grade['instance_id'], grade['repeat']) != (case['instance_id'], case['repeat']):
            raise ValueError('grade identity differs')
        controller = {}
        if 'failure' not in grade:
            ge = events(grade['task_run'])
            retained, = of(ge, 'external.v3_private_grade')
            controller = private_controller(ge, retained)
            if retained['transport_exit'] != grade['transport_exit_code']:
                raise ValueError('grade transport status differs')
        marks = controller.get('worker', {}).get('grading', {})
        frozen = lock['grade_plans'][case['instance_id']]
        rows.append({**{k: case[k] for k in ('slot', 'instance_id', 'repeat', 'arm', 'task_run')},
            'usage': usage(model), 'trace': trace_summary(original['events']), 'grading': marks,
            'quality': quality({'transport_exit_code': grade.get('transport_exit_code'), 'controller': controller},
                source_policy_compliant=case['source_policy_compliant'],
                expected_f2p=frozen['expected_f2p'], expected_p2p=frozen['expected_p2p']),
            'source_policy_compliant': case['source_policy_compliant'],
            'stop_reason': model['stop_reason'], 'elapsed_ms': model['elapsed_ms'],
            'supervisor_elapsed_ms': case['supervisor_elapsed_ms'],
            'preparation_elapsed_ms': stages[case['slot']]['cases'][case['arm']]['stage_elapsed_ms']})
    result = comparison(rows, lock['staging_manifest']['blocks'])
    vault.capture(run_id=RUN, kind='external.v3_comparison_completed', principal=principal, payload=result)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}), flush=True)


if __name__ == '__main__': main()
