import io
import json

import pytest

from atbot.providers.openai_compatible import OpenAICompatibleProvider


@pytest.mark.parametrize('endpoint,expected', [
    ('https://api.openai.com/v1', 'https://api.openai.com/v1/chat/completions'),
    ('https://openrouter.ai/api/v1/', 'https://openrouter.ai/api/v1/chat/completions'),
    ('http://127.0.0.1:8000', 'http://127.0.0.1:8000/v1/chat/completions'),
])
def test_provider_base_url_and_non_strict_schema_are_explicit(monkeypatch, endpoint, expected):
    requests = []
    def respond(request, **kwargs):
        requests.append(request)
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': '{"facts":[]}'}}],
                                     'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}).encode())
    monkeypatch.setattr('atbot.providers.openai_compatible.urlopen', respond)
    provider = OpenAICompatibleProvider(name='fixture', model='fixture', endpoint=endpoint)
    schema = {'type': 'object', 'properties': {'facts': {'type': 'array'}}, 'required': ['facts']}
    before = json.dumps(schema)
    result = provider.complete(system='fixture', prompt='fixture', schema=schema)
    assert requests[0].full_url == expected
    payload = json.loads(requests[0].data)
    assert payload['response_format']['json_schema']['strict'] is False
    assert payload['response_format']['json_schema']['schema'] == schema
    assert json.dumps(schema) == before
    assert result.structured == {'facts': []}


def test_availability_uses_one_version_prefix(monkeypatch):
    addresses = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_args): pass
    def respond(request, **kwargs):
        addresses.append(request.full_url)
        return Response()
    monkeypatch.setattr('atbot.providers.openai_compatible.urlopen', respond)
    provider = OpenAICompatibleProvider(name='fixture', model='fixture', endpoint='https://openrouter.ai/api/v1')
    assert provider.available()
    assert addresses == ['https://openrouter.ai/api/v1/models']
