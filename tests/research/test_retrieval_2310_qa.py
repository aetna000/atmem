from research.retrieval_2310.qa_run import full_history, reader_request


def test_reader_request_has_no_grader_or_paid_fallback_parameters():
    result = reader_request('fixture question', 'authorized fixture context', ['A', 'B'])
    assert result['model'] == 'openai/gpt-5.6-luna'
    assert result['reasoning_effort'] == 'high'
    assert set(result) == {'model', 'reasoning_effort', 'messages', 'stream'}
    assert result['messages'][0]['content'].endswith('Question: fixture question\nAnswer:\n')


def test_published_history_formatter_keeps_dates_and_original_turn_order():
    context = full_history({'session_1_date_time': '2024-01-01',
        'session_1': [{'speaker': 'A', 'clean_text': 'first'}, {'speaker': 'B', 'clean_text': 'second'}],
        'session_2_date_time': '2024-01-02', 'session_2': [{'speaker': 'A', 'clean_text': 'later'}]})
    assert context.index('2024-01-02') < context.index('2024-01-01')
    assert context.index('first') < context.index('second')
