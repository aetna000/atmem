"""Form source-linked candidate statements from history with source quotes.

A model proposes durable facts (standing rules, preferences, defaults, policies,
commitments, roles, decisions in force) from dated user messages. Every proposed
fact must carry a verbatim quote from the message it came from; a fact whose quote
is not found in that source is dropped, so every stored fact can be traced. This verifies quotation occurrence, not whether a model-generated statement is
entailed by that quotation. Treat all statements as unverified interpretations.

Standard-library-only; the model is any OpenAI-compatible chat endpoint.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import urllib.request
from collections import Counter
from pathlib import Path

FORMAT = 'atmem-standing-facts-v1'
KINDS = ('rule', 'preference', 'default', 'policy', 'commitment', 'relationship', 'decision', 'profile')
EXTRACT_PROMPT = (
    'You are proposing source-linked long-term memory for the person who wrote the dated messages below. '
    'Extract durable facts that should guide future actions taken on their behalf: standing rules and '
    'boundaries, preferences, defaults (for example what a word or request usually means for them), '
    'policies and thresholds, recurring commitments, people and their roles, and decisions that remain '
    'in force. Skip one-off chatter, transient status and details that only mattered for a single day, '
    'unless they set a rule. Each fact must be one self-contained sentence that names the person. '
    'Return only JSON: {"facts": [{"fact": str, "kind": one of ' + json.dumps(list(KINDS)) + ', '
    '"as_of": "YYYY-MM-DD", "quote": str}]} with at most 60 facts. "quote" must be copied exactly, '
    'character for character, from one message (at most 200 characters) and must support the fact.')
SELECT_PROMPT = (
    'Below are unverified source-linked statements about one person, each with an id, date and kind. Choose the statements that '
    'should be in a compact profile loaded before every future task: standing rules, preferences, '
    'defaults, policies, thresholds and commitments that are still in force as of the latest date. '
    'When facts conflict, prefer the most recent. Prefer facts that change how an action should be '
    'done (who, where, when, whether to accept or decline, limits) over background. '
    'Return only JSON: {"ids": [int, ...]} with at most {limit} ids, most important first.')
WORD = re.compile(r"[a-z0-9][a-z0-9'\-]*")
STOP = frozenset('a an and are as at be by for from has have i in is it its me my of on or our that the their '
                 'them they this to was we were will with you your if please check can could would'.split())


def normalize(text):
    return re.sub(r'\s+', ' ', str(text)).strip().lower()


def load_history(ingestion_path, persona):
    """Dated user messages for one persona, in recorded order: [{'session', 'text'}]."""
    sessions = json.loads(Path(ingestion_path).read_text())['sessions']
    return [{'session': s['session_id'], 'text': m['content']}
            for s in sessions if s['persona'] == persona
            for m in s['messages'] if m.get('role') == 'user' and isinstance(m.get('content'), str)]


def chunks(messages, budget=90_000):
    batch, size = [], 0
    for message in messages:
        if batch and size + len(message['text']) > budget:
            yield batch
            batch, size = [], 0
        batch.append(message)
        size += len(message['text'])
    if batch:
        yield batch


def chat(endpoint, token, model, prompt, content, *, attempts=3):
    body = json.dumps({'model': model, 'messages': [{'role': 'system', 'content': prompt},
                                                    {'role': 'user', 'content': content}]}).encode()
    for attempt in range(attempts):
        request = urllib.request.Request(endpoint, data=body, headers={
            'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                return json.loads(response.read())['choices'][0]['message']['content']
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(10 * (attempt + 1))


def parse_json(text):
    """JSON object from a model answer; {} when the answer is not valid JSON."""
    text = text.strip()
    start, end = text.find('{'), text.rfind('}')
    try:
        return json.loads(text[start:end + 1]) if start >= 0 and end > start else {}
    except ValueError:
        return {}


def ask_json(endpoint, token, model, prompt, content, key):
    """Chat and parse; one retry when the answer is not valid JSON with ``key``."""
    for _ in range(2):
        answer = parse_json(chat(endpoint, token, model, prompt, content))
        if isinstance(answer.get(key), list):
            return answer
    return {key: []}


def verify(proposals, batch):
    """Keep proposals whose quote occurs verbatim (whitespace-normalised) in one batch message."""
    sources = [(m, normalize(m['text'])) for m in batch]
    kept = []
    for item in proposals if isinstance(proposals, list) else []:
        if not isinstance(item, dict):
            continue
        fact, quote = str(item.get('fact', '')).strip(), normalize(item.get('quote', ''))
        if not fact or len(quote) < 8 or len(quote) > 400:
            continue
        source = next((m for m, text in sources if quote in text), None)
        if source is None:
            continue
        kept.append({'fact': fact, 'kind': item.get('kind') if item.get('kind') in KINDS else 'profile',
                     'as_of': str(item.get('as_of', ''))[:10], 'quote': str(item.get('quote', '')).strip(),
                     'session': source['session'],
                     'source_sha256': hashlib.sha256(source['text'].encode()).hexdigest()})
    return kept


def extract(messages, endpoint, token, model, *, journal=None, log=print):
    """Propose statements and check quote occurrence; resumable through a JSONL journal."""
    done = {}
    if journal and Path(journal).exists():
        for line in Path(journal).read_text().splitlines():
            row = json.loads(line)
            done[row['chunk']] = row
    facts, proposed = [], 0
    for index, batch in enumerate(chunks(messages)):
        if index in done:
            row = done[index]
        else:
            content = '\n\n'.join(m['text'] for m in batch)
            answer = ask_json(endpoint, token, model, EXTRACT_PROMPT, content, 'facts')
            row = {'chunk': index, 'proposed': len(answer.get('facts', []) or []),
                   'facts': verify(answer.get('facts', []), batch)}
            if journal:
                with open(journal, 'a') as output:
                    output.write(json.dumps(row) + '\n')
        proposed += row['proposed']
        facts.extend(row['facts'])
        log(json.dumps({'chunk': index, 'verified': len(row['facts']), 'proposed': row['proposed']}))
    seen, unique = set(), []
    for fact in facts:
        key = normalize(fact['fact'])
        if key not in seen:
            seen.add(key)
            unique.append(fact)
    for number, fact in enumerate(unique):
        fact['id'] = number
    return unique, proposed


def select_profile(facts, endpoint, token, model, *, limit=45, max_chars=7000, batch_size=350):
    """Model chooses ids only (wording remains unchanged); hierarchical for large sets."""
    def choose(candidates, count):
        listing = '\n'.join(f"{f['id']}\t{f['as_of']}\t{f['kind']}\t{f['fact']}" for f in candidates)
        answer = ask_json(endpoint, token, model, SELECT_PROMPT.replace('{limit}', str(count)), listing, 'ids')
        valid = {f['id'] for f in candidates}
        return [i for i in answer.get('ids', []) if isinstance(i, int) and i in valid]
    pool = [f for f in facts if f['kind'] != 'profile' or True]
    while len(pool) > batch_size:
        shortlisted = []
        for start in range(0, len(pool), batch_size):
            shortlisted.extend(choose(pool[start:start + batch_size], max(limit, 60)))
        by_id = {f['id']: f for f in facts}
        pool = [by_id[i] for i in dict.fromkeys(shortlisted)]
    chosen = choose(pool, limit) if pool else []
    by_id = {f['id']: f for f in facts}
    selected, size = [], 0
    for fact_id in chosen:
        line = f"- ({by_id[fact_id]['as_of']}) {by_id[fact_id]['fact']}"
        if size + len(line) > max_chars:
            break
        selected.append(fact_id)
        size += len(line) + 1
    return selected


def profile_text(store):
    by_id = {f['id']: f for f in store['facts']}
    lines = [f"- ({by_id[i]['as_of']}) {by_id[i]['fact']}" for i in store['profile']]
    return ('AtMem standing profile (source-linked statements from earlier conversations, each traceable to a source '
            'quote; the generated statements are unverified interpretations and can contradict their sources. '
            'Check the source quote and current authority before acting; use fact_search for evidence):\n' + '\n'.join(lines)) if lines else ''


def prefetch_text(store, request, *, limit=12):
    """Source-linked statements matching the request, like a memory prefetch."""
    query = re.sub(r'^\s*\[[^\]]*\]\s*', '', str(request or ''))
    results = search(store, query, limit=limit) if query.strip() else []
    if not results:
        return ''
    return ('Source-linked model-generated statements that may be relevant (quotation occurrence is checked, but meaning is unverified; check the source and whether they '
            'apply before acting):\n' + '\n'.join(f"- ({r['as_of']}) {r['fact']}" for r in results))


def build(ingestion_path, persona, endpoint, token, model, output, *, log=print):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    messages = load_history(ingestion_path, persona)
    facts, proposed = extract(messages, endpoint, token, model, journal=output.with_suffix('.journal.jsonl'), log=log)
    profile = select_profile(facts, endpoint, token, model)
    store = {'format': FORMAT, 'persona': persona, 'model': model, 'messages': len(messages),
             'proposed': proposed, 'verified': len(facts), 'facts': facts, 'profile': profile,
             'source_sha256': hashlib.sha256(Path(ingestion_path).read_bytes()).hexdigest()}
    output.write_text(json.dumps(store, indent=1, ensure_ascii=False))
    return store


def verify_store(store, ingestion_path):
    """Re-check every stored quote against the original history; returns the failures."""
    persona = store['persona']
    texts = {}
    for message in load_history(ingestion_path, persona):
        texts.setdefault(message['session'], []).append(normalize(message['text']))
    return [f['id'] for f in store['facts']
            if not any(normalize(f['quote']) in text for text in texts.get(f['session'], []))]


def stem(word):
    """Light plural/possessive folding so 'Fridays' matches 'Friday' and 'calls' matches 'call'."""
    word = word.removesuffix("'s").removesuffix("’s")
    if len(word) > 4 and word.endswith('ies'):
        return word[:-3] + 'y'
    if len(word) > 3 and word.endswith('s') and not word.endswith('ss'):
        return word[:-1]
    return word


def terms_of(text):
    # Clock times and bare numbers ("11", "12:30", "2028") match unrelated schedules.
    return [stem(w) for w in WORD.findall(normalize(text))
            if w not in STOP and len(w) > 1 and not re.fullmatch(r"[\d.:'\-]+", w)]


def search(store, query, *, limit=8):
    """BM25 over fact text and quote; returns facts with date, quote and source session."""
    documents = [Counter(terms_of(f['fact'] + ' ' + f['quote'])) for f in store['facts']]
    terms = terms_of(query)
    if not documents or not terms:
        return []
    average = sum(sum(d.values()) for d in documents) / len(documents)
    frequency = Counter(t for d in documents for t in set(d))
    scored = []
    for fact, document in zip(store['facts'], documents):
        length = sum(document.values())
        score = sum(math.log(1 + (len(documents) - frequency[t] + .5) / (frequency[t] + .5))
                    * document[t] * 2.2 / (document[t] + 1.2 * (.25 + .75 * length / average))
                    for t in terms if document[t])
        if score:
            scored.append((score, fact))
    scored.sort(key=lambda pair: -pair[0])
    return [{'fact': f['fact'], 'as_of': f['as_of'], 'kind': f['kind'], 'quote': f['quote'], 'session': f['session']}
            for _, f in scored[:limit]]


def main():
    import argparse
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ingestion', type=Path, required=True)
    parser.add_argument('--persona', required=True)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--model', default='openai/gpt-5.6-luna')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    store = build(args.ingestion, args.persona, args.endpoint, os.environ['ATMEM_FORMATION_TOKEN'], args.model,
                  args.output)
    print(json.dumps({k: store[k] for k in ('persona', 'messages', 'proposed', 'verified')} |
                     {'profile_facts': len(store['profile'])}))


if __name__ == '__main__':
    main()
