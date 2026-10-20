"""Private resumable DolphinBench campaign, with an explicit US$250 hard ceiling.

Upstream datasets, ordering, app resets and rubrics are reused. The official
runner's Azure-deployment-only transport gate is not claimed as satisfied:
this private entry point uses an explicitly disclosed OpenRouter adaptation.
"""
import argparse
import json
import os
import time
from pathlib import Path
import sys

from .adapter import AtMemAdapter
from .gateway import Gateway, save_new
from .judge import openrouter_judge
from .recording import BudgetLedger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--confirm-paid-calls', action='store_true')
    parser.add_argument('--pilot-sessions', type=int, default=0,
                        help='Stop after this many chronological ingestion sessions; zero runs the whole campaign')
    parser.add_argument('--record-backup-repair', action='store_true',
                        help='Record this specific controller-only portable-backup repair; preserve completed interactions')
    args = parser.parse_args()
    if not args.confirm_paid_calls:
        parser.error('Execution requires --confirm-paid-calls')
    if args.pilot_sessions < 0:
        parser.error('Pilot limit cannot be negative')
    if args.pilot_sessions == 0:
        parser.error(
            'Full paid execution is blocked: this private adapter has not qualified '
            'the historical V3 formation/retrieval path or official judge transport. '
            'Do not resume preparation stores as a submission run. '
            'Only an explicitly bounded --pilot-sessions diagnostic is available.'
        )
    root = args.output.resolve()
    if not root.is_relative_to(Path('/Volumes/AtMemDolphin')):
        parser.error('Campaign data must stay on the external benchmark workspace')
    if not os.environ.get('ATMEM_HOME', '').startswith('/Volumes/AtMemDolphin/'):
        parser.error('Set an isolated external ATMEM_HOME before importing the product')
    upstream = Path('/Volumes/AtMemDolphin/upstream')
    sys.path.append(str(upstream))
    from harness.submission import read_release
    from harness.runner import Runner, run_lock, digest
    from scripts.openrouter_azure_sol import load_key

    release = read_release(upstream)
    campaign_identity = {'format': 'atmem-dolphin-private-campaign-v1',
        'upstream_commit': '81cb6f8405b40a9e76089cef650806a80af06ea2',
        'corpus_digest': digest(release), 'cap_usd': 249.90,
        'total_user_ceiling_usd': 250,
        'prior_pilot_and_setup_reserved_allowance_usd': 0.10,
        'prior_pilot_ledger': '/Volumes/AtMemDolphin/campaign-atmem-239/budget.db',
        'prior_pilot_actual_plus_uncertain_upper_bound_usd': 0.051654,
        'prior_qualified_pilot_ledger': '/Volumes/AtMemDolphin/campaign-atmem-239-qualified/budget.db',
        'prior_host_background_review_trial_ledger': '/Volumes/AtMemDolphin/campaign-atmem-239-full/budget.db',
        'session_title_model_upgrade': False,
        'host_background_skill_review': False,
        'agent': {'model': 'openai/gpt-5.6-luna', 'reasoning': 'medium', 'output_cap': 4096, 'max_turns': 20},
        'judge': {'model': 'openai/gpt-5.6-sol', 'reasoning': 'medium', 'output_cap': 8000},
        'transport': 'OpenRouter Azure-only, fallback disabled',
        'official_transport_acceptance': 'unconfirmed',
        'atmem': {'base_version': '2.3.9', 'base_commit': 'a50659256ac14caae0f60cbdb98e534d4e7df1d0',
            'patch': 'product-owned monotonic Hermes memory freeze',
            'wheel_sha256': 'bc9a2e0e678b1b99caf9ef7b5c8c60db64f820b3bed527a3a7198d525ac25c51'},
        'fresh_profile_per_interaction': True,
        'persistent_memory': 'AtMem only; no cross-interaction native session-search history'}
    with run_lock(root):
        adapter = AtMemAdapter({'campaign_identity': campaign_identity, 'env_file': str(args.env_file)}, root)
        try:
            if args.record_backup_repair:
                path = root / 'run.json'
                previous = json.loads(path.read_text())
                current = adapter.identity()
                old_identity = previous['configuration']
                if {k: v for k, v in old_identity.items() if k != 'adapter_source'} != {k: v for k, v in current.items() if k != 'adapter_source'}:
                    raise ValueError('Backup repair cannot alter runtime, product, model, corpus or budget configuration')
                changed = {name for name in set(current['adapter_source']) | set(old_identity['adapter_source'])
                           if current['adapter_source'].get(name) != old_identity['adapter_source'].get(name)}
                if changed != {'campaign.py', 'driver.py', 'archive.py'}:
                    raise ValueError('Unexpected source changes; this narrow backup repair is not applicable')
                stamp = str(time.time_ns())
                repair = root / 'repairs' / stamp
                save_new(repair / 'previous-run.json', previous)
                save_new(repair / 'repair.json', {'reason': 'Portable export tenant resolved from admin principal, not tenant-less AuthorityScope; preserve and archive this controller repair record',
                    'changed_modules': sorted(changed), 'old_identity': old_identity, 'new_identity': current,
                    'replayed_model_calls': 0, 'product_or_semantic_changes': False})
                from .driver import private_json
                private_json(path, {**previous, 'configuration': current})
            runner = Runner(release, root, adapter, identity=adapter.identity(),
                            release_root=upstream, allow_paid=False)
            # This entry point deliberately does not impersonate an upstream
            # qualified Azure deployment. Only the private grader below is paid.
            runner.allow_paid = True
            completed = 0
            for persona, data in release.items():
                checkpoint = root / 'checkpoints' / f'{persona}.json'
                if checkpoint.exists():
                    adapter.verify_checkpoint(persona, json.loads(checkpoint.read_text()))
                    continue
                for spec in data['sessions']:
                    result = runner._execute('ingestion', persona, spec)
                    completed += 1
                    print(json.dumps({'phase': 'ingestion', 'persona': persona, 'session': spec['id'],
                        'completed_this_invocation': completed,
                        'phase_cost_usd': adapter.total_cost_usd('ingestion')}), flush=True)
                    if completed % 25 == 0:
                        adapter.archive()
                    if args.pilot_sessions and completed >= args.pilot_sessions:
                        adapter.archive()
                        print(json.dumps({'pilot_complete': True, 'graded_tasks': 0,
                            'resume': 'same command without --pilot-sessions; completed interactions will not be replayed'}), flush=True)
                        return
                save_new(checkpoint, adapter.freeze(persona))
                adapter.archive()
            runner._collect_cost('ingestion')
            judge = Gateway(key=load_key(args.env_file), output=root / 'judge-calls', ledger_path=adapter.ledger,
                campaign_identity=campaign_identity, cap_usd=campaign_identity['cap_usd'], phase='judge', model='openai/gpt-5.6-sol',
                input_per_million=5, output_per_million=30, output_token_cap=8000).start()
            try:
                with openrouter_judge(judge):
                    runner.evaluate()
            finally:
                judge.stop()
            # Do not create an "official" submission ZIP whose replay validator
            # requires the direct Azure transport. Preserve full private records.
            grades = [json.loads(p.read_text()) for p in (root / 'grades').glob('*/*.json')]
            passed = sum(bool(g['checks']) and all(c['passed'] for c in g['checks']) for g in grades)
            save_new(root / 'private-result.json', {'completed_tasks': len(grades), 'passed_tasks': passed,
                'official_submission': False, 'transport_acceptance': 'unconfirmed',
                'campaign_identity': campaign_identity})
            adapter.archive()
            print(json.dumps({'completed_tasks': len(grades), 'passed_tasks': passed}), flush=True)
        finally:
            adapter.stop()


if __name__ == '__main__':
    main()
