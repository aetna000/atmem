"""Recover a retained native execution, never replay a model or application.

The original failed run and its inflight marker remain immutable. Recovery is
stored separately, structurally checked by upstream, and independently graded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from benchmarks.dolphinbench.export import export_interaction, UNSENT_GUARD_ERROR
from benchmarks.dolphinbench.gateway import Gateway, save_new
from benchmarks.dolphinbench.judge import openrouter_judge
from benchmarks.dolphinbench.recording import BudgetLedger, fingerprint
from scripts.openrouter_azure_sol import load_key
from .grade_run import claim_budget, settle_budget
from .preflight import Review, inventory, validate_review
from .protocol import digest


def configuration(parent, persona, item_id, *, original_gateway_source=None):
    return {'stage': 'retained-native-recording-recovery-v1',
        'parent': str(parent.resolve()), 'persona': persona, 'item_id': item_id,
        'parent_manifest_sha256': hashlib.sha256((parent/'stage-manifest.json').read_bytes()).hexdigest(),
        'original_recording_failure':json.loads((parent/'failure.json').read_text())['detail'],
        'original_gateway_source':str(original_gateway_source) if original_gateway_source else None,
        'original_gateway_sha256':hashlib.sha256(Path(original_gateway_source).read_bytes()).hexdigest()
            if original_gateway_source else None,
        'model_or_tool_replay': False, 'original_evidence_modified': False,
        'grader': 'Azure-only openai/gpt-5.6-sol medium', 'cap_usd': 1,
        'latency_not_comparable_to_complete_task_wall_time': True,
        'source_execution_not_release_artifact': True, 'ready_for_600': False}


def reconstruct(parent, persona, item_id, *, upstream, runtime_root, original_gateway_source=None):
    from harness.submission import read_release, check_settings, check_messages
    from harness.runner import digest as upstream_digest
    from graders.mechanical import load_tool_calls
    failure = json.loads((parent/'failure.json').read_text())
    supported={'Conflicting duplicate model argument keys cannot be normalized',
               'Unreconciled missing gateway response'}
    guard_failure=(failure.get('type')=='RuntimeError'
        and failure.get('detail')=='Native interaction failed; no automatic paid replay'
        and original_gateway_source is not None)
    if (set(failure)!={'type','detail','all_evidence_preserved'}
            or (not guard_failure and (failure['type']!='ValueError' or failure['detail'] not in supported))
            or failure['all_evidence_preserved'] is not True):
        raise ValueError('unsupported original failure; no automatic recovery')
    marker = parent/'tests'/persona/(item_id+'.inflight')
    if not marker.is_file() or (parent/'tests'/persona/(item_id+'.json')).exists():
        raise ValueError('only an unreconciled retained execution may be recovered')
    release = read_release(upstream)
    task = next(t for t in release[persona]['tests'] if str(t['id']).zfill(3) == item_id)
    if json.loads(marker.read_text())['source_sha256'] != upstream_digest(task):
        raise ValueError('original task changed')
    manifest = json.loads((parent/'stage-manifest.json').read_text())
    if digest(release) != manifest['corpus_digest']:
        raise ValueError('original corpus changed')
    native = parent/'native/tests'/persona/item_id
    process = json.loads((native/'process.json').read_text())
    terminals = [json.loads(line) for line in process['stdout'].splitlines()
                 if line.startswith('{') and json.loads(line).get('type') == 'result']
    expected_exit=1 if guard_failure else 0
    if process['exit_code'] != expected_exit or len(terminals) != 1 or terminals[0].get('exit_code') != expected_exit:
        raise ValueError('native execution did not finish successfully')
    if guard_failure and terminals[0].get('error')!=UNSENT_GUARD_ERROR:
        raise ValueError('Original terminal failure was not the qualified unsent guard')
    duration = terminals[0].get('duration_ms')
    if type(duration) not in (int, float) or not 0 <= duration < float('inf'):
        raise ValueError('missing native duration; do not invent task wall time')
    profile = 'db-'+fingerprint({'run': str(parent), 'persona': persona,
                                 'phase': 'tests', 'id': item_id})[:24]
    witness = runtime_root/'profiles'/profile/'api-witness.jsonl'
    log = parent/'apps'/persona/item_id/'calls.jsonl'
    files = [marker, native/'process.json', parent/'stage-manifest.json', witness, log]
    if guard_failure:files.extend([parent/'budget.db',Path(original_gateway_source)])
    files += [p for p in (native/'calls').rglob('*.json') if p.is_file()]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    calls = load_tool_calls(log)
    exported = export_interaction(native/'calls', witness, app_calls=calls,
        default_source_paths=(upstream/'mock_mcp').glob('repair*.py'),
        terminal_failure=terminals[0] if guard_failure else None,
        unforwarded_guard={'ledger_path':parent/'budget.db','campaign_identity':manifest,
            'original_gateway_source':original_gateway_source} if guard_failure else None)
    if (failure['detail']=='Conflicting duplicate model argument keys cannot be normalized'
            and not exported['witnessed_conflicting_argument_key_normalization']):
        raise ValueError('recovery requires independently witnessed native arguments')
    if (failure['detail']=='Unreconciled missing gateway response' and not any(
            attempt.get('failure_witness',{}).get('basis')==
            'unique_completed_native_lifecycle_and_semantically_identical_sdk_retry'
            for attempt in exported['failed_transport_attempts'])):
        raise ValueError('recovery requires independently witnessed native SDK retry')
    check_settings(exported['settings'], 'retained native recovery')
    check_messages(exported['messages'], 'retained native recovery')
    expected = f"[{task['narrative_anchor_date']}] {task['test']}"
    if [m['content'] for m in exported['messages'] if m['role'] == 'user'] != [expected]:
        raise ValueError('original user boundary changed')
    if before != {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}:
        raise ValueError('original evidence changed during reconstruction')
    evidence = {'settings': exported['settings'], 'row': {'persona': persona,
        'test_id': item_id, 'messages': exported['messages'], 'duration_ms': duration,
        'app_calls': [{k:c[k] for k in ('tool','args','result') if k in c} for c in calls]},
        'attempts': [{'recording_recovery': True, 'model_or_tool_replay': False,
                      'latency_comparable_to_complete_task_wall_time':False}]}
    receipt = {'format': 'retained-native-recording-recovery-v1',
        'original_files_sha256': before, 'original_evidence_modified': False,
        'model_or_tool_replay': False, 'upstream_structural_validation_passed': True,
        'recovered_recording_boundary':failure['detail'],
        'native_execution_completed_successfully':not guard_failure,
        'application_outcome_not_repaired':True,
        'failed_transport_attempts_retained':len(exported['failed_transport_attempts']),
        'duration_origin': 'retained native CLI result, excludes unrecorded preparation',
        'latency_comparable_to_complete_task_wall_time': False,
        'official_transport_acceptance_not_established': True, 'ready_for_600': False}
    return task, evidence, exported, receipt


def settle_recovery_costs(output, config, master):
    """Settle even mechanical-only grading; preserve every uncertain paid bound."""
    book = BudgetLedger(output/'budget.db', cap_usd=1, identity=config)
    try:
        save_new(output/'costs-final.json', book.totals())
        amount = book.connection.execute("SELECT COALESCE(SUM(CASE WHEN state IN ('completed','overrun') THEN actual WHEN state='reserved' THEN reserved ELSE 0 END),0) FROM calls").fetchone()[0]
        settle_budget(master, output.name, amount)
    finally: book.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=Path); parser.add_argument('output', type=Path)
    parser.add_argument('--persona', required=True); parser.add_argument('--item-id', required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--runtime-root',type=Path)
    parser.add_argument('--original-gateway-source',type=Path)
    args = parser.parse_args()
    parent, output = args.parent.resolve(), args.output.resolve()
    for path in (parent,output):
        if not any(path.is_relative_to(p) for p in
            (Path('/Volumes/AtMemDolphin'),Path('/Volumes/AtMemBenchRuntime'))):
            raise ValueError('recovery must remain on dedicated private benchmark volumes')
    if output.exists(): raise ValueError('fresh recovery output required')
    upstream = Path('/Volumes/AtMemDolphin/upstream'); sys.path.append(str(upstream))
    config = configuration(parent, args.persona, args.item_id,original_gateway_source=args.original_gateway_source)
    review = Review(**json.loads(args.review.read_text())['review'])
    validate_review(Path.cwd(), config, review, stage=config['stage'],
        required_specs={'specs/046-retrieval-performance-2310/spec.md',
                        'specs/046-retrieval-performance-2310/architecture.md',
                        'specs/046-retrieval-performance-2310/plan.md'})
    recorded_runtime=json.loads((parent/'stage-manifest.json').read_text()).get(
        'execution_paths',{}).get('runtime_root','/private/tmp/atmem-dolphin-runtime-v3-20261021')
    runtime=args.runtime_root or Path(recorded_runtime)
    if str(runtime)!=recorded_runtime:raise ValueError('original native witness runtime must match')
    task, evidence, exported, receipt = reconstruct(parent, args.persona, args.item_id,
        upstream=upstream, runtime_root=runtime, original_gateway_source=args.original_gateway_source)
    # Complete all offline proof checks before reserving or requesting a judge.
    master = Path('/Volumes/AtMemDolphin/retrieval-2310-budget.db')
    claim_budget(master, output.name, cap_usd='1')
    from harness.runner import Runner
    from harness.submission import read_release
    runner = Runner(read_release(upstream), output, None, identity=config,
                    release_root=upstream, allow_paid=False)
    runner.allow_paid = True
    save_new(output/'recovery-receipt.json', receipt)
    save_new(output/'export.json', exported)
    save_new(output/'tests'/args.persona/(args.item_id+'.json'), evidence)
    gateway = None
    try:
        gateway = Gateway(key=load_key(args.env_file), output=output/'judge-calls',
            ledger_path=output/'budget.db', campaign_identity=config, cap_usd=1,
            phase='judge', model='openai/gpt-5.6-sol', input_per_million=5,
            output_per_million=30, output_token_cap=8000).start()
        with openrouter_judge(gateway): grade = runner._grade(task, evidence)
        save_new(output/'grades'/args.persona/(args.item_id+'.json'), grade)
        result = {'tasks': 1, 'passed': int(all(c['passed'] for c in grade['checks'])),
            'results': [{'persona': args.persona, 'task_id': args.item_id,
                        'passed': all(c['passed'] for c in grade['checks'])}],
            'recovered_original_execution': True, 'parent': str(parent),
            'model_or_tool_replay': False, 'ready_for_600': False}
        save_new(output/'result.json', result); print(json.dumps(result), flush=True)
    except BaseException as exc:
        save_new(output/'failure.json', {'type': type(exc).__name__, 'detail': str(exc)[:300]})
        raise
    finally:
        if gateway is not None: gateway.stop()
        # Mechanical grading may require no API calls at all. The allocation
        # must still settle; no ledger previously meant no forwarded request,
        # not permission to leave a phantom dollar reserved indefinitely.
        settle_recovery_costs(output,config,master)


if __name__ == '__main__': main()
