from datetime import date
import pytest

from atmem.context_engine.temporal_frames import question_date,temporal_frames,parse_date_literal


def test_accepted_future_period_is_not_the_period_containing_question_date():
    evidence=[{'unit_id':'old','text':'The existing agreement runs March 2, 2030 through March 2, 2031.'},
              {'unit_id':'new','text':'We accepted the renewal for March 2, 2031–March 2, 2032.'}]
    original=[dict(row) for row in evidence]
    frames=temporal_frames(evidence,as_of=date(2031,2,20))
    assert [(f['unit_id'],f['relation'],f['period_end']) for f in frames]==[
        ('old','inside_quoted_period','2031-03-02'),('new','not_started_at_query','2032-03-02')]
    assert evidence==original
    assert all(f['quoted_interval'] in next(r['text'] for r in evidence if r['unit_id']==f['unit_id']) for f in frames)


def test_iso_and_short_month_dates_and_ambiguous_boundary():
    evidence=[{'unit_id':'one','text':'Coverage: 2030-02-03 to 2031-02-03.'},
              {'unit_id':'two','text':'Term Feb 3, 2030 until Feb 3, 2031.'}]
    frames=temporal_frames(evidence,as_of=date(2031,2,3))
    assert len(frames)==2 and all(f['relation']=='on_period_boundary' for f in frames)
    assert question_date('[2031-02-03T09:00:00Z] current term')==date(2031,2,3)
    assert question_date('current term') is None


def test_no_invented_bounds_from_relative_unsupported_or_invalid_dates():
    evidence=[{'unit_id':'one','text':'It starts next year and runs through summer.'},
              {'unit_id':'two','text':'February 30, 2030 to March 5, 2030.'},
              {'unit_id':'three','text':'2031-01-01 to 2030-01-01.'}]
    assert temporal_frames(evidence,as_of=date(2030,1,1))==[]
    with pytest.raises(ValueError):parse_date_literal('next summer')
