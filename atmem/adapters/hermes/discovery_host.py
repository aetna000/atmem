"""Encrypted, administrator-created leases for read-only evidence discovery."""
from __future__ import annotations

import copy
import json
import time
import uuid

from atmem.context_engine.contracts import ContextRequestV3
from atmem.context_engine.navigator import NavigationBudget
from atmem.contracts import RetrievalBudget
from .binding import _identifier


class DiscoveryHost:
    def _discovery_authority(self, row):
        binding=self._binding(row)
        binding._scope()
        state,warning=self.manager.effective_state()
        if (row['revoked'] or row['expires_at']<=time.time() or not binding.enabled
                or not binding.influence or warning or not state.mode.influences_agent
                or binding.memory_engine!='context-v3'):
            raise PermissionError('evidence discovery is inactive or unauthorized')
        return binding

    def open_discovery(self, principal, binding_id, *, query, session_id, turn_id,
                       allow_remote_assessment=False):
        """Trusted host setup, never a model-callable mint/reset operation."""
        self._admin(principal)
        if type(allow_remote_assessment) is not bool:raise TypeError('explicit egress selection required')
        if not isinstance(query,str) or not query.strip() or len(query.encode())>8192:
            raise ValueError('discovery query requires 1..8192 UTF-8 bytes')
        session_id=_identifier(session_id,'session_id');turn_id=_identifier(turn_id,'turn_id')
        with self._locked():
            row=self._load(_identifier(binding_id,'binding_id'));self._owner(principal,row)
            binding=self._discovery_authority(row)
            with binding.v3().memory() as (memory,scope):
                generation=memory.context_generation(scope)
            leases={key:value for key,value in row.get('discovery_leases',{}).items()
                    if value['expires_at']>time.time()}
            if len(leases)>=32:raise RuntimeError('too many active discovery leases')
            lease_id=uuid.uuid4().hex
            leases[lease_id]={'session_id':session_id,'turn_id':turn_id,'query':query,
                'binding_generation':row['generation'],
                'source_generation':int(generation['canonical_generation']),
                'view_generation':str(generation['generation_id']),
                'view_revision':int(generation['revision']),
                'expires_at':min(time.time()+900,row['expires_at']),
                'operations_used':0,'bytes_used':0,'max_operations':8,'max_bytes':96000}
            leases[lease_id]['allow_remote_assessment']=allow_remote_assessment
            row['discovery_leases']=leases;self._save(row)
            return {'format':'atmem-discovery-lease-v1','lease_id':lease_id,
                    'expires_at':leases[lease_id]['expires_at']}

    def _live_discovery(self, token, lease_id):
        row=self._authenticate(token);binding=self._discovery_authority(row)
        lease=row.get('discovery_leases',{}).get(lease_id)
        if (lease is None or lease['expires_at']<=time.time()
                or lease['binding_generation']!=row['generation']):
            raise PermissionError('discovery lease is expired or revoked')
        return row,binding,lease

    def dispatch_discovery(self, token, operation, body):
        field={'discovery-search':'query','discovery-inspect':'unit_id'}.get(operation)
        if field is None or set(body)!={'lease_id',field}:
            raise ValueError('invalid discovery operation or fields')
        lease_id=_identifier(body['lease_id'],'lease_id')
        value=body[field]
        maximum=8192 if field=='query' else 512
        if not isinstance(value,str) or not value.strip() or len(value.encode())>maximum:
            raise ValueError('invalid discovery argument')
        # Reserve before slow work. A crash retains the reservation, so restart
        # and concurrent requests cannot reset or overspend a session budget.
        with self._locked():
            row,binding,lease=self._live_discovery(token,lease_id)
            reserved=min(16000,lease['max_bytes']-lease['bytes_used'])
            if lease['operations_used']>=lease['max_operations'] or reserved<512:
                raise RuntimeError('discovery lease budget exhausted')
            lease['operations_used']+=1;lease['bytes_used']+=reserved
            serial=lease['operations_used'];self._save(row)
            frozen=copy.deepcopy(lease)
        operation_started=time.monotonic()
        with binding.v3().memory() as (memory,scope):
            def authorize(request):
                with self._locked():
                    self._live_discovery(token,lease_id)
                generation=memory.context_generation(scope)
                if (str(generation['generation_id'])!=frozen['view_generation']
                        or int(generation['revision'])!=frozen['view_revision']
                        or int(generation['canonical_generation'])!=frozen['source_generation']):
                    raise PermissionError('discovery source generation changed')
                return request.scope==scope
            request=ContextRequestV3(context_id='discovery-'+lease_id,
                request_id=f'discovery-{lease_id}-{serial}',scope=scope,
                query=frozen['query'],profile_id='context-fast',mode='active',
                generation=frozen['source_generation'],turn_id=frozen['turn_id'],
                budget=RetrievalBudget(total_candidates=200,context_bytes=reserved))
            nominate=getattr(self.context_engine_factory,'nominate',None)
            semantic=(lambda query,manifest,limit:nominate(memory.store,frozen['view_generation'],
                       query,manifest,limit)) if callable(nominate) else None
            assessor=getattr(self,'state_assessor',None)
            if assessor is not None and not frozen.get('allow_remote_assessment'):
                raise PermissionError('remote state assessment was not explicitly authorized')
            raw_budget=reserved-6000 if (assessor is not None or getattr(self,'source_time_frames',False)) else reserved
            if raw_budget<512:raise RuntimeError('state assessment response budget exhausted')
            session=memory.open_evidence_discovery(request,authorize=authorize,
                budget=NavigationBudget(1,raw_budget,120000),semantic_nominate=semantic,
                source_bundles=getattr(self,'source_bundles',False))
            result=session.search(value,limit=32) if field=='query' else session.inspect(value)
            if assessor is not None and result['evidence']:
                from atmem.context_engine.state_assessment import validate_state_assessment
                authorize(request)
                try:
                    if time.monotonic()-operation_started>=50:
                        result['state_assessment']={'status':'deferred_due_to_time_budget',
                                                   'assurance':'not_assessed','canonical_storage':False}
                    else:
                        memory.store.append_audit_event(subject_id=scope.subject_id,
                            event_type='context.discovery.state_egress.authorized',actor=scope.agent_id,
                            turn_id=frozen['turn_id'],payload={'request_id':request.request_id,
                                'provider':getattr(assessor,'identity',{'provider':'application-owned'}),
                                'fields':['question','unit_id','text','source_range'],
                                'evidence_ids':[r['unit_id'] for r in result['evidence']],
                                'explicit_lease_egress_permission':True})
                        # Provider-owned mutable objects cannot redefine the
                        # host's already-authorized source quotations.
                        evidence_snapshot=copy.deepcopy(result['evidence'])
                        assessment=copy.deepcopy(assessor(frozen['query'],copy.deepcopy(evidence_snapshot)))
                        validate_state_assessment(assessment,evidence_snapshot)
                        result['state_assessment']=assessment
                except Exception:
                    result['state_assessment']={'status':'unavailable_or_rejected',
                        'assurance':'not_assessed','canonical_storage':False}
                authorize(request)
                if len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode())>reserved:
                    result['state_assessment']={'status':'assessment_output_exceeds_budget',
                        'assurance':'not_assessed','canonical_storage':False}
                memory.store.append_audit_event(subject_id=scope.subject_id,
                    event_type='context.discovery.state_assessment.prepared',actor=scope.agent_id,
                    turn_id=frozen['turn_id'],payload={'response':result,'delivery_assurance':'prepared_only'})
            if getattr(self,'source_time_frames',False):
                from atmem.context_engine.temporal_frames import question_date,temporal_frames
                as_of=question_date(frozen['query'])
                result['temporal_evidence']={'as_of_origin':'question_date_prefix' if as_of else 'not_supplied',
                    'frames':temporal_frames(result['evidence'],as_of=as_of) if as_of else [],
                    'assurance':'date_order_computed_from_quoted_intervals',
                    'state_identity_or_truth_verified':False,
                    'supported_forms':['ISO date','English named month date'],
                    'boundary_inclusivity':'not_inferred'}
                if len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode())>reserved:
                    if 'state_assessment' in result:
                        result['state_assessment']={'status':'omitted_to_preserve_computed_temporal_evidence',
                            'assurance':'not_assessed','canonical_storage':False}
                    if len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode())>reserved:
                        result['temporal_evidence']={'status':'temporal_frames_exceed_response_budget'}
                authorize(request)
                memory.store.append_audit_event(subject_id=scope.subject_id,
                    event_type='context.discovery.temporal_frames.prepared',actor=scope.agent_id,
                    turn_id=frozen['turn_id'],payload={'response':result,'delivery_assurance':'prepared_only'})
            if time.monotonic()-operation_started>=120:
                raise RuntimeError('discovery operation time budget exhausted')
            # The ephemeral primitive's number is deliberately separate from
            # the durable lease serial; preserve the audited response bytes.
            size=len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode())
            if size>reserved:raise RuntimeError('discovery response exceeded its reservation')
            authorize(request)
            with self._locked():
                current,_,live=self._live_discovery(token,lease_id)
                live['bytes_used']-=reserved-size;self._save(current)
            return result
