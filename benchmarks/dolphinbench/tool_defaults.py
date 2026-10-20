"""Lossless effective-call export of defaults in pinned application signatures.

Never executes source, changes explicit arguments, or alters app logs/grades.
The original model calls and signature provenance are retained reversibly.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path


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
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def normalize_effective_arguments(messages, app_calls, source_paths):
    result, changes, available = copy.deepcopy(messages), [], []
    defaults = signature_defaults(source_paths)
    for position, message in enumerate(result):
        for index, call in enumerate(message.get('tool_calls', [])):
            name, arguments = call['name'], call['arguments']
            if name == 'tool_call' and isinstance(arguments.get('name'), str):
                name, arguments = arguments['name'], arguments.get('arguments', {})
            for prefix in ('mcp__dolphinbench_apps__', 'mcp_dolphinbench_apps_'):
                if name.startswith(prefix):
                    name = name[len(prefix):]
                    break
            available.append((position, index, call, name, arguments))
    for backend in app_calls:
        matched = None
        for candidate in available:
            position, index, call, name, arguments = candidate
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
                if proofs:
                    changes.append({'message_position': position, 'tool_call_position': index,
                                    'original': copy.deepcopy(call), 'default_provenance': proofs})
                    if call['name'] == 'tool_call':
                        call['arguments']['arguments'] = copy.deepcopy(backend['args'])
                    else:
                        call['arguments'] = copy.deepcopy(backend['args'])
                break
        if matched is None:
            raise ValueError('Independent app arguments differ beyond proven omitted signature defaults')
        available.remove(matched)
    return result, {'format': 'application-signature-default-export-v1', 'changes': changes,
                    'explicit_arguments_changed': False, 'backend_logs_or_results_changed': False}
