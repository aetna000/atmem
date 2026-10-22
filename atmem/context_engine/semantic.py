"""Optional bounded semantic nominations inside the existing encrypted store.

This derived index is not memory authority or evidence sufficiency. Callers must
authorize document/query embedding and provide the current allowed unit IDs.
No models, downloads or network access occur in this module. The default V3
engine does not activate this index implicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import random
import struct
from typing import Iterable, Sequence


def _normalize(vector: Sequence[float], dimensions: int) -> tuple[float, ...]:
    if len(vector) != dimensions or any(isinstance(v, bool) for v in vector):
        raise ValueError("semantic vector dimensions/types differ from index")
    result = tuple(float(v) for v in vector)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("semantic vectors must be finite")
    norm = math.hypot(*result)
    if not norm or not math.isfinite(norm):
        raise ValueError("zero semantic vector")
    return tuple(v/norm for v in result)


@dataclass(frozen=True)
class SemanticHit:
    unit_id: str
    score: float


class SemanticIndex:
    """Versioned random-hyperplane LSH with bounded SQL bucket nomination.

    Tables are derived/rebuildable and inherit their owner's encryption. Build
    only in a building generation, before its benchmark/product checkpoint.
    Lookup filters authorization before reading candidate vectors. Unknown
    generation/model identities and stale revisions fail closed.
    """
    FORMAT = "atmem-context-semantic-lsh-v1"

    def __init__(self, store, *, generation_id: str, model_identity: dict,
                 dimensions: int, tables: int = 8, bits: int = 10, seed: int = 2310):
        if (type(dimensions) is not int or not 1 <= dimensions <= 8192 or
                type(tables) is not int or not 1 <= tables <= 16 or
                type(bits) is not int or not 2 <= bits <= 16):
            raise ValueError("invalid bounded semantic index configuration")
        if not model_identity or not all(k in model_identity for k in ('model', 'revision')):
            raise ValueError("pinned semantic model and revision required")
        self.store, self.generation_id = store, generation_id
        self.dimensions, self.tables, self.bits = dimensions, tables, bits
        config = {'format': self.FORMAT, 'model': model_identity, 'dimensions': dimensions,
                  'tables': tables, 'bits': bits, 'seed': seed}
        self.config = json.dumps(config, sort_keys=True, separators=(',', ':'), allow_nan=False)
        self.index_id = 'semantic3_' + hashlib.sha256(self.config.encode()).hexdigest()
        rng = random.Random(seed)
        self.planes = tuple(tuple(tuple(rng.gauss(0, 1) for _ in range(dimensions))
                                  for _ in range(bits)) for _ in range(tables))

    def _generation(self):
        row = self.store._conn.execute(
            'SELECT state,revision FROM context_view_generations WHERE generation_id=?',
            (self.generation_id,)).fetchone()
        if row is None or row['state'] == 'retired':
            raise ValueError('semantic generation unavailable')
        return row

    def _buckets(self, vector: Sequence[float]) -> tuple[int, ...]:
        return tuple(sum((1 << bit) for bit, plane in enumerate(table)
                         if sum(a*b for a, b in zip(plane, vector)) >= 0)
                     for table in self.planes)

    def build(self, rows: Iterable[tuple[str, Sequence[float]]], *,
              allowed_unit_ids: frozenset[str]) -> int:
        generation = self._generation()
        if generation['state'] != 'building':
            raise ValueError('semantic index must be built before generation freeze')
        if not isinstance(allowed_unit_ids, frozenset):
            raise ValueError('explicit authorized unit IDs required')
        # All validation and writes occur in one transaction; errors cannot leave
        # a partially usable index. No existing canonical unit/source is modified.
        with self.store.transaction():
            self.store._conn.execute('''CREATE TABLE IF NOT EXISTS context_semantic_indexes_v1(
                generation_id TEXT NOT NULL, index_id TEXT NOT NULL, config TEXT NOT NULL,
                revision INTEGER NOT NULL, unit_count INTEGER NOT NULL,
                PRIMARY KEY(generation_id,index_id),
                FOREIGN KEY(generation_id) REFERENCES context_view_generations(generation_id) ON DELETE CASCADE)''')
            self.store._conn.execute('''CREATE TABLE IF NOT EXISTS context_semantic_buckets_v1(
                generation_id TEXT NOT NULL, index_id TEXT NOT NULL, table_no INTEGER NOT NULL,
                bucket INTEGER NOT NULL, unit_id TEXT NOT NULL,
                PRIMARY KEY(generation_id,index_id,table_no,bucket,unit_id),
                FOREIGN KEY(generation_id,unit_id) REFERENCES context_evidence_units(generation_id,unit_id) ON DELETE CASCADE)''')
            if self.store._conn.execute('SELECT 1 FROM context_semantic_indexes_v1 WHERE generation_id=? AND index_id=?',
                                        (self.generation_id, self.index_id)).fetchone():
                raise ValueError('semantic index already built; create a new generation to rebuild')
            count, seen = 0, set()
            for identity, vector in rows:
                if identity not in allowed_unit_ids or identity in seen:
                    raise ValueError('unauthorized or duplicate semantic unit')
                unit = self.store._conn.execute('SELECT lifecycle FROM context_evidence_units WHERE generation_id=? AND unit_id=?',
                                                (self.generation_id, identity)).fetchone()
                if unit is None or unit['lifecycle'] != 'active':
                    raise ValueError('semantic unit missing, inactive or in another generation')
                normalized = _normalize(vector, self.dimensions)
                self.store._conn.execute('INSERT INTO context_vectors VALUES(?,?,?,?,?)',
                    (self.generation_id, identity, self.index_id, self.dimensions,
                     struct.pack('<'+'f'*self.dimensions, *normalized)))
                self.store._conn.executemany('INSERT INTO context_semantic_buckets_v1 VALUES(?,?,?,?,?)',
                    [(self.generation_id, self.index_id, table, bucket, identity)
                     for table, bucket in enumerate(self._buckets(normalized))])
                count += 1
                seen.add(identity)
            if not count:
                raise ValueError('cannot build an empty semantic index')
            self.store._conn.execute('INSERT INTO context_semantic_indexes_v1 VALUES(?,?,?,?,?)',
                                    (self.generation_id, self.index_id, self.config, int(generation['revision']), count))
        return count

    def nominate(self, vector: Sequence[float], *, allowed_unit_ids: frozenset[str],
                 limit: int = 32, candidate_limit: int = 256,
                 max_probes: int = 64) -> tuple[SemanticHit, ...]:
        if (not isinstance(allowed_unit_ids, frozenset) or type(limit) is not int or
                type(candidate_limit) is not int or type(max_probes) is not int or
                not 1 <= limit <= candidate_limit <= 1024 or not 1 <= max_probes <= 256):
            raise ValueError('explicit authorized IDs and bounded query limits required')
        generation = self._generation()
        row = self.store._conn.execute('SELECT config,revision FROM context_semantic_indexes_v1 WHERE generation_id=? AND index_id=?',
                                       (self.generation_id, self.index_id)).fetchone()
        if row is None or row['config'] != self.config or row['revision'] != generation['revision']:
            raise ValueError('missing, mismatched or stale semantic index')
        if not allowed_unit_ids:
            return ()
        vector = _normalize(vector, self.dimensions)
        buckets = self._buckets(vector)
        # Exact probes precede bounded Hamming-distance-one probes. This is a
        # persistent bucket lookup, not a corpus-wide vector scan.
        probes = [(table, bucket) for table, bucket in enumerate(buckets)]
        probes += [(table, bucket ^ (1 << bit)) for bit in range(self.bits)
                   for table, bucket in enumerate(buckets)]
        authorized_json = json.dumps(sorted(allowed_unit_ids))
        nominated = set()
        for table, bucket in probes[:max_probes]:
            rows = self.store._conn.execute('''SELECT b.unit_id FROM context_semantic_buckets_v1 b
                JOIN context_evidence_units u ON u.generation_id=b.generation_id AND u.unit_id=b.unit_id
                WHERE b.generation_id=? AND b.index_id=? AND b.table_no=? AND b.bucket=? AND u.lifecycle='active'
                AND b.unit_id IN (SELECT value FROM json_each(?))
                ORDER BY b.unit_id LIMIT ?''',
                (self.generation_id, self.index_id, table, bucket, authorized_json, candidate_limit)).fetchall()
            nominated.update(r['unit_id'] for r in rows if r['unit_id'] in allowed_unit_ids)
            if len(nominated) >= candidate_limit:
                break
        selected = sorted(nominated)[:candidate_limit]
        hits = []
        for identity in selected:
            row = self.store._conn.execute('''SELECT dimensions,vector_bytes FROM context_vectors
                WHERE generation_id=? AND unit_id=? AND model_id=?''',
                (self.generation_id, identity, self.index_id)).fetchone()
            if row is None or row['dimensions'] != self.dimensions:
                raise ValueError('semantic vector missing or dimension mismatch')
            values = struct.unpack('<'+'f'*self.dimensions, row['vector_bytes'])
            if not all(math.isfinite(v) for v in values):
                raise ValueError('invalid stored semantic vector')
            hits.append(SemanticHit(identity, sum(a*b for a, b in zip(vector, values))))
        return tuple(sorted(hits, key=lambda h: (-h.score, h.unit_id))[:limit])


class SQLiteExactSemanticIndex(SemanticIndex):
    """Optional native exact search over the persistent *derived vector* table.

    Does not load or scan canonical source text or build a temporary corpus
    index. Native distance evaluation is O(index_vectors * dimensions), so this
    explicit operating point refuses indexes above its declared capacity. The
    optional sqlite-vec extension is loaded only on this selected path; no
    default dependency or plaintext external vector sidecar is introduced.
    Existing frozen vectors can be used for approximation-controlled comparison.
    """

    backend = 'sqlite-vec-exact-v1'

    def nominate(self, vector: Sequence[float], *, allowed_unit_ids: frozenset[str],
                 limit: int = 32, candidate_limit: int = 256,
                 max_probes: int = 64, max_index_vectors: int = 100_000) -> tuple[SemanticHit, ...]:
        if (not isinstance(allowed_unit_ids, frozenset) or type(limit) is not int or
                type(candidate_limit) is not int or not 1 <= limit <= candidate_limit <= 1024
                or type(max_index_vectors) is not int or not 1 <= max_index_vectors <= 100_000):
            raise ValueError('explicit authorized IDs and bounded exact limits required')
        generation = self._generation()
        metadata = self.store._conn.execute('''SELECT config,revision,unit_count FROM context_semantic_indexes_v1
            WHERE generation_id=? AND index_id=?''', (self.generation_id, self.index_id)).fetchone()
        if metadata is None or metadata['config'] != self.config or metadata['revision'] != generation['revision']:
            raise ValueError('missing, mismatched or stale semantic index')
        if metadata['unit_count'] > max_index_vectors:
            raise ValueError('exact vector capacity exceeded; select a qualified larger-scale backend')
        if not allowed_unit_ids:
            return ()
        normalized = _normalize(vector, self.dimensions)
        try:
            self.store._conn.execute('SELECT vec_version()').fetchone()
        except Exception as exc:
            # Only a missing function is eligible for loading the selected,
            # operator-installed extension. Never hide corruption/other errors.
            if 'no such function' not in str(exc):
                raise
            try:
                import sqlite_vec
            except ImportError as missing:
                raise ValueError('optional sqlite-vec backend is not installed') from missing
            if not callable(getattr(self.store._conn, 'enable_load_extension', None)):
                raise ValueError('selected SQLite runtime cannot load extensions; use the encrypted SQLCipher backend or an extension-enabled Python build')
            self.store._conn.enable_load_extension(True)
            try:
                sqlite_vec.load(self.store._conn)
            finally:
                self.store._conn.enable_load_extension(False)
        rows = self.store._conn.execute('''SELECT v.unit_id,
            vec_distance_cosine(v.vector_bytes, ?) AS distance
            FROM context_vectors v
            JOIN context_evidence_units u ON u.generation_id=v.generation_id AND u.unit_id=v.unit_id
            WHERE v.generation_id=? AND v.model_id=? AND v.dimensions=? AND u.lifecycle='active'
              AND v.unit_id IN (SELECT value FROM json_each(?))
            ORDER BY distance, v.unit_id LIMIT ?''',
            (struct.pack('<'+'f'*self.dimensions, *normalized), self.generation_id,
             self.index_id, self.dimensions, json.dumps(sorted(allowed_unit_ids)), limit)).fetchall()
        if any(row['distance'] is None or not math.isfinite(row['distance']) for row in rows):
            raise ValueError('invalid native semantic distance')
        return tuple(SemanticHit(row['unit_id'], 1.-row['distance']) for row in rows)
