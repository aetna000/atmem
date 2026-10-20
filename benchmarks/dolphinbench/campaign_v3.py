"""Fresh V3 DolphinBench campaign; local episode ingestion and subscription agent.

The historical memory APIs/budgets are retained, not its Qwen/GPT-5.2 score.
Sol-medium grading uses disclosed Azure-only OpenRouter transport. Listing
acceptance is not asserted; the unmodified submission validator is the format gate.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import time
import urllib.request

from .adapter import AtMemAdapter
from .gateway import Gateway, save_new
from .judge import openrouter_judge
from .recording import BudgetLedger


def prior_exposure():
    roots = ('campaign-atmem-239', 'campaign-atmem-239-qualified',
             'campaign-atmem-239-full', 'campaign-atmem-239-frozen',
             'atbot-semantic-diagnostic', 'sol-judge-qualification-20261021')
    total = 0
    for name in roots:
        path = Path('/Volumes/AtMemDolphin') / name / 'budget.db'
        if name == 'sol-judge-qualification-20261021' and not path.exists():
            continue
        connection = sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True)
        try:
            total += connection.execute("SELECT COALESCE(SUM(CASE WHEN state IN ('completed','overrun') "
                "THEN actual WHEN state='reserved' THEN reserved ELSE 0 END),0) FROM calls").fetchone()[0]
        finally:
            connection.close()
    return total / 1_000_000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--confirm-paid-grading', action='store_true')
    parser.add_argument('--qualification-only', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Resume only the exact frozen condition; never replay uncertain model interactions')
    parser.add_argument('--baseline-from', type=Path, help='Adopt only cloud-verified histories and frozen checkpoints, never prior task outputs')
    args = parser.parse_args()
    if not args.confirm_paid_grading:
        parser.error('The operator must explicitly confirm the existing run-specific budget')
    root = args.output.resolve()
    root.relative_to(Path('/Volumes/AtMemDolphin'))
    if root.exists() and not args.resume:
        parser.error('This entry point starts a fresh condition only; never overwrite or relabel prior runs')
    if args.resume and not (root / 'run.json').is_file():
        parser.error('No frozen full-campaign identity is available for resumption')
    if not os.environ.get('ATMEM_HOME', '').startswith('/Volumes/AtMemDolphin/'):
        parser.error('An isolated external AtMem Home is required')
    proof_path = Path('/Volumes/AtMemDolphin/qualification-native-v3-internal-runtime-20261021/result.json')
    proof = json.loads(proof_path.read_text())
    if not proof.get('passed') or proof.get('memory_engine') != 'context-v3' or not proof.get('upstream_app_tools'):
        parser.error('Installed native V3 qualification did not pass')
    sol_path = Path('/Volumes/AtMemDolphin/sol-judge-qualification-20261021/result.json')
    if not args.qualification_only and (not sol_path.exists() or not json.loads(sol_path.read_text()).get('replay_equal')):
        parser.error('The actual fixed Sol judge/record/replay qualification did not pass')
    wheel = Path('/Volumes/AtMemDolphin/v3-wheels/atmem-2.3.9-py3-none-any.whl')
    wheel_sha = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if wheel_sha != '8a7e972c03bea5cc7eb143daeb6b57c4e13b1baff4613df00d32fa2ff49df345':
        parser.error('The installed V3 artifact changed; repeat qualification')
    exposure = prior_exposure()
    if exposure > 1.0:
        parser.error('Preparation exposure exceeds its reserved US$1 allowance; reconcile the global ceiling')
    root.mkdir(mode=0o700, exist_ok=args.resume)
    upstream = Path('/Volumes/AtMemDolphin/upstream')
    sys.path.append(str(upstream))
    from harness.adapter import Interaction
    from harness.runner import Runner, run_lock, digest, save
    from harness.submission import read_release, grading_calls
    from scripts.openrouter_azure_sol import load_key
    release = read_release(upstream)
    identity = {'format': 'atmem-dolphin-v3-campaign-v1',
        'upstream_commit': '81cb6f8405b40a9e76089cef650806a80af06ea2',
        'corpus_digest': digest(release), 'cap_usd': 249.0, 'user_total_ceiling_usd': 250,
        'prior_actual_plus_uncertain_usd': exposure, 'prior_reserved_allowance_usd': 1.0,
        'atmem_base_version': '2.3.9', 'artifact_kind': 'unreleased research wheel, not PyPI wheel',
        'wheel_sha256': wheel_sha, 'memory_engine': 'context-v3',
        'formation': 'scoped administrator-authorized Memory.form_context_episode',
        'retrieval': 'Memory.prepare_context_v3; context-fast; 200 candidates; 32000 bytes',
        'pre_action_gate': 'product V3 sufficient status required before model invocation',
        'memory_delivery': 'unchanged product prepare-turn context through native Hermes ephemeral_system_prompt; no user-side prefetch',
        'frozen_baseline_from': str(args.baseline_from.resolve()) if args.baseline_from else None,
        'ingestion': 'local source-episode import, no model calls, same mode as historical 5% run',
        'agent': {'model': 'openai/gpt-5.6-luna', 'reasoning': 'medium', 'max_turns': 20,
            'transport': 'native Hermes Chat Completions over Hermes Codex OAuth compatibility bridge',
            'completion_cap': 'Codex OAuth ignores unsupported max_output_tokens; provider native behavior'},
        'judge': {'model': 'gpt-5.6-sol', 'reasoning': 'medium', 'max_completion_tokens': 8000,
                  'transport': 'OpenRouter Azure-only; no fallback; raw routing alias retained'},
        'subscription_accounting': 'incremental API charge zero; report actual tokens and separate pricing estimates; subscription fee not allocated',
        'official_transport_acceptance': 'unconfirmed; do not claim maintainer endorsement',
        'native_qualification_sha256': hashlib.sha256(proof_path.read_bytes()).hexdigest()}
    if sol_path.exists():
        identity['sol_qualification_sha256'] = hashlib.sha256(sol_path.read_bytes()).hexdigest()
    # The upstream runner must establish identity before *any* nested JSON
    # evidence, including listener/qualification receipts, exists. A placeholder
    # selects the subscription transport identity only; it is never called.
    options = {'campaign_identity': identity, 'env_file': str(args.env_file),
        'memory_engine': 'context-v3', 'ingestion_mode': 'source-episode',
        'app_python': '/private/tmp/atmem-dolphin-apps-v3-20261021/bin/python',
        'runtime_root': '/private/tmp/atmem-dolphin-runtime-v3-20261021',
        'memory_delivery': 'native-ephemeral-system',
        'subscription_endpoint': 'listener-pending'}
    if args.baseline_from:
        options['baseline_memory_root'] = str(args.baseline_from.resolve() / 'memory')
    adapter = AtMemAdapter(options, root)
    with run_lock(root):
        runner = Runner(release, root, adapter, identity=adapter.identity(),
            release_root=upstream, allow_paid=False)
        runner.allow_paid = True
        BudgetLedger(adapter.ledger, cap_usd=identity['cap_usd'], identity=identity).close()
    os.environ['ATMEM_SUBSCRIPTION_PROXY_TOKEN'] = secrets.token_urlsafe(32)
    child_env = {**os.environ, 'HERMES_HOME': '/Users/javadtaghia/.hermes', 'PYTHONDONTWRITEBYTECODE': '1'}
    subscription_root = root / 'subscription-transport'
    stamp = str(time.time_ns())
    listener = subscription_root / 'listeners' / (stamp + '.json')
    log = (root / ('subscription-service-' + stamp + '.log')).open('x')
    process = subprocess.Popen([
        '/Users/javadtaghia/.hermes/tools/python-3.14.7+20260901-darwin-arm64/bin/python3.14', '-I',
        str(Path(__file__).with_name('subscription_service.py')), '--output', str(subscription_root),
        '--listener-file', str(listener)],
        cwd='/Volumes/AtMemDolphin/tmp', env=child_env, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(180):
            if process.poll() is not None:
                raise RuntimeError('Subscription service did not start; inspect the protected log')
            if listener.exists():
                try:
                    options['subscription_endpoint'] = json.loads(listener.read_text())['endpoint']
                    break
                except json.JSONDecodeError:
                    pass
            time.sleep(0.5)
        else:
            raise RuntimeError('Subscription service startup deadline elapsed')
        # Live transport/memory diagnostic is isolated from the full condition.
        qualification = root / ('resume-qualification-' + stamp if args.resume else 'live-qualification')
        qualification_options = {k: v for k, v in options.items() if k != 'baseline_memory_root'}
        test_adapter = AtMemAdapter(qualification_options, qualification)
        try:
            first = release['morgan']['sessions'][0]
            controller = Runner({'morgan': {'sessions': [first], 'tests': []}}, qualification, test_adapter,
                identity={'diagnostic_only': True, 'user_boundary_gate': 'unmodified Runner._execute'}, release_root=upstream)
            controller._execute('ingestion', 'morgan', first)
            checkpoint = test_adapter.freeze('morgan')
            result = controller._execute('tests', 'morgan', {'id': 'diagnostic',
                'test': 'What company did I start with Devon?', 'narrative_anchor_date': first['narrative_date']})
            text = '\n'.join(str(m.get('content', '')) for m in result['row']['messages'] if m.get('role') == 'assistant')
            if 'Scaffold' not in text or any(a.get('gate_blocked') for a in result['attempts']):
                raise RuntimeError('Live subscription agent did not use V3 memory; do not scale this condition')
            # Separate read-only tool transport diagnostic, not a memory-quality
            # case. It does not require a personal-memory sufficiency ruling.
            tool_adapter = AtMemAdapter({**qualification_options, 'pre_action_gate': False}, qualification)
            try:
                controller.adapter = tool_adapter
                tool_result = controller._execute('tests', 'morgan', {'id': 'diagnostic-tools',
                    'test': 'List my inbox using the provided application tools. Do not send or change anything.',
                    'narrative_anchor_date': first['narrative_date']})
                observed_tools = [call['tool'] for call in tool_result['row'].get('app_calls', [])]
                grading_calls(tool_result['row'], 'live tool-format qualification')
                if 'list_inbox' not in observed_tools:
                    raise RuntimeError('The live subscription agent did not execute the simulated inbox read')
            finally:
                tool_adapter.stop()
            test_adapter.verify_checkpoint('morgan', checkpoint)
            save_new(root / ('resume-qualification-' + stamp + '.json' if args.resume else 'live-qualification.json'), {'passed': True, 'diagnostic_only': True,
                'native_agent': 'Hermes', 'provider': 'OpenAI-Subscription', 'memory_engine': 'context-v3',
                'exact_original_user_verified_by_upstream_runner': True,
                'memory_delivery': 'native-ephemeral-system',
                'response': text, 'model_calls_have_actual_usage': True,
                'simulated_tool_calls': observed_tools,
                'tool_diagnostic_memory_gate': 'not applied to the separate transport-only read',
                'test_questions_or_answers_supplied': False})
            test_adapter.archive()
        finally:
            test_adapter.stop()
        if args.qualification_only:
            print(json.dumps({'qualification_passed': True, 'full_run_started': False}), flush=True)
            return
        with run_lock(root):
            if args.baseline_from and not args.resume:
                from .baseline import adopt
                adopt(args.baseline_from, root, release, adapter)
            # Each persona remains chronological. Batches join before exports,
            # so a backup cannot observe a half-written interaction.
            positions = {persona: 0 for persona in release}
            for persona in release:
                adapter.host(persona)
                completed_ids = {path.stem for path in (root / 'ingestion' / persona).glob('*.json')}
                while positions[persona] < len(release[persona]['sessions']) and release[persona]['sessions'][positions[persona]]['id'] in completed_ids:
                    positions[persona] += 1
                if len(completed_ids) != positions[persona]:
                    raise ValueError('Saved history has a gap or unknown IDs; do not silently reorder it')
            with ThreadPoolExecutor(max_workers=3) as pool:
                while any(positions[p] < len(release[p]['sessions']) for p in release):
                    def ingest_batch(persona):
                        start = positions[persona]
                        stop = min(start + 500, len(release[persona]['sessions']))
                        for i in range(start, stop):
                            runner._execute('ingestion', persona, release[persona]['sessions'][i])
                            if (i + 1) % 100 == 0:
                                print(json.dumps({'phase': 'ingestion', 'persona': persona,
                                    'completed': i + 1, 'total': len(release[persona]['sessions'])}), flush=True)
                        return stop
                    futures = {p: pool.submit(ingest_batch, p) for p in release
                               if positions[p] < len(release[p]['sessions'])}
                    for persona, future in futures.items():
                        positions[persona] = future.result()
                    progress = root / 'costs' / f'progress-{sum(positions.values()):06d}.json'
                    if not progress.exists():
                        save_new(progress, {'phase': 'ingestion', 'completed': positions.copy(), 'agent_api_charge_usd': 0})
                    adapter.archive()
            for persona in release:
                save(root / 'checkpoints' / f'{persona}.json', adapter.freeze(persona))
            runner._collect_cost('ingestion')
            adapter.archive()
            judge = Gateway(key=load_key(args.env_file), output=root / 'judge-calls',
                ledger_path=adapter.ledger, campaign_identity=identity, cap_usd=identity['cap_usd'],
                phase='judge', model='openai/gpt-5.6-sol', input_per_million=5,
                output_per_million=30, output_token_cap=8000).start()
            try:
                for persona in release:
                    adapter.verify_checkpoint(persona, json.loads((root / 'checkpoints' / f'{persona}.json').read_text()))
                runner._saved_cost('ingestion')
                with openrouter_judge(judge):
                    for persona, data in release.items():
                        for spec in data['tests']:
                            evidence = runner._execute('tests', persona, spec)
                            grade_path = runner._path('grades', persona, str(spec['id']).zfill(3))
                            if grade_path.exists():
                                grade = json.loads(grade_path.read_text())
                            else:
                                grade = runner._grade(spec, evidence)
                                save(grade_path, grade)
                            adapter.verify_checkpoint(persona, json.loads((root / 'checkpoints' / f'{persona}.json').read_text()))
                            book = BudgetLedger(adapter.ledger, cap_usd=identity['cap_usd'], identity=identity)
                            try:
                                totals = book.totals()
                            finally:
                                book.close()
                            print(json.dumps({'phase': 'tests', 'persona': persona, 'id': spec['id'],
                                'passed': all(check['passed'] for check in grade['checks']),
                                'budget': totals}), flush=True)
                            if int(spec['id']) % 10 == 0:
                                adapter.archive()
                runner._collect_cost('tests')
            finally:
                judge.stop()
            # The upstream packager replays recorded judge calls and validates
            # complete release coverage. Never hand-assemble or silently patch it.
            package = runner.package(root / 'submission.zip')
            grades = [json.loads(p.read_text()) for p in (root / 'grades').glob('*/*.json')]
            passed = sum(all(check['passed'] for check in g['checks']) for g in grades)
            save_new(root / 'private-result.json', {'tasks': len(grades), 'passed': passed,
                'package_validation': package, 'transport_acceptance': 'unconfirmed',
                'historical_reference': {'atmem': '9/30', 'mem0_oss': '7/30'},
                'matched_mem0_rerun': False, 'campaign_identity': identity})
            adapter.archive()
            print(json.dumps({'completed': len(grades), 'passed': passed, 'package': package}), flush=True)
    except BaseException as exc:
        save_new(root / f'controller-error-{time.time_ns()}.json',
            {'error_type': type(exc).__name__, 'detail': str(exc)[:500], 'evidence_preserved': True})
        if adapter is not None:
            adapter.archive()
        raise
    finally:
        if adapter is not None:
            adapter.stop()
        process.terminate()
        try:
            process.wait(30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()


if __name__ == '__main__':
    main()
