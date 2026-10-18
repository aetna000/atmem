import ast
import base64
from hashlib import sha256

import pytest

from benchmarks.code_replay.windows_omission_build import CHANGED, updated_job


def test_separate_preview_changes_only_declared_product_files():
    files = {name: b'old' for name in (*CHANGED, 'atmem/knowledge/code/mapping.py')}
    prior = {'program': 'import json\nprint(json.dumps({}))\n', 'cache': '/benchmark/cache', 'constraints': 'unchanged',
        'files': {name: base64.b64encode(raw).decode() for name, raw in files.items()},
        'manifest': {name: sha256(raw).hexdigest() for name, raw in files.items()}}
    new = updated_job(prior, {name: b'new' for name in CHANGED})
    ast.parse(new['program'])
    assert new['files']['atmem/knowledge/code/mapping.py'] == prior['files']['atmem/knowledge/code/mapping.py']
    assert new['constraints'] == prior['constraints'] and new['cache'] == prior['cache']
    assert 'physical disk guard' in new['program']
    assert base64.b64decode(prior['files'][CHANGED[0]]) == b'old'
    with pytest.raises(ValueError, match='two declared'):
        updated_job(prior, {CHANGED[0]: b'new'})
