"""Static source-boundary fixtures, not training data or repair-quality scores."""
import ast
import base64
from hashlib import sha256

import pytest

from atmem.knowledge.code.packing import _query_literal_targets, pack_generation
from tests.test_knowledge_packing import example


def targets(task, text, *, eligible=None):
    tree = ast.parse(text)
    if eligible is None:
        eligible = {('module.py', n.lineno, n.name) for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    return _query_literal_targets(task, {'module.py': text.splitlines()}, eligible)


def test_literal_registry_binds_only_the_existing_same_module_function():
    text = 'def decode_palette(value):\n    return value\n\nTRANSFORMS = {"color-mode": decode_palette}\n'
    assert targets('`color-mode=warm` is ignored', text) == {('module.py', 1, 'decode_palette'): 8000}
    assert targets('Use --color-mode=warm', text) == {('module.py', 1, 'decode_palette'): 8000}
    assert targets('`color` is ignored', text) == {}
    assert targets('`color-mode=warm` is ignored', text, eligible=set()) == {}
    assert targets('ordinary color mode words', text) == {}


@pytest.mark.parametrize('suffix', [
    'decode_palette = other\n', 'from external import decode_palette\n',
    'def decode_palette(value):\n    return other\n',
])
def test_rebound_imported_or_multiply_defined_callables_are_not_resolved(suffix):
    text = 'def decode_palette(value):\n    return value\nTRANSFORMS = {"color-mode": decode_palette}\n' + suffix
    assert targets('`color-mode`', text) == {}


def test_dynamic_forward_or_duplicate_registry_entries_are_not_guessed():
    prefix = 'def decode_palette(value):\n    return value\n'
    for declaration in ('TRANSFORMS = {"color-mode": decode_palette()}\n',
                        'TRANSFORMS = {"color-mode": external.decode_palette}\n',
                        'TRANSFORMS = {"color-mode": decode_palette, "color-mode": decode_palette}\n',
                        'TRANSFORMS = {"color-mode": decode_palette}\nTRANSFORMS = {}\n'):
        assert targets('`color-mode`', prefix + declaration) == {}
    assert targets('`color-mode`', 'TRANSFORMS = {"color-mode": decode_palette}\n' + prefix) == {}


def test_immediate_class_declarations_do_not_absorb_method_strings():
    text = ('class Palette:\n    options = (("color-mode", {"default": "warm"}),)\n'
            '    def render(self):\n        return "different-mode"\n')
    assert targets('`color-mode`', text) == {('module.py', 1, 'Palette'): 6000}
    assert targets('`different-mode`', text) == {}
    assert targets('`color-mode`', text + 'Palette = other\n') == {}


def test_static_source_is_not_executed_and_unicode_keys_are_supported(tmp_path):
    marker = tmp_path/'must-not-exist'
    text = (f'open({str(marker)!r}, "w").write("executed")\n'
            'def translate_style(value):\n    return value\n'
            'STYLES = {"主题模式": translate_style}\n')
    assert targets('`主题模式=暗色`', text) == {('module.py', 2, 'translate_style'): 8000}
    assert not marker.exists()


def test_literal_work_and_ambiguity_are_bounded_without_partial_guessing():
    sources = {f'module{i}.py': ['def decode(value):', '    return value', 'REGISTRY = {"style-mode": decode}'] for i in range(9)}
    eligible = {(path, 1, 'decode') for path in sources}
    assert _query_literal_targets('`style-mode`', sources, eligible) == {}
    assert targets(' '.join(f'`option-{i}`' for i in range(33)), 'class Palette:\n    options = {"option-1": True}\n') == {}


def test_historical_line_hint_cannot_displace_an_explicit_current_symbol():
    value = example()
    raw = b'def unrelated():\n    return 0\n\ndef decode_palette():\n    return 1\n\ndef other():\n    return 2\n'
    digest = sha256(raw).hexdigest()
    value['snapshot']['files'] = [['src/module.py', digest]]
    value['source_bytes'] = {'src/module.py': base64.b64encode(raw).decode()}
    for obj, name, first, last in zip(value['objects'], ['unrelated', 'decode_palette', 'other'], [1, 4, 7], [2, 5, 8]):
        obj['name'] = 'src/module.'+name
        obj['anchors'][0].update(path='src/module.py', start_line=first, end_line=last, content_sha256=digest)
    pack = pack_generation(value, 'Fix decode_palette() https://host/repo/src/module.py#L2', budget=1024)
    assert pack.index('decode_palette; complete definition') < pack.index('unrelated; complete definition')
    assert len(pack.encode()) <= 1024


def test_literal_binding_nominates_the_callable_not_verbose_configuration_prose():
    value = example()
    raw = (b'def decode_palette(value):\n    return value\n'
           b'REGISTRY = {"color-mode": decode_palette}\n\n'
           b'def load_configuration_color_mode():\n    return "configuration color mode options"\n\n'
           b'def unrelated():\n    return 2\n')
    digest = sha256(raw).hexdigest()
    value['snapshot']['files'] = [['src/module.py', digest]]
    value['source_bytes'] = {'src/module.py': base64.b64encode(raw).decode()}
    for obj, name, first, last in zip(value['objects'], ['decode_palette', 'load_configuration_color_mode', 'unrelated'], [1, 5, 8], [2, 6, 9]):
        obj['name'] = 'src/module.'+name
        obj['anchors'][0].update(path='src/module.py', start_line=first, end_line=last, content_sha256=digest)
    task = 'Configuration color mode option is ignored for `color-mode=warm`'
    pack = pack_generation(value, task, budget=1024)
    assert pack.index('decode_palette; complete definition') < pack.index('load_configuration_color_mode; complete definition')
    assert len(pack.encode()) <= 1024
    explicit = pack_generation(value, task+' Fix unrelated().', budget=1024)
    assert explicit.index('unrelated; complete definition') < explicit.index('decode_palette; complete definition')
    value['source_bytes']['src/module.py'] = base64.b64encode(raw+b'# changed\n').decode()
    with pytest.raises(ValueError):
        pack_generation(value, task, budget=1024)
