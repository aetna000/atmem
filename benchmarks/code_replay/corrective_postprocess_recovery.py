"""Recover an interrupted parent journal from already completed private grades.

This module has no model or private-grader dispatch path. Original phase programs
are loaded from the retained plan; only report and public-log inspection run.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import types

PREFIX = 'external-windows-corrective-development-'
RUN = PREFIX+'postprocessing-v1-20261018'
GRADING = PREFIX+'grading-v1-20261018'
MODELS = PREFIX+'models-v1-20261018'
LOCK = PREFIX+'execution-lock-v1-20261018'


def projected_controller(retained, original):
    """Reproduce retain_control's inline-only projection, without losing bytes."""
    if retained['transport_exit'] != 0:
        if 'controller' in retained:
            raise ValueError('unexpected controller on failed transport')
        return None
    projection = dict(original)
    if 'worker_fields_projection' in retained:
        worker = original['worker']
        heavy = {'original_files_base64', 'candidate_files_base64', 'assembled_files_base64',
                 'public_candidate_files_base64', 'original_files_sha256'} & set(worker)
        expected = {'omitted_from_inline_only': sorted(heavy), 'complete_result_retained': True}
        if retained['worker_fields_projection'] != expected or 'decoded_worker_stream' not in retained:
            raise ValueError('complete original worker projection framing required')
        projection['worker'] = {k: v for k, v in worker.items() if k not in heavy}
    if projection != retained.get('controller'):
        raise ValueError('inline controller differs from original retained transport')
    return projection


def summary(case, retained, original_controller, reference, target_run):
    if retained['instance_id'] != case['instance_id'] or retained['phase'] != 'solver_candidate':
        raise ValueError('private result role differs')
    return {**{k: case[k] for k in ('slot', 'instance_id', 'repeat', 'arm')},
        'task_run': target_run, 'transport_exit_code': retained['transport_exit'],
        'controller': projected_controller(retained, original_controller),
        'source_policy_compliant': case['source_policy_compliant'],
        'expected_f2p': reference['expected_f2p'], 'expected_p2p': reference['expected_p2p']}


def missing_summaries(derived, existing):
    def key(row): return row['slot'], row['arm']
    expected = {key(row): row for row in derived}
    observed = {key(row): row for row in existing}
    if len(derived) != 38 or len(expected) != 38 or len(observed) != len(existing):
        raise ValueError('complete unique recovered cells and unique existing summaries required')
    if any(expected.get(k) != row for k, row in observed.items()):
        raise ValueError('existing parent summary differs; never overwrite it')
    return [row for row in derived if key(row) not in observed]


def assert_no_grade_writers():
    for path in Path('/proc').iterdir():
        if not path.name.isdigit() or int(path.name) == os.getpid(): continue
        try: command = (path/'cmdline').read_bytes()
        except OSError: continue
        if b'<corrective-postprocessing>' in command:
            raise ValueError('original postprocessing writer remains live')
    result = subprocess.run(['docker', 'ps', '--filter', 'name=atmem-reference-control-',
                             '--format', '{{.Names}}'], capture_output=True, timeout=15)
    if result.returncode or result.stdout.strip():
        raise ValueError('private grading writers are active or unobservable')


def main():
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from atmem.core.canonical import canonical_json
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=RUN)
    def events(run): return vault.inspect(principal, run)
    def of(rows, kind): return [e['envelope']['payload'] for e in rows if e['envelope']['event_type'] == kind]
    def save(kind, payload): return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    previous = events(RUN)
    if [e['envelope']['event_type'] for e in previous] != [
            'external.v3_postprocessing_planned', 'external.v3_postprocessing_phase_started']:
        raise ValueError('exact interrupted grade-only parent journal required')
    plan, = of(previous, 'external.v3_postprocessing_planned')
    started, = of(previous, 'external.v3_postprocessing_phase_started')
    if started['phase'] != 'grade': raise ValueError('only grade-parent projection recovery allowed')
    assert_no_grade_writers()
    programs = plan['postprocess_programs']
    for name, source in programs.items():
        module = types.ModuleType(name); sys.modules[name] = module
        exec(compile(source, '<original-frozen-CD1-phase>', 'exec'), module.__dict__)
    private_controller = sys.modules['benchmarks.code_replay.confirmation_v3_report'].private_controller
    audit_namespace = {}
    exec(compile(job['request_audit_source'], '<original-frozen-request-verifier>', 'exec'), audit_namespace)
    recover_dispatch = audit_namespace['recover_dispatch']
    grade = sys.modules['benchmarks.code_replay.confirmation_v3_grade']
    lock, = of(events(LOCK), 'external.v3_execution_manifest_frozen')
    model_events = events(MODELS)
    cases = of(model_events, 'external.v3_case_completed')
    grade.complete_cases(lock, cases, of(model_events, 'external.v3_models_completed'))
    old_grades = events(GRADING)
    if of(old_grades, 'external.v3_grading_completed'):
        raise ValueError('grading already terminal; do not add another terminal')
    existing = of(old_grades, 'external.v3_grade_summary')
    if len(existing) != 24: raise ValueError('exact observed twenty-four-summary interruption required')
    derived = []; originals = []
    for case in cases:
        target_run = GRADING+'-block-'+str(case['slot'])+'-'+case['arm']
        records = events(target_run)
        actuals = [e for e in records if e['envelope']['event_type'] == 'external.v3_private_grade']
        if len(actuals) != 1: raise ValueError('exact one completed private result required; never rerun')
        retained = actuals[0]['envelope']['payload']
        dispatch, _ = recover_dispatch(records)
        reference = lock['grade_plans'][case['instance_id']]
        if (any(dispatch[k] != case[k] for k in ('slot', 'instance_id', 'repeat', 'arm'))
                or dispatch['candidate_case_run'] != case['task_run']
                or dispatch['frozen_grader_receipt'] != reference):
            raise ValueError('original dispatch role/reference differs')
        controller = private_controller(records, retained)
        derived.append(summary(case, retained, controller, reference, target_run))
        originals.append({'case_run': target_run, 'private_grade_object': actuals[0]['object_id'],
                          'private_grade_payload_sha256': __import__('hashlib').sha256(canonical_json(retained).encode()).hexdigest()})
    missing = missing_summaries(derived, existing)
    assert_no_grade_writers()
    save('external.v3_postprocessing_parent_recovery_planned', {'driver_source': job['driver_source'],
        'request_audit_source': job['request_audit_source'],
        'original_grade_objects': originals, 'existing_summaries': 24, 'missing_parent_summaries': len(missing),
        'models_repeated': 0, 'private_grades_repeated': 0, 'reason': 'SSH exit 255; all private results retained'})
    grade_vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=GRADING)
    for row in missing:
        grade_vault.capture(run_id=GRADING, kind='external.v3_grade_summary', principal=principal, payload=row)
    grade_vault.capture(run_id=GRADING, kind='external.v3_grading_completed', principal=principal,
        payload={'cases': 38, 'model_feedback': False, 'comparison_and_archive': 'pending', 'parent_projection_recovered': True})
    save('external.v3_postprocessing_phase_completed', {'phase': 'grade', 'model_retries': 0,
         'parent_projection_recovered': True, 'private_grades_repeated': 0})
    for short in ('report', 'retain'):
        name = 'benchmarks.code_replay.confirmation_v3_'+short
        module = sys.modules[name]
        module.job = {'driver_source': programs[name], 'bridge_source': plan['bridge_source']}
        save('external.v3_postprocessing_phase_started', {'phase': short, 'model_retries': 0})
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output): module.main()
        except Exception:
            save('external.v3_postprocessing_recovery_failure', {'phase': short, 'output': output.getvalue(),
                 'traceback': traceback.format_exc(), 'no_automatic_retry': True})
            raise
        save('external.v3_postprocessing_phase_completed', {'phase': short, 'model_retries': 0,
             'retained_phase_output': output.getvalue()})
    save('external.v3_postprocessing_completed', {'comparison_and_public_recovery': True,
         'archive_acceptance': 'pending', 'goal_complete': False, 'parent_projection_recovered': True})


if __name__ == '__main__': main()
