"""Lifecycle ownership for encrypted, rebuildable source-part vector caches.

Reuse the existing semantic registry. Its reserved epoch prefix distinguishes
this cache schema from the legacy semantic index; neither is canonical memory.
Purging a cache before a canonical transaction commits is deliberately one-way:
rollback can require rebuilding an optimization, never restore stale vectors.
"""
from __future__ import annotations

import json
from pathlib import Path

from atmem.core.canonical import sha256_hex
from atmem.core.storage import connect, row_factory_for


PART_CACHE_PREFIX = 'context-part-v1:'


def is_part_cache(registry):
    return str(registry.get('active_epoch_id') or '').startswith(PART_CACHE_PREFIX)


def purge_part_cache(store, registry, subject_id, *, generation_ids=None):
    """Verify row removal without deleting a file or another subject's cache."""
    path = Path(registry['index_path']).expanduser().resolve()
    if not is_part_cache(registry) or not path.is_file():
        raise RuntimeError('registered source-part cache unavailable; deletion cannot be verified')
    if str(path) == str(Path(store.path).resolve()):
        raise RuntimeError('derived cache cannot be the canonical database')
    selected = None if generation_ids is None else frozenset(generation_ids)
    connection = connect(path, policy=store.policy, isolation_level=None)
    connection.row_factory = row_factory_for(store.policy)
    try:
        connection.execute('PRAGMA secure_delete=ON')
        connection.execute('PRAGMA busy_timeout=5000')
        identities = []
        for row in connection.execute('SELECT id,identity FROM part_index').fetchall():
            identity = json.loads(row['identity'])
            if not isinstance(identity, dict) or not isinstance(identity.get('scope'), dict):
                raise RuntimeError('invalid registered cache identity; deletion cannot be verified')
            if (identity['scope'].get('subject_id') == subject_id
                    and (selected is None or identity.get('generation_id') in selected)):
                identities.append(row['id'])
        removed = 0
        connection.execute('BEGIN IMMEDIATE')
        try:
            for index_id in identities:
                removed += connection.execute('DELETE FROM part_vectors WHERE index_id=?', (index_id,)).rowcount
                connection.execute('DELETE FROM part_index WHERE id=?', (index_id,))
            connection.execute('COMMIT')
        except BaseException:
            connection.execute('ROLLBACK')
            raise
        for index_id in identities:
            if (connection.execute('SELECT 1 FROM part_vectors WHERE index_id=? LIMIT 1', (index_id,)).fetchone()
                    or connection.execute('SELECT 1 FROM part_index WHERE id=?', (index_id,)).fetchone()):
                raise RuntimeError('source-part vector purge did not verify')
        checkpoint = connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
        if checkpoint is not None and checkpoint[0] != 0:
            raise RuntimeError('source-part cache checkpoint busy; deletion not verified')
        return {'format': 'atmem-context-part-cache-purge-v1', 'verified_absent': True,
            'index_verification_valid': True, 'index_path_sha256': sha256_hex(str(path)),
            'removed_vector_rows': removed, 'removed_index_ids': identities,
            'generation_ids': sorted(selected) if selected is not None else None}
    finally:
        connection.close()


def purge_registered_part_caches(store, subject_id, *, generation_ids=None):
    return [purge_part_cache(store, registry, subject_id, generation_ids=generation_ids)
        for registry in store.semantic_index_paths(subject_id) if is_part_cache(registry)]
