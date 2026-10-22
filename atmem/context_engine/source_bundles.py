"""Bounded source-part expansion; canonical ranges remain the evidence objects."""
from __future__ import annotations

from .service import GovernanceViolation, load_stored_canonical


# CROSS JOIN fixes the access order: begin with one indexed source part, not
# every active unit in the generation for each of the eight possible bundles.
SOURCE_MEMBERS_SQL = '''
    SELECT u.unit_id, r.start_offset, r.end_offset, r.source_sha256
    FROM context_source_ranges r INDEXED BY idx_context_source_ranges_order
    CROSS JOIN context_unit_ranges ur INDEXED BY idx_context_unit_ranges_range
    CROSS JOIN context_evidence_units u
    WHERE ur.generation_id=? AND r.source_id=? AND r.part_id=?
      AND ur.range_id=r.range_id AND ur.ordinal=0
      AND u.generation_id=ur.generation_id AND u.unit_id=ur.unit_id
      AND u.lifecycle='active'
    ORDER BY r.start_offset, r.end_offset, u.unit_id LIMIT 257'''


def expand_source_bundles(store, *, generation_id, request, manifest, nominated):
    allowed = frozenset(manifest.authorized_unit_ids)
    if set(nominated) - allowed:
        raise GovernanceViolation('source bundle nomination is outside authorized scope')
    seeds = load_stored_canonical(store, request.scope, generation_id,
                                  tuple(nominated), request.generation)
    if tuple(row.unit_id for row in seeds) != tuple(nominated):
        raise GovernanceViolation('source bundle nomination disappeared')
    if any(row.lifecycle != 'active' or row.scope != request.scope
           or row.generation != request.generation for row in seeds):
        raise GovernanceViolation('source bundle nomination changed authority')
    keys = list(dict.fromkeys((e.source_range.source_id, e.source_range.part_id) for e in seeds))
    result, omitted = [], max(0, len(keys) - 8)
    for source, part in keys[:8]:
        # Scope is bound by the verified generation; authorization is checked
        # against the live manifest, never a model-supplied source identifier.
        rows = store._conn.execute(SOURCE_MEMBERS_SQL,
            (generation_id, source, part))
        members, ranges = [], set()
        oversized = False
        for ordinal, row in enumerate(rows):
            if ordinal == 256:
                oversized = True
                break
            if row['unit_id'] not in allowed:
                continue
            key = (row['start_offset'], row['end_offset'], row['source_sha256'])
            if key in ranges:
                continue
            ranges.add(key)
            members.append(row['unit_id'])
            if len(members) > 32:
                oversized = True
                break
        if oversized or len(result) + len(members) > 32:
            omitted += 1
            continue
        result.extend(members)
    return tuple(result), omitted
