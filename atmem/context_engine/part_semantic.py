"""Opt-in source-coherent semantic nomination over an encrypted derived cache.

Embeds only authorized active source ranges. Original memory is never changed.
Local model only; no downloads or paid provider fallback. Native exact vector
search is an explicitly capacity-bounded experimental operating point, not an
unbounded/scalable ANN claim. Default retrieval never constructs this component.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import struct
from urllib.parse import urlparse

from atmem.core.storage import connect,row_factory_for
from .hybrid import HybridStoredContextEngine
from .semantic import SemanticHit,_normalize
from .service import StoredContextEngine


def _sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _chunks(text: str, maximum: int=1024):
    raw=text.encode()
    start=0
    while start < len(raw):
        end=min(len(raw),start+maximum)
        while end<len(raw) and raw[end]&0xC0==0x80:
            end-=1
        if end<=start:
            raise ValueError('invalid UTF-8 chunk bound')
        yield raw[start:end].decode()
        start=end


class SourcePartSemanticIndex:
    backend='source-part-native-exact-v1'

    def __init__(self,store,*,generation_id,manifest,path,model_identity):
        if store.policy.state!='encrypted':
            raise ValueError('persistent semantic cache requires encrypted household')
        row=store._conn.execute('SELECT * FROM context_view_generations WHERE generation_id=?',
                                (generation_id,)).fetchone()
        if row is None or row['state'] not in {'verified','active'} or (
            row['subject_id'],row['agent_id'],row['workspace_id']) != (
            manifest.scope.subject_id,manifest.scope.agent_id,manifest.scope.workspace_id):
            raise ValueError('semantic source generation is not authorized')
        self.store,self.generation_id=store,generation_id
        self.allowed=frozenset(manifest.authorized_unit_ids)
        self.all_generation_units_authorized=manifest.all_generation_units_authorized
        self.model=model_identity
        self.identity={'format':'source-part-native-exact-v1','generation_id':generation_id,
            'revision':int(row['revision']),'canonical_generation':manifest.generation,
            'scope':manifest.scope.to_dict(),'authorized_ids_sha256':_sha(sorted(self.allowed)),
            'model':model_identity,'chunk_bytes':1024,'capacity_vectors':10000}
        self.index_id='part-semantic-'+_sha(self.identity)
        self.path=Path(path)
        if self.path.expanduser().resolve() == Path(store.path).expanduser().resolve():
            raise ValueError('semantic cache must be separate from canonical storage')
        self._assert_current()
        from .cache_lifecycle import PART_CACHE_PREFIX, is_part_cache
        # Also adopts a pre-registry research cache when explicitly reopened;
        # never claim an arbitrary unknown directory was discovered or purged.
        for registry in store.semantic_index_paths(manifest.scope.subject_id):
            if Path(registry['index_path']).resolve()==self.path.resolve() and not is_part_cache(registry):
                raise ValueError('source-part cache cannot replace a different registered index kind')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.connection=connect(self.path,policy=store.policy,isolation_level=None)
        self.connection.row_factory=row_factory_for(store.policy)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.execute('PRAGMA secure_delete=ON')
        if self.connection.execute("SELECT 1 FROM sqlite_master WHERE name='vector_epochs'").fetchone():
            self.connection.close()
            raise ValueError('source-part cache cannot share a legacy semantic index database')
        store.register_semantic_index(manifest.scope.subject_id,str(self.path),
            active_epoch_id=PART_CACHE_PREFIX+generation_id)
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS part_index(
                id TEXT PRIMARY KEY,identity TEXT NOT NULL,state TEXT NOT NULL,dimensions INTEGER);
            CREATE TABLE IF NOT EXISTS part_vectors(
                index_id TEXT NOT NULL,source_id TEXT NOT NULL,part_id TEXT NOT NULL,
                chunk INTEGER NOT NULL,unit_ids TEXT NOT NULL,vector BLOB NOT NULL,
                PRIMARY KEY(index_id,source_id,part_id,chunk));
        ''')

    def close(self):
        self.connection.close()

    def _assert_current(self):
        row=self.store._conn.execute('SELECT state,revision,canonical_generation FROM context_view_generations WHERE generation_id=?',
                                    (self.generation_id,)).fetchone()
        if (row is None or row['state'] not in {'verified','active'}
                or int(row['revision'])!=self.identity['revision']
                or int(row['canonical_generation'])!=self.identity['canonical_generation']):
            raise ValueError('source semantic generation is stale, retired or deleted')
        current=self.store._conn.execute('''SELECT COUNT(*) FROM context_evidence_units
            WHERE generation_id=? AND lifecycle='active'
              AND unit_id IN (SELECT value FROM json_each(?))''',
            (self.generation_id,json.dumps(sorted(self.allowed)))).fetchone()[0]
        if current!=len(self.allowed):
            raise ValueError('source semantic authorization is stale or deleted')

    def _documents(self):
        # Eligibility is inside the SQL before source bytes are read. No source
        # gap is added back: a retained but withheld range is not model input.
        eligibility=('' if self.all_generation_units_authorized else
                     ' AND u.unit_id IN (SELECT value FROM json_each(?))')
        parameters=((self.generation_id,) if self.all_generation_units_authorized else
                    (self.generation_id,json.dumps(sorted(self.allowed))))
        rows=self.store._conn.execute('''SELECT u.unit_id,r.source_id,r.part_id,
            r.start_offset,r.end_offset,p.content_bytes
            FROM context_evidence_units u CROSS JOIN context_unit_ranges ur
              ON ur.generation_id=u.generation_id AND ur.unit_id=u.unit_id
            CROSS JOIN context_source_ranges r ON r.range_id=ur.range_id
            CROSS JOIN context_source_parts p ON p.source_id=r.source_id AND p.part_id=r.part_id
            WHERE u.generation_id=? AND u.kind='raw_state' AND u.lifecycle='active'
            '''+eligibility+''' ORDER BY r.source_id,r.part_id,r.start_offset,r.end_offset,u.unit_id''',
            parameters)
        groups=OrderedDict()
        for row in rows:
            if row['unit_id'] not in self.allowed:
                raise ValueError('generation-wide authorization flag does not match allowed IDs')
            key=(row['source_id'],row['part_id'])
            ids,texts,last_end=groups.setdefault(key,[[],[],0])
            start,end=int(row['start_offset']),int(row['end_offset'])
            if row['unit_id'] not in ids:
                ids.append(row['unit_id'])
            if end>last_end:
                texts.append(bytes(row['content_bytes'])[max(start,last_end):end].decode())
                groups[key][2]=end
        for (source,part),(ids,texts,_) in groups.items():
            for number,chunk in enumerate(_chunks('\n\n'.join(texts))):
                yield source,part,number,tuple(ids),chunk

    def build(self,embedder,*,progress=None):
        self._assert_current()
        if (embedder.identity != self.model or
            urlparse(self.model.get('endpoint','')).hostname!='127.0.0.1'
            or self.model.get('truncate') is not False):
            raise ValueError('explicit pinned local nontruncating embedder required')
        previous=self.connection.execute('SELECT * FROM part_index WHERE id=?',(self.index_id,)).fetchone()
        if previous is not None and previous['state']=='ready':
            raise ValueError('index already built; do not rerun embeddings')
        self.connection.execute('INSERT OR IGNORE INTO part_index VALUES(?,?,?,NULL)',
            (self.index_id,json.dumps(self.identity,sort_keys=True),'building'))
        existing={(r[0],r[1],r[2]) for r in self.connection.execute(
            'SELECT source_id,part_id,chunk FROM part_vectors WHERE index_id=?',(self.index_id,))}
        batch=[]
        count=len(existing)
        dimensions=int(previous['dimensions'] or 0) if previous else 0
        def commit(items):
            nonlocal dimensions,count
            if count+len(items)>10000:
                raise ValueError('declared semantic cache capacity exceeded')
            self._assert_current()
            embedder.verify_identity()
            vectors=embedder.embed_documents([row[4] for row in items])
            self._assert_current()
            if len(vectors)!=len(items):
                raise ValueError('embedding count mismatch')
            dimensions=dimensions or len(vectors[0])
            prepared=[(self.index_id,s,p,n,json.dumps(ids),
                struct.pack('<'+'f'*dimensions,*_normalize(v,dimensions)))
                for (s,p,n,ids,_),v in zip(items,vectors)]
            self.connection.execute('BEGIN IMMEDIATE')
            try:
                self.connection.executemany('INSERT INTO part_vectors VALUES(?,?,?,?,?,?)',prepared)
                self.connection.execute('UPDATE part_index SET dimensions=? WHERE id=?',(dimensions,self.index_id))
                self.connection.execute('COMMIT')
            except BaseException:
                self.connection.execute('ROLLBACK');raise
            count+=len(prepared)
            if progress: progress(count)
        for row in self._documents():
            if row[:3] in existing:
                continue
            batch.append(row)
            if len(batch)==32:
                commit(batch);batch=[]
        if batch: commit(batch)
        if not count:
            raise ValueError('no authorized active raw ranges to index')
        self.connection.execute("UPDATE part_index SET state='ready' WHERE id=?",(self.index_id,))
        return {'index_id':self.index_id,'vectors':count,'dimensions':dimensions,
                'model_identity':self.model,'source_memory_mutated':False}

    def nominate(self,vector,*,allowed_unit_ids,limit=128,candidate_limit=128):
        self._assert_current()
        if frozenset(allowed_unit_ids)!=self.allowed or not 1<=limit<=candidate_limit<=200:
            raise ValueError('authorization or semantic request bounds changed')
        row=self.connection.execute('SELECT * FROM part_index WHERE id=?',(self.index_id,)).fetchone()
        if row is None or row['state']!='ready' or json.loads(row['identity'])!=self.identity:
            raise ValueError('source-coherent semantic cache unavailable or stale')
        dimensions=int(row['dimensions'])
        normalized=_normalize(vector,dimensions)
        import sqlite_vec
        self.connection.enable_load_extension(True)
        try: sqlite_vec.load(self.connection)
        finally: self.connection.enable_load_extension(False)
        rows=self.connection.execute('''SELECT source_id,part_id,unit_ids,
            vec_distance_cosine(vector,?) distance FROM part_vectors WHERE index_id=?
            ORDER BY distance,source_id,part_id,chunk LIMIT ?''',
            (struct.pack('<'+'f'*dimensions,*normalized),self.index_id,min(512,max(60,candidate_limit*4))))
        seen_parts,seen_ids,hits=set(),set(),[]
        for result in rows:
            if result['distance'] is None or not math.isfinite(result['distance']):
                raise ValueError('invalid semantic cache distance')
            key=(result['source_id'],result['part_id'])
            if key in seen_parts: continue
            seen_parts.add(key)
            for identity in json.loads(result['unit_ids']):
                if identity not in self.allowed:
                    raise ValueError('semantic cache nominated unauthorized unit')
                if identity in seen_ids: continue
                hits.append(SemanticHit(identity,1.-result['distance']));seen_ids.add(identity)
                if len(hits)==limit: return tuple(hits)
        return tuple(hits)


class SourceCoherentHybridFactory:
    """Trusted host configuration; no query/tenant-controlled import or endpoint."""
    def __init__(self,*,directory,embedder):
        self.directory=Path(directory)
        self.embedder=embedder

    def nominate(self,store,generation_id,query,manifest,limit):
        """Independent read-only discovery; never conditioned on lexical status."""
        index=SourcePartSemanticIndex(store,generation_id=generation_id,manifest=manifest,
            path=self.directory/(generation_id+'.db'),model_identity=self.embedder.identity)
        try:
            self.embedder.verify_identity()
            hits=index.nominate(self.embedder.embed_query(query),
                allowed_unit_ids=frozenset(manifest.authorized_unit_ids),limit=limit,candidate_limit=limit)
            return tuple(hit.unit_id for hit in hits)
        finally:index.close()

    def __call__(self,store,generation_id):
        factory=self
        class Engine:
            identity={'engine':'source-coherent-hybrid-v1','optional':True}
            def select(self,request,manifest):
                index=SourcePartSemanticIndex(store,generation_id=generation_id,manifest=manifest,
                    path=factory.directory/(generation_id+'.db'),model_identity=factory.embedder.identity)
                try:
                    factory.embedder.verify_identity()
                    vector=factory.embedder.embed_query(request.query)
                    return HybridStoredContextEngine(store,generation_id=generation_id,semantic_index=index,
                        query=request.query,query_vector=vector,semantic_candidates=64).select(request,manifest)
                finally: index.close()
        return Engine()
