"""Independent host validation/rendering of quoted evidence-selection proposals."""
from __future__ import annotations


def validate_source_dossier(value, evidence):
    fields={'format','needs','unresolved_needs','assurance','canonical_storage',
            'authority_decision','provider','model','input_tokens','output_tokens'}
    if (not isinstance(value,dict) or set(value)!=fields
            or value['format']!='atbot-source-dossier-v1'
            or value['assurance']!='model_selected_source_quotes'
            or value['canonical_storage'] is not False or value['authority_decision'] is not None):
        raise ValueError('invalid source dossier authority or response contract')
    sources={e['unit_id']:e['text'] for e in evidence}
    if not isinstance(value['needs'],list) or len(value['needs'])>8:
        raise ValueError('invalid information-need bound')
    for need in value['needs']:
        if (not isinstance(need,dict) or set(need)!={'need','quotes'}
                or not isinstance(need['need'],str) or not 1<=len(need['need'])<=200
                or not isinstance(need['quotes'],list) or not 1<=len(need['quotes'])<=2):
            raise ValueError('invalid information-need proposal')
        for quote in need['quotes']:
            if (not isinstance(quote,dict) or set(quote)!={'unit_id','quote'}
                    or not isinstance(quote['unit_id'],str) or quote['unit_id'] not in sources
                    or not isinstance(quote['quote'],str) or not 1<=len(quote['quote'])<=600
                    or quote['quote'] not in sources[quote['unit_id']]):
                raise ValueError('dossier must cite exact authorized source quotations')
    needs=value['unresolved_needs']
    if (not isinstance(needs,list) or len(needs)>4
            or any(not isinstance(n,str) or not 1<=len(n)<=256 for n in needs)):
        raise ValueError('invalid unresolved needs')
    for key in ('provider','model'):
        if not isinstance(value[key],str) or not 1<=len(value[key])<=256:
            raise ValueError('provider identity required')
    for key in ('input_tokens','output_tokens'):
        if type(value[key]) is not int or value[key]<0:
            raise ValueError('actual nonnegative usage required')
    return value


def render_source_dossier(value, evidence):
    sources={e['unit_id']:e for e in evidence}
    selected=[]; needs=[]
    for need in value['needs']:
        quotes=[]
        for citation in need['quotes']:
            identity=citation['unit_id']
            if identity not in selected:selected.append(identity)
            quotes.append({'unit_id':identity,'text':citation['quote'],
                           'source_range':sources[identity].get('source_range',{})})
        needs.append({'information_need_proposal':need['need'],'original_quotations':quotes})
    return {'format':'atmem-source-dossier-v1','status':'investigative_evidence',
        'sufficiency':'not_assessed','assurance':'model_selected_literal_source_quotes',
        'needs':needs,'unresolved_needs':value['unresolved_needs'],
        'original_source_unit_count':len(evidence),'delivered_unit_ids':selected,
        'original_records_retained':True},tuple(selected)
