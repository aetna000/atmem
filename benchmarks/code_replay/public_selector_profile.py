"""Change only the pinned selector validator in retained public-test programs."""
import ast
from hashlib import sha256
from pathlib import Path

ORIGINAL_SHA256 = '79905b374db7faf5ca58487cf4b11a29258965a5c467635964ddf40e7f4d3a20'
OLD = '        in_tests = any(pieces[0] == root or (root == "tests" and path.parts and path.parts[0] == "tests") for root in allowed)'
NEW = ('        in_tests = any(pieces[0] == root or (PurePosixPath(root).suffix != ".py"\n'
       '                       and PurePosixPath(root) in path.parents) for root in allowed)')
ROLES = {'server': 'atmem_public_test_helpers', 'worker': 'atmem_public_validation'}


def validators():
    source = Path(__file__).with_name('public_test_worker.py').read_text()
    matches = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'pytest_arguments']
    if len(matches) != 1:
        raise ValueError('one public selector validator required')
    new = ast.get_source_segment(source, matches[0])
    if new.count(NEW) != 1:
        raise ValueError('exact approved directory-ancestry correction required')
    old = new.replace(NEW, OLD, 1)
    if sha256(old.encode()).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('other selector, resource or command semantics changed')
    return old, new


def program_modules(program):
    tree = ast.parse(program)
    matches = [n for n in tree.body if isinstance(n, ast.For) and isinstance(n.target, ast.Tuple)
               and [getattr(x, 'id', None) for x in n.target.elts] == ['name', 'source']]
    if len(matches) != 1:
        raise ValueError('one retained public module bootstrap required')
    node = matches[0].iter
    modules = ast.literal_eval(node)
    if (not isinstance(modules, list) or not modules or len(modules) > 64
            or any(not isinstance(pair, tuple) or len(pair) != 2 or not all(isinstance(x, str) for x in pair) for pair in modules)
            or len({name for name, _ in modules}) != len(modules)):
        raise ValueError('unique bounded literal module bundle required')
    return node, modules


def corrected_program(program, *, role, validator_pair=None):
    if role not in ROLES:
        raise ValueError('explicit public server or worker role required')
    old, new = validators() if validator_pair is None else validator_pair
    if (sha256(old.encode()).hexdigest() != ORIGINAL_SHA256 or new.count(NEW) != 1
            or new.replace(NEW, OLD, 1) != old):
        raise ValueError('only the approved validator delta may be supplied')
    node, modules = program_modules(program)
    selected = [i for i, (name, _) in enumerate(modules) if name == ROLES[role]]
    if len(selected) != 1:
        raise ValueError('exact role-bound public validation module required')
    index = selected[0]; name, source = modules[index]
    functions = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'pytest_arguments']
    if len(functions) != 1 or ast.get_source_segment(source, functions[0]) != old:
        raise ValueError('retained original validator differs; no blind program replacement')
    if source.count(old) != 1:
        raise ValueError('one exact selector definition required')
    replacement = source.replace(old, new, 1)
    revised = list(modules); revised[index] = (name, replacement)
    fragment = ast.get_source_segment(program, node)
    if program.count(fragment) != 1:
        raise ValueError('one exact module literal required')
    corrected = program.replace(fragment, repr(revised), 1)
    ast.parse(corrected, feature_version=(3, 9))
    after_node, after = program_modules(corrected)
    if after != revised or corrected.replace(ast.get_source_segment(corrected, after_node), fragment, 1) != program:
        raise ValueError('outer program or unrelated modules changed')
    if replacement.replace(new, old, 1) != source:
        raise ValueError('non-validator bytes changed')
    return corrected
