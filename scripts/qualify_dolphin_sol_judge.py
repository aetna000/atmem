"""One budgeted Sol-medium judge/record/replay diagnostic; no benchmark cases."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--confirm-paid-call', action='store_true')
    args = parser.parse_args()
    if not args.confirm_paid_call:
        parser.error('A paid diagnostic must be explicitly confirmed')
    root = Path('/Volumes/AtMemDolphin/sol-judge-qualification-20261021')
    root.mkdir(mode=0o700)
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    sys.path.append('/Volumes/AtMemDolphin/upstream')
    from benchmarks.dolphinbench.gateway import Gateway, save_new
    from benchmarks.dolphinbench.judge import openrouter_judge
    from benchmarks.dolphinbench.recording import BudgetLedger
    from scripts.openrouter_azure_sol import load_key
    from graders import llm_judge
    from graders.judge_recording import record_judge, replay_judge
    identity = {'format': 'sol-judge-diagnostic-v1', 'diagnostic_only': True,
        'model': 'gpt-5.6-sol', 'reasoning': 'medium', 'cap_usd': 0.45,
        'included_in_preparation_allowance_usd': 1.0}
    gateway = Gateway(key=load_key(args.env_file), output=root / 'calls',
        ledger_path=root / 'budget.db', campaign_identity=identity, cap_usd=0.45,
        phase='qualification', model='openai/gpt-5.6-sol', input_per_million=5,
        output_per_million=30, output_token_cap=8000).start()
    user = "USER'S TEST MESSAGE: Say ready.\nAGENT'S RESPONSE: Ready.\nCRITERION: The response says ready."
    try:
        with record_judge() as recorded, openrouter_judge(gateway):
            result = llm_judge._call_judge(llm_judge.JUDGE_SYSTEM_PROMPT, user, {})
        if type(result.get('passed')) is not bool:
            raise ValueError('The actual judge verdict is not Boolean')
        with replay_judge(recorded.messages, recorded.settings):
            replayed = llm_judge._call_judge(llm_judge.JUDGE_SYSTEM_PROMPT, user, {})
        if replayed != result:
            raise ValueError('The unmodified upstream judge replay changed the verdict')
        book = BudgetLedger(root / 'budget.db', cap_usd=0.45, identity=identity)
        try:
            totals = book.totals()
        finally:
            book.close()
        save_new(root / 'result.json', {'passed': True, 'diagnostic_only': True,
            'benchmark_cases_used': False, 'judge_settings': recorded.settings,
            'judge_messages': recorded.messages, 'replay_equal': True, 'budget': totals})
        print(json.dumps({'passed': True, 'replay_equal': True, 'budget': totals}), flush=True)
    finally:
        gateway.stop()


if __name__ == '__main__':
    main()
