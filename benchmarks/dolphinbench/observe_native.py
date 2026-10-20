"""Observation only: retain the ordinary installed Hermes shutdown/drain result."""
import json
import hashlib
import os
from pathlib import Path
import threading

from agent.memory_manager import MemoryManager

original = MemoryManager.shutdown_all


def observed_shutdown(self):
    try:
        return original(self)
    finally:
        providers = []
        for provider in self._providers:
            providers.append({'name': provider.name,
                              'pending_writes': getattr(provider, '_pending', None),
                              'write_errors': getattr(provider, '_errors', None),
                              'evidence_errors': getattr(provider, '_evidence_errors', None)})
        record = {'format': 'atmem-hermes-shutdown-observation-v1',
                  'drain': self.shutdown_drain_state, 'providers': providers}
        path = Path(os.environ['ATMEM_BENCH_WITNESS'])
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump(record, output)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())


MemoryManager.shutdown_all = observed_shutdown

# Observe native lifecycle identity, not prompt text heuristics. In particular,
# session-title calls are paid auxiliary work, not conversation turns.
from hermes_cli import lifecycle

_invoke = lifecycle.invoke_hook
_has_hook = lifecycle.has_hook
_observed = {'pre_api_request', 'post_api_request', 'api_request_error',
             'pre_auxiliary_call', 'post_auxiliary_call'}
_lock = threading.Lock()


def _observe_hook(name, **kwargs):
    if name in _observed:
        record = {'event': name}
        for key in ('api_request_id', 'session_id', 'aux_task', 'retry_count',
                    'api_call_count', 'api_duration', 'error_type'):
            if key in kwargs:
                record[key] = kwargs[key]
        if name.startswith('pre_'):
            messages = kwargs.get('request_messages')
            if not isinstance(messages, list) or not messages:
                raise RuntimeError('Native request observation lacks complete messages')
            raw = json.dumps(messages, sort_keys=True, ensure_ascii=False,
                             allow_nan=False, separators=(',', ':')).encode()
            record['messages_sha256'] = hashlib.sha256(raw).hexdigest()
        path = Path(os.environ['ATMEM_BENCH_WITNESS']).with_name('api-witness.jsonl')
        with _lock:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, 'w') as output:
                output.write(json.dumps(record, allow_nan=False) + '\n')
                output.flush()
                os.fsync(output.fileno())
    return _invoke(name, **kwargs)


lifecycle.invoke_hook = _observe_hook
lifecycle.has_hook = lambda name: name in _observed or _has_hook(name)
