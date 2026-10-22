"""Host-owned validation of optional companion state classifications."""
from __future__ import annotations

LABELS={'current_at_query','future_effective','historical','conditional','unresolved'}
STAGES={'observed','requested','proposed','accepted','completed','standing_rule','unknown'}


def validate_state_assessment(value,evidence):
    fields={'format','rows','unresolved_needs','assurance','canonical_storage','authority_decision',
            'provider','model','input_tokens','output_tokens'}
    if (not isinstance(value,dict) or set(value)!=fields
            or value['format']!='atbot-source-state-assessment-v1'
            or value['assurance']!='model_interpreted' or value['canonical_storage'] is not False
            or value['authority_decision'] is not None):
        raise ValueError('companion attempted an invalid authority or response contract')
    sources={r['unit_id']:r['text'] for r in evidence}
    if not isinstance(value['rows'],list) or len(value['rows'])>8:raise ValueError('invalid row bound')
    for row in value['rows']:
        if (not isinstance(row,dict) or set(row)!={'unit_id','quote','applicability','stage'}
                or not isinstance(row['unit_id'],str) or row['unit_id'] not in sources or not isinstance(row['quote'],str)
                or not 1<=len(row['quote'])<=600 or row['quote'] not in sources[row['unit_id']]
                or row['applicability'] not in LABELS or row['stage'] not in STAGES):
            raise ValueError('companion cited unsupported source evidence')
    if (not isinstance(value['unresolved_needs'],list) or len(value['unresolved_needs'])>4
            or any(not isinstance(n,str) or not n or len(n)>256 for n in value['unresolved_needs'])):
        raise ValueError('invalid unresolved information needs')
    for key in ('provider','model'):
        if not isinstance(value[key],str) or not 1<=len(value[key])<=256:raise ValueError('provider identity required')
    for key in ('input_tokens','output_tokens'):
        if value[key] is not None and (type(value[key]) is not int or value[key]<0):raise ValueError('invalid usage')
    return value
