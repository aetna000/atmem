"""Recorded, arm-blind grading of the completed development reader experiment.

Separate from formal pillar acceptance: no product code is invoked, no reader
answer is regenerated, and no confirmation data is opened. Requires a fresh
scoped review receipt. All paid requests pass the existing durable budget guard.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import time
import urllib.request

from benchmarks.dolphinbench.gateway import Gateway, save_new
from benchmarks.dolphinbench.recording import BudgetLedger
from scripts.openrouter_azure_sol import load_key
from .evaluate import Outcome, paired_summary
from .grading import RUBRIC, RUBRIC_VERSION, judge_request, parse_verdict
from .preflight import Review, inventory, validate_review
from .protocol import CampaignLedger, digest
from .qa_run import full_history
from .reader_report import summarize

REQUIRED_SPECS = {'specs/046-retrieval-performance-2310/spec.md',
                  'specs/046-retrieval-performance-2310/plan.md',
                  'specs/040-atmem-context-engine/spec.md'}
CAP = '35'
CONTROL_VERSION = 'source-verified-utterance-controls-v2'


def configuration(source: Path, reader: Path) -> dict:
    report = summarize(reader)
    if (not report['all_cases_attempted'] or not report['reader_complete_marker_present']
            or report['attempted_cases'] != 90
            or any(a['transport_errors'] or a['cases_with_unknown_token_usage']
                   for a in report['arms'].values())):
        raise ValueError('complete recorded 90-case subscription development run required')
    if source.name != 'Chat_1_Emi_Elise.json':
        raise ValueError('only the already-inspected development conversation is eligible')
    data_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = json.loads((reader/'manifest.json').read_text())
    if data_hash != manifest['source_sha256']:
        raise ValueError('reader source identity changed')
    return {'stage': 'development-grader-qualification', 'rubric': RUBRIC_VERSION,
            'rubric_sha256': hashlib.sha256(RUBRIC.encode()).hexdigest(),
            'source_sha256': data_hash, 'reader_manifest_sha256': report['manifest_sha256'],
            'reader_results': report['result_sha256'], 'questions': manifest['qa_indices'],
            'model': 'openai/gpt-5.6-sol', 'reasoning': 'medium', 'provider': 'Azure',
            'maximum_calls': 96, 'request_retries': 0, 'cap_usd': CAP,
            'max_completion_tokens': 8000, 'input_price_ceiling_per_million': 5,
            'output_price_ceiling_per_million': 30, 'controls_required': 6,
            'control_version': CONTROL_VERSION,
            'primary_metric': 'fully-correct-binary-all-30-original-questions',
            'reference_issues_remain_in_denominator': True,
            'single_conversation_descriptive_only': True,
            'formal_acceptance_authorized': False, 'ready_for_600': False}


def controls(data: dict) -> list[dict]:
    # Hand-authored calibration questions about exact released utterances, NOT
    # benchmark tasks, fabricated conversations, model training or quality data.
    # V1 incorrectly assumed two published answer keys were valid. Retain that
    # failed suite; V2 verifies its sources before any scored reader grading.
    turns = {turn['dia_id']: turn for turn in data['session_1']}
    probes = [
        ('D1:29', 'I study at NYU', 'NYU', 'Stanford University',
         'In the opening conversation, which university does speaker Emi say they study at?'),
        ('D1:32', "I'm Kate", 'Kate', 'Mona',
         'In the opening conversation, what name does speaker Emi use to introduce themself?'),
        ('D1:28', 'majoring in Economics', 'Economics', 'Physics',
         'In the opening conversation, what subject does speaker elise say they are majoring in?'),
    ]
    result = []
    for number, (turn_id, required, answer, wrong, question) in enumerate(probes):
        if required not in turns[turn_id]['clean_text']:
            raise ValueError('grader calibration source changed')
        for correct in (True, False):
            result.append({'id': f'utterance-{number}-'+('positive' if correct else 'negative'),
                           'source_turn_id': turn_id, 'question': question, 'reference': answer,
                           'prediction': answer if correct else wrong, 'expected': correct})
    random.Random(2310).shuffle(result)
    return result


def claim_budget(ledger_path: Path, name: str, *, cap_usd: str = CAP) -> None:
    from .protocol import microdollars
    bound = microdollars(cap_usd)
    if not 0 < bound <= 35_000_000:
        raise ValueError('child allocation outside confidence limits')
    ledger = CampaignLedger(ledger_path)
    try:
        ledger.db.execute('''CREATE TABLE IF NOT EXISTS grading_children(
            name TEXT PRIMARY KEY, state TEXT NOT NULL, amount INTEGER NOT NULL)''')
        ledger.db.execute('BEGIN IMMEDIATE')
        phase = ledger.db.execute("SELECT state,amount FROM entries WHERE id='confidence-and-judging'").fetchone()
        final = ledger.db.execute("SELECT state,amount FROM entries WHERE id='final-600-and-comparator'").fetchone()
        exposure = ledger.db.execute('SELECT COALESCE(SUM(amount),0) FROM grading_children').fetchone()[0]
        if (phase != ('reserved', 40_000_000) or final != ('reserved', 200_000_000)
                or exposure+bound > phase[1]):
            raise ValueError('grading allocation unavailable, including prior/uncertain children')
        ledger.db.execute("INSERT INTO grading_children VALUES(?,'reserved',?)", (name,bound))
        ledger.db.execute('COMMIT')
    finally:
        if ledger.db.in_transaction:
            ledger.db.execute('ROLLBACK')
        ledger.close()


def settle_budget(ledger_path: Path, name: str, exposure_micro_usd: int) -> None:
    ledger = CampaignLedger(ledger_path)
    try:
        # Retain actual/unknown exposure, never release a sent/uncertain call.
        cursor = ledger.db.execute("UPDATE grading_children SET state='accounted',amount=? WHERE name=? AND state='reserved'",
                                   (exposure_micro_usd, name))
        if cursor.rowcount != 1:
            raise ValueError('missing child allocation; reconcile before further calls')
    finally:
        ledger.close()


def call_judge(gateway, body: dict) -> dict:
    body = dict(body)
    # Gateway supplies its stricter Azure-only route and price ceilings. Do not
    # send a weaker caller override or silently switch providers.
    if body.pop('provider') != {'only': ['Azure'], 'allow_fallbacks': False}:
        raise ValueError('unexpected evaluator provider policy')
    body['response_format'] = {'type': 'json_object'}
    request = urllib.request.Request(gateway.base_url+'/chat/completions',
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json',
        'Authorization': 'Bearer '+gateway.local_token})
    with urllib.request.urlopen(request, timeout=320) as response:
        raw = json.load(response)
    if raw['choices'][0].get('finish_reason') != 'stop':
        raise ValueError('incomplete grader response; no completed-verdict retry')
    return {'verdict': parse_verdict(raw['choices'][0]['message']['content']),
            'usage': raw['usage'], 'response_id': raw['id'], 'request_sha256': digest(body)}


def run(source: Path, reader: Path, output: Path, review_path: Path,
        env_file: Path, campaign_ledger: Path) -> None:
    output = output.resolve()
    output.relative_to(Path('/Volumes/AtMemDolphin'))
    if output.exists():
        raise ValueError('new grader directory required; never reroll completed judgments')
    config = configuration(source, reader)
    review = Review(**json.loads(review_path.read_text()))
    root = Path(__file__).resolve().parents[2]
    validate_review(root, config, review, stage=config['stage'], required_specs=REQUIRED_SPECS)
    claim_budget(campaign_ledger, output.name)
    data = json.loads(source.read_text())
    history = full_history(data)
    output.mkdir(parents=True, mode=0o700)
    save_new(output/'manifest.json', config)
    save_new(output/'review.json', asdict(review))
    identity = {'stage': config['stage'], 'config_digest': digest(config)}
    gateway = Gateway(key=load_key(env_file), output=output/'calls',
        ledger_path=output/'budget.db', campaign_identity=identity,
        cap_usd=CAP, phase='judge', model=config['model'],
        input_per_million=5, output_per_million=30, output_token_cap=8000).start()
    try:
        qualified = []
        for control in controls(data):
            result = call_judge(gateway, judge_request(question=control['question'], reference=control['reference'],
                                prediction=control['prediction'], history=history))
            valid = result['verdict']['passed'] == control['expected'] and not result['verdict']['reference_issue']
            save_new(output/'controls'/f'{control["id"]}.json', {**control, **result, 'control_correct': valid})
            qualified.append(valid)
            print(json.dumps({'stage': 'grader-controls', 'completed': len(qualified),
                              'total': 6, 'control_correct': valid}), flush=True)
        if not all(qualified):
            raise ValueError('grader controls failed; retain evidence and do not grade reader answers')
        save_new(output/'grader-qualified.json', {'controls_correct': 6, 'total': 6})
        cases = list(config['reader_results'])
        random.Random(2311).shuffle(cases)
        outcomes = {}
        for number, name in enumerate(cases, 1):
            path = reader/'results'/name
            if hashlib.sha256(path.read_bytes()).hexdigest() != config['reader_results'][name]:
                raise ValueError('reader output changed after grader review')
            record = json.loads(path.read_text())
            qa = data['qa'][record['qa_index']]
            prediction = record['response']['choices'][0]['message']['content']
            started = time.monotonic()
            result = call_judge(gateway, judge_request(question=qa['question'], reference=qa['answer'],
                                                     prediction=prediction, history=history))
            # Arm identifiers are used only here in the retained local receipt;
            # judge_request has no arm/system name and receives no retrieval score.
            save_new(output/'grades'/name, {**result, 'arm': record['arm'], 'qa_index': record['qa_index'],
                     'reader_result_sha256': config['reader_results'][name],
                     'grader_duration_ms': (time.monotonic()-started)*1000})
            usage = record['response']['usage']
            outcomes.setdefault(record['arm'], []).append(Outcome(
                str(record['qa_index']), 'REALTALK-Chat1-connected-component', result['verdict']['passed'],
                record['duration_ms'], usage['prompt_tokens'], usage['completion_tokens']))
            print(json.dumps({'stage': 'reader-grading', 'completed': number, 'total': 90}), flush=True)
        report = {'mode': 'inspected-development-QA-not-DolphinBench', 'ready_for_600': False,
                  'independent_grader_model': config['model'], 'strict_protocol_adaptation': True,
                  'semantic_vs_unchanged': paired_summary(outcomes['unchanged_v3'], outcomes['semantic_exact']),
                  'full_history_vs_unchanged': paired_summary(outcomes['unchanged_v3'], outcomes['full_history_control'])}
        save_new(output/'comparison.json', report)
    finally:
        gateway.stop()
        book = BudgetLedger(output/'budget.db', cap_usd=CAP, identity=identity)
        try:
            save_new(output/'costs.json', book.totals())
            exposure = book.connection.execute("SELECT COALESCE(SUM(CASE WHEN state IN ('completed','overrun') THEN actual WHEN state='reserved' THEN reserved ELSE 0 END),0) FROM calls").fetchone()[0]
            settle_budget(campaign_ledger, output.name, exposure)
        finally:
            book.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'reader', 'output', 'review', 'env_file', 'campaign_ledger'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    run(args.source, args.reader, args.output, args.review, args.env_file, args.campaign_ledger)


if __name__ == '__main__':
    main()
