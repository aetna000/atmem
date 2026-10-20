"""Counterfactual pack-only development check; never a model performance result."""
from hashlib import sha256
import inspect
import json

RUN='external-windows-strict-identifier-pack-replay-v1-20261018'


def main():
    from pathlib import Path
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from atmem.knowledge.code import packing
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.packing_replay_audit import retained_generation
    baseline_sha=sha256(Path(inspect.getsourcefile(packing)).read_bytes()).hexdigest()
    if baseline_sha!=job['baseline_packing_sha256']:raise ValueError('frozen installed baseline differs')
    namespace={'__name__':'strict_identifier_candidate_replay'}
    exec(compile(job['candidate_source'],'<strict-identifier-candidate>','exec'),namespace)
    candidate=namespace['pack_generation']
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('candidate pack replay already attempted')
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    records=vault.inspect(principal,'external-windows-confirmation-v3-execution-lock-v1-20261018')
    lock=next(e['envelope']['payload'] for e in records if e['envelope']['event_type']=='external.v3_execution_manifest_frozen')
    save('external.strict_identifier_replay_planned',{'driver_source':job['driver_source'],
        'candidate_source':job['candidate_source'],'baseline_packing_sha256':baseline_sha,
        'candidate_packing_sha256':sha256(job['candidate_source'].encode()).hexdigest(),
        'interpretation':'reused development corpus; pack bytes are not input-token or task-quality results',
        'models_or_grades_repeated':0,'mutates_installed_baseline':False})
    seen=set();results=[]
    for row in lock['staged_blocks']:
        identity=row['block']['instance_id']
        if identity in seen:continue
        seen.add(identity)
        generation,case=retained_generation(vault.inspect(principal,row['task_run']))
        task=lock['staging_manifest']['issues'][identity]
        old=packing.pack_generation(generation,task,budget=4096)
        if old!=case['prepared']['package']['content']:raise ValueError('original baseline does not reproduce')
        new=candidate(generation,task,budget=4096)
        if len(new.encode())>4096:raise ValueError('candidate exceeds unchanged byte budget')
        result={'identity':identity,'stage_run':row['task_run'],'baseline_content':old,'candidate_content':new,
            'baseline_bytes':len(old.encode()),'candidate_bytes':len(new.encode()),'changed':old!=new}
        save('external.strict_identifier_replay_case',result);results.append(result)
        def first(content):return next((line for line in content.splitlines() if line.startswith('[AtMem structure ')),None)
        print(json.dumps({'identity':identity,'changed':old!=new,'baseline_bytes':len(old.encode()),
            'candidate_bytes':len(new.encode()),'baseline_first_reference':first(old),'candidate_first_reference':first(new)}),flush=True)
    summary={'identities':len(results),'changed_packs':sum(r['changed'] for r in results),
        'all_original_packs_reproduced':len(results)==19,'models_or_grades_repeated':0,
        'token_or_quality_gain_established':False}
    save('external.strict_identifier_replay_completed',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
