import json

import pytest

from atmem import facts_stdio, standing_facts as sf

BATCH = [{'session': 's1', 'text': '[2023-01-31] keep fridays light. no vendor calls on fridays unless it is a real emergency.'},
         {'session': 's2', 'text': '[2023-05-02] when I say brunch I mean Salud, the taco place by the park.'}]


def test_only_facts_with_verbatim_source_quotes_are_kept():
    proposals = [
        {'fact': 'Morgan avoids vendor calls on Fridays.', 'kind': 'rule', 'as_of': '2023-01-31',
         'quote': 'no vendor calls on fridays unless it is a real   emergency'},
        {'fact': 'Riley means Salud by brunch.', 'kind': 'default', 'as_of': '2023-05-02', 'quote': 'brunch I mean Salud'},
        {'fact': 'Invented fact.', 'kind': 'rule', 'as_of': '2023-01-01', 'quote': 'this sentence never appears'},
        {'fact': '', 'kind': 'rule', 'quote': 'keep fridays light'}, 'junk']
    kept = sf.verify(proposals, BATCH)
    assert [f['session'] for f in kept] == ['s1', 's2']
    assert kept[0]['kind'] == 'rule' and len(kept[0]['source_sha256']) == 64


def test_extract_is_resumable_and_dedupes(tmp_path, monkeypatch):
    calls = []
    def fake_chat(endpoint, token, model, prompt, content, **_):
        calls.append(content)
        return json.dumps({'facts': [{'fact': 'Morgan avoids vendor calls on Fridays.', 'kind': 'rule',
                                      'as_of': '2023-01-31', 'quote': 'no vendor calls on fridays'}]})
    monkeypatch.setattr(sf, 'chat', fake_chat)
    journal = tmp_path / 'j.jsonl'
    facts, proposed = sf.extract(BATCH, 'e', 't', 'm', journal=journal, log=lambda *_: None)
    assert len(facts) == 1 and proposed == 1 and len(calls) == 1
    facts_again, _ = sf.extract(BATCH, 'e', 't', 'm', journal=journal, log=lambda *_: None)
    assert len(calls) == 1 and facts_again == facts  # resumed from the journal


def test_profile_keeps_verified_wording_and_size_cap(monkeypatch):
    facts = [{'id': i, 'fact': f'Fact number {i}.', 'kind': 'rule', 'as_of': '2024-01-01', 'quote': 'q', 'session': 's'}
             for i in range(5)]
    monkeypatch.setattr(sf, 'chat', lambda *a, **k: json.dumps({'ids': [3, 1, 99, 'x']}))
    assert sf.select_profile(facts, 'e', 't', 'm') == [3, 1]
    assert sf.select_profile(facts, 'e', 't', 'm', max_chars=30) == [3]
    text = sf.profile_text({'facts': facts, 'profile': [3, 1]})
    assert text.startswith('AtMem standing profile') and '- (2024-01-01) Fact number 3.' in text


def test_search_ranks_relevant_facts_and_server_serves_them():
    store = {'facts': sf.verify([
        {'fact': 'Morgan avoids vendor calls on Fridays unless there is an emergency.', 'kind': 'rule',
         'as_of': '2023-01-31', 'quote': 'no vendor calls on fridays'},
        {'fact': 'Riley means Salud when saying brunch.', 'kind': 'default', 'as_of': '2023-05-02',
         'quote': 'brunch I mean Salud'}], BATCH)}
    for i, f in enumerate(store['facts']):
        f['id'] = i
    assert sf.search(store, 'Friday vendor call')[0]['fact'].startswith('Morgan avoids')
    assert sf.search(store, 'brunch place')[0]['quote'] == 'brunch I mean Salud'
    listed = facts_stdio.handle(store, {'method': 'tools/list'})
    assert listed['tools'][0]['name'] == 'fact_search'
    called = facts_stdio.handle(store, {'method': 'tools/call', 'params': {'name': 'fact_search',
                                                                        'arguments': {'query': 'brunch'}}})
    assert 'Salud' in called['content'][0]['text']
    assert facts_stdio.handle(store, {'method': 'tools/call', 'params': {'name': 'x', 'arguments': {}}})['isError']


def test_verify_store_detects_tampered_quotes(tmp_path):
    ingestion = tmp_path / 'ingestion.json'
    ingestion.write_text(json.dumps({'sessions': [
        {'persona': 'riley', 'session_id': 's2', 'messages': [{'role': 'user', 'content': BATCH[1]['text']}]}]}))
    store = {'persona': 'riley', 'facts': [{'id': 0, 'quote': 'brunch I mean Salud', 'session': 's2'},
                                           {'id': 1, 'quote': 'brunch I mean Lupe', 'session': 's2'}]}
    assert sf.verify_store(store, ingestion) == [1]


def test_malformed_model_json_is_retried_then_skipped(monkeypatch):
    answers = iter(['{"ids": [1, 2,, }', '{"ids": [2]}'])
    monkeypatch.setattr(sf, 'chat', lambda *a, **k: next(answers))
    assert sf.ask_json('e', 't', 'm', 'p', 'c', 'ids') == {'ids': [2]}
    monkeypatch.setattr(sf, 'chat', lambda *a, **k: 'not json')
    assert sf.ask_json('e', 't', 'm', 'p', 'c', 'ids') == {'ids': []}
