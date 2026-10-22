"""Initial interpretation plumbing/authority fixtures, not quality evidence."""
import json

import pytest

from atmem.context_engine.initial_state import prepare_initial_state


def interpreted(rows):
    return {'format':'atbot-source-state-assessment-v1',
        'rows':[{'unit_id':rows[0]['unit_id'],'quote':rows[0]['text'],
                 'applicability':'current_at_query','stage':'standing_rule'}],
        'unresolved_needs':[], 'assurance':'model_interpreted',
        'canonical_storage':False,'authority_decision':None,
        'provider':'fixture','model':'fixture','input_tokens':1,'output_tokens':1}


def prepare(assessor, *, authorize=lambda:True, audit=lambda k,v:'audit-'+k,
            evidence=None, context='Original authorized source.',presentation='annotated-source'):
    return prepare_initial_state('What applies?',context,
        evidence if evidence is not None else [{'unit_id':'source','text':context}],
        assessor=assessor,authorize=authorize,audit=audit,source_preparation_id='prepare:original',
        presentation=presentation)


def dossier(rows):
    return {'format':'atbot-source-dossier-v1',
        'needs':[{'need':'Current configuration and its qualifications',
                  'quotes':[{'unit_id':rows[-1]['unit_id'],'quote':rows[-1]['text']}]}],
        'unresolved_needs':[],'assurance':'model_selected_source_quotes',
        'canonical_storage':False,'authority_decision':None,
        'provider':'fixture','model':'fixture','input_tokens':1,'output_tokens':1}


def test_dossier_projects_exact_sources_and_records_actual_delivery_without_deleting_originals():
    rows=[{'unit_id':'old','text':'Unrelated old source.'},
          {'unit_id':'current','text':'Current setting, with its exact qualification.',
           'source_range':{'source_id':'original-source','part_id':'part'}}]
    context='\n\n'.join(r['text'] for r in rows);events=[]
    text,_,status=prepare(lambda q,r:dossier(r),context=context,evidence=rows,
        presentation='dossier',audit=lambda k,v:events.append((k,v)) or 'receipt')
    assert status=='model_interpreted'
    assert rows[-1]['text'] in text and rows[0]['text'] not in text
    packet=json.loads(text.split('\n',1)[1])
    assert packet['sufficiency']=='not_assessed'
    assert packet['delivered_unit_ids']==['current']
    assert packet['needs'][0]['original_quotations'][0]['source_range']==rows[-1]['source_range']
    assert events[-1][1]['original_source_context']==context
    assert events[-1][1]['delivered_unit_ids']==['current']
    assert len(text.encode())<=16000


@pytest.mark.parametrize('presentation',['annotated-source','dossier'])
def test_provider_cannot_mutate_its_input_to_validate_a_fabricated_quotation(presentation):
    rows=[{'unit_id':'source','text':'Original authorized source.'}]
    def mutator(query,evidence):
        evidence[0]['text']='Injected replacement fact.'
        return dossier(evidence) if presentation=='dossier' else interpreted(evidence)
    text,_,status=prepare(mutator,evidence=rows,presentation=presentation)
    assert status=='not_assessed_provider_or_contract_failure'
    assert 'Injected replacement fact.' not in text
    assert rows[0]['text']=='Original authorized source.'


def test_empty_dossier_falls_back_to_unchanged_authorized_source_packet():
    def empty(q,rows):
        value=dossier(rows);value['needs']=[];return value
    text,_,status=prepare(empty,presentation='dossier')
    assert status=='not_assessed_empty_selection'
    assert text.endswith('Original authorized source.')


def test_initial_interpretation_precedes_reader_and_retains_entire_original():
    calls=[]; events=[]
    context='原文。 Original authorized source.'
    def assessor(query, rows):
        calls.append((query,rows)); return interpreted(rows)
    text, receipt, status=prepare(assessor,context=context,
        audit=lambda k,v:events.append((k,v)) or 'audit-'+k)
    assert len(calls)==1 and status=='model_interpreted'
    assert text.endswith(context) and text.index('classifications') < text.index(context)
    assert receipt=='audit-prepared'
    assert [k for k,v in events]==['egress_authorized','prepared']
    assert events[-1][1]['original_source_context']==context
    assert events[-1][1]['source_preparation_id']=='prepare:original'
    assert events[-1][1]['composed_context']==text


@pytest.mark.parametrize('failure',['provider','quote','output_bound'])
def test_failed_interpretation_is_explicit_and_does_not_rewrite_sources(failure):
    def assessor(query,rows):
        if failure=='provider':raise RuntimeError('provider unavailable')
        value=interpreted(rows)
        if failure=='quote':value['rows'][0]['quote']='invented fact'
        if failure=='output_bound':
            value['rows']*=8
            for row in value['rows']:row['quote']=rows[0]['text'][:600]
            value['unresolved_needs']=['x'*256]*4
        return value
    context='a'*600 if failure=='output_bound' else 'Original authorized source.'
    text,_,status=prepare(assessor,context=context)
    assert status.startswith('not_assessed') and text.endswith(context)
    assert 'invented fact' not in text


def test_denied_initial_authority_cannot_reach_provider_or_fall_back_after_revocation():
    calls=[]
    def assessor(q,rows):calls.append(1);return interpreted(rows)
    with pytest.raises(PermissionError):prepare(assessor,authorize=lambda:False)
    assert calls==[]
    live=[True]
    def revoking(q,rows):live[0]=False;return interpreted(rows)
    with pytest.raises(PermissionError):prepare(revoking,authorize=lambda:live[0])


def test_input_bounds_omit_assessment_not_source_rows():
    rows=[{'unit_id':str(i),'text':'x'} for i in range(257)]
    def forbidden(*args):pytest.fail('out-of-bound packet must not reach provider')
    text,_,status=prepare(forbidden,evidence=rows)
    assert status=='not_assessed_input_bound' and text.endswith('Original authorized source.')


def test_failed_audit_and_late_revoke_are_terminal():
    with pytest.raises(PermissionError):prepare(lambda q,r:interpreted(r),audit=lambda k,v:None)
    live=[True]
    def audit(kind,value):
        if kind=='prepared':live[0]=False
        return 'audit'
    with pytest.raises(PermissionError):
        prepare(lambda q,r:interpreted(r),authorize=lambda:live[0],audit=audit)
