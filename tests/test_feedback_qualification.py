from copy import deepcopy
import json
from pathlib import Path

import pytest

from atmem.feedback.baseline import BaselineError
from atmem.feedback.qualification import QualificationService
from atmem.feedback.store import FeedbackError
from test_feedback_actions import actions_fixture


def test_frozen_synthetic_qualification_is_inconclusive_and_bounded(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    manifest = json.loads((Path(__file__).parent/"fixtures/feedback/baseline-manifest.json").read_text())
    service = QualificationService(f.feedback)
    frozen = service.freeze(f.owner["token"], f.scope, manifest, artifact_sha256="a"*64)
    assert not frozen["execution_authorized"] and not frozen["paid_calls_authorized"]
    receipt = service.evaluate(f.owner["token"], f.scope, manifest_sha256=frozen["manifest_sha256"], idempotency_key="one")
    assert receipt["decision"] == "inconclusive"
    assert receipt["metrics"]["unknown_items"] == 18
    assert receipt["metrics"]["model_calls"] == 0
    assert service.evaluate(f.owner["token"], f.scope, manifest_sha256=frozen["manifest_sha256"], idempotency_key="one") == receipt
    for key in ("two", "three"):
        service.evaluate(f.owner["token"], f.scope, manifest_sha256=frozen["manifest_sha256"], idempotency_key=key)
    with pytest.raises(FeedbackError, match="attempt_budget_exhausted"):
        service.evaluate(f.owner["token"], f.scope, manifest_sha256=frozen["manifest_sha256"], idempotency_key="four")
    with pytest.raises(FeedbackError, match="denied"):
        service.evaluate(f.user["token"], f.scope, manifest_sha256=frozen["manifest_sha256"], idempotency_key="forged")


def test_freeze_does_not_accept_a_paid_budget_or_contaminated_split(tmp_path):
    f, _ = actions_fixture(tmp_path)
    manifest = json.loads((Path(__file__).parent/"fixtures/feedback/baseline-manifest.json").read_text())
    service = QualificationService(f.feedback)
    for mutate in (lambda m: m["budget"].update(usd=1),
                   lambda m: m["tasks"][1].update(episode=m["tasks"][0]["episode"]),
                   lambda m: m["tasks"][0].update(verified_success=True)):
        changed = deepcopy(manifest)
        mutate(changed)
        with pytest.raises(BaselineError):
            service.freeze(f.owner["token"], f.scope, changed, artifact_sha256="a"*64)
