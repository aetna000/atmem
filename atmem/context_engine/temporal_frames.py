"""Deterministic positions in explicitly quoted date intervals.

This computes date order only: it does not prove ownership, acceptance, truth,
supersession, or inclusive/exclusive period boundaries. Unsupported/relative
date forms remain unparsed. Source content is never mutated.
"""
from __future__ import annotations

from datetime import date
import re

MONTHS={name:index for index,names in enumerate((
    ('january','jan'),('february','feb'),('march','mar'),('april','apr'),('may',),
    ('june','jun'),('july','jul'),('august','aug'),('september','sep','sept'),
    ('october','oct'),('november','nov'),('december','dec')),1) for name in names}
_MONTH='(?:'+'|'.join(sorted(MONTHS,key=len,reverse=True))+')'
_DATE=rf'(?:\d{{4}}-\d{{2}}-\d{{2}}|{_MONTH}\.?\s+\d{{1,2}},?\s+\d{{4}})'
_INTERVAL=re.compile(rf'(?<!\w)(?P<start>{_DATE})\s*(?:through|until|to|[–—-])\s*(?P<end>{_DATE})(?!\w)',re.I)


def parse_date_literal(value):
    try:return date.fromisoformat(value)
    except ValueError:pass
    match=re.fullmatch(rf'({_MONTH})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})',value,re.I)
    if not match:raise ValueError('unsupported explicit date literal')
    return date(int(match[3]),MONTHS[match[1].lower()],int(match[2]))


def question_date(query):
    match=re.match(r'^\s*\[(\d{4}-\d{2}-\d{2})(?:T[^\]]*)?\]',query)
    if not match:return None
    try:return date.fromisoformat(match[1])
    except ValueError:return None


def temporal_frames(evidence,*,as_of):
    if not isinstance(as_of,date):raise TypeError('host-selected date required')
    frames=[]
    for row in evidence:
        for match in _INTERVAL.finditer(row['text']):
            try:start,end=parse_date_literal(match['start']),parse_date_literal(match['end'])
            except ValueError:continue
            if end<start:continue
            relation=('not_started_at_query' if as_of<start else 'ended_before_query' if as_of>end
                      else 'on_period_boundary' if as_of in (start,end) else 'inside_quoted_period')
            frames.append({'unit_id':row['unit_id'],'quoted_interval':match.group(0),
                'period_start':start.isoformat(),'period_end':end.isoformat(),
                'question_as_of':as_of.isoformat(),'relation':relation})
            if len(frames)==8:return frames
    return frames
