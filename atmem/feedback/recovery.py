"""Owner-previewed source cleanup and conservative post-restore quarantine.

Only the authenticated evidence controller may purge retained content. Ordinary
canonical forgetting invalidates future selection/enforcement; historical flight
retention remains separately controlled. External providers/backups are not
silently erased. No model-facing tool exposes these owner operations.
"""
from contextlib import nullcontext
from hashlib import sha256

from atmem.core.canonical import canonical_json
from atmem.evidence.models import EvidenceOperation
from atmem.feedback.store import FeedbackError, snapshot


CONTROL_KINDS = frozenset({'audit','agent_grant','evaluation_budget','proxy_handler','proxy_write_hold','verifier','attribution_verifier','source_revocation','restore_binding'})
AUTH_FIELDS = frozenset({'scope','actor_id','principal_id','tenant_id','subject_id','agent_id','workspace_id','verifier_id','recipient_id'})


def revocation_key(source_id, kind='memory'):
    return sha256((kind+'\0'+source_id).encode()).hexdigest()


def ensure_sources_not_revoked(tx, sources):
    if any(tx.get('source_revocation',revocation_key(source.source_id)) is not None for source in sources):
        raise FeedbackError('source_revoked')


def _references(value, field='', *, source_domain='memory_source', artifact_domain='artifact'):
    """Read typed protocol links, never instructions/IDs inside raw evidence.

    A business tool may legitimately return ``source_id`` or ``outcome_id``.
    Those payload fields are not AtMem authority and cannot drive deletion.
    """
    if field in AUTH_FIELDS:return set()
    if type(value) is dict:
        form=value.get('format','')
        if type(form) is str and form.startswith('atmem-rag-'):
            source_domain='rag_source'
        elif form=='atmem-feedback-source-revision-v1':
            source_domain='memory_source'
        if value.get('kind') in ('rule','profile'):
            artifact_domain=value['kind']
        elif form=='atmem-feedback-rule-candidate-v1':artifact_domain='rule'
        elif form=='atmem-feedback-profile-candidate-v1':artifact_domain='profile'
        observation=form=='atmem-feedback-action-observation-v1'
        execution='invocation' in value and 'receipt_id' in value
        result=set()
        for key,item in value.items():
            if key in {'raw','arguments','evidence','encrypted_bundle','reported_result'}:
                continue
            if key=='result' and (observation or execution):
                continue
            result.update(_references(item,key,source_domain=source_domain,artifact_domain=artifact_domain))
        return result
    if type(value) is list:
        result=set()
        for item in value:result.update(_references(item,field,source_domain=source_domain,artifact_domain=artifact_domain))
        return result
    domains={'source_id':source_domain,'record_id':'memory_source','record_ids':'memory_source',
             'receipt_id':'receipt','receipt_ids':'receipt','evidence_id':'receipt','evidence_ids':'receipt','context_receipt_id':'receipt',
             'rule_id':'rule','rule_ids':'rule','policy':'rule','profile_id':'profile','profile_ids':'profile',
             'artifact_id':artifact_domain,'outcome_id':'outcome','outcome_ids':'outcome','predecessor_id':'outcome',
             'outcome_sha256':'outcome_digest','candidate_sha256':'artifact_digest','artifact_sha256':'artifact_digest',
             'manifest_sha256':'manifest_digest','preview_sha256':'preview_digest',
             'activation_id':'receipt','consent_id':'consent','export_id':'export',
             'attribution_id':'attribution','evaluation_attempt_id':'evaluation_attempt'}
    if type(value) is str and field in domains:
        return {(domains[field],value)}
    return set()


def _key_identity(row):
    kind=row['kind']
    domain={'rag_source':'rag_source','outcome':'outcome','outcome_revision':'outcome_digest',
            'evaluation_manifest':'manifest_digest','evaluation_attempt':'evaluation_attempt','export_consent':'consent','example_export':'export','attribution':'attribution',
            'rule_proposal':'rule','rule_lifecycle':'rule','profile_proposal':'profile','profile_lifecycle':'profile'}.get(kind)
    if kind in {'context_evidence','rag_receipt','readback_evidence','verification','proxy_execution',
                'qualification','activation','verification_attempt','rag_attempt','reported_usage',
                'attribution_verification','attribution_attempt'}:
        domain='receipt'
    return (domain or 'row:'+kind,row['key'])


def _owned_identities(row):
    """Only a defining record owns an identity; cached/copied results do not."""
    result={_key_identity(row)}
    if row['kind'] in ('rule_proposal','profile_proposal'):
        digest=row['value'].get('candidate_sha256')
        if type(digest) is str:result.add(('artifact_digest',digest))
    if row['kind']=='outcome_revision':
        outcome_id=row['value'].get('outcome',{}).get('outcome_id')
        if type(outcome_id) is str:result.add(('outcome',outcome_id))
    if row['kind']=='evaluation_trial':
        attempt_id=row['value'].get('evaluation_attempt_id')
        if type(attempt_id) is str:result.add(('evaluation_attempt',attempt_id))
    if row['kind']=='attribution_lineage':
        attribution_id=row['value'].get('attribution_id')
        if type(attribution_id) is str:result.add(('attribution',attribution_id))
    return result


class FeedbackRecovery:
    def __init__(self,feedback):self.feedback=feedback

    def _plan(self,tx,source_id,source_kind):
        from atmem.contracts.feedback import identifier
        identifier(source_id)
        if source_kind not in ('memory','rag'):raise ValueError('known source kind required')
        if source_kind=='memory':
            if self.feedback.memory is None:raise FeedbackError('missing_evidence')
            source=self.feedback.memory.store.get_record(tx.scope.subject_id,source_id)
            if source is None or source['status']!='active':raise FeedbackError('source_unavailable')
            if source['raw'].get('authority_scope')!=tx.scope.authority_scope().to_dict():raise FeedbackError('denied')
        else:
            source=tx.get('rag_source',source_id)
            if source is None:raise FeedbackError('source_unavailable')
        records=list(tx.store.documents(partition_id=tx.scope.partition))
        seeds={('memory_source' if source_kind=='memory' else 'rag_source',source_id)}
        selected={}
        changed=True
        while changed:
            changed=False
            for row in records:
                if row['kind'] in CONTROL_KINDS or row['object_id'] in selected:continue
                references=_references(row['value'],source_domain='rag_source' if row['kind'].startswith('rag_') else 'memory_source',
                                       artifact_domain='rule' if row['kind'].startswith('rule_') else 'profile' if row['kind'].startswith('profile_') else 'artifact')
                if _key_identity(row) in seeds or references & seeds:
                    selected[row['object_id']]=row
                    seeds.update(_owned_identities(row))
                    changed=True
        for row in selected.values():
            if row['kind'] in ('rule_lifecycle','profile_lifecycle'):
                current=tx.get(row['kind'],row['key'])
                if current and (current['state'] in ('active','qualified') or current.get('block_covered')):
                    # Purging the policy must never turn a covered denial into
                    # an unconfigured allow. Withdrawal is a separate owner act.
                    raise FeedbackError('dependent_policy_requires_revocation')
        counts={}
        for row in selected.values():counts[row['kind']]=counts.get(row['kind'],0)+1
        inflight=[row['key'] for row in selected.values() if row['kind']=='proxy_execution' and row['value'].get('status')=='uncertain']
        value={'format':'atmem-feedback-forget-preview-v1','scope':tx.scope.to_dict(),'source_id':source_id,
               'source_kind':source_kind,'source_sha256':sha256(canonical_json(source).encode()).hexdigest(),
               'objects':len(selected),'kinds':counts,'inflight_receipts':inflight[:128],
               'effects_cannot_be_undone':True,'external_sources_and_backups':'not_erased'}
        value['preview_sha256']=sha256(canonical_json({'preview':value,'objects':sorted(selected)}).encode()).hexdigest()
        return value,selected,source

    def preview_forget(self,owner_credential,scope,*,source_id,source_kind='memory'):
        canonical=self.feedback.memory.store.transaction() if self.feedback.memory is not None else nullcontext()
        with canonical,self.feedback.owner_transaction(owner_credential,scope,operation=EvidenceOperation.DELETE) as (tx,principal):
            value,_,_=self._plan(tx,source_id,source_kind)
            tx.audit(principal.principal_id,'preview_forget_source',allowed=True)
            return value

    def forget(self,owner_credential,scope,*,source_id,preview_sha256,confirm_sha256,source_kind='memory'):
        canonical=self.feedback.memory.store.transaction() if self.feedback.memory is not None else nullcontext()
        with canonical,self.feedback.owner_transaction(owner_credential,scope,operation=EvidenceOperation.DELETE) as (tx,principal):
            if preview_sha256 != confirm_sha256:
                raise FeedbackError('stale_preview')
            tombstone_key=revocation_key(source_id,source_kind)
            prior=tx.get('source_revocation',tombstone_key)
            if prior is not None and prior['preview_sha256']==preview_sha256:
                if source_kind=='memory' and self.feedback.memory is None:
                    raise FeedbackError('missing_evidence')
                present=(self.feedback.memory.store.get_record(scope.subject_id,source_id) if source_kind=='memory'
                         else tx.get('rag_source',source_id))
                if present is not None and present.get('status','active')=='active':
                    raise FeedbackError('restored_source_requires_new_preview')
                if prior.get('canonical_commit')=='pending':
                    prior={**prior,'canonical_commit':'verified','completed_at':int(self.feedback.clock())}
                    tx.put('source_revocation',tombstone_key,prior,expected_revision=tx.revision('source_revocation',tombstone_key))
                return prior
            value,selected,source=self._plan(tx,source_id,source_kind)
            if value['preview_sha256']!=preview_sha256 or confirm_sha256!=preview_sha256:
                raise FeedbackError('stale_preview')
            # The protected tombstone is committed with removal. On any failure
            # canonical source mutation rolls back; no false deletion is reported.
            if source_kind=='memory':
                self.feedback.memory.forget_record(scope.subject_id,source_id,actor=principal.principal_id)
            idempotency={row['key']:row['value']['payload_sha256'] for row in selected.values() if row['kind']=='idempotency'}
            tx.store.purge_partition_objects(scope.partition,tuple(selected))
            removed={(row['kind'],row['key']) for row in selected.values()}
            for key in removed:tx.rows.pop(key,None)
            for key,payload_sha256 in idempotency.items():
                tx.put('idempotency',key,{'payload_sha256':payload_sha256,'result':{},'tombstone':True},expected_revision=0)
            receipt={'format':'atmem-feedback-forget-receipt-v1','source_kind':source_kind,
                     'source_id_sha256':sha256(source_id.encode()).hexdigest(),'preview_sha256':preview_sha256,
                     'removed_objects':len(selected),'current_registered_rows_removed':True,
                     'inflight_effects_not_undone':len(value['inflight_receipts']),
                     'external_sources_backups_and_forensic_erasure':'not_guaranteed',
                     'canonical_commit':'pending' if source_kind=='memory' else 'not_applicable',
                     'actor_id':principal.principal_id,'generation':source.get('generation',0)+1}
            tx.put('source_revocation',tombstone_key,receipt,expected_revision=tx.revision('source_revocation',tombstone_key))
            tx.audit(principal.principal_id,'forget_source',allowed=True,detail={'removed_objects':len(selected)})
        if source_kind=='memory':
            # Canonical commit has now completed. A failed finalization leaves a
            # durable pending tombstone and never an asserted successful erasure.
            with self.feedback.memory.store.transaction(),self.feedback.owner_transaction(owner_credential,scope,operation=EvidenceOperation.DELETE) as (tx,principal):
                current=self.feedback.memory.store.get_record(scope.subject_id,source_id)
                if current is not None and current.get('status')=='active':
                    raise FeedbackError('source_deletion_not_verified')
                receipt={**receipt,'canonical_commit':'verified','completed_at':int(self.feedback.clock())}
                tx.put('source_revocation',tombstone_key,receipt,expected_revision=tx.revision('source_revocation',tombstone_key))
        return receipt

    def reconcile_after_restore(self,owner_credential,scope,*,restore_id):
        """Never infer that restored active authority is still safe to execute."""
        from atmem.contracts.feedback import identifier
        identifier(restore_id)
        with self.feedback.owner_transaction(owner_credential,scope,allow_restore=True) as (tx,principal):
            from atmem.feedback.home_binding import home_restore_binding
            binding=home_restore_binding(self.feedback)
            if binding is not None and binding['mode']=='restore_read_only':
                raise FeedbackError('restore_requires_adoption')
            def reconcile():
                quarantined=[]
                barrier=max((row['sequence'] for row in tx.rows.values()),default=0)
                for kind in ('rule','profile'):
                    for row in tx.iter_kind(kind+'_lifecycle'):
                        if row['state'] not in ('active','qualified') and not row.get('block_covered'):continue
                        row={**row,'state':'suspended','generation':row['generation']+1,
                             'block_covered':True,'qualification_barrier':barrier,
                             'reason':'restore_requires_requalification','actor_id':principal.principal_id}
                        tx.put(kind+'_lifecycle',row['artifact_id'],row,expected_revision=tx.revision(kind+'_lifecycle',row['artifact_id']))
                        quarantined.append({'kind':kind,'artifact_id':row['artifact_id']})
                counts={}
                for kind,field in (('agent_grant','active'),('export_consent','active'),('call_approval','used'),('rag_source','active')):
                    counts[kind]=0
                    for (row_kind,key),stored in list(tx.rows.items()):
                        if row_kind!=kind or stored['deleted']:continue
                        value=snapshot(stored['value'])
                        if kind=='call_approval':value['used']=True
                        else:value[field]=False
                        if kind=='rag_source':value['generation']+=1
                        tx.put(kind,key,value,expected_revision=tx.revision(kind,key))
                        counts[kind]+=1
                tx.put('restore_binding','home',{'binding_sha256':binding['binding_sha256'] if binding else None},
                       expected_revision=tx.revision('restore_binding','home'))
                if home_restore_binding(self.feedback)!=binding:
                    raise FeedbackError('restore_state_changed')
                tx.audit(principal.principal_id,'restore_reconciliation',allowed=True)
                return {'status':'requalification_required','quarantined':quarantined,'disabled':counts,
                        'restore_id':restore_id,'uncertain_writes':'not_reexecuted','ordinary_core_recall':'unchanged'}
            return tx.once('restore_reconciliation',restore_id,{'actor_id':principal.principal_id,'binding':binding},reconcile)
