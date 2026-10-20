"""Build the cohort comparison from retained source, usage and grade evidence."""
import base64
from collections import defaultdict
import json
from pathlib import Path
import statistics

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.source_policy import SourcePolicy, collect_source_patch
from benchmarks.code_replay.windows_execute import ROOT, RUN
from benchmarks.code_replay.windows_grade import cell_key, require_complete_cohort
from benchmarks.code_replay.windows_metrics import usage, quality, trace_summary, recover_stream, acceptance


def main():
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / 'vault', vault_id='click-20261017', scope=scope)
    events = vault.inspect(principal, RUN)
    def rows(kind):
        return [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == kind]
    if rows('external.cohort_comparison'):
        raise ValueError('comparison already retained; inspect it rather than overwrite')
    frozen = rows('external.cohort_manifest_frozen')[0]
    models, candidates, grades = rows('external.cohort_model_result'), rows('external.cohort_candidate_capture'), rows('external.cohort_private_grade')
    expected = require_complete_cohort(frozen, candidates, models, rows('external.cohort_models_completed'))
    if len(rows('external.cohort_grading_completed')) != 1 or len(grades) != 30 or {cell_key(g) for g in grades} != expected:
        raise ValueError('all actual grade records required before comparison')
    by_id = {e['object_id']: e for e in events}
    capture = {cell_key(c): c for c in candidates}; grade = {cell_key(g): g for g in grades}
    staged = {r['slot']: r for r in rows('external.cohort_staged')}
    sources = {r['instance_id']: r['job']['source'] for r in rows('external.cohort_stage_dispatch')}
    result = []
    for model in models:
        key = cell_key(model); task = model['instance_id']; final = capture[key]
        raw = recover_stream(by_id, model['raw_response_transport']['streams']['stdout'])
        original_result = json.loads(raw)
        if original_result['arm'] != model['arm'] or original_result['prompt_sha256'] != model['prompt_sha256']:
            raise ValueError('model response transport binding differs')
        receipts = [e for e in original_result['events'] if e.get('type') == 'turn.completed']
        if receipts != model['usage_receipts']:
            raise ValueError('reported usage differs from retained raw CLI events')
        source = sources[task]
        original = {name: base64.b64decode(encoded) for name, encoded in source['files_base64'].items()}
        candidate = {name: base64.b64decode(encoded) for name, encoded in final['files_base64'].items()}
        definition = frozen['task_plans'][task]['expectations']
        policy = SourcePolicy(tuple(definition['source_roots']), test_roots=tuple(definition['test_roots']))
        proposal = collect_source_patch(original, candidate, policy)
        # All arms were instructed to change implementation only. Report test
        # edits rather than silently crediting them after the grader restores tests.
        compliant = not proposal['out_of_scope_changes'] and not proposal['ignored_test_changes']
        verdict = quality(grade[key], source_policy_compliant=compliant,
            expected_f2p=definition['expected_f2p'], expected_p2p=definition['expected_p2p'])
        case = staged[model['slot']]['cases'][model['arm']]
        prepared = case['prepared']
        marks = grade[key].get('controller', {}).get('worker', {}).get('grading', {})
        result.append({**{k: model[k] for k in ('slot', 'repeat', 'arm', 'instance_id')},
            'usage': usage(model), 'quality': verdict, 'grading': marks,
            'solver_ms': model['elapsed_ms'], 'stop_reason': model['stop_reason'],
            'tool_calls': model['tool_calls'], 'trace': trace_summary(original_result['events']),
            'index_ms': prepared['index_ms'] if prepared else 0,
            'context_ms': prepared['context_ms'] if prepared else 0,
            'initial_context_bytes': len(prepared['package']['content'].encode()) if prepared else 0,
            'changed_paths': proposal['changed_paths'], 'ignored_test_changes': proposal['ignored_test_changes'],
            'out_of_scope_changes': proposal['out_of_scope_changes'],
            'raw_response_recovered_and_bound': True})
    groups = defaultdict(list)
    for row in result:
        groups[row['arm']].append(row)
    aggregate = []
    for arm, values in sorted(groups.items()):
        known = [r for r in values if r['usage'] is not None]
        aggregate.append({'arm': arm, 'attempts': len(values), 'known_usage': len(known),
            'task_passes': sum(r['quality']['task_pass'] for r in values),
            'tests_passes': sum(r['quality']['tests_pass'] for r in values),
            'grade_available': sum(r['quality']['grade_available'] for r in values),
            'input_tokens': sum(r['usage']['input_tokens'] for r in known) if len(known) == len(values) else None,
            'known_input_subtotal': sum(r['usage']['input_tokens'] for r in known),
            'cached_input_tokens': sum(r['usage']['cached_input_tokens'] for r in known),
            'median_solver_ms': statistics.median(r['solver_ms'] for r in values),
            'median_index_ms': statistics.median(r['index_ms'] for r in values),
            'median_context_ms': statistics.median(r['context_ms'] for r in values),
            'median_component_sum_ms': statistics.median(r['solver_ms'] + r['index_ms'] + r['context_ms'] for r in values),
            'code_mcp_calls': sum(r['trace']['code_mcp_calls'] for r in values),
            'public_test_calls': sum(r['trace']['public_test_calls'] for r in values)})
    summary = {'original_slots': 36, 'eligible_attempts': 30, 'unqualified_environment_slots': 6,
        'rows': sorted(result, key=lambda r: (r['slot'], r['arm'])), 'aggregate': aggregate,
        'acceptance': [acceptance(result, arm) for arm in ('pack', 'tools')],
        'first_triplet_supervisor_interruption_disclosed': True,
        'latency_assurance': 'solver and cold component sums, not instrumented full end-to-end latency',
        'independent_confirmation_completed': False, 'goal_complete': False}
    vault.capture(run_id=RUN, kind='external.cohort_comparison', payload=summary, principal=principal)
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
