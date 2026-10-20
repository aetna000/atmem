"""Replay retained initial packs and inspect lexical ranking without a model."""
import ast
import base64
from hashlib import sha256
import inspect
import json
import zlib

RUN='external-windows-confirmation-v3-packing-replay-audit-v1-20261018'


def retained_generation(events):
    from atmem.core.canonical import canonical_json
    transports=[e for e in events if e['envelope']['event_type']=='external.confirmation_v3_stage_transport']
    if len(transports)!=1 or transports[0]['envelope']['payload']['exit_code']!=0:
        raise ValueError('exact successful original stage transport required')
    transport=transports[0];expected=transport['envelope']['payload']['streams']['stdout']
    by_id={e['object_id']:e for e in events};parts=[];size=0
    if not 0<expected['bytes']<=128_000_000:raise ValueError('bounded stage transport required')
    for receipt in expected['receipts']:
        event=by_id[receipt['object_id']];envelope=event['envelope'];payload=envelope['payload']
        if (envelope['event_type']!='external.confirmation_v3_stage_chunk'
                or envelope['run_id']!=transport['envelope']['run_id'] or receipt['run_id']!=envelope['run_id']
                or sha256(canonical_json(payload).encode()).hexdigest()!=receipt['payload_sha256']
                or payload['stream']!='stdout' or payload['offset']!=size):
            raise ValueError('original stage chunk role, receipt or order differs')
        raw=base64.b64decode(payload['bytes_base64'],validate=True)
        if not 0<len(raw)<=3_000_000:raise ValueError('bounded original stage chunk required')
        parts.append(raw);size+=len(raw)
    raw=b''.join(parts)
    if len(raw)!=expected['bytes'] or sha256(raw).hexdigest()!=expected['sha256']:
        raise ValueError('complete original stage transport differs')
    case=json.loads(raw)['cases']['tools']
    decoder=zlib.decompressobj()
    generation=decoder.decompress(base64.b64decode(case['generation_zlib_base64'],validate=True),64_000_001)
    if (len(generation)>64_000_000 or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail):
        raise ValueError('bounded exact original generation required')
    return json.loads(generation),case


def lexical_inspector():
    from atmem.knowledge.code import packing
    source=inspect.getsource(packing.pack_generation)
    marker='    executable = [r for r in candidates'
    if source.count(marker)!=1:raise ValueError('known frozen lexical nomination boundary required')
    diagnostic=source[:source.index(marker)]+'''    ranked=sorted(candidates,key=lambda r:(-lexical(r),r['path'],r['start']))
    return {'query_terms':sorted(terms),'top_lexical':[{'name':r['name'],'path':r['path'],
        'start':r['start'],'score':lexical(r),'explicit':r['explicit'],
        'name_matches':sorted(r['label'] & terms),'body_matches':sorted(r['terms'] & terms),
        'owner_matches':sorted(r['owner'] & terms)} for r in ranked[:12]]}
'''
    namespace=dict(vars(packing));exec(compile(diagnostic,'<frozen-packer-lexical-inspection>','exec'),namespace)
    return namespace['pack_generation'],diagnostic


def main():
    from pathlib import Path
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from atmem.knowledge.code import packing
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    if sha256(Path(inspect.getsourcefile(packing)).read_bytes()).hexdigest()!=job['packing_sha256']:
        raise ValueError('frozen installed packer identity differs')
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('pack replay audit already attempted')
    records=vault.inspect(principal,'external-windows-confirmation-v3-execution-lock-v1-20261018')
    lock=next(e['envelope']['payload'] for e in records if e['envelope']['event_type']=='external.v3_execution_manifest_frozen')
    inspector,diagnostic=lexical_inspector()
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.v3_packing_replay_planned',{'driver_source':job['driver_source'],
        'packing_sha256':job['packing_sha256'],'diagnostic_function':diagnostic,
        'selection':'first original stage for every declared identity','models_or_grades_repeated':0,
        'interpretation':'reused development diagnosis; no new confirmation claim'})
    seen=set();results=[]
    for row in lock['staged_blocks']:
        identity=row['block']['instance_id']
        if identity in seen:continue
        seen.add(identity)
        generation,case=retained_generation(vault.inspect(principal,row['task_run']))
        task=lock['staging_manifest']['issues'][identity]
        if case['prepared']['request']['task']!=task:raise ValueError('original task binding differs')
        reproduced=packing.pack_generation(generation,task,budget=4096)
        original=case['prepared']['package']['content']
        result={'identity':identity,'stage_run':row['task_run'],'query_matches':True,
                'reproduces_original_pack':reproduced==original,'original_bytes':len(original.encode()),
                'reproduced_sha256':sha256(reproduced.encode()).hexdigest(),
                **inspector(generation,task,budget=4096)}
        save('external.v3_packing_replay_case',result);results.append(result)
        print(json.dumps(result),flush=True)
    save('external.v3_packing_replay_completed',{'identities':len(results),
        'all_original_packs_reproduced':len(results)==19 and all(r['reproduces_original_pack'] for r in results),
        'models_or_grades_repeated':0})


if __name__=='__main__':main()
