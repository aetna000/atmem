"""Grade captured cohort candidates only after all model attempts finish."""
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.external_qualification import worker_command
from benchmarks.code_replay.solver_proposal import proposal_request
from benchmarks.code_replay.windows_execute import ROOT, RUN
from benchmarks.code_replay.windows_transport import command, worker_program


def cell_key(value):
    return value['slot'], value['arm']


def require_complete_cohort(frozen, candidates, models, completed):
    expected = {(block['slot'], arm) for block in frozen['blocks']
        if block['eligibility'] == 'qualified' for arm in block['order']}
    if len(expected) != 30 or len(completed) != 1 or completed[0]['attempts_completed'] != 30:
        raise ValueError('all thirty model attempts must finish before private grading')
    if (len(candidates) != 30 or len(models) != 30 or {cell_key(r) for r in candidates} != expected
        or {cell_key(r) for r in models} != expected):
        raise ValueError('one captured candidate and model receipt per frozen cell required')
    if any(not r['temporary_cli_auth_absent'] or r['writer_processes_observed'] for r in candidates):
        raise ValueError('candidate auth/writer terminal invariant failed')
    return expected


def main():
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / 'vault', vault_id='click-20261017', scope=scope)
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    def envelopes(run):
        return [e['envelope'] for e in vault.inspect(principal, run)]
    def only(run, kind):
        rows = [e['payload'] for e in envelopes(run) if e['event_type'] == kind]
        if len(rows) != 1:
            raise ValueError('exact qualified predecessor required: ' + kind)
        return rows[0]
    events = envelopes(RUN)
    def rows(kind):
        return [e['payload'] for e in events if e['event_type'] == kind]
    if rows('external.cohort_grading_planned'):
        raise ValueError('grading already dispatched; inspect its handle, never silently retry')
    frozen = rows('external.cohort_manifest_frozen')[0]
    candidates, models = rows('external.cohort_candidate_capture'), rows('external.cohort_model_result')
    require_complete_cohort(frozen, candidates, models, rows('external.cohort_models_completed'))
    staged = {r['slot']: r for r in rows('external.cohort_staged')}
    sources = {r['instance_id']: r['job']['source'] for r in rows('external.cohort_stage_dispatch')}
    material = {e['payload']['instance_id']: e['payload']
        for e in envelopes('external-windows-remaining-reference-v1-20261018')
        if e['event_type'] == 'external.remaining_private_material'}
    first = 'marshmallow-code__marshmallow-1229'
    material[first] = only('external-reference-control-v2-20261017', 'external.private_material')
    plans = only('external-windows-selected-proposals-v1-20261018', 'external.selected_proposals_planned')['plans']
    previous = only('external-windows-solver-proposal-control-v2-20261018', 'external.solver_proposal_control_planned')
    plans[first] = {'bootstrap_source_base64': previous['bootstrap_source_base64'],
        'bootstrap_sha256': previous['bootstrap_sha256'], 'image': previous['image']}
    save('external.cohort_grading_planned', {'driver_source': Path(__file__).read_text(),
        'cells': [cell_key(r) for r in candidates], 'qualified_plans': plans,
        'max_workers': 2, 'no_feedback_to_solvers': True, 'models_already_completed': 30})
    jobs = []
    for candidate in candidates:
        identity = {k: candidate[k] for k in ('slot', 'arm', 'instance_id', 'repeat')}
        expected = staged[candidate['slot']]['cases'][candidate['arm']]
        if candidate['workspace'] != expected['workspace'] or candidate['case_root'] != expected['root']:
            raise ValueError('candidate differs from the frozen source origin')
        plan = plans[candidate['instance_id']]
        bootstrap = base64.b64decode(plan['bootstrap_source_base64']).decode()
        if sha256(bootstrap.encode()).hexdigest() != plan['bootstrap_sha256']:
            raise ValueError('qualified private worker source differs')
        name = 'atmem-reference-control-' + uuid4().hex
        job = {'program': worker_program(), 'name': name,
            'command': worker_command(plan['image'], name, bootstrap),
            'payload': proposal_request(material[candidate['instance_id']], sources[candidate['instance_id']], candidate['files_base64'])}
        save('external.cohort_grade_dispatch', {**identity, 'job': job})
        jobs.append((identity, job))
    def execute(item):
        identity, job = item
        try:
            proc = subprocess.run(command(), input=json.dumps(job).encode(), capture_output=True, timeout=205)
            return identity, proc, None
        except Exception as exc:
            return identity, None, type(exc).__name__ + ': ' + str(exc)
    finished = 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(execute, item) for item in jobs]):
            identity, proc, failure = future.result()
            result = {**identity}
            if failure:
                result['transport_failure'] = failure
            else:
                result.update(transport_exit_code=proc.returncode, streams={})
                for stream, raw in [('stdout', proc.stdout), ('stderr', proc.stderr)]:
                    receipts = []
                    for offset in range(0, len(raw), 3_000_000):
                        receipts.append(save('external.cohort_grade_stream_chunk', {**identity, 'stream': stream,
                            'offset': offset, 'total_bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
                            'content_base64': base64.b64encode(raw[offset:offset + 3_000_000]).decode()}))
                    result['streams'][stream] = {'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'receipts': receipts}
                if proc.returncode == 0:
                    controller = json.loads(proc.stdout)
                    controller.pop('raw_output_base64', None)
                    result['controller'] = controller
            save('external.cohort_private_grade', result)
            finished += 1
            controller = result.get('controller', {})
            print(json.dumps({**identity, 'graded': finished, 'reason': controller.get('reason') or failure,
                'controller_exit': controller.get('exit_code'), 'grading': controller.get('worker', {}).get('grading')}), flush=True)
    save('external.cohort_grading_completed', {'graded': finished, 'no_model_feedback': True,
        'comparison_and_confirmation': 'pending; not goal acceptance'})


if __name__ == '__main__':
    main()
