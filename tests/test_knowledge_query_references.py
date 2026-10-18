"""Boundary fixtures, never model-training data or performance evidence."""
from atmem.knowledge.code.packing import _query_call_names, _references, _named


def test_ordinary_prose_and_traceback_labels_are_not_call_references():
    assert 'name' not in _query_call_names('Reject an empty name (for example, an empty string).')
    assert 'Traceback' not in _query_call_names('Traceback (most recent call last):\n  File "module.py", line 1')
    assert 'value' not in _query_call_names('A default value (rather than an array) is accepted.')
    assert 'name' not in _query_call_names('The new name\n(supplied by the user) is empty.')
    assert not _named('package.Unrelated.name', _references('Reject an empty name (for example).'))


def test_immediate_spaced_inline_fenced_and_doctest_calls_are_preserved():
    for query in ('convert(1)', 'convert (1)', 'Fix `convert (1)` before proceeding.',
                  'Fix this:\n```python\nconvert (1)\n```\n',
                  'Fix this:\n~~~~python\nconvert (1)\n~~~~\n',
                  'Fix this:\n````python\nconvert (1)\n````\n',
                  'Fix this:\n```pycon\n>>> convert (1)\nexpected output\n```\n'):
        assert 'convert' in _query_call_names(query)
        assert _named('package.convert', _references(query))


def test_invalid_code_is_not_repaired_and_query_code_is_never_executed(tmp_path):
    marker = tmp_path/'not-created'
    query = f'```python\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\nconvert (1)\nraise RuntimeError("must not execute")\n```\n'
    assert 'convert' in _query_call_names(query)
    assert not marker.exists()
    assert 'convert' not in _query_call_names('Please fix:\n```python\nconvert (\n```\n')


def test_qualified_names_aliases_and_underscored_fields_keep_their_contract():
    assert _named('src/vendor/service.process', _references('```python\nimport vendor as v\nv.process ()\n```\n'))
    assert not _named('src/other/service.process', _references('```python\nimport vendor as v\nv.process ()\n```\n'))
    assert _named('src/vendor/api.convert', _references('from vendor import convert as fn\nfn (1)'))
    assert _named('package.Config.timeout_seconds', _references('Preserve timeout_seconds.'))
