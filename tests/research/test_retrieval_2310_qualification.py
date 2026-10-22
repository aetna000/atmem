"""Minimal parser/security fixtures only, not scored conversation data."""
import json

import pytest

from research.retrieval_2310.qualify import expand_reference, qualify_realtalk, qualify_rhelm


def save(path, value, jsonl=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + ('\n' if jsonl else ''))


def test_realtalk_ref_resolution_and_missing_evidence(tmp_path):
    save(tmp_path/'data/Chat_1_A_B.json', {
        'session_1': [{'dia_id': 'D1:1', 'clean_text': 'fixture'}],
        'qa': [
            {'question': 'fixture', 'answer': 'fixture', 'evidence': ['D1:1']},
            {'question': 'fixture', 'answer': 'fixture', 'evidence': []},
            {'question': 'fixture', 'answer': 'fixture', 'evidence': ['D1:2']},
        ]})
    result = qualify_realtalk(tmp_path)
    assert result['counts'] == {'total': 3, 'references_resolved': 1,
                                'missing_evidence': 1, 'unresolved_evidence': 1}
    assert result['dispatch_qualified'] is False
    assert 'question' not in json.dumps(result)


def test_realtalk_duplicate_source_ids_are_not_silently_replaced(tmp_path):
    save(tmp_path/'data/Chat_1_A_B.json', {
        'session_1': [{'dia_id': 'D1:1'}, {'dia_id': 'D1:1'}], 'qa': []})
    with pytest.raises(ValueError, match='duplicate'):
        qualify_realtalk(tmp_path)


def test_rhelm_future_and_unresolved_evidence(tmp_path):
    save(tmp_path/'data/conversations/Person/session.json', {
        'date': '2024-01-02', 'conversation': [{'turn': 1}]})
    qa = {'id': 'q', 'question': 'fixture', 'answer': 'fixture',
          'question_date': '2024-01-01', 'supporting_evidence': ['2024-01-02:1']}
    save(tmp_path/'data/QA_final/low_score_qa_Person_all_validated.jsonl', qa, True)
    (tmp_path/'data/QA_final/._low_score_qa_Person_all_validated.jsonl').write_bytes(b'\x00\xb0')
    (tmp_path/'data/conversations/Person/._session.json').write_bytes(b'\x00\xb0')
    result = qualify_rhelm(tmp_path)
    assert result['counts']['future_evidence'] == 1
    assert result['dispatch_qualified'] is False


def test_empty_corpus_refused(tmp_path):
    with pytest.raises(ValueError, match='no REALTALK'):
        qualify_realtalk(tmp_path)
    with pytest.raises(ValueError, match='no RHELM'):
        qualify_rhelm(tmp_path)


def test_explicit_reference_lists_ranges_and_punctuation_not_inferred_sessions():
    assert expand_reference('D5:12;D5:16.') == ('D5:12', 'D5:16')
    assert expand_reference('D12:3-D12:5') == ('D12:3', 'D12:4', 'D12:5')
    assert expand_reference('2024-05-28:9,2024-05-28:10') == ('2024-05-28:9', '2024-05-28:10')
    assert expand_reference('D:56') == ('D:56',)
    with pytest.raises(ValueError, match='ambiguous'):
        expand_reference('D1:1-D2:3')
