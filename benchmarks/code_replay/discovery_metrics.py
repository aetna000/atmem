"""Host-specific usage, without imputing missing counts or cache double counts."""
import json


def events(raw):
    values = []
    for line in raw.splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                values.append(value)
        except (ValueError, UnicodeDecodeError):
            continue
    return values


def usage(host, values):
    missing = {'complete': False, 'input_tokens': None, 'cached_input_tokens': None, 'output_tokens': None}
    if host == 'claude':
        terminal = [v for v in values if v.get('type') == 'result']
        if len(terminal) != 1:
            return missing
        if terminal[0].get('is_error') and not terminal[0].get('modelUsage'):
            return missing
        row = terminal[0].get('usage', {})
        keys = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')
        if any(type(row.get(k)) is not int or row[k] < 0 for k in keys):
            return missing
        return {'complete': True, 'input_tokens': sum(row[k] for k in keys[:3]),
            'cached_input_tokens': row['cache_read_input_tokens'], 'output_tokens': row['output_tokens'],
            'semantics': 'anthropic_uncached_plus_creation_plus_read',
            'models': terminal[0].get('modelUsage', {}), 'terminal': terminal[0].get('subtype')}
    if host == 'codex':
        terminal = [v['usage'] for v in values if v.get('type') == 'turn.completed' and isinstance(v.get('usage'), dict)]
        keys = ('input_tokens', 'cached_input_tokens', 'output_tokens')
        if not terminal or any(type(row.get(k)) is not int or row[k] < 0 for row in terminal for k in keys):
            return missing
        if any(row['cached_input_tokens'] > row['input_tokens'] for row in terminal):
            return missing
        return {'complete': True, **{k: sum(row[k] for row in terminal) for k in keys},
            'semantics': 'codex_input_already_includes_cached'}
    # Copilot schemas vary by billing generation. Do not guess from counters
    # named total/tokens; qualify a real retained receipt before normalization.
    return missing


def summarize_tools(retained):
    written = [e['envelope']['payload'] for e in retained if e['envelope']['event_type'] == 'discovery.tool_written']
    calls = [e for e in written if e['request']['method'] == 'tools/call']
    discovery = [e for e in calls if e['request']['params']['name'] == 'repository_discover']
    return {'tool_calls': len(calls), 'discovery_calls': len(discovery),
        'discovery_errors': sum('error' in e['response'] for e in discovery),
        'discovery_ms': sum(e['elapsed_ms'] for e in discovery),
        'response_bytes': sum(len(json.dumps(e['response']).encode()) for e in discovery),
        'source_read_coverage': 'exact_shell_commands_retained_ranges_not_inferred',
        'treatment_used': bool(discovery)}
