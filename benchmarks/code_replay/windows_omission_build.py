"""Build a separate Windows preview with only the explicit omission correction."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
from benchmarks.code_replay.windows_execute import ROOT
from benchmarks.code_replay.windows_transport import framed_command, framed_input

RUN = 'external-windows-product-build-explicit-omissions-v1-20261018'
STRICT_RUN = 'external-windows-product-build-explicit-omissions-v2-20261018'
PRIOR = 'external-windows-product-build-module-rollup-v2-20261018'
CHANGED = ('atmem/knowledge/projections.py', 'atmem/knowledge/code/mcp.py')


def updated_job(prior, replacements):
    if set(replacements) != set(CHANGED):
        raise ValueError('only the two declared product files may change')
    job = json.loads(json.dumps(prior))
    for name, raw in replacements.items():
        if name not in job['files'] or sha256(base64.b64decode(job['files'][name])).hexdigest() != job['manifest'][name]:
            raise ValueError('prior product source identity differs')
        job['files'][name] = base64.b64encode(raw).decode()
        job['manifest'][name] = sha256(raw).hexdigest()
    lines = job['program'].splitlines()
    lines.insert(1, "import shutil\nassert min(shutil.disk_usage('/tmp').free,shutil.disk_usage('/mnt/c').free)>=8*1024**3,'physical disk guard'")
    job['program'] = '\n'.join(lines) + '\n'
    return job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict-execution-v2', action='store_true',
        help='New source build after making graph omissions explicit and preserving strict execution capture')
    args = parser.parse_args()
    run_id = STRICT_RUN if args.strict_execution_v2 else RUN
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope)
    if vault.inspect(principal, run_id):
        raise ValueError('build already dispatched; inspect its handle, never overwrite')
    original = ReplayEvidence(ROOT / 'vault', vault_id='click-20261017', scope=scope)
    events = original.inspect(principal, PRIOR)
    prior = next(e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'external.windows_rollup_build_planned')
    job = updated_job(prior['job'], {name: Path(name).read_bytes() for name in CHANGED})
    def save(kind, payload):
        return vault.capture(run_id=run_id, kind=kind, principal=principal, payload=payload)
    save('external.windows_omission_build_planned', {'driver_source': Path(__file__).read_text(),
        'job': job, 'transport': framed_command(), 'prior_build': PRIOR,
        'changed_product_files': CHANGED, 'prior_dependency_versions': prior['prior_dependency_versions'],
        'no_owner_install': True, 'solver_calls': 0, 'frozen_candidate_replaced': False,
        'explicit_graph_only_omissions': args.strict_execution_v2,
        'prior_omission_build': RUN if args.strict_execution_v2 else None})
    proc = subprocess.run(framed_command(), input=framed_input(job), capture_output=True, timeout=1100)
    save('external.windows_omission_build_transport', {'exit_code': proc.returncode,
        'stdout_base64': base64.b64encode(proc.stdout).decode(), 'stderr_base64': base64.b64encode(proc.stderr).decode()})
    if proc.returncode:
        raise RuntimeError('new preview build transport failed; retained, no automatic retry')
    result = json.loads(proc.stdout)
    save('external.windows_omission_build_result', result)
    if not result['qualified_installed_source_identity']:
        raise RuntimeError('new preview did not qualify installed source identity')
    program = "import importlib.metadata as m,json;print(json.dumps(sorted([{'name':d.metadata['Name'].lower(),'version':d.version} for d in m.distributions()],key=lambda r:r['name'])))"
    cmd = framed_command()
    cmd[-1] = cmd[-1].replace('python3 -c', result['python'] + ' -I -c')
    check = subprocess.run(cmd, input=framed_input({'program': program}), capture_output=True, timeout=30)
    if check.returncode:
        raise RuntimeError('dependency inspection failed')
    actual = json.loads(check.stdout)
    proof = {'actual': actual, 'exact_dependency_versions_match_prior_preview': actual == prior['prior_dependency_versions'],
        'wheel_sha256': result['wheel_sha256'], 'packages_checked': len(actual), 'solver_calls': 0}
    save('external.windows_omission_dependencies_verified', proof)
    if not proof['exact_dependency_versions_match_prior_preview']:
        raise RuntimeError('preview dependency versions differ')
    print(json.dumps({k: result[k] for k in ('python', 'wheel_sha256', 'qualified_installed_source_identity', 'preview_not_release')}), flush=True)


if __name__ == '__main__':
    main()
