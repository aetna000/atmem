"""Boundary fixtures only; not training data or task-performance evidence."""
from hashlib import sha256
import base64

from atmem.knowledge.code.packing import _query_term_weights, pack_generation, words
from tests.test_knowledge_packing import example


def test_only_subsection_only_terms_are_downweighted_without_discarding_words():
    task = '# Memory repair\n## Scope\n### Configuration\n### Command used\nFix the cache expiry behavior.'
    weights = _query_term_weights(task)
    assert weights.keys() == words(task)
    assert weights['configuration'] == weights['command'] == 0.25
    assert weights['memory'] == weights['scope'] == weights['cache'] == 1.0
    assert _query_term_weights('### Configuration\nFix configuration loading.')['configuration'] == 1.0
    assert all(weight == 1.0 for weight in _query_term_weights('### Configuration').values())


def test_hash_prefixed_literal_code_and_matching_fences_are_preserved():
    for delimiter in ('```', '~~~~'):
        task = f'### Configuration\n{delimiter}python\n### command_protocol\n{delimiter}\nFix cache expiry.'
        weights = _query_term_weights(task)
        assert weights['configuration'] == 0.25
        assert weights['command'] == weights['protocol'] == 1.0
    # A shorter or wrong-kind fence cannot close a literal block.
    task = '### Configuration\n````python\n```\n~~~\n### command_protocol\n````\nFix cache expiry.'
    assert _query_term_weights(task)['command'] == 1.0


def test_plain_queries_and_indented_nonheadings_retain_weights():
    for task in ('load configuration from command line', '###configuration\nFix cache.',
                 '    ### configuration\nFix cache.', '\t### configuration\nFix cache.',
                 '####### configuration\nFix cache.'):
        assert all(weight == 1.0 for weight in _query_term_weights(task).values())


def test_issue_form_labels_do_not_displace_supported_implementation():
    value = example()
    definitions = [('cache_expiry', 'return expired_cache_entries'),
                   ('load_configuration_command', 'return parser_options'),
                   ('read_environment', 'return environment_options')]
    for obj, (name, body) in zip(value['objects'], definitions):
        path = obj['anchors'][0]['path']; raw = f'def {name}():\n    {body}\n'.encode()
        identity = sha256(raw).hexdigest(); obj['name'] = 'package.'+name
        obj['anchors'][0]['content_sha256'] = identity
        value['source_bytes'][path] = base64.b64encode(raw).decode()
        for record in value['snapshot']['files']:
            if record[0] == path: record[1] = identity
    task = 'Cache expiry fails.\n### Configuration\n### Command\n### Environment'
    pack = pack_generation(value, task, budget=600)
    assert 'package.cache_expiry' in pack
    if 'package.load_configuration_command' in pack:
        assert pack.index('package.cache_expiry') < pack.index('package.load_configuration_command')
    # Explicit identifiers still outrank ordinary lexical weighting.
    pack = pack_generation(value, '### load_configuration_command\nFix cache expiry.', budget=600)
    assert 'package.load_configuration_command' in pack
