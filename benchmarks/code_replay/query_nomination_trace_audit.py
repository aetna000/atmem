"""Reuse the all-case descriptive audit on independently recovered CD2 evidence."""
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

from benchmarks.code_replay.query_nomination_preview import evidence
from benchmarks.code_replay.query_nomination_screen import PREFIX
from benchmarks.code_replay.query_nomination_transfer import RUN as TRANSFER, OUTPUT, KEYS

RUN = PREFIX+'trace-audit-v1-20261018'


def reader_program(bootstrap, audit_source):
    marker = '\nproof=archive.recover_collection'
    if bootstrap.count(marker) != 1:
        raise ValueError('exact recorded standalone archive-only reader required')
    return bootstrap[:bootstrap.index(marker)] + '\nns={"__name__":"cd2_descriptive_reader"}\n' + (
        'exec(compile('+repr(audit_source)+',"<retained-all-case-descriptive-audit>","exec"),ns)\n'
        'print(json.dumps(ns["audit"](archive,Path('+repr(OUTPUT)+'),Path('+repr(KEYS)+'))),flush=True)\n')


def main():
    from benchmarks.code_replay.corrective_trace_audit import source_text_overlap, audit
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(RUN)
    if vault.inspect(principal, RUN):
        raise ValueError('trace audit already attempted; inspect retained evidence')
    rows = vault.inspect(principal, TRANSFER)
    def only(kind):
        value, = [r['envelope']['payload'] for r in rows if r['envelope']['event_type'] == kind]
        return value
    terminal = only('external.query_nomination_MEM_recovery_completed')
    proof = terminal['proof']
    if (proof['source_vault_opened'] is not False or proof['request_audit']['verified_original_requests'] != 38
            or (proof['candidates'], proof['private_grades'], proof['public_vaults']) != (38, 38, 38)):
        raise ValueError('complete independent recovery required before diagnosis')
    plan = only('external.query_nomination_MEM_transfer_planned')
    source = ('from collections import Counter\nfrom hashlib import sha256\nimport json,re\nfrom pathlib import Path\n'
              'PREFIX='+repr(PREFIX)+'\n\n'+inspect.getsource(source_text_overlap)+'\n\n'+inspect.getsource(audit))
    program = reader_program(plan['standalone_recovery_program'], source)
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.query_nomination_trace_audit_planned', {
        'driver_source': Path(__file__).read_text(), 'reader_program': program,
        'audit_source': source, 'selection': 'all 38 original cells', 'source_vault_access': False,
        'models_repeated': 0, 'private_grades_repeated': 0, 'efficacy_result': '26.231768438% saving; 7 versus 8 passes; combined gate failed'})
    loader = "import json,sys;exec(compile(json.load(sys.stdin)['program'],'<archive-only-CD2-audit>','exec'))"
    result = subprocess.run([sys.executable, '-c', loader], input=json.dumps({'program': program}).encode(),
                            capture_output=True, timeout=3600)
    if result.returncode:
        save('external.query_nomination_trace_audit_failed', {
            'exit_code': result.returncode, 'stderr': result.stderr.decode(errors='replace'),
            'no_outcome_retry': True})
        raise RuntimeError('archive-only diagnostic failed; preserve original evidence')
    value = json.loads(result.stdout)
    save('external.query_nomination_trace_audit_completed', value)
    print(json.dumps(value['summary'], indent=2), flush=True)


if __name__ == '__main__':
    main()
