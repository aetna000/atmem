"""Source/authority boundary fixtures, not task-quality evidence."""
import base64
from hashlib import sha256

import pytest

from atmem.knowledge.code.packing import _query_source_locations, pack_generation
from tests.test_knowledge_packing import example


def test_locations_use_longest_exact_authorized_path_and_in_range_lines(monkeypatch):
    import socket
    def forbidden(*args, **kwargs): raise AssertionError('network forbidden')
    monkeypatch.setattr(socket, 'socket', forbidden)
    sources = {'src/module.py': [''] * 8, 'module.py': [''] * 8, 'other/module.py': [''] * 8}
    assert _query_source_locations('https://host/org/repo/blob/ref/src/module.py#L2-L4.', sources) == {'src/module.py': [(2, 4)]}
    assert _query_source_locations('https://host/org/repo/src%2Fmodule.py#L2-4', sources) == {'src/module.py': [(2, 4)]}
    assert _query_source_locations('https://host/org/repo/module.py#L2', {'a/module.py': [''] * 8}) == {}
    assert _query_source_locations('https://host/org/repo/src/module.py#L9', sources) == {}


@pytest.mark.parametrize('url', [
    'https://user:password@host/src/module.py#L2',
    'https://host/../src/module.py#L2', 'https://host/%2e%2e/src/module.py#L2',
    'https://host/%5Csrc/module.py#L2', 'https://host/%00/src/module.py#L2',
    'https://host/src/module.py#L0', 'https://host/src/module.py#L4-L2',
    'https://host/src/module.py#bad', 'file:///src/module.py#L2',
    'https://[malformed/src/module.py#L2',
])
def test_unsafe_or_unsupported_hints_do_not_nominate_any_source(url):
    assert _query_source_locations(url, {'src/module.py': [''] * 8}) == {}


def test_hint_work_is_bounded_and_plain_queries_are_unchanged():
    task = ' '.join('https://host/missing.py#L1' for _ in range(8))+' https://host/module.py#L1'
    assert _query_source_locations(task, {'module.py': ['line']}) == {}
    value = example()
    ordinary = pack_generation(value, 'entry', budget=1024)
    assert pack_generation(value, 'entry https://host/unknown.py#L2', budget=1024) == ordinary


def test_line_hint_prefers_existing_innermost_definition_and_keeps_byte_budget():
    value = example()
    raw = b'class Container:\n    def entry(self):\n        return 1\n\ndef unrelated():\n    return 2\n'
    identity = sha256(raw).hexdigest()
    value['snapshot']['files'] = [['src/module.py', identity]]
    value['source_bytes'] = {'src/module.py': base64.b64encode(raw).decode()}
    for obj, name, first, last in zip(value['objects'], ['Container', 'Container.entry', 'unrelated'], [1, 2, 5], [3, 3, 6]):
        obj['name'] = 'src/module.'+name
        obj['anchors'][0].update(path='src/module.py', start_line=first, end_line=last, content_sha256=identity)
    pack = pack_generation(value, 'Fix https://host/repo/src/module.py#L3', budget=1024)
    assert 'Container.entry; complete definition' in pack
    if 'Container; method inventory' in pack:
        assert pack.index('Container.entry; complete definition') < pack.index('Container; method inventory')
    assert len(pack.encode()) <= 1024
