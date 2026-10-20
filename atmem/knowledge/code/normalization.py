"""Share work on immutable metadata only while constructing one query snapshot.

Not a generation, authorization, source or cross-request cache. Query selection
and public-result copying stay in the incorporated algorithms unchanged.
"""
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar

_ACTIVE = ContextVar('atmem_code_metadata_construction', default=None)


@contextmanager
def shared_metadata_scope(roots=()):
    roots = {id(value): value for value in roots if isinstance(value, (Mapping, list, tuple, set))}
    state = {'roots': roots, 'normalized': {}, 'shared_ids': set(), 'formatted': {}} if roots else None
    token = _ACTIVE.set(state)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def normalize_shared(value, normalize):
    state = _ACTIVE.get()
    identity = id(value)
    if state is None or identity not in state['roots'] or state['roots'][identity] is not value:
        return normalize(value)
    if identity not in state['normalized']:
        normalized = normalize(value)
        state['normalized'][identity] = normalized
        pending = [normalized]
        while pending:
            item = pending.pop()
            if not isinstance(item, (Mapping, list, tuple, set)) or id(item) in state['shared_ids']:
                continue
            state['shared_ids'].add(id(item))
            pending.extend(item.values() if isinstance(item, Mapping) else item)
    return state['normalized'][identity]


def scalar_shared(value, format_scalar):
    state = _ACTIVE.get()
    identity = id(value)
    if state is None or identity not in state['shared_ids']:
        return format_scalar(value)
    # The normalized root retains all children until this construction ends;
    # identities cannot be recycled while this tiny formatting memo is alive.
    if identity not in state['formatted']:
        state['formatted'][identity] = format_scalar(value)
    return state['formatted'][identity]
