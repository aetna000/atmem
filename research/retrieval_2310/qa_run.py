"""Subscription-only development QA reader comparison, not DolphinBench scores.

Uses the existing recorded Hermes OAuth transport. No paid API fallback, no
grader calls, no answer keys in reader requests, and no memory mutation.
Independent grading is a separate stage; ungraded output proves no efficacy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import secrets
import subprocess
import time
import urllib.request

from benchmarks.dolphinbench.gateway import save_new
from .protocol import digest

QA_PROMPT = '''Based on the above context, write an answer in the form of a short phrase for the following question.
If the question is about a date, try to infer the approximate date (e.g., "In the 1800s", "Before Jan 2021", etc.).

Question: {}
Answer:
'''


def reader_request(question: str, context: str, speakers: list[str]) -> dict:
    start = ('Below is a conversation between two people: {} and {}. The conversation takes place over multiple days '
             'and the date of each conversation is written at the beginning of the conversation.\n\n').format(*speakers)
    return {'model': 'openai/gpt-5.6-luna', 'reasoning_effort': 'high',
            'messages': [{'role': 'user', 'content': start+context+'\n\n'+QA_PROMPT.format(question)}],
            'stream': False}


def full_history(data: dict) -> str:
    # Uses published ordering (newest session first, original turn order within
    # session). Strict session-key matching avoids counting events_session_N as
    # a second copy of session_N. No generated event summaries enter the reader.
    context = ''
    sessions = sorted(int(k.split('_')[1]) for k in data if re.fullmatch(r'session_\d+', k))
    for i in sessions:
        turns = []
        for turn in data[f'session_{i}']:
            text = f'{turn["speaker"]} said, "{turn.get("clean_text", turn.get("text", ""))}"'
            if 'blip_caption' in turn:
                text += f'\n{turn["speaker"]} shared, an image of "{turn["blip_caption"]}".'
            turns.append(text+'\n')
        context = f'DATE: {data[f"session_{i}_date_time"]}\nCONVERSATION:\n'+''.join(turns)+'\n'+context
    return context


def run(source: Path, baseline: Path, candidate: Path, output: Path) -> None:
    output = output.resolve()
    output.relative_to(Path('/Volumes/AtMemDolphin'))
    if source.name != 'Chat_1_Emi_Elise.json' or output.exists():
        raise ValueError('inspected development conversation and a new output directory required')
    data = json.loads(source.read_text())
    base = json.loads((baseline/'manifest.json').read_text())
    cand = json.loads((candidate/'manifest.json').read_text())
    if (base['corpus_sha256'] != hashlib.sha256(source.read_bytes()).hexdigest()
            or base['corpus_sha256'] != cand['corpus_sha256']
            or base['selected_qa_indices'] != cand['selected_qa_indices']):
        raise ValueError('paired source/question identities differ')
    speakers = list(dict.fromkeys(turn['speaker'] for turn in data['session_1']))
    if len(speakers) != 2:
        raise ValueError('expected two published conversation participants')
    contexts = {}
    for arm, directory in [('unchanged_v3', baseline), ('semantic_exact', candidate)]:
        for qid in base['selected_qa_indices']:
            ruling = json.loads((directory/f'question-{qid}.json').read_text())
            contexts[(arm, qid)] = ruling.get('context', '') if ruling.get('reason') == 'authorized' else ''
    for qid in base['selected_qa_indices']:
        contexts[('full_history_control', qid)] = full_history(data)
    cases = sorted(contexts)
    random.Random(2310).shuffle(cases)
    output.mkdir(parents=True, mode=0o700)
    manifest = {'mode': 'development-qa-reader-not-tool-action-benchmark',
                'source_sha256': base['corpus_sha256'], 'qa_indices': base['selected_qa_indices'],
                'baseline': str(baseline), 'candidate': str(candidate), 'cases': cases,
                'reader': 'gpt-5.6-luna', 'reasoning': 'high', 'authentication': 'existing-Hermes-ChatGPT-subscription',
                'paid_fallback': False, 'expected_answer_in_reader_request': False,
                'full_history_control_not_matched_context_budget': True,
                'full_history_format': 'published-order-unique-sessions-no-event-summaries',
                'judge': 'not-run; independent grading required', 'ready_for_600': False,
                'source_file_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save_new(output/'manifest.json', manifest)
    token = secrets.token_urlsafe(32)
    listener = output/'transport/listener.json'
    env = {**os.environ, 'ATMEM_SUBSCRIPTION_PROXY_TOKEN': token,
           'HERMES_HOME': '/Users/javadtaghia/.hermes', 'PYTHONDONTWRITEBYTECODE': '1'}
    service = Path(__file__).resolve().parents[2]/'benchmarks/dolphinbench/subscription_service.py'
    with (output/'subscription.log').open('x') as log:
        process = subprocess.Popen([
            '/Users/javadtaghia/.hermes/tools/python-3.14.7+20260901-darwin-arm64/bin/python3.14',
            '-I', str(service), '--output', str(output/'transport'), '--listener-file', str(listener),
            '--reasoning-effort', 'high', '--max-transport-attempts', '1'],
            cwd='/Volumes/AtMemDolphin/tmp', env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError('subscription route unavailable; no API fallback')
                if listener.exists():
                    break
                time.sleep(.25)
            else:
                raise RuntimeError('subscription startup deadline exceeded')
            endpoint = json.loads(listener.read_text())['endpoint']
            for number, (arm, qid) in enumerate(cases, 1):
                body = reader_request(data['qa'][qid]['question'], contexts[(arm,qid)], speakers)
                started = time.monotonic()
                request = urllib.request.Request(endpoint, json.dumps(body).encode(),
                    headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+token})
                response = None
                error = None
                try:
                    with urllib.request.urlopen(request, timeout=220) as incoming:
                        response = json.load(incoming)
                except Exception as exc:
                    error = {'type': type(exc).__name__, 'usage': None, 'paid_fallback': False}
                save_new(output/'results'/f'{arm}-{qid}.json', {
                    'arm': arm, 'qa_index': qid, 'reader_request_sha256': digest(body),
                    'response': response, 'error': error,
                    'duration_ms': (time.monotonic()-started)*1000,
                    'judged': False})
                print(json.dumps({'completed': number, 'total': len(cases), 'arm': arm,
                                  'reader_error': error is not None}), flush=True)
                if error:
                    # Stop on transport failure; preserve partial evidence and
                    # untouched cases rather than consume quota on a broken route.
                    raise RuntimeError('reader transport failed; partial evidence retained')
            save_new(output/'reader-complete.json', {'cases': len(cases), 'graded': False, 'ready_for_600': False})
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'baseline', 'candidate', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    run(args.source, args.baseline, args.candidate, args.output)


if __name__ == '__main__':
    main()
