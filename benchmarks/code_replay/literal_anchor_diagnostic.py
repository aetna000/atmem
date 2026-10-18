"""Exact bounded source delta and all-case replay for static literal anchors."""
import ast
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

from benchmarks.code_replay.query_nomination_preview import evidence
from benchmarks.code_replay.query_nomination_transfer import RUN as TRANSFER
from benchmarks.code_replay.query_nomination_trace_audit import reader_program

RUN = 'external-windows-query-literal-anchors-diagnostic-v1-20261018'
BASELINE = '004a4ff9f66843206456f28d2bd08b59c09196ecee16c88a25b51dc85fa62020'


def allowed_delta(baseline, candidate):
    helpers = [n for n in ast.parse(candidate).body if isinstance(n, ast.FunctionDef) and n.name == '_query_literal_targets']
    if len(helpers) != 1:
        raise ValueError('one bounded literal helper required')
    helper = ast.get_source_segment(candidate, helpers[0])
    binding = ('    literal_targets = _query_literal_targets(task, sources, {\n'
               '        (r["path"], r["node"].lineno, r["node"].name) for r in candidates\n'
               '        if r["node"] is not None and r["name"].rsplit(".", 1)[-1] == r["node"].name})\n'
               '    explicit_paths = {r["path"] for r in candidates if r["explicit"]}\n')
    priority = ('        literal_priority = literal_targets.get((row["path"], row["node"].lineno, row["node"].name)) if row["node"] is not None else None\n'
                '        if literal_priority:\n'
                '            return literal_priority + min(score, 100)\n')
    old = '        if row["location_span"] is not None:'
    new = '        if row["location_span"] is not None and (row["explicit"] or row["path"] not in explicit_paths):'
    if candidate.count(binding) != 1 or candidate.count(priority) != 1 or candidate.count(new) != 1 or baseline.count(old) != 1:
        raise ValueError('exact literal and named-target bindings required')
    restored = candidate.replace(helper+'\n\n\n', '', 1).replace(binding, '', 1).replace(priority, '', 1).replace(new, old, 1)
    if restored != baseline:
        raise ValueError('only literal helper and declared nomination bindings may change')
    return helper


def main():
    from benchmarks.code_replay import corrective_layout_diagnostic as replay
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(RUN)
    rows = vault.inspect(principal, RUN)
    if [r['envelope']['event_type'] for r in rows] != ['external.literal_anchors_planned']:
        raise ValueError('exact unexecuted frozen baseline plan required')
    plan = rows[0]['envelope']['payload']; candidate = Path('atmem/knowledge/code/packing.py').read_text()
    if sha256(plan['baseline_source'].encode()).hexdigest() != BASELINE:
        raise ValueError('complete unchanged CD2 source required')
    allowed_delta(plan['baseline_source'], candidate)
    transfer = vault.inspect(principal, TRANSFER)
    terminal, = [r['envelope']['payload'] for r in transfer if r['envelope']['event_type'] == 'external.query_nomination_MEM_recovery_completed']
    if terminal['proof']['request_audit']['verified_original_requests'] != 38:
        raise ValueError('complete independent recovery required')
    transfer_plan, = [r['envelope']['payload'] for r in transfer if r['envelope']['event_type'] == 'external.query_nomination_MEM_transfer_planned']
    source = ('import types\nbase=types.ModuleType("retained_generic_pack_replay")\n'
              'exec(compile('+repr(inspect.getsource(replay))+',"<unchanged-generic-pack-replay>","exec"),base.__dict__)\n'
              'base.BASELINE='+repr(BASELINE)+'\n'+inspect.getsource(allowed_delta)+'\n'
              'def audit(archive,output,keys):\n'
              ' return base.audit(archive,output,keys,'+repr(plan['baseline_source'])+','+repr(candidate)+',validate=allowed_delta)\n')
    source = 'import ast\n'+source
    program = reader_program(transfer_plan['standalone_recovery_program'], source)
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.literal_anchors_started', {
        'driver_source': Path(__file__).read_text(), 'candidate_source': candidate,
        'candidate_sha256': sha256(candidate.encode()).hexdigest(), 'reader_program': program,
        'generic_replay_source': inspect.getsource(replay), 'profile_baseline_sha256': BASELINE,
        'source_vault_access': False, 'models_or_grades_repeated': 0})
    loader = "import json,sys;exec(compile(json.load(sys.stdin)['program'],'<archive-only-literal-replay>','exec'))"
    result = subprocess.run([sys.executable, '-c', loader], input=json.dumps({'program': program}).encode(),
                            capture_output=True, timeout=3600)
    if result.returncode:
        save('external.literal_anchors_failed', {'exit_code': result.returncode, 'stderr': result.stderr.decode(errors='replace')})
        raise RuntimeError('static literal replay failed; preserve original evidence')
    value = json.loads(result.stdout)
    save('external.literal_anchors_completed', value)
    print(json.dumps(value['summary'], indent=2), flush=True)


if __name__ == '__main__':
    main()
