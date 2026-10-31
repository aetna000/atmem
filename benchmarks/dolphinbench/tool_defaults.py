"""Lossless effective-call export of defaults in pinned application signatures.

Never executes source, changes explicit arguments, or alters app logs/grades.
The original model calls and signature provenance are retained reversibly.
"""
import ast
import copy
import hashlib
import json
import math
from pathlib import Path

# Standard MCP metadata methods are client-side protocol operations, not logged
# simulated app actions. Do not require a mutation log for these exact methods.
MCP_METADATA = frozenset({'get_prompt', 'list_prompts', 'list_resources', 'read_resource', 'list_resource_templates'})


def signature_defaults(paths):
    values = {}
    for path in sorted(map(Path, paths)):
        source = path.read_bytes()
        digest = hashlib.sha256(source).hexdigest()
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args.posonlyargs + node.args.args
            pairs = list(zip(args[len(args) - len(node.args.defaults):], node.args.defaults))
            pairs += list(zip(node.args.kwonlyargs, node.args.kw_defaults))
            for arg, default in pairs:
                if default is None:
                    continue
                try:
                    value = ast.literal_eval(default)
                    json.dumps(value, allow_nan=False)
                except (ValueError, TypeError, SyntaxError):
                    continue
                values.setdefault((node.name, arg.arg), []).append({'value': value,
                    'source_file': path.name, 'source_sha256': digest, 'source_line': node.lineno})
    return values


def _same(left, right):
    """Exact finite JSON equality; Python int/float comparison retains big ints.

    Never coerce through float, decimal text, truthiness or string conversion.
    Validate both complete trees first, including unmatched/nonfinite children.
    """
    def valid(value):
        if type(value) in (str, bool, int) or value is None:
            return True
        if type(value) is float:
            return math.isfinite(value)
        if type(value) is list:
            return all(valid(v) for v in value)
        if type(value) is dict:
            return all(type(k) is str and valid(v) for k, v in value.items())
        return False

    def equal(a, b):
        if type(a) in (int, float) and type(b) in (int, float):
            return a == b
        if type(a) is not type(b):
            return False
        if type(a) is dict:
            return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
        if type(a) is list:
            return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
        return a == b

    return valid(left) and valid(right) and equal(left, right)


# Hermes deferred-call validation (tools/tool_search_validation.py) and the opt-in
# strict argument proxy (atmem/mcp/strict_proxy.py) refuse a call before the
# application sees it. Only these exact host refusals are treated as undispatched.
STRICT_PROXY_REFUSALS = (
    'Unexpected tool arguments. Use exactly the advertised tool schema; a tool with no parameters requires {}.',
    'Required tool arguments are missing.', 'Describe the tool before invoking it.')


def rejected_before_dispatch(content):
    """Basis string when a tool result proves the call never reached the application."""
    if not isinstance(content, str):
        return None
    text = content[content.find('{'):content.rfind('}') + 1] if '{' in content else ''
    try:
        value = json.loads(text)
    except ValueError:
        return None
    error = value.get('error') if isinstance(value, dict) else None
    if not isinstance(error, str):
        return None
    if set(value) == {'error'} and error.startswith('tool_call '):
        return 'Hermes deferred-call validation refused the call before invocation'
    if error.strip() in STRICT_PROXY_REFUSALS:
        return 'strict argument proxy refused the call before forwarding'
    return None


def _effective_calls(call):
    """[(calls-entry index or None, tool name, arguments)] behind a tool_call wrapper."""
    name, arguments = call['name'], call['arguments']
    if name != 'tool_call':
        return [(None, name, arguments)]
    if isinstance(arguments.get('name'), str):
        return [(None, arguments['name'], arguments.get('arguments', {}))]
    entries = arguments.get('calls')
    if isinstance(entries, list):
        return [(i, e.get('name', ''), e.get('arguments', {})) for i, e in enumerate(entries) if isinstance(e, dict)]
    return [(None, name, arguments)]


def normalize_effective_arguments(messages, app_calls, source_paths):
    result, changes, available, metadata = copy.deepcopy(messages), [], [], []
    source_paths = list(source_paths)
    defaults = signature_defaults(source_paths)
    application_names = {node.name for path in source_paths for node in ast.walk(ast.parse(Path(path).read_bytes()))
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    results = {m.get('tool_call_id'): m.get('content') for m in result if m.get('role') == 'tool'}
    rejected = []
    for position, message in enumerate(result):
        for index, call in enumerate(message.get('tool_calls', [])):
            if not isinstance(call['arguments'], dict):
                raise ValueError('Tool arguments must be a decoded JSON object')
            basis = rejected_before_dispatch(results.get(call.get('id')))
            if basis:
                # Provably refused by the host or the strict argument proxy before any
                # application call; retained reversibly, never matched to a backend log.
                rejected.append({'message_position': position, 'tool_call_position': index,
                                 'original': copy.deepcopy(call), 'basis': basis})
                continue
            for entry, name, arguments in _effective_calls(call):
                if not isinstance(arguments, dict):
                    raise ValueError('Nested tool arguments must be a decoded JSON object')
                wrapped = name
                for prefix in ('mcp__dolphinbench_apps__', 'mcp_dolphinbench_apps_'):
                    if name.startswith(prefix):
                        name = name[len(prefix):]
                        break
                if name in MCP_METADATA and name not in {b['tool'] for b in app_calls}:
                    metadata.append({'message_position': position, 'tool_call_position': index,
                        'original': copy.deepcopy(call), 'basis': 'read-only MCP protocol metadata; no app action log'})
                    continue
                if name in application_names | {b['tool'] for b in app_calls} or wrapped.startswith(
                        ('mcp__dolphinbench_apps__', 'mcp_dolphinbench_apps_')):
                    available.append((position, index, call, name, arguments, entry))
    for backend in app_calls:
        matched = None
        for candidate in available[:1]:
            position, index, call, name, arguments, entry = candidate
            if name != backend['tool'] or any(k not in backend['args'] or not _same(v, backend['args'][k])
                                               for k, v in arguments.items()):
                continue
            proofs = {}
            for key in set(backend['args']) - set(arguments):
                definitions = defaults.get((name, key), [])
                if not definitions or any(not _same(d['value'], backend['args'][key]) for d in definitions):
                    break
                proofs[key] = definitions
            else:
                matched = candidate
                representation = json.dumps(arguments, sort_keys=True, allow_nan=False) != json.dumps(
                    {k: backend['args'][k] for k in arguments}, sort_keys=True, allow_nan=False)
                if proofs or representation:
                    changes.append({'message_position': position, 'tool_call_position': index,
                                    'original': copy.deepcopy(call), 'default_provenance': proofs,
                                    'exact_finite_numeric_representation_only': representation})
                    # Upstream grading_calls keys serialized arguments. Preserve
                    # original bytes/call reversibly, exporting only already
                    # proven equal values in the independent app's JSON form.
                    if entry is not None:
                        call['arguments']['calls'][entry]['arguments'] = copy.deepcopy(backend['args'])
                    elif call['name'] == 'tool_call':
                        call['arguments']['arguments'] = copy.deepcopy(backend['args'])
                    else:
                        call['arguments'] = copy.deepcopy(backend['args'])
                break
        if matched is None:
            raise ValueError('Independent app arguments differ beyond proven omitted signature defaults')
        available.remove(matched)
    if available:
        raise ValueError('Independent app arguments differ beyond proven omitted signature defaults: missing calls')
    return result, {'format': 'application-signature-default-export-v1', 'changes': changes,
                    'unlogged_metadata_calls': metadata, 'rejected_before_dispatch': rejected,
                    'explicit_arguments_changed': False, 'backend_logs_or_results_changed': False}
