"""Embedding transport fixtures are not benchmark or training observations."""
from atmem.semantic import providers


def test_strict_embedding_refuses_implicit_truncation_and_pins_identity(monkeypatch):
    monkeypatch.setattr(providers, '_ollama_model_digest', lambda *a, **k: 'sha256:'+'a'*64)
    calls = []
    def post(url, body, **kwargs):
        calls.append(body)
        return {'embeddings': [[1., 0.]]}
    monkeypatch.setattr(providers, '_post_json', post)
    strict = providers.OllamaEmbedder('nomic-embed-text:latest', truncate=False)
    assert strict.embed_query('transport fixture') == [1., 0.]
    assert calls[-1]['truncate'] is False
    assert strict.identity['truncate'] is False
    legacy = providers.OllamaEmbedder('nomic-embed-text:latest')
    legacy.embed_query('transport fixture')
    assert 'truncate' not in calls[-1]
    assert 'truncate' not in legacy.identity
