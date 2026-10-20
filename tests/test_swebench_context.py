from hashlib import sha256
import json

import pytest

from benchmarks.code_replay.swebench_context import context_request, validated_context, prompt_context


def response(content='def implementation(): pass\n', **changes):
    pack = {'format': 'atmem-code-source-pack-v1', 'status': 'current',
            'snapshot_id': 'frozen-public-source', 'content': content,
            'content_sha256': sha256(content.encode()).hexdigest(), **changes}
    return {'result': {'content': [{'type': 'text', 'text': json.dumps(pack)}]}}


def test_automatic_query_is_bounded_without_corrupting_multilingual_text():
    request = context_request('结构检索' * 1000)
    query = request['params']['arguments']['query']
    assert len(query.encode()) <= 1000 and '\ufffd' not in query
    assert request['params']['arguments']['budget'] == 4096


def test_full_query_preserves_late_references_and_multibyte_text_without_clipping():
    problem = '结构检索 ' * 100 + '\nImportantLateReference.fix()'
    assert len(problem.encode()) > 1000
    request = context_request(problem, full_query=True)
    assert request['params']['arguments']['query'] == problem
    assert request['params']['arguments']['budget'] == 4096
    assert 'ImportantLateReference' not in context_request(problem)['params']['arguments']['query']
    with pytest.raises(ValueError, match='no silent truncation'):
        context_request('界' * 1334, full_query=True)
    assert len(context_request('a' * 4000, full_query=True)['params']['arguments']['query']) == 4000
    with pytest.raises(ValueError, match='explicit'):
        context_request('text', full_query=1)


def test_only_current_integrity_checked_product_pack_reaches_prompt():
    pack = validated_context(response())
    prompt = prompt_context(pack)
    assert pack['content_sha256'] in prompt and 'untrusted' in prompt
    assert 'def implementation' in prompt
    assert validated_context(response(status='not_current')) is None
    assert validated_context(response('')) is None
    assert validated_context({'error': {'message': 'failure'}}) is None
    assert prompt_context(None) == ''
    for reply in [response(content_sha256='wrong'), response(snapshot_id=''),
                  response('x' * 4097), response(format='arbitrary')]:
        with pytest.raises(ValueError):
            validated_context(reply)
