"""Packaged boundary pins are aligned; no host import in the base installation."""
import json
from pathlib import Path

import pytest

from atmem.adapters.hermes.feedback_guard import BOUNDARY_FILES, HOST_COMMIT, verify_host_boundary
from atmem.feedback.store import FeedbackError


def test_hermes_boundary_pins_match_the_reviewed_candidate_manifest():
    record = json.loads((Path(__file__).parents[1]/"integrations/hermes/patches/final-tool-policy-boundary.json").read_text())
    assert BOUNDARY_FILES == record["files"] and HOST_COMMIT == record["candidate_commit"]
    assert not record["installed_on_owner_runtime"]


def test_missing_or_unreviewed_host_cannot_install_enforcement(tmp_path):
    with pytest.raises(FeedbackError, match="unsupported_host_boundary"):
        verify_host_boundary(tmp_path)
