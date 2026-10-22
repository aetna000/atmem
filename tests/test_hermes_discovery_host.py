"""Authenticated discovery leases and actual stdio/HTTP plumbing, no paid calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from tests.test_hermes_v3 import v3,observe
from atmem.adapters.hermes.service import HermesService
from atmem.control.web import ControlDashboardServer


def setup(v3):
    service,admin,grant=v3
    observe(v3)
    checkpoint=service.freeze_memory(admin,grant['binding']['binding_id'])
    lease=service.open_discovery(admin,grant['binding']['binding_id'],query='deployment channel',
        session_id='session',turn_id='turn')
    return service,admin,grant,lease,checkpoint


def test_lease_budget_survives_service_restart_and_is_not_in_public_config(v3):
    service,admin,grant,lease,checkpoint=setup(v3)
    for _ in range(8):
        # A new service object and DB connection for every request.
        service=HermesService(service.manager)
        value=service.dispatch(grant['credential'],'discovery-search',
            {'lease_id':lease['lease_id'],'query':'deployment channel'})
        assert '#engineering' in str(value) and value['sufficiency']=='not_assessed'
    with pytest.raises(RuntimeError,match='budget'):
        service.dispatch(grant['credential'],'discovery-search',
            {'lease_id':lease['lease_id'],'query':'deployment channel'})
    assert 'discovery_leases' not in service.list_bindings(admin)[0]
    service.verify_memory_checkpoint(admin,grant['binding']['binding_id'],checkpoint)


def test_lease_requires_administrator_and_rejects_scope_fields_and_revoke(v3):
    service,admin,grant,lease,checkpoint=setup(v3)
    from dataclasses import replace
    with pytest.raises(Exception):
        service.open_discovery(replace(admin,role='agent'),grant['binding']['binding_id'],
                              query='x',session_id='s',turn_id='t')
    with pytest.raises(ValueError):
        service.dispatch(grant['credential'],'discovery-search',
            {'lease_id':lease['lease_id'],'query':'deployment','subject_id':'other'})
    service.configure(admin,grant['binding']['binding_id'],enabled=False)
    with pytest.raises(PermissionError):
        service.dispatch(grant['credential'],'discovery-search',
            {'lease_id':lease['lease_id'],'query':'deployment'})


def test_actual_standalone_mcp_to_http_returns_canonical_evidence(v3,tmp_path):
    service,admin,grant,lease,checkpoint=setup(v3)
    server=ControlDashboardServer(('127.0.0.1',0),service.manager,html='fixture')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        connection=tmp_path/'discovery.json'
        connection.write_text(json.dumps({'endpoint':f'http://127.0.0.1:{server.server_port}',
                                         'lease_id':lease['lease_id']}))
        (tmp_path/'credential').write_text(grant['credential'])
        script=Path(__file__).resolve().parents[1]/'atmem/adapters/hermes/discovery_stdio.py'
        calls=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},
               {'jsonrpc':'2.0','id':2,'method':'tools/list'},
               {'jsonrpc':'2.0','id':3,'method':'tools/call',
                'params':{'name':'memory_search','arguments':{'query':'deployment channel'}}}]
        completed=subprocess.run([sys.executable,'-I',str(script),str(connection)],
            input='\n'.join(json.dumps(c) for c in calls)+'\n',text=True,capture_output=True,timeout=30)
        assert completed.returncode==0,completed.stderr
        replies=[json.loads(line) for line in completed.stdout.splitlines()]
        assert {t['name'] for t in replies[1]['result']['tools']}=={'memory_search','memory_inspect'}
        assert replies[2]['result']['isError'] is False,replies[2]
        assert '#engineering' in replies[2]['result']['content'][0]['text']
        service.verify_memory_checkpoint(admin,grant['binding']['binding_id'],checkpoint)
    finally:
        server.shutdown();server.server_close();thread.join(5)


def test_failed_discovery_keeps_crash_safe_byte_reservation(v3):
    service,admin,grant,lease,checkpoint=setup(v3)
    class Failing:
        def nominate(self,*args):raise RuntimeError('provider failed')
    service.context_engine_factory=Failing()
    with pytest.raises(RuntimeError):
        service.dispatch(grant['credential'],'discovery-search',
            {'lease_id':lease['lease_id'],'query':'deployment'})
    restarted=HermesService(service.manager)
    with restarted._locked():
        retained=restarted._authenticate(grant['credential'])['discovery_leases'][lease['lease_id']]
    assert retained['bytes_used']==16000 and retained['operations_used']==1


def test_lease_source_revision_changes_are_terminal(v3):
    service,admin,grant,lease,checkpoint=setup(v3)
    binding=service._binding(service._authenticate(grant['credential']))
    with binding.v3().memory() as (memory,scope):
        generation=memory.context_generation(scope)
        memory.store._conn.execute('UPDATE context_view_generations SET revision=revision+1 WHERE generation_id=?',
                                   (generation['generation_id'],))
    with pytest.raises(PermissionError):
        service.dispatch(grant['credential'],'discovery-search',
            {'lease_id':lease['lease_id'],'query':'deployment'})


def test_optional_assessment_requires_explicit_egress_and_validates_quotes(v3):
    service,admin,grant,lease,checkpoint=setup(v3)
    called=[]
    def assessor(query,evidence):
        called.append(query)
        return {'format':'atbot-source-state-assessment-v1',
            'rows':[{'unit_id':evidence[0]['unit_id'],'quote':evidence[0]['text'],
                     'applicability':'current_at_query','stage':'standing_rule'}],
            'unresolved_needs':[],'assurance':'model_interpreted',
            'canonical_storage':False,'authority_decision':None,
            'provider':'fixture','model':'fixture','input_tokens':1,'output_tokens':1}
    service.state_assessor=assessor
    with pytest.raises(PermissionError,match='explicitly authorized'):
        service.dispatch(grant['credential'],'discovery-search',{'lease_id':lease['lease_id'],'query':'deployment'})
    assert called==[]
    allowed=service.open_discovery(admin,grant['binding']['binding_id'],query='deployment',
        session_id='state-test',turn_id='turn',allow_remote_assessment=True)
    value=service.dispatch(grant['credential'],'discovery-search',{'lease_id':allowed['lease_id'],'query':'deployment'})
    assert value['state_assessment']['assurance']=='model_interpreted'
    assert called==['deployment']
    service.verify_memory_checkpoint(admin,grant['binding']['binding_id'],checkpoint)


def test_deterministic_temporal_evidence_needs_no_remote_assessor(v3):
    service,admin,grant=v3
    observe(v3,text='The agreement runs March 2, 2030 through March 2, 2031.')
    checkpoint=service.freeze_memory(admin,grant['binding']['binding_id'])
    service.source_time_frames=True
    lease=service.open_discovery(admin,grant['binding']['binding_id'],query='[2030-02-01] Current agreement?',
                                 session_id='temporal',turn_id='turn')
    result=service.dispatch(grant['credential'],'discovery-search',{'lease_id':lease['lease_id'],'query':'agreement runs'})
    assert result['temporal_evidence']['frames'][0]['relation']=='not_started_at_query'
    assert result['temporal_evidence']['state_identity_or_truth_verified'] is False
    service.verify_memory_checkpoint(admin,grant['binding']['binding_id'],checkpoint)


@pytest.mark.parametrize('mutate_input',[True,False])
def test_followup_provider_cannot_redefine_sources_or_mutate_a_validated_return(v3,mutate_input):
    service,admin,grant,lease,checkpoint=setup(v3)
    retained=[]
    def assessor(query,evidence):
        if mutate_input:evidence[0]['text']='Invented replacement source'
        value={'format':'atbot-source-state-assessment-v1',
            'rows':[{'unit_id':evidence[0]['unit_id'],'quote':evidence[0]['text'],
                     'applicability':'current_at_query','stage':'standing_rule'}],
            'unresolved_needs':[],'assurance':'model_interpreted',
            'canonical_storage':False,'authority_decision':None,
            'provider':'fixture','model':'fixture','input_tokens':1,'output_tokens':1}
        retained.append(value)
        return value
    service.state_assessor=assessor
    allowed=service.open_discovery(admin,grant['binding']['binding_id'],query='deployment',
        session_id='mutation-test',turn_id='turn',allow_remote_assessment=True)
    result=service.dispatch(grant['credential'],'discovery-search',
        {'lease_id':allowed['lease_id'],'query':'deployment'})
    assert 'Invented replacement source' not in str(result['evidence'])
    if mutate_input:assert result['state_assessment']['status']=='unavailable_or_rejected'
    else:
        original=result['state_assessment']['rows'][0]['quote']
        retained[0]['rows'][0]['quote']='Invented after return'
        assert result['state_assessment']['rows'][0]['quote']==original
    service.verify_memory_checkpoint(admin,grant['binding']['binding_id'],checkpoint)


def test_source_bundles_survive_actual_http_boundary_and_keep_canonical_state(v3):
    from urllib.request import Request,urlopen
    service,admin,grant=v3
    observe(v3,text='The agreement is accepted. It takes effect next quarter. The old agreement is current.')
    checkpoint=service.freeze_memory(admin,grant['binding']['binding_id'])
    lease=service.open_discovery(admin,grant['binding']['binding_id'],query='current agreement',
                                 session_id='bundle',turn_id='turn')
    server=ControlDashboardServer(('127.0.0.1',0),service.manager,html='fixture',source_bundles=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        request=Request(f'http://127.0.0.1:{server.server_port}/v1/hermes/discovery-search',
            data=json.dumps({'lease_id':lease['lease_id'],'query':'current agreement'}).encode(),
            headers={'Authorization':'Bearer '+grant['credential'],'Content-Type':'application/json'},method='POST')
        with urlopen(request,timeout=5) as response:value=json.load(response)
        assert value['presentation']=='atomic-source-bundles-v1'
        assert [row['text'] for row in value['evidence']]==[
            'The agreement is accepted.','It takes effect next quarter.','The old agreement is current.']
        service.verify_memory_checkpoint(admin,grant['binding']['binding_id'],checkpoint)
    finally:
        server.shutdown();server.server_close();thread.join(5)
