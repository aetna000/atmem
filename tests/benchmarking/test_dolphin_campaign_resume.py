"""Resume scheduling changes backups only, never executions or outcomes."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.dolphinbench.campaign_v3 import checkpoint_due


@pytest.mark.parametrize('case,reused,expected', [
    ('010', True, False), ('010', False, True), ('011', True, False),
    ('011', False, False), ('090', False, True),
])
def test_only_newly_graded_boundaries_create_backups(case, reused, expected):
    assert checkpoint_due(case, reused_grade=reused) is expected
