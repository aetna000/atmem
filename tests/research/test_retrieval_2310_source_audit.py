import pytest

from research.retrieval_2310.source_audit import covered_bytes


def test_overlapping_duplicate_source_spans_are_not_double_counted():
    assert covered_bytes([(4,8),(0,5),(4,8),(12,14)])==10
    assert covered_bytes([])==0
    assert covered_bytes([(0,4),(4,8)])==8


def test_invalid_source_offsets_cannot_be_called_complete():
    with pytest.raises(ValueError):
        covered_bytes([(-1,5)])
