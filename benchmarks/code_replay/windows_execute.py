"""Execute the frozen staged cohort serially, retaining every attempt.

No private grades are inspected or sent to solvers here. Full transport bytes
are chunked; parsed metadata never substitutes for those retained bytes.
"""
import ast
import argparse
import base64
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.windows_cohort import policy
from benchmarks.code_replay.windows_transport import command


ROOT = Path(os.environ.get('ATMEM_BENCHMARK_ROOT',
    '/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/click-20261017'))
RUN = 'external-windows-selected-validation-v2-20261018'


def runner_helpers():
    source = Path('benchmarks/code_replay/runner.py').read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'run_cli')
    runner = ast.get_source_segment(source, node).replace('    from benchmarks.code_replay.progressive import arguments as mcp_arguments\n', '')
    runner = runner.replace('str(session.workspace / ".solver-tmp")', 'str(session.tool_temporary)')
    runner = runner.replace('*permission_arguments((session.executable.parent, *runtime_roots)),',
        "'-c', 'shell_environment_policy.set.PYTHONPYCACHEPREFIX=' + json.dumps(str(session.tool_temporary / 'pycache')), *permission_arguments((session.executable.parent, *runtime_roots)),")
    source = Path('benchmarks/code_replay/progressive.py').read_text()
    helpers = '\n\n'.join(ast.get_source_segment(source, n) for n in ast.parse(source).body
        if isinstance(n, ast.FunctionDef) and n.name in {'configuration', 'arguments'})
    return runner, helpers


def model_metadata(result):
    meta = {key: value for key, value in result.items() if key not in {'events', 'stdout_base64', 'stderr_base64'}}
    meta['event_count'] = len(result['events'])
    meta['usage_receipts'] = [e for e in result['events'] if e.get('type') == 'turn.completed']
    return meta


def descriptor_resume_guard(rows, frozen_program):
    """Only the proved os.environ failure before CLI launch may be resumed."""
    results = rows('external.cohort_model_result')
    finished = rows('external.cohort_case_completed')
    dispatches = rows('external.cohort_model_dispatch')
    stops = rows('external.cohort_execution_stopped')
    if (len(results) != 1 or len(finished) != 1 or len(dispatches) != 2 or len(stops) != 1
        or results[0]['slot'] != 0 or results[0]['arm'] != 'native'
        or finished[0]['slot'] != 0 or finished[0]['arm'] != 'native'
        or dispatches[-1]['slot'] != 0 or dispatches[-1]['arm'] != 'pack'
        or stops[0]['reason'] != 'supervisor_failure'
        or rows('external.cohort_descriptor_resume_planned')):
        raise ValueError('descriptor resume requires the exact single pre-inference failure')
    transports = [r for r in rows('external.cohort_model_transport') if r['arm'] == 'pack']
    if len(transports) != 1 or transports[0]['exit_code'] != 1 or transports[0]['streams']['stdout']['bytes']:
        raise ValueError('ambiguous pack execution; resume refused')
    chunks = sorted([r for r in rows('external.cohort_model_transport_chunk')
        if r['arm'] == 'pack' and r['stream'] == 'stderr'], key=lambda r: r['offset'])
    raw = b''.join(base64.b64decode(r['content_base64'], validate=True) for r in chunks)
    expected = transports[0]['streams']['stderr']
    if (len(raw) != expected['bytes'] or sha256(raw).hexdigest() != expected['sha256']
        or b'line 8' not in raw or b'TypeError: str expected, not NoneType' not in raw
        or frozen_program.splitlines()[7] != "if arm!='native':os.environ['ATMEM_HOME']=case['atmem_home']"):
        raise ValueError('failure does not prove the pre-CLI descriptor error')
    if not rows('external.cohort_descriptors_verified'):
        raise ValueError('real database/home verification required before resume')
    return {(0, 'native')}


def terminal_capture_resume_guard(rows, frozen):
    order = [(b['slot'], arm) for b in frozen['blocks'] if b['eligibility'] == 'qualified' for arm in b['order']]
    models, captures, completed = (rows(k) for k in ('external.cohort_model_result', 'external.cohort_candidate_capture', 'external.cohort_case_completed'))
    key = lambda row: (row['slot'], row['arm'])
    count = len(models)
    stops, recovered = rows('external.cohort_execution_stopped'), rows('external.cohort_terminal_capture_recovered')
    expected = set(order[:count])
    if (not 0 < count < 30 or len(captures) != count or len(completed) != count
        or {key(r) for r in models} != expected or {key(r) for r in captures} != expected
        or {key(r) for r in completed} != expected
        or any(not r['temporary_cli_auth_absent'] or r['writer_processes_observed'] for r in captures)
        or not stops or stops[-1]['reason'] != 'stopped_source_capture_withheld'
        or key(stops[-1]) != order[count - 1]
        or not recovered or key(recovered[-1]) != order[count - 1]
        or recovered[-1]['complete_model_and_capture_prefix'] != count
        or any(r.get('completed_prefix_count', 0) >= count for r in rows('external.cohort_terminal_resume_planned'))):
        raise ValueError('terminal resume requires an exact recovered closed prefix; no unknown or repeated model')
    if any(key(r) not in expected for r in rows('external.cohort_model_dispatch')):
        raise ValueError('an unclosed dispatch exists beyond the captured prefix')
    dispatch_counts = Counter(key(r) for r in rows('external.cohort_model_dispatch'))
    allowed = Counter({cell: 1 for cell in expected})
    if rows('external.cohort_descriptor_resume_planned'):
        allowed[(0, 'pack')] += 1  # Previously proved zero-CLI null-home failure.
    if dispatch_counts != allowed:
        raise ValueError('unaccounted duplicate or missing model dispatch')
    return expected


def main(*, resume_descriptors=False, resume_terminal=False):
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / 'vault', vault_id='click-20261017', scope=scope)
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    events = vault.inspect(principal, RUN)
    def rows(kind):
        return [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == kind]
    resuming = resume_descriptors or resume_terminal
    if rows('external.cohort_execution_planned') and not resuming:
        raise ValueError('execution already dispatched: inspect its live handle; never silently restart')
    if len(rows('external.cohort_staging_completed')) != 1:
        raise ValueError('complete staging required before inference')
    frozen = rows('external.cohort_manifest_frozen')[0]
    completed = (terminal_capture_resume_guard(rows, frozen) if resume_terminal else
        descriptor_resume_guard(rows, frozen['model_program']) if resume_descriptors else set())
    verified_descriptors = {(r['slot'], r['arm']): r for r in rows('external.cohort_descriptors_verified')[-1]['verified']} if resuming else {}
    staged = {r['slot']: r for r in rows('external.cohort_staged')}
    dispatches = {r['slot']: r for r in rows('external.cohort_stage_dispatch')}
    if len(staged) != 10:
        raise ValueError('all ten feasible blocks required')
    earlier = vault.inspect(principal, frozen['prior_run'])
    issues = {e['envelope']['payload']['instance_id']: base64.b64decode(e['envelope']['payload']['content_base64']).decode()
        for e in earlier if e['envelope']['event_type'] == 'external.cohort_public_issue'}
    predecessor = vault.inspect(principal, 'external-windows-first-repair-integration-v1-20261018')
    capture_plan = next(e['envelope']['payload'] for e in predecessor if e['envelope']['event_type'] == 'external.first_repair_capture_planned')
    capture_program = capture_plan['program'].replace('atmem-windows-first-pair-', 'atmem-windows-selected-')
    modules = [('benchmarks.code_replay.' + name, Path('benchmarks/code_replay', name + '.py').read_text())
        for name in ('source_policy', 'source_capture')]
    runner, helpers = runner_helpers()
    transport = command()
    model_transport = transport[:-1] + [frozen['root_transport'][-1].replace(' -u root ', ' ')]
    if resuming:
        previous = rows('external.cohort_execution_planned')[0]
        if runner != previous['runner_source'] or helpers != previous['mcp_helpers']:
            raise ValueError('runner/helpers changed; descriptor-only resume refused')
    save('external.cohort_terminal_resume_planned' if resume_terminal else 'external.cohort_descriptor_resume_planned' if resume_descriptors else 'external.cohort_execution_planned', {'driver_source': Path(__file__).read_text(),
        'runner_source': runner, 'mcp_helpers': helpers, 'model_transport': model_transport,
        'capture_transport': transport, 'capture_program': capture_program, 'capture_modules': modules,
        'model_program_sha256': sha256(frozen['model_program'].encode()).hexdigest(),
        'policy_by_task': {i: policy(p['expectations']['source_roots']) for i, p in frozen['task_plans'].items()},
        'model_calls_so_far': len(completed), 'completed_cells_not_repeated': sorted(completed),
        'completed_prefix_count': len(completed),
        'descriptor_correction_only': resume_descriptors,
        'private_grading': 'after all model attempts; no feedback'})
    def streams(kind, identity, proc):
        metadata = {'exit_code': proc.returncode, 'streams': {}}
        for stream, raw in [('stdout', proc.stdout), ('stderr', proc.stderr)]:
            receipts = []
            for offset in range(0, len(raw), 3_000_000):
                receipts.append(save(kind + '_chunk', {**identity, 'stream': stream,
                    'offset': offset, 'total_bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
                    'content_base64': base64.b64encode(raw[offset:offset + 3_000_000]).decode()}))
            metadata['streams'][stream] = {'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'receipts': receipts}
        save(kind, {**identity, **metadata})
        return metadata
    finished = len(completed)
    for block in frozen['blocks']:
        if block['eligibility'] != 'qualified':
            continue
        slot = block['slot']; state = staged[slot]
        for arm in block['order']:
            if (slot, arm) in completed:
                continue
            identity = {'slot': slot, 'instance_id': block['instance_id'], 'repeat': block['repeat'], 'arm': arm}
            case = {k: v for k, v in state['cases'][arm].items() if k != 'generation_zlib_base64'}
            if resuming and arm != 'native':
                verified = verified_descriptors[(slot, arm)]
                case = {**case, 'atmem_home': verified['atmem_home'], 'database': verified['database']}
            roots = frozen['task_plans'][block['instance_id']]['expectations']['source_roots']
            source = dispatches[slot]['job']['source']
            probe = next(name for name in sorted(source['files_base64']) if name.endswith('.py') and any(name.startswith(root) for root in roots))
            job = {'program': frozen['model_program'], 'case': case, 'arm': arm, 'runner': runner,
                'mcp_helpers': helpers, 'product_python': frozen['build']['python'],
                'prompt': policy(roots) + issues[block['instance_id']], 'probe_source': probe,
                'cli_sha256': '628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1'}
            save('external.cohort_model_dispatch', {**identity, 'job': job, 'transport': model_transport})
            print(json.dumps({**identity, 'phase': 'model_running'}), flush=True)
            proc = subprocess.run(model_transport, input=json.dumps(job).encode(), capture_output=True, timeout=690)
            retained = streams('external.cohort_model_transport', identity, proc)
            if proc.returncode:
                save('external.cohort_execution_stopped', {**identity, 'reason': 'supervisor_failure', 'no_automatic_retry': True})
                raise RuntimeError('model supervisor failure retained; inspect raw transport before further dispatch')
            result = json.loads(proc.stdout)
            save('external.cohort_model_result', {**identity, **model_metadata(result), 'raw_response_transport': retained})
            capture_job = {'program': capture_program, 'modules': modules, 'cases': {arm: case}}
            save('external.cohort_capture_dispatch', {**identity, 'job': capture_job})
            captured = subprocess.run(transport, input=json.dumps(capture_job).encode(), capture_output=True, timeout=60)
            streams('external.cohort_capture_transport', identity, captured)
            if captured.returncode:
                save('external.cohort_execution_stopped', {**identity, 'reason': 'stopped_source_capture_withheld', 'no_automatic_retry': True})
                raise RuntimeError('source capture withheld; inspect remaining actors before proceeding')
            candidate = json.loads(captured.stdout)[arm]
            save('external.cohort_candidate_capture', {**identity, **candidate})
            if not candidate['temporary_cli_auth_absent'] or candidate['writer_processes_observed']:
                raise RuntimeError('temporary-auth/writer terminal check failed')
            finished += 1
            save('external.cohort_case_completed', {**identity, 'attempts_completed': finished,
                'usage_receipts': model_metadata(result)['usage_receipts'], 'private_grade': 'pending'})
            print(json.dumps({**identity, 'phase': 'model_captured', 'completed': finished,
                'elapsed_ms': result['elapsed_ms'], 'stop_reason': result['stop_reason'],
                'usage': model_metadata(result)['usage_receipts']}), flush=True)
    save('external.cohort_models_completed', {'attempts_completed': finished, 'unqualified_slots': 6,
        'private_grading': 'pending', 'not_goal_acceptance': True})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-descriptors-v1', action='store_true')
    parser.add_argument('--resume-captured-terminal', action='store_true')
    args = parser.parse_args()
    if args.resume_descriptors_v1 and args.resume_captured_terminal:
        parser.error('choose one proved resume condition')
    main(resume_descriptors=args.resume_descriptors_v1, resume_terminal=args.resume_captured_terminal)
