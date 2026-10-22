"""Classifier contract fixtures only; no training or benchmark-quality claims."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from atmem.context_engine.state_assessment import validate_state_assessment

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/atbot/src'))
from atbot.state_assessment import assess_state


def assessment(evidence):
    return {'rows':[{'unit_id':evidence[0]['unit_id'],'quote':evidence[0]['text'],
                    'applicability':'future_effective','stage':'accepted'}],
            'unresolved_needs':['Which agreement is effective before the replacement begins?']}


def test_source_quoted_state_contract_preserves_language_and_non_authority():
    evidence=[{'unit_id':'original','text':'新协议从六月一日生效。'}]
    class Provider:
        def complete(self,**kwargs):
            assert kwargs['schema']['additionalProperties'] is False
            assert '新协议' in kwargs['prompt']
            return SimpleNamespace(structured=assessment(evidence),provider='fixture',model='fixture',
                                   input_tokens=10,output_tokens=5)
    value=assess_state(Provider(),'As of May 10, which agreement is effective?',evidence)
    assert value['canonical_storage'] is False and value['authority_decision'] is None
    assert validate_state_assessment(value,evidence)==value
    assert value['rows'][0]['quote']==evidence[0]['text']


def test_initial_application_bound_does_not_expand_default_followup_bound():
    evidence=[{'unit_id':str(i),'text':'x'*600,
               'source_range':{'source_id':'source-'+('a'*80),'part_id':'part'}}
              for i in range(80)]
    class Provider:
        calls=0
        def complete(self,**kwargs):
            self.calls+=1
            return SimpleNamespace(structured=assessment(evidence),provider='fixture',model='fixture',
                                   input_tokens=1,output_tokens=1)
    provider=Provider()
    with pytest.raises(ValueError):assess_state(provider,'What applies?',evidence)
    assert provider.calls==0
    result=assess_state(provider,'What applies?',evidence,max_evidence=256,max_input_bytes=80000)
    assert provider.calls==1 and result['rows'][0]['quote']==evidence[0]['text']


@pytest.mark.parametrize('kind',['foreign_id','invented_quote','invalid_label','authority_claim'])
def test_host_rejects_unsupported_or_authority_shaped_assessment(kind):
    evidence=[{'unit_id':'original','text':'The new agreement begins June 1.'}]
    value={**assessment(evidence),'format':'atbot-source-state-assessment-v1',
           'assurance':'model_interpreted','canonical_storage':False,'authority_decision':None,
           'provider':'fixture','model':'fixture','input_tokens':10,'output_tokens':5}
    if kind=='foreign_id':value['rows'][0]['unit_id']='other-scope'
    if kind=='invented_quote':value['rows'][0]['quote']='Already active in May.'
    if kind=='invalid_label':value['rows'][0]['applicability']='verified_true'
    if kind=='authority_claim':value['authority_decision']='approved'
    with pytest.raises(ValueError):validate_state_assessment(value,evidence)


@pytest.mark.parametrize('evidence', [None,{},[{}],[{'unit_id':[], 'text':'one'}],
    [{'unit_id':'same','text':'one'},{'unit_id':'same','text':'two'}],
    [{'unit_id':'one','text':'one','authority':'approved'}]])
def test_bad_input_rejected_before_provider(evidence):
    class Provider:
        def complete(self, **kwargs):
            pytest.fail('malformed input must not reach the model')
    with pytest.raises(ValueError):assess_state(Provider(),'current status?',evidence)


def test_companion_http_client_contract_and_authentication():
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.request import Request,urlopen
    from urllib.error import HTTPError
    import json
    from atbot.service import make_handler
    from atmem.control.atbot_companion import AtBotCompanionClient

    evidence=[{'unit_id':'original','text':'The agreement starts June 1.',
               'source_range':{'source_id':'source-original','start':0,'end':29}}]
    class Companion:
        calls=[]
        def capabilities(self):
            return {'role':'atmem-intelligence-companion','protocol_version':'1',
                    'canonical_storage':False,'features':{'source_state_assessment':True}}
        def assess_memory_state(self,query,rows,*,remote=False):
            self.calls.append((query,rows,remote))
            return {**assessment(rows),'format':'atbot-source-state-assessment-v1',
                    'assurance':'model_interpreted','canonical_storage':False,'authority_decision':None,
                    'provider':'fixture','model':'fixture','input_tokens':10,'output_tokens':5}
    companion=Companion()
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(companion,'fixture-secret'))
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    endpoint=f'http://127.0.0.1:{server.server_port}'
    try:
        client=AtBotCompanionClient(endpoint)
        value=client.assess_memory_state('Which agreement?',evidence)
        assert value['rows'][0]['quote']==evidence[0]['text']
        assert companion.calls==[('Which agreement?',evidence,False)]
        for token,body,status in [('',{'query':'q','evidence':evidence},403),
            ('fixture-secret',{'query':'q','evidence':evidence,'remote':'true'},400),
            ('fixture-secret',{'query':'q','evidence':evidence,'authority':True},400),
            ('fixture-secret',{'query':'q','evidence':[{}]},400)]:
            request=Request(endpoint+'/api/companion/source-state/assess',
                data=json.dumps(body).encode(),headers={'X-AtBot-CSRF':token},method='POST')
            with pytest.raises(HTTPError) as caught:urlopen(request,timeout=2)
            assert caught.value.code==status
        assert len(companion.calls)==1
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
